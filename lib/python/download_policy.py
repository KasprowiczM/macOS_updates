"""Bounded HTTPS transport with per-hop validation and DNS address pinning.

Metadata may follow public HTTPS redirects. Artifacts require an explicit,
reviewed exact-host list; a redirect never expands that list. No proxy or TLS
verification bypass is supported. Exceptions never contain request URLs.
"""

import http.client
import ipaddress
import os
import re
import socket
import ssl
import tempfile
import time
import threading
import queue
from urllib.parse import urlsplit, urljoin


def _public(address):
    value = ipaddress.ip_address(address)
    if not value.is_global or value.is_multicast or value.is_reserved:
        return False
    if value.version == 6:
        # Reject transition mechanisms that can encode a nonpublic IPv4
        # endpoint even when the enclosing IPv6 address appears global.
        if (
            value.sixtofour
            or value.teredo
            or value in ipaddress.ip_network("64:ff9b::/96")
            or value in ipaddress.ip_network("64:ff9b:1::/48")
        ):
            return False
        if value.ipv4_mapped:
            return _public(str(value.ipv4_mapped))
    return True


def _host(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9.-]+", value):
        raise ValueError("invalid_host")
    value = value.lower()
    if value.endswith(".") or ".." in value or value == "localhost" or "." not in value:
        raise ValueError("invalid_host")
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        if any(
            not part or part.startswith("-") or part.endswith("-")
            for part in value.split(".")
        ):
            raise ValueError("invalid_host")
    else:
        if not _public(str(address)):
            raise ValueError("nonpublic_address")
    return value


def validate_download_url(url, allowed_hosts):
    if (
        not isinstance(url, str)
        or len(url) > 16384
        or any(ord(c) <= 32 or ord(c) >= 127 for c in url)
        or "\\" in url
    ):
        raise ValueError("invalid_url")
    try:
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.username is not None
            or parts.password is not None
            or parts.fragment
            or parts.port not in (None, 443)
        ):
            raise ValueError("invalid_url")
        host = _host(parts.hostname)
        if parts.netloc.lower() not in (host, host + ":443"):
            raise ValueError("invalid_url")
        if allowed_hosts is not None and host not in {_host(h) for h in allowed_hosts}:
            raise ValueError("host_not_reviewed")
    except (TypeError, AttributeError, ValueError):
        raise ValueError("download_url_rejected") from None
    return url


def validate_redirect_chain(urls, allowed_hosts):
    try:
        if not urls or len(urls) > 6:
            return False
        for url in urls:
            validate_download_url(url, allowed_hosts)
        return True
    except ValueError:
        return False


def resolve_public_addresses(host, timeout=10):
    # libc DNS can outlive socket timeouts. A daemon resolver and bounded wait
    # keep total download time bounded without trusting a second resolution.
    results = queue.Queue(maxsize=1)
    lookup = socket.getaddrinfo

    def resolve():
        try:
            values = lookup(host, 443, type=socket.SOCK_STREAM)
            results.put((True, values))
        except Exception:
            results.put((False, None))

    worker = threading.Thread(target=resolve, daemon=True)
    worker.start()
    try:
        ok, values = results.get(timeout=timeout)
    except queue.Empty:
        raise ValueError("dns_timeout") from None
    if not ok:
        raise ValueError("dns_unavailable")
    addresses = list(dict.fromkeys(row[4][0] for row in values))
    if not addresses or any(not _public(address) for address in addresses):
        raise ValueError("dns_nonpublic_address")
    return addresses


class _PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, host, address, timeout):
        super().__init__(
            host, 443, timeout=timeout, context=ssl.create_default_context()
        )
        self.address = address

    def connect(self):
        # Connect to the checked numeric address, retain the original TLS SNI
        # and hostname verification. Never re-resolve inside HTTPSConnection.
        raw = socket.create_connection((self.address, 443), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except BaseException:
            raw.close()
            raise


def _request(url, addresses, timeout):
    parts = urlsplit(url)
    conn = _PinnedHTTPS(parts.hostname, addresses[0], min(30, timeout))
    expired = threading.Event()
    transport = [None]

    def abort():
        expired.set()
        sock = transport[0] or conn.sock
        if sock is not None:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        conn.close()

    timer = threading.Timer(timeout, abort)
    timer.daemon = True
    timer.start()
    try:
        conn.request(
            "GET",
            (parts.path or "/") + ("?" + parts.query if parts.query else ""),
            headers={"User-Agent": "mac-update/1", "Accept-Encoding": "identity"},
        )
        transport[0] = conn.sock
        response = conn.getresponse()
        if expired.is_set():
            response.close()
            raise ValueError("download_timeout")
        response._download_connection = conn
        response._download_deadline_timer = timer
        return response
    except BaseException:
        timer.cancel()
        conn.close()
        raise


def download(url, dest, allowed_hosts, timeout=60, max_bytes=10485760, request=None):
    if (
        not isinstance(timeout, (int, float))
        or not 0 < timeout <= 1800
        or type(max_bytes) is not int
        or not 0 < max_bytes <= 4294967296
    ):
        raise ValueError("invalid_download_bound")
    deadline = time.monotonic() + timeout
    request = request or _request
    fd, temporary = tempfile.mkstemp(
        prefix=".macupd-download-", dir=os.path.dirname(os.path.abspath(dest))
    )
    try:
        with os.fdopen(fd, "wb") as output:
            for hop in range(6):
                validate_download_url(url, allowed_hosts)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("download_timeout")
                addresses = resolve_public_addresses(
                    urlsplit(url).hostname, timeout=min(10, remaining)
                )
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise ValueError("download_timeout")
                response = request(url, addresses, remaining)
                try:
                    if response.status in (301, 302, 303, 307, 308):
                        location = response.getheader("Location")
                        if not location or hop == 5:
                            raise ValueError("redirect_limit")
                        url = urljoin(url, location)
                        # Validate before another DNS lookup or network request.
                        validate_download_url(url, allowed_hosts)
                        continue
                    if response.status != 200:
                        raise ValueError("download_http_failure")
                    length = response.getheader("Content-Length")
                    if length is not None and (
                        not length.isdigit() or int(length) > max_bytes
                    ):
                        raise ValueError("download_size_limit")
                    size = 0
                    while True:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise ValueError("download_timeout")
                        connection = getattr(response, "_download_connection", None)
                        if connection and connection.sock:
                            connection.sock.settimeout(min(30, remaining))
                        chunk = response.read1(min(65536, max_bytes - size + 1))
                        if time.monotonic() >= deadline:
                            raise ValueError("download_timeout")
                        if not chunk:
                            break
                        size += len(chunk)
                        if size > max_bytes:
                            raise ValueError("download_size_limit")
                        output.write(chunk)
                    if size == 0:
                        raise ValueError("download_empty")
                    if length is not None and size != int(length):
                        raise ValueError("download_incomplete")
                    output.flush()
                    os.fsync(output.fileno())
                    break
                finally:
                    timer = getattr(response, "_download_deadline_timer", None)
                    if timer:
                        timer.cancel()
                    response.close()
                    connection = getattr(response, "_download_connection", None)
                    if connection:
                        connection.close()
        os.replace(temporary, dest)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def reviewed_artifact_hosts(action, catalog, artifact):
    """Bind transport permission to the concrete action's reviewed identity."""
    if (
        action.get("action_scope") != "direct_update"
        or action.get("target", {}).get("kind") != "app"
    ):
        raise ValueError("reviewed_direct_required")
    target = action.get("expected_target", {})
    resolution = action.get("expected_resolution", {})
    if (
        resolution.get("source") != "vendor"
        or resolution.get("capability") != "reviewed_direct"
    ):
        raise ValueError("reviewed_direct_required")
    adapter = action.get("adapter_id")
    # Generic appcast parsing does not authenticate Sparkle EdDSA signatures.
    if adapter not in ("github_dmg", "mozilla_dmg"):
        raise ValueError("artifact_adapter_unreviewed")
    matching = [
        r
        for r in catalog.get("recipes", [])
        if r.get("adapter_id") == adapter
        and target.get("bundle_id") in r.get("bundle_ids", [])
        and target.get("team_id") in r.get("team_ids", [])
        and target.get("channel") in r.get("channels", [])
        and artifact in r.get("allowed_artifacts", [])
        and "arm64" in r.get("architectures", [])
        and r.get("minimum_os")
        and r.get("download_hosts")
    ]
    if len(matching) != 1:
        raise ValueError("reviewed_recipe_missing_or_ambiguous")
    return [_host(h) for h in matching[0]["download_hosts"]]
