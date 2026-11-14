"""Acquire one immutable zip bundle without mounting or launching its payload.

Acquisition grants no installation authority. The caller must validate recipe
acceptance and consent separately before mutation; every returned bundle still
passes the transaction's fresh signature and identity checks.
"""

import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
import time
import zipfile
import unicodedata
from download_policy import download, validate_download_url
from update_transaction import observe_bundle
from vendor_feeds import version_compare


def _bound(value, maximum):
    if type(value) is not int or not 0 < value <= maximum:
        raise ValueError("invalid_artifact_bound")
    return value


def _name(value):
    if (
        not isinstance(value, str)
        or not value.endswith(".app")
        or value in (".app", "..app")
    ):
        raise ValueError("invalid_bundle_name")
    if any(c in value for c in "/\\\x00") or any(ord(c) < 32 for c in value):
        raise ValueError("invalid_bundle_name")
    return value


def _extract(archive, destination, bundle_name, limits, deadline):
    total_limit = _bound(limits["maximum_expanded_bytes"], 8 * 1024**3)
    entry_limit = _bound(limits["maximum_entries"], 100000)
    links = []
    paths = set()
    total = 0
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if not entries or len(entries) > entry_limit:
            raise ValueError("archive_entry_limit")
        # Preflight the entire central directory before creating payload files.
        for entry in entries:
            raw = entry.filename.rstrip("/")
            parts = PurePosixPath(raw).parts
            if (
                not raw
                or "\\" in raw
                or raw.startswith("/")
                or any(p in ("", ".", "..") for p in raw.split("/"))
                or any(ord(c) < 32 for c in raw)
                or not parts
                or parts[0] != bundle_name
            ):
                raise ValueError("archive_path_rejected")
            key = unicodedata.normalize("NFD", raw).casefold()
            if key in paths:
                raise ValueError("archive_duplicate_path")
            paths.add(key)
            mode = entry.external_attr >> 16
            kind = stat.S_IFMT(mode)
            if entry.flag_bits & 1 or kind not in (
                0,
                stat.S_IFREG,
                stat.S_IFDIR,
                stat.S_IFLNK,
            ):
                raise ValueError("archive_special_file")
            if entry.file_size < 0:
                raise ValueError("archive_expansion_limit")
            total += entry.file_size
            if total > total_limit:
                raise ValueError("archive_expansion_limit")
            if stat.S_ISLNK(mode):
                if entry.file_size > 4096:
                    raise ValueError("archive_symlink_rejected")
                links.append(raw)
        for raw in paths:
            if any(
                raw.startswith(unicodedata.normalize("NFD", link).casefold() + "/")
                for link in links
            ):
                raise ValueError("archive_symlink_parent")
        written = 0
        for entry in entries:
            if time.monotonic() >= deadline:
                raise ValueError("acquisition_timeout")
            raw = entry.filename.rstrip("/")
            path = os.path.join(destination, *PurePosixPath(raw).parts)
            mode = entry.external_attr >> 16
            if raw in links:
                continue
            if entry.is_dir() or stat.S_ISDIR(mode):
                os.makedirs(path, mode=0o755, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(path), mode=0o755, exist_ok=True)
            with z.open(entry) as src, open(path, "xb") as dst:
                while True:
                    if time.monotonic() >= deadline:
                        raise ValueError("acquisition_timeout")
                    chunk = src.read(65536)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > total_limit:
                        raise ValueError("archive_expansion_limit")
                    dst.write(chunk)
            os.chmod(path, 0o755 if mode & 0o111 else 0o644)
        # Materialize links only after all regular files. No write follows a link.
        for raw in links:
            entry = z.getinfo(raw)
            target = z.read(entry).decode("utf-8")
            if (
                not target
                or os.path.isabs(target)
                or "\\" in target
                or any(ord(c) < 32 for c in target)
            ):
                raise ValueError("archive_symlink_rejected")
            path = os.path.join(destination, *PurePosixPath(raw).parts)
            os.makedirs(os.path.dirname(path), mode=0o755, exist_ok=True)
            os.symlink(target, path)
        bundle = os.path.join(destination, bundle_name)
        for raw in links:
            link = os.path.join(destination, *PurePosixPath(raw).parts)
            try:
                resolved = str(Path(link).resolve(strict=True))
            except (OSError, RuntimeError):
                raise ValueError("archive_symlink_rejected") from None
            if os.path.commonpath([bundle, resolved]) != bundle:
                raise ValueError("archive_symlink_escape")
        if not os.path.isfile(os.path.join(bundle, "Contents", "Info.plist")):
            raise ValueError("bundle_metadata_missing")
    return bundle


def acquire_candidate(action, staging_root, observer=None):
    """Return private staging plus verified observations, or remove failed staging.

    Only zip acquisition is executable. dmg/pkg/app require separate contracts.
    A caller may inject an observer for synthetic tests, never through JSON.
    """
    candidate = action["candidate"]
    if candidate.get("artifact_type") != "zip":
        raise ValueError("artifact_format_requires_review")
    name = _name(candidate.get("bundle_name"))
    expected = candidate.get("sha256")
    if not isinstance(expected, str) or not re.fullmatch("[a-f0-9]{64}", expected):
        raise ValueError("artifact_hash_required")
    root = os.path.realpath(staging_root)
    info = os.lstat(root)
    if (
        os.path.islink(staging_root)
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) & 0o022
    ):
        raise ValueError("unsafe_staging_root")
    limits = action["limits"]
    maximum = _bound(limits["maximum_bytes"], 4 * 1024**3)
    hosts = action.get("download_hosts")
    if not isinstance(hosts, list) or not hosts:
        raise ValueError("artifact_hosts_required")
    validate_download_url(candidate["url"], hosts)
    staging = tempfile.mkdtemp(prefix=".recipe-", dir=root)
    try:
        archive = os.path.join(staging, "payload.zip")
        deadline = time.monotonic() + 600
        download(
            candidate["url"],
            archive,
            allowed_hosts=hosts,
            timeout=300,
            max_bytes=maximum,
        )
        h = hashlib.sha256()
        with open(archive, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        if h.hexdigest() != expected:
            raise ValueError("artifact_hash_changed")
        bundle = _extract(archive, staging, name, limits, deadline)
        observed = (observer or observe_bundle)(bundle)
        if (
            observed.get("good") is not True
            or observed.get("receipt_present") is not False
            or any(
                observed.get(k) != candidate.get(c)
                for k, c in [
                    ("bundle_id", "bundle_id"),
                    ("team_id", "team_id"),
                    ("version", "version"),
                    ("build", "build"),
                ]
            )
        ):
            raise ValueError("candidate_identity_changed")
        if "arm64" not in observed.get("architectures", []) or version_compare(
            observed.get("host_os"), observed.get("minimum_os")
        ) not in (0, 1):
            raise ValueError("candidate_incompatible")
        return dict(
            staging_path=staging,
            bundle_path=bundle,
            observed=observed,
            artifact_sha256=expected,
        )
    except BaseException:
        shutil.rmtree(staging)
        raise
