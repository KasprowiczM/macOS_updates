"""Selected-product public metadata probes with bounded local caching/history.

Only reviewed declarative sources are consulted. Local SUFeedURL, package scripts,
apps and manager commands are never used to discover or probe a channel.
"""

import concurrent.futures
import copy
import datetime
import hashlib
import json
import os
import pathlib
import re
import tempfile
import threading
import time
from urllib.parse import urlsplit
from channel_advisor import recommend_channel, timestamp
from download_policy import download, validate_download_url, _request

MAX_METADATA = 2 * 1024 * 1024
PARSERS = {
    "unknown",
    "github_release",
    "json_path",
    "chrome_versions",
    "proton_releases",
    "open_design",
    "brew_cask",
    "app_store_mac",
}
STABLE_POLICIES = {
    "unknown",
    "github_flags",
    "reviewed_endpoint",
    "reviewed_field",
    "category_stable",
    "channel_field",
    "beta_only",
    "public_store_listing",
    "cask_artifact_stable",
}


def default_manifest_path():
    return str(
        pathlib.Path(__file__).resolve().parents[2] / "config/channel_sources.json"
    )


def load_channel_sources(path=None):
    with open(path or default_manifest_path(), "rb") as stream:
        raw = stream.read(MAX_METADATA + 1)
    if len(raw) > MAX_METADATA:
        raise ValueError("channel_manifest_too_large")
    value = json.loads(raw)
    if (
        value.get("schema_version") != 1
        or not isinstance(value.get("products"), list)
        or not isinstance(value.get("registry_rows"), list)
    ):
        raise ValueError("invalid_channel_manifest")
    ids = set()
    for product in value["products"]:
        pid = product.get("product_id")
        if (
            not isinstance(pid, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", pid)
            or pid in ids
            or product.get("edition") not in ("gui", "cli", "suite")
        ):
            raise ValueError("invalid_channel_product")
        ids.add(pid)
        if product.get("version_comparison_policy") not in (
            "numeric",
            "numeric_before_comma",
            "office_release_family",
            "warp_stable",
            "build_b",
            "incomparable",
        ):
            raise ValueError("unreviewed_comparison_policy")
        if not isinstance(product.get("sources"), list) or len(product["sources"]) > 8:
            raise ValueError("invalid_channel_sources")
        source_ids = set()
        for source in product["sources"]:
            if not isinstance(source.get("source_id"), str) or not re.fullmatch(
                r"[a-z][a-z0-9_-]{0,63}", source["source_id"]
            ):
                raise ValueError("invalid_channel_source_id")
            if (
                source.get("source_id") in source_ids
                or source.get("parser") not in PARSERS
                or source.get("stable_policy") not in STABLE_POLICIES
            ):
                raise ValueError("invalid_channel_source")
            source_ids.add(source.get("source_id"))
            if (
                not isinstance(source.get("allowed_hosts"), list)
                or not source["allowed_hosts"]
            ):
                raise ValueError("source_hosts_required")
            validate_download_url(source.get("url"), source["allowed_hosts"])
            if type(source.get("identity_reviewed")) is not bool:
                raise ValueError("source_identity_required")
    rows = value["registry_rows"]
    if len(rows) > 1000 or any(
        not isinstance(r.get("product_ids"), list) or not set(r["product_ids"]) <= ids
        for r in rows
    ):
        raise ValueError("invalid_channel_rows")
    return value


class ProbeBudget:
    def __init__(self, seconds=60):
        self.deadline = time.monotonic() + seconds
        self.hosts = {}
        self.cooldowns = {}
        self.mutex = threading.Lock()

    def remaining(self):
        return max(0, self.deadline - time.monotonic())

    def host(self, name):
        with self.mutex:
            return self.hosts.setdefault(name, threading.Lock())

    def cooldown(self, name, seconds=None):
        with self.mutex:
            if seconds is not None:
                self.cooldowns[name] = time.monotonic() + seconds
            return max(0, self.cooldowns.get(name, 0) - time.monotonic())


class _LockedResponse:
    def __init__(self, response, lock):
        self.response = response
        self.lock = lock

    def __getattr__(self, name):
        return getattr(self.response, name)

    def close(self):
        try:
            self.response.close()
        finally:
            if self.lock is not None:
                self.lock.release()
                self.lock = None


def _public_metadata_fetch(
    url, allowed_hosts, timeout=10, max_bytes=MAX_METADATA, budget=None
):
    budget = budget or ProbeBudget()
    status = {"status": None, "retry_after": None}

    def request(url, addresses, remaining):
        lock = budget.host(urlsplit(url).hostname)
        if not lock.acquire(timeout=min(remaining, budget.remaining())):
            raise ValueError("probe_budget_exhausted")
        try:
            cooldown = budget.cooldown(urlsplit(url).hostname)
            if cooldown > 0:
                status.update(
                    status=429,
                    retry_after=str(int(cooldown) + 1),
                    response_host=urlsplit(url).hostname,
                )
                raise ValueError("host_rate_limited")
            response = _request(url, addresses, min(remaining, budget.remaining()))
            status["status"] = response.status
            status["response_host"] = urlsplit(url).hostname
            status["retry_after"] = response.getheader("Retry-After")
            if response.status == 429:
                current = datetime.datetime.now(datetime.timezone.utc).isoformat()
                delay = _retry_after(status["retry_after"], current)
                budget.cooldown(
                    urlsplit(url).hostname, delay if delay is not None else 60
                )
            return _LockedResponse(response, lock)
        except BaseException:
            lock.release()
            raise

    with tempfile.TemporaryDirectory(prefix="mac_update_channel_") as root:
        dest = os.path.join(root, "metadata")
        try:
            download(
                url,
                dest,
                allowed_hosts,
                timeout=min(timeout, budget.remaining()),
                max_bytes=max_bytes,
                request=request,
            )
            with open(dest, "r", encoding="utf-8") as stream:
                body = stream.read(max_bytes + 1)
            return dict(status, body=body)
        except Exception:
            # Never expose URL query secrets or transport exception text.
            return dict(status, body="", error="metadata_unavailable")


def _base(recipe, source, now):
    return dict(
        product_id=recipe["product_id"],
        edition=recipe["edition"],
        source_id=source["source_id"],
        updater_id=source.get("updater_id"),
        release_channel="unknown",
        stable_confirmed=False,
        version=None,
        build=None,
        release_identity=None,
        published_at=None,
        observed_at=now,
        availability="unknown",
        compatibility={"status": "unknown", "minimum_os": None, "architectures": []},
        region=source.get("region"),
        evidence_url=source["url"],
        fetch_status="unknown",
        cached=False,
    )


def _numeric(value):
    return (
        tuple(map(int, value.split(".")))
        if isinstance(value, str) and re.fullmatch(r"\d+(?:\.\d+)*", value)
        else None
    )


def _compatibility(source, environment, minimum=None, architectures=None):
    minimum = minimum or source.get("minimum_os")
    architectures = architectures or source.get("architectures", [])
    os_version = _numeric(environment.get("os_version"))
    min_version = _numeric(minimum)
    architecture = environment.get("architecture")
    status = "unknown"
    if architecture and architectures and architecture not in architectures:
        status = "incompatible"
    elif os_version and min_version:
        count = max(len(os_version), len(min_version))
        if os_version + (0,) * (count - len(os_version)) < min_version + (0,) * (
            count - len(min_version)
        ):
            status = "incompatible"
        elif architecture and architectures:
            status = "compatible"
    return dict(status=status, minimum_os=minimum, architectures=architectures)


def _path(obj, keys):
    for key in keys:
        obj = obj[key]
    return obj


def _parse(recipe, source, response, environment, now):
    base = _base(recipe, source, now)
    base["fetch_status"] = "ok"
    base["availability"] = "listed"
    obj = json.loads(response["body"])
    parser = source["parser"]
    releases = []
    if parser == "github_release":
        base.update(
            version=obj.get("tag_name"),
            published_at=obj.get("published_at"),
            stable_confirmed=obj.get("prerelease") is False
            and obj.get("draft") is False
            and source["stable_policy"] == "github_flags",
        )
        releases = [base]
    elif parser == "json_path":
        base.update(
            version=_path(obj, source["version_path"]),
            stable_confirmed=source["stable_policy"]
            in ("reviewed_endpoint", "reviewed_field"),
        )
        releases = [base]
    elif parser == "chrome_versions":
        releases = [
            dict(
                base,
                version=row.get("version"),
                stable_confirmed=source["stable_policy"] == "reviewed_endpoint",
            )
            for row in obj.get("versions", [])[:100]
        ]
    elif parser == "proton_releases":
        for row in obj.get("Releases", [])[:100]:
            if row.get("CategoryName") != "Stable":
                continue
            releases.append(
                dict(
                    base,
                    version=row.get("Version"),
                    published_at=row.get("ReleaseDate"),
                    stable_confirmed=source["stable_policy"] == "category_stable",
                    availability="staged"
                    if isinstance(row.get("RolloutProportion"), (float, int))
                    and row["RolloutProportion"] < 1
                    else "listed",
                    compatibility=_compatibility(
                        source, environment, row.get("MinimumOsVersion")
                    ),
                )
            )
    elif parser == "open_design":
        base.update(
            version=obj.get("stableVersion"),
            stable_confirmed=obj.get("channel") == "stable"
            and source["stable_policy"] == "channel_field",
        )
        if "mac_arm64" not in obj.get(
            "expectedPlatforms", []
        ) or "mac_arm64" in obj.get("failedPlatforms", []):
            base["availability"] = "unavailable"
        releases = [base]
    elif parser == "brew_cask":
        if obj.get("token") != source.get("token") or obj.get("disabled") is True:
            raise ValueError("manager_identity_changed")
        version = obj.get("version")
        stable = source[
            "stable_policy"
        ] == "cask_artifact_stable" and "/stable/" in str(obj.get("url", ""))
        depends = obj.get("depends_on", {}).get("macos", {}).get(">=", [])
        minimum = (
            depends[0] if isinstance(depends, list) and len(depends) == 1 else None
        )
        base.update(
            version=version,
            stable_confirmed=stable,
            compatibility=_compatibility(source, environment, minimum),
        )
        releases = [base]
    elif parser == "app_store_mac":
        matches = [
            r
            for r in obj.get("results", [])
            if r.get("trackId") == source.get("store_id")
            and r.get("bundleId") == source.get("bundle_id")
            and r.get("kind") == "mac-software"
        ]
        if len(matches) != 1:
            raise ValueError("store_identity_or_platform_unverified")
        row = matches[0]
        base.update(
            version=row.get("version"),
            published_at=row.get("currentVersionReleaseDate"),
            stable_confirmed=source["stable_policy"] == "public_store_listing",
            compatibility=_compatibility(
                source, environment, row.get("minimumOsVersion")
            ),
        )
        releases = [base]
    else:
        raise ValueError("parser_unreviewed")
    if not releases:
        raise ValueError("no_release_metadata")
    for row in releases:
        version = row.get("version")
        if not isinstance(version, str) or not version or len(version) > 256:
            raise ValueError("version_missing")
        if version.startswith("v") and source["parser"] == "github_release":
            row["version"] = version[1:]
        row["release_channel"] = "stable" if row["stable_confirmed"] else "unknown"
        row["release_identity"] = row["version"]
        if row["compatibility"]["minimum_os"] is None:
            row["compatibility"] = _compatibility(source, environment)
        # A public page cannot establish account/device offered state.
        if row["availability"] == "offered":
            row["availability"] = "listed"
    return releases


def _cache_key(recipe, source, environment):
    value = [
        recipe["product_id"],
        recipe["edition"],
        source,
        environment.get("os_version"),
        environment.get("architecture"),
        environment.get("region"),
    ]
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _retry_after(value, now):
    try:
        return min(86400, max(0, int(value)))
    except (ValueError, TypeError):
        try:
            import email.utils

            return min(
                86400,
                max(
                    0,
                    int(
                        (
                            email.utils.parsedate_to_datetime(value) - timestamp(now)
                        ).total_seconds()
                    ),
                ),
            )
        except (ValueError, TypeError, AttributeError):
            return None


def collect_channel_observations(recipe, environment, fetch, cache, now):
    timestamp(now)
    budget = environment.get("_budget") or ProbeBudget()
    observations = []
    for source in recipe.get("sources", []):
        base = _base(recipe, source, now)
        try:
            try:
                validate_download_url(source["url"], source["allowed_hosts"])
            except ValueError:
                base["fetch_status"] = "unreviewed_source"
                observations.append(base)
                continue
            if not source.get("identity_reviewed") or source.get("parser") == "unknown":
                base["fetch_status"] = "unreviewed_source"
                observations.append(base)
                continue
            key = _cache_key(recipe, source, environment)
            cached = cache.get(key)
            if (
                cached
                and cached.get("retry_until")
                and timestamp(now) < timestamp(cached["retry_until"])
            ):
                observations.extend(
                    [
                        dict(r, cached=True)
                        for r in copy.deepcopy(cached["observations"])
                    ]
                )
                continue
            if (
                cached
                and not cached.get("retry_until")
                and not environment.get("refresh")
                and 0
                <= (timestamp(now) - timestamp(cached["observed_at"])).total_seconds()
                < 86400
            ):
                observations.extend(
                    [
                        dict(r, cached=True)
                        for r in copy.deepcopy(cached["observations"])
                    ]
                )
                continue
            host = urlsplit(source["url"]).hostname
            cooldown = budget.cooldown(host)
            if cooldown > 0:
                base.update(fetch_status="rate_limited", retry_after=int(cooldown) + 1)
                observations.append(base)
                continue
            if budget.remaining() <= 0:
                base["fetch_status"] = "pending"
                observations.append(base)
                continue
            if fetch is None:
                response = _public_metadata_fetch(
                    source["url"],
                    source["allowed_hosts"],
                    timeout=min(10, budget.remaining()),
                    budget=budget,
                )
            else:
                lock = budget.host(urlsplit(source["url"]).hostname)
                if not lock.acquire(timeout=budget.remaining()):
                    raise ValueError("probe_budget_exhausted")
                try:
                    if budget.remaining() <= 0:
                        raise ValueError("probe_budget_exhausted")
                    cooldown = budget.cooldown(host)
                    if cooldown > 0:
                        response = {
                            "status": 429,
                            "retry_after": str(int(cooldown) + 1),
                            "body": "",
                        }
                    else:
                        response = fetch(
                            source["url"],
                            source["allowed_hosts"],
                            timeout=min(10, budget.remaining()),
                            max_bytes=MAX_METADATA,
                        )
                        if isinstance(response, dict) and response.get("status") == 429:
                            delay = _retry_after(response.get("retry_after"), now)
                            budget.cooldown(host, delay if delay is not None else 60)
                finally:
                    lock.release()
            if not isinstance(response, dict) or response.get("status") != 200:
                base["fetch_status"] = (
                    "rate_limited"
                    if isinstance(response, dict) and response.get("status") == 429
                    else "unavailable"
                )
                if base["fetch_status"] == "rate_limited":
                    base["retry_after"] = _retry_after(response.get("retry_after"), now)
                    # Unknown Retry-After gets a short bounded backoff, never a
                    # blocking retry loop. Explicit refresh respects the server.
                    delay = (
                        base["retry_after"] if base["retry_after"] is not None else 60
                    )
                    budget.cooldown(response.get("response_host", host), delay)
                    until = (
                        timestamp(now) + datetime.timedelta(seconds=delay)
                    ).isoformat()
                    cache[key] = {
                        "observed_at": now,
                        "retry_until": until,
                        "observations": [copy.deepcopy(base)],
                    }
                observations.append(base)
                continue
            body = response.get("body")
            if not isinstance(body, str) or len(body.encode("utf-8")) > MAX_METADATA:
                raise ValueError("metadata_size_limit")
            parsed = _parse(recipe, source, response, environment, now)
            observations.extend(parsed)
            cache[key] = {"observed_at": now, "observations": copy.deepcopy(parsed)}
        except (ValueError, TypeError, KeyError, AttributeError, OSError):
            base["fetch_status"] = (
                "unreviewed_source"
                if not source.get("identity_reviewed")
                else "unavailable"
            )
            observations.append(base)
    return observations


def _load_cache(state_dir):
    from inventory_store import _root

    root = _root(state_dir)
    if root is None:
        return {"schema_version": 1, "cache": {}, "history": []}
    path = os.path.join(root, "channel-observations.json")
    if not os.path.exists(path):
        return {"schema_version": 1, "cache": {}, "history": []}
    from inventory_store import _open_regular

    fd = _open_regular(path, os.O_RDONLY)
    with os.fdopen(fd, "rb") as stream:
        raw = stream.read(16 * MAX_METADATA + 1)
    if len(raw) > 16 * MAX_METADATA:
        raise ValueError("channel_cache_too_large")
    value = json.loads(raw)
    if (
        value.get("schema_version") != 1
        or not isinstance(value.get("cache"), dict)
        or not isinstance(value.get("history"), list)
    ):
        raise ValueError("invalid_channel_cache")
    return value


def _save_cache(state_dir, value):
    from inventory_store import locked_state
    from policy_runtime import _atomic_json

    with locked_state(state_dir) as root:
        # Concurrent explicit checks keep both sets of observations. Cache keys
        # include the reviewed source policy and OS/architecture context.
        previous = _load_cache(root)
        merged = dict(previous.get("cache", {}))
        merged.update(value["cache"])
        history = {}
        for row in previous.get("history", []) + value.get("history", []):
            key = (
                row.get("product_id"),
                row.get("edition"),
                row.get("source_id"),
                row.get("release_identity"),
            )
            if key not in history:
                history[key] = copy.deepcopy(row)
                continue
            existing = history[key]
            if row.get("first_observed_at", "") < existing.get("first_observed_at", ""):
                existing["first_observed_at"] = row["first_observed_at"]
                existing["first_seen_interval"] = row.get("first_seen_interval")
            existing["last_observed_at"] = max(
                existing.get("last_observed_at", ""), row.get("last_observed_at", "")
            )
        # Preserve the newest source entries with a bounded private cache.
        keys = sorted(
            merged, key=lambda k: merged[k].get("observed_at", ""), reverse=True
        )[:4096]
        saved = {
            "schema_version": 1,
            "cache": {k: merged[k] for k in keys},
            "history": list(history.values())[-20000:],
        }
        _atomic_json(os.path.join(root, "channel-observations.json"), saved)


def _record_history(history, rows):
    by_key = {
        (
            r.get("product_id"),
            r.get("edition"),
            r.get("source_id"),
            r.get("release_identity"),
        ): r
        for r in history
    }
    for row in rows:
        if (
            row.get("cached")
            or row.get("fetch_status") != "ok"
            or not row.get("stable_confirmed")
        ):
            continue
        key = (
            row["product_id"],
            row["edition"],
            row["source_id"],
            row.get("release_identity"),
        )
        if key in by_key:
            by_key[key]["last_observed_at"] = row["observed_at"]
            continue
        previous = [
            r
            for r in history
            if r.get("product_id") == row["product_id"]
            and r.get("edition") == row["edition"]
            and r.get("source_id") == row["source_id"]
            and r.get("last_observed_at", r.get("first_observed_at", ""))
            < row["observed_at"]
        ]
        lower = max(
            (r.get("last_observed_at", r.get("first_observed_at")) for r in previous),
            default=None,
        )
        record = {
            k: row.get(k)
            for k in (
                "product_id",
                "edition",
                "source_id",
                "release_identity",
                "stable_confirmed",
                "published_at",
            )
        }
        record.update(
            first_observed_at=row["observed_at"],
            last_observed_at=row["observed_at"],
            first_seen_interval={"after": lower, "at_or_before": row["observed_at"]},
        )
        history.append(record)
        by_key[key] = record
    return history[-20000:]


def _system_environment():
    import platform

    # OS/CPU facts only; no app scan, manager, shell or account access.
    return {
        "os_version": os.environ.get("MAC_UPDATE_OS_VERSION")
        or platform.mac_ver()[0]
        or None,
        "architecture": os.environ.get("MAC_UPDATE_ARCH") or platform.machine() or None,
    }


def match_installed_products(snapshot, manifest):
    """Match reviewed bundle IDs or verified installed-manager identities.

    Names and local feed URLs never establish a product. This mapping grants
    metadata-check scope only and is independent of install/update authority.
    """
    products = manifest["products"]
    matched = {}
    instances = {
        i.get("instance_id"): i
        for i in snapshot.get("instances", [])
        if i.get("presence") == "present" and i.get("freshness") == "fresh"
    }
    for product in products:
        pid = product["product_id"]
        for source in product["sources"]:
            if not source.get("identity_reviewed"):
                continue
            bundle = source.get("bundle_id")
            if bundle:
                apps = [i for i in instances.values() if i.get("bundle_id") == bundle]
                if len(apps) == 1:
                    app = apps[0]
                    evidence = app.get("evidence", [])
                    store = any(
                        e.get("kind") == "app_store_receipt"
                        or e.get("kind") == "mas"
                        and str(e.get("store_id")) == str(source.get("store_id"))
                        for e in evidence
                        if isinstance(e, dict)
                    )
                    prior = matched.get(pid)
                    source_id = (
                        "conflict"
                        if store
                        and prior
                        and prior.get("source_id") in ("homebrew", "conflict")
                        else "app_store"
                        if store
                        else prior.get("source_id")
                        if prior
                        else "unknown"
                    )
                    matched[pid] = dict(
                        app,
                        product_id=pid,
                        edition=product["edition"],
                        source_id=source_id,
                        updater_id="app_store" if source_id == "app_store" else None,
                    )
            token = source.get("token")
            if not token or source["source_id"] != "homebrew":
                continue
            packages = []
            for item in snapshot.get("packages", []):
                if (
                    item.get("manager") != "homebrew"
                    or item.get("presence") != "present"
                    or item.get("freshness") != "fresh"
                    or item.get("source_identity") != "cask:" + token
                    or not item.get("installed_receipt")
                ):
                    continue
                proven = any(
                    e.get("kind") == "homebrew"
                    and e.get("token") == token
                    and e.get("prefix") == item.get("prefix")
                    and e.get("installed_receipt") == item["installed_receipt"]
                    for e in item.get("evidence", [])
                    if isinstance(e, dict)
                )
                if proven:
                    packages.append(item)
            if len(packages) == 1:
                item = packages[0]
                apps = [
                    instances[i]
                    for i in item.get("related_instance_ids", [])
                    if i in instances
                ]
                # A receipt claiming the same bundle as MAS remains a conflict,
                # and public advice cannot silently pick either installation.
                if pid in matched and matched[pid]["source_id"] in (
                    "app_store",
                    "conflict",
                ):
                    matched[pid]["source_id"] = "conflict"
                    matched[pid]["updater_id"] = None
                    continue
                matched[pid] = dict(
                    apps[0] if len(apps) == 1 else item,
                    product_id=pid,
                    edition=product["edition"],
                    source_id="homebrew",
                    updater_id="homebrew",
                )
    return matched


def compare_selected_channels(
    snapshot,
    selected_product_ids=None,
    environment=None,
    refresh=False,
    state_dir=None,
    manifest_path=None,
    fetch=None,
    now=None,
):
    manifest = load_channel_sources(manifest_path)
    products = {p["product_id"]: p for p in manifest["products"]}
    now = now or datetime.datetime.now(datetime.timezone.utc).isoformat().replace(
        "+00:00", "Z"
    )
    timestamp(now)
    supplied = environment or {}
    environment = _system_environment()
    environment.update({k: v for k, v in supplied.items() if v not in (None, "")})
    environment.update(refresh=refresh, _budget=ProbeBudget())
    installed = match_installed_products(snapshot, manifest)
    selected = (
        set(installed) if selected_product_ids is None else set(selected_product_ids)
    )
    if len(selected) > 1000 or not selected <= products.keys():
        raise ValueError("unknown_channel_product")
    persisted = (
        _load_cache(state_dir)
        if selected
        else {"schema_version": 1, "cache": {}, "history": []}
    )
    cache = persisted["cache"]
    observations = []
    recommendations = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(
                collect_channel_observations,
                products[pid],
                environment,
                fetch,
                cache,
                now,
            ): pid
            for pid in sorted(selected)
        }
        for future, pid in futures.items():
            rows = future.result()
            observations.extend(rows)
            recommendations.append(
                recommend_channel(
                    products[pid],
                    rows,
                    installed.get(pid),
                    {"history": persisted["history"]},
                )
            )
    persisted["history"] = _record_history(persisted["history"], observations)
    if selected:
        _save_cache(state_dir, persisted)
    return {
        "schema_version": 1,
        "as_of": now,
        "recommendations": recommendations,
        "observations": observations,
        "pending": sorted(
            {
                r["product_id"]
                for r in observations
                if r["fetch_status"] in ("pending", "unreviewed_source")
            }
        ),
        "network_scope": "selected_or_trusted_installed_products",
        "unmatched_installed_count": max(
            0,
            len(
                [
                    i
                    for i in snapshot.get("instances", [])
                    if i.get("presence") == "present"
                ]
            )
            - len(installed),
        ),
        "mutation_authority": False,
    }
