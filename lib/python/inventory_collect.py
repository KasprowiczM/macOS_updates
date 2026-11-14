"""Bounded static inventory collection; never executes discovered binaries."""

import copy
import datetime
import os
import plistlib
import stat
import uuid
from dataclasses import dataclass, field
from inventory_model import _timestamp

MAX_RECORDS = 10000
MAX_ENTRIES = 50000
MAX_PLIST = 1024 * 1024
MAX_TEXT = 4096


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def source_result(
    status,
    items=None,
    observed_at=None,
    covered_roots=None,
    complete=None,
    reason_code=None,
):
    return dict(
        schema_version=1,
        status=status,
        items=items or [],
        observed_at=observed_at or now(),
        covered_roots=covered_roots or [],
        complete=(status == "ok" if complete is None else complete),
        reason_code=reason_code,
    )


def _inside(path, root):
    try:
        return os.path.commonpath((path, root)) == root
    except ValueError:
        return False


def read_bundle_static(path):
    plist = os.path.join(path, "Contents", "Info.plist")
    try:
        real = os.path.realpath(path)
        if not _inside(os.path.realpath(plist), real) or os.path.islink(plist):
            raise OSError("unsafe plist")
        fd = os.open(
            plist,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        with os.fdopen(fd, "rb") as f:
            if not stat.S_ISREG(os.fstat(f.fileno()).st_mode):
                raise OSError("not regular")
            data = f.read(MAX_PLIST + 1)
        if len(data) > MAX_PLIST:
            return source_result("partial", reason_code="metadata_too_large")
        info = plistlib.loads(data)
        if not isinstance(info, dict):
            raise ValueError("invalid plist")
        oversized = any(
            isinstance(info.get(k), str) and len(info[k]) > MAX_TEXT
            for k in (
                "CFBundleIdentifier",
                "CFBundleName",
                "CFBundleShortVersionString",
                "CFBundleVersion",
                "LSMinimumSystemVersion",
            )
        )

        def string(key):
            v = info.get(key)
            return v if isinstance(v, str) and len(v) <= MAX_TEXT else None

        receipt = os.path.join(path, "Contents", "_MASReceipt", "receipt")
        evidence = [{"kind": "info_plist", "path": plist}]
        # Only record marker presence. Feed URLs can contain credentials and are
        # deliberately neither retained nor contacted.
        sparkle = os.path.join(path, "Contents", "Frameworks", "Sparkle.framework")
        electron = os.path.join(path, "Contents", "Resources", "app-update.yml")

        def safe_marker(marker, want_directory=False):
            try:
                st = os.lstat(marker)
                return (
                    not stat.S_ISLNK(st.st_mode)
                    and _inside(os.path.realpath(marker), real)
                    and (
                        stat.S_ISDIR(st.st_mode)
                        if want_directory
                        else stat.S_ISREG(st.st_mode)
                    )
                )
            except OSError:
                return False

        if (
            isinstance(info.get("SUFeedURL"), str) and bool(info["SUFeedURL"])
        ) or safe_marker(sparkle, True):
            evidence.append({"kind": "framework", "name": "sparkle"})
        if safe_marker(electron):
            evidence.append({"kind": "framework", "name": "electron_updater"})
        squirrel = os.path.join(path, 'Contents', 'Frameworks', 'Squirrel.framework')
        if safe_marker(squirrel, True):
            evidence.append({'kind': 'framework', 'name': 'squirrel'})
        if isinstance(info.get('KSUpdateURL'), str) and info['KSUpdateURL']:
            evidence.append({'kind': 'framework', 'name': 'keystone'})
        protected = "/System/Applications"
        if _inside(os.path.abspath(path), protected) and _inside(
            real, os.path.realpath(protected)
        ):
            evidence.append({"kind": "protected_root", "path": protected})
        if (
            _inside(os.path.realpath(receipt), real)
            and os.path.isfile(receipt)
            and not os.path.islink(receipt)
        ):
            evidence.append({"kind": "app_store_receipt", "path": receipt})
        return source_result(
            "partial" if oversized else "ok",
            [
                dict(
                    bundle_id=string("CFBundleIdentifier"),
                    team_id=None,
                    name=string("CFBundleName"),
                    short_version=string("CFBundleShortVersionString"),
                    build_version=string("CFBundleVersion"),
                    architectures=None,
                    minimum_os=string("LSMinimumSystemVersion"),
                    channel="unknown",
                    evidence=evidence,
                )
            ],
        )
    except (OSError, ValueError, plistlib.InvalidFileException, OverflowError):
        receipt = os.path.join(path, "Contents", "_MASReceipt", "receipt")
        evidence = []
        if (
            _inside(os.path.realpath(receipt), os.path.realpath(path))
            and os.path.isfile(receipt)
            and not os.path.islink(receipt)
        ):
            evidence.append({"kind": "app_store_receipt", "path": receipt})
        return source_result(
            "partial", [{"evidence": evidence}], reason_code="invalid_metadata"
        )


def _unavailable(*args):
    return source_result("unavailable", reason_code="not_configured")


@dataclass
class Providers:
    read_bundle: object = read_bundle_static
    list_mas: object = _unavailable
    list_brew: object = _unavailable
    list_cli: object = _unavailable
    brew_prefixes: list = field(default_factory=list)
    cli_prefixes: list = field(default_factory=list)


def _call(fn, *args):
    try:
        result = fn(*args)
        if (
            not isinstance(result, dict)
            or result.get("status") not in ("ok", "partial", "error", "unavailable")
            or not isinstance(result.get("items"), list)
            or not isinstance(result.get("complete"), bool)
            or result.get("schema_version") != 1
            or not _timestamp(result.get("observed_at"))
            or not isinstance(result.get("covered_roots"), list)
            or any(not isinstance(x, str) for x in result["covered_roots"])
            or not isinstance(result.get("reason_code"), (str, type(None)))
            or any(not isinstance(x, dict) for x in result["items"])
            or (result["status"] != "ok" and result["complete"])
        ):
            raise ValueError()
        return copy.deepcopy(result)
    except Exception:
        return source_result("error", reason_code="provider_error")


def _file_identity(evidence):
    for item in evidence if isinstance(evidence, list) else []:
        if isinstance(item, dict) and item.get("kind") == "file_metadata":
            path = item.get("path")
            if isinstance(path, str) and os.path.isabs(path):
                return os.path.realpath(path)
    return None


def _complete_formula_domain_package(source, package):
    """Bind the provider's Cellar proof only to its exact formula receipt.

    No cask, unknown receipt, malformed peer or global traversal failure can
    inherit this narrower observation. Aggregate absence rules stay unchanged.
    """
    if (source.get("formula_domain_complete") is not True
            or source.get("status") != "partial"
            or source.get("reason_code") != "manager_metadata_incomplete"
            or package.get("manager") != "homebrew"):
        return False
    identity, version, prefix = (package.get(key) for key in ("source_identity", "version", "prefix"))
    if not isinstance(identity, str) or not identity.startswith("formula:"):
        return False
    token = identity[len("formula:"):]
    if (any(not isinstance(value, str) or not value or value in (".", "..")
            or "/" in value for value in (token, version))
            or source.get("covered_roots") != [prefix]):
        return False
    receipt = os.path.join(prefix, "Cellar", token, version, "INSTALL_RECEIPT.json")
    evidence = package.get("evidence", [])
    return (package.get("installed_receipt") == receipt and bool(evidence)
            and all(e.get("kind") == "homebrew" and e.get("token") == token
                    and e.get("prefix") == prefix and e.get("installed_receipt") == receipt
                    and e.get("artifact_path") is None for e in evidence))


def _package_key(record):
    receipt = record.get("installed_receipt")
    observation = _file_identity(record.get("evidence")) if receipt is None else None
    return (
        record["manager"],
        record["prefix"],
        str(record.get("source_identity")),
        str(receipt),
        observation,
    )



def _receipt_lineage(record):
    """Verified Homebrew receipt family, excluding version/timestamp segments."""
    manager, prefix = record.get('manager'), record.get('prefix')
    identity, receipt = record.get('source_identity'), record.get('installed_receipt')
    if manager != 'homebrew' or not all(isinstance(x, str) for x in (prefix, identity, receipt)):
        return None
    category, separator, token = identity.partition(':')
    if not separator or category not in ('formula', 'cask') or not token or '/' in token or token in ('.', '..'):
        return None
    if os.path.normpath(receipt) != receipt or not _inside(receipt, prefix):
        return None
    parts = os.path.relpath(receipt, prefix).split(os.sep)
    if category == 'formula':
        valid = len(parts) == 4 and parts[:2] == ['Cellar', token] and parts[-1] == 'INSTALL_RECEIPT.json'
    else:
        valid = (len(parts) == 7 and parts[:3] == ['Caskroom', token, '.metadata']
                 and parts[-2:] == ['Casks', token + '.json'])
    if not valid or not any(e.get('kind') == 'homebrew' and e.get('prefix') == prefix
                            and e.get('token') == token and e.get('installed_receipt') == receipt
                            for e in record.get('evidence', []) if isinstance(e, dict)):
        return None
    return manager, prefix, identity, record.get('channel', 'unknown')


def collect_snapshot(roots, providers, previous):
    if previous is not None:
        from inventory_model import validate_snapshot

        validate_snapshot(previous)
    timestamp = now()
    sources, instances, packages = {}, [], []
    old_apps = {x["path"]: x for x in (previous or {}).get("instances", [])}
    old_packages = {_package_key(x): x for x in (previous or {}).get("packages", [])}
    seen_apps, seen_packages = set(), set()
    old_lineages = {}
    for previous_package in old_packages.values():
        lineage = _receipt_lineage(previous_package)
        if lineage is not None:
            old_lineages.setdefault(lineage, []).append(previous_package)
    for raw in roots:
        root = os.path.realpath(os.path.expanduser(raw))
        source = source_result("ok", covered_roots=[root])
        sources["filesystem:" + root] = source
        visited = set()
        entry_budget = [MAX_ENTRIES]
        try:
            root_device = os.stat(root).st_dev
        except OSError:
            source.update(
                status="error", complete=False, reason_code="root_unavailable"
            )
            continue

        def walk(directory, depth):
            if entry_budget[0] <= 0:
                source.update(
                    status="partial", complete=False, reason_code="entry_limit"
                )
                return
            if len(instances) >= MAX_RECORDS:
                source.update(
                    status="partial", complete=False, reason_code="record_limit"
                )
                return
            try:
                resolved = os.path.realpath(directory)
                if not _inside(resolved, root) or resolved in visited:
                    return
                if os.stat(resolved).st_dev != root_device:
                    source.update(
                        status="partial", complete=False, reason_code="different_volume"
                    )
                    return
                visited.add(resolved)
                with os.scandir(directory) as it:
                    entries = []
                    for entry in it:
                        if entry_budget[0] <= 0:
                            source.update(
                                status="partial",
                                complete=False,
                                reason_code="entry_limit",
                            )
                            break
                        entry_budget[0] -= 1
                        entries.append(entry)
                for entry in sorted(entries, key=lambda e: e.name):
                    path = os.path.abspath(entry.path)
                    real = os.path.realpath(path)
                    if not _inside(real, root):
                        source.update(
                            status="partial", complete=False, reason_code="outside_root"
                        )
                        continue
                    if not entry.is_dir(follow_symlinks=True):
                        continue
                    if entry.name.lower().endswith(".app"):
                        if path in seen_apps:
                            continue
                        if len(instances) >= MAX_RECORDS:
                            source.update(
                                status="partial",
                                complete=False,
                                reason_code="record_limit",
                            )
                            break
                        result = _call(providers.read_bundle, path)
                        item = (
                            result["items"][0]
                            if result["items"] and isinstance(result["items"][0], dict)
                            else {}
                        )
                        if result["status"] != "ok" or not result["complete"]:
                            source.update(
                                status="partial",
                                complete=False,
                                reason_code="bundle_metadata_partial",
                            )
                        fields = (
                            "bundle_id",
                            "team_id",
                            "name",
                            "short_version",
                            "build_version",
                            "minimum_os",
                        )
                        if (
                            any(
                                item.get(k) is not None and not isinstance(item[k], str)
                                for k in fields
                            )
                            or not isinstance(item.get("evidence", []), list)
                            or any(
                                not isinstance(e, dict)
                                or not isinstance(e.get("kind"), str)
                                for e in item.get("evidence", [])
                            )
                            or (
                                item.get("architectures") is not None
                                and (
                                    not isinstance(item["architectures"], list)
                                    or any(
                                        not isinstance(x, str)
                                        for x in item["architectures"]
                                    )
                                )
                            )
                            or item.get("channel", "unknown")
                            not in ("stable", "beta", "testflight", "unknown")
                        ):
                            item = {}
                            result = source_result(
                                "partial", reason_code="invalid_metadata"
                            )
                            source.update(
                                status="partial",
                                complete=False,
                                reason_code="bundle_metadata_partial",
                            )
                        old = old_apps.get(path, {})
                        if (
                            old.get("bundle_id")
                            and item.get("bundle_id")
                            and old["bundle_id"] != item["bundle_id"]
                        ):
                            old = {}
                        evidence = (
                            item.get("evidence")
                            if isinstance(item.get("evidence"), list)
                            else []
                        )
                        if result["status"] != "ok" or not result["complete"]:
                            evidence = [
                                e
                                for e in evidence
                                if isinstance(e, dict)
                                and e.get("kind") in ("info_plist", "app_store_receipt")
                            ]
                        inst = dict(
                            instance_id=old.get("instance_id", str(uuid.uuid4())),
                            path=path,
                            real_path=real,
                            is_symlink=entry.is_symlink(),
                            scope=(
                                "system"
                                if root in ("/Applications", "/System/Applications")
                                else (
                                    "user"
                                    if root
                                    == os.path.realpath(
                                        os.path.expanduser("~/Applications")
                                    )
                                    else "optional_root"
                                )
                            ),
                            bundle_id=item.get("bundle_id"),
                            team_id=item.get("team_id"),
                            name=item.get("name"),
                            short_version=item.get("short_version"),
                            build_version=item.get("build_version"),
                            architectures=item.get("architectures"),
                            minimum_os=item.get("minimum_os"),
                            channel=item.get("channel") or "unknown",
                            observed_at=timestamp,
                            evidence=evidence,
                            presence="present",
                            freshness=(
                                "fresh"
                                if result["status"] == "ok" and result["complete"]
                                else "stale"
                            ),
                            parent_instance_id=None,
                        )
                        instances.append(inst)
                        seen_apps.add(path)
                    elif entry.name != "Contents":
                        if entry.is_symlink():
                            source.update(
                                status="partial",
                                complete=False,
                                reason_code="directory_alias",
                            )
                            continue
                        if depth < 3:
                            walk(path, depth + 1)
                        else:
                            source.update(
                                status="partial",
                                complete=False,
                                reason_code="depth_limit",
                            )
            except OSError:
                source.update(
                    status="partial", complete=False, reason_code="directory_error"
                )

        walk(root, 0)
    sources["mas"] = _call(providers.list_mas)
    for kind, prefixes, fn in (
        ("brew", providers.brew_prefixes, providers.list_brew),
        ("cli", providers.cli_prefixes, providers.list_cli),
    ):
        for raw in prefixes:
            prefix = os.path.realpath(os.path.expanduser(raw))
            source = _call(fn, prefix)
            sources[kind + ":" + prefix] = source
            current_lineages = {}
            for item in source['items']:
                lineage = _receipt_lineage(dict(item, prefix=prefix))
                if lineage is not None:
                    current_lineages[lineage] = current_lineages.get(lineage, 0) + 1
            for item in source["items"]:
                if not isinstance(item, dict):
                    source.update(
                        status="partial", complete=False, reason_code="invalid_item"
                    )
                    continue
                if (
                    not isinstance(item.get("evidence", []), list)
                    or any(
                        not isinstance(e, dict) or not isinstance(e.get("kind"), str)
                        for e in item.get("evidence", [])
                    )
                    or any(
                        item.get(k) is not None and not isinstance(item[k], str)
                        for k in (
                            "manager",
                            "name",
                            "source_identity",
                            "installed_receipt",
                            "version",
                            "channel",
                        )
                    )
                    or item.get("channel", "unknown")
                    not in ("stable", "beta", "testflight", "unknown")
                    or item.get("explicitly_installed") is not None
                    and type(item["explicitly_installed"]) is not bool
                    or not isinstance(item.get("related_instance_ids", []), list)
                ):
                    source.update(
                        status="partial", complete=False, reason_code="invalid_item"
                    )
                    continue
                manager = item.get("manager") or (
                    "homebrew" if kind == "brew" else "unknown"
                )
                identity = item.get("source_identity") or item.get("name")
                receipt = item.get("installed_receipt")
                file_identity = (
                    _file_identity(item.get("evidence")) if receipt is None else None
                )
                key = (manager, prefix, str(identity), str(receipt), file_identity)
                old = (
                    old_packages.get(key, {})
                    if receipt is not None or file_identity is not None
                    else {}
                )
                lineage = _receipt_lineage(dict(item, prefix=prefix))
                candidates = old_lineages.get(lineage, []) if lineage is not None else []
                if (not old and source['status'] == 'ok' and source['complete']
                        and len(candidates) == 1 and current_lineages.get(lineage) == 1
                        and candidates[0].get('freshness') == 'fresh'
                        and candidates[0].get('presence') == 'present'):
                    old = candidates[0]
                    seen_packages.add(_package_key(old))
                if identity is None:
                    source.update(
                        status="partial", complete=False, reason_code="invalid_item"
                    )
                    continue
                packages.append(
                    dict(
                        package_id=old.get("package_id", str(uuid.uuid4())),
                        manager=manager,
                        prefix=prefix,
                        version=item.get("version"),
                        installed_receipt=receipt,
                        explicitly_installed=item.get("explicitly_installed"),
                        related_instance_ids=item.get("related_instance_ids", []),
                        evidence=[
                            dict(
                                e,
                                source_key=kind + ":" + prefix,
                                source_status=source["status"],
                                source_complete=source["complete"],
                            )
                            for e in item.get("evidence", [])
                            if isinstance(e, dict)
                        ],
                        presence="present",
                        freshness=(
                            "fresh"
                            if source["status"] == "ok" and source["complete"]
                            else "stale"
                        ),
                        observed_at=timestamp,
                        source_identity=identity,
                        channel=item.get("channel") or "unknown",
                    )
                )
                if receipt is not None or file_identity is not None:
                    seen_packages.add(key)
    # Later malformed entries can downgrade the whole manager response.
    for package in packages:
        package_kind = (
            "brew"
            if package["manager"] in ("homebrew", "brew", "brew_formula", "brew_cask")
            else "cli"
        )
        source_key = package_kind + ":" + package["prefix"]
        package_source = sources.get(source_key)
        if (package_kind == "brew" and package_source
                and _complete_formula_domain_package(package_source, package)):
            domain_key = "brew_formula:" + package["prefix"]
            domain = sources.setdefault(domain_key, source_result(
                "ok", observed_at=package_source["observed_at"],
                covered_roots=[os.path.join(package["prefix"], "Cellar")]))
            for evidence in package["evidence"]:
                evidence.update(source_key=domain_key, source_status="ok", source_complete=True)
            package["freshness"] = "fresh"
            package_source = domain
        if package_source and (
            package_source["status"] != "ok" or not package_source["complete"]
        ):
            package["freshness"] = "stale"
        for evidence in package["evidence"]:
            key = evidence.get("source_key")
            if key in sources:
                evidence["source_status"] = sources[key]["status"]
                evidence["source_complete"] = sources[key]["complete"]
                if sources[key]["status"] != "ok" or not sources[key]["complete"]:
                    package["freshness"] = "stale"
    # Attach ownership evidence only to an exact observed artifact path.
    by_path = {app["path"]: app for app in instances}
    for package in packages:
        related = set()
        for evidence in package["evidence"]:
            if evidence.get("kind") != "homebrew":
                continue
            artifact = evidence.get("artifact_path")
            if isinstance(artifact, str) and os.path.abspath(artifact) in by_path:
                related.add(by_path[os.path.abspath(artifact)]["instance_id"])
        package["related_instance_ids"] = sorted(related)
    for source_key, source in sources.items():
        if source_key != "mas" and not source_key.startswith("brew:"):
            continue
        for item in source["items"]:
            if not isinstance(item, dict):
                continue
            evidence_items = item.get("evidence", [])
            if not isinstance(evidence_items, list):
                continue
            for evidence in evidence_items:
                if not isinstance(evidence, dict):
                    continue
                path = (
                    evidence.get("artifact_path")
                    if evidence.get("kind") == "homebrew"
                    else evidence.get("path") if evidence.get("kind") == "mas" else None
                )
                if isinstance(path, str) and os.path.abspath(path) in by_path:
                    app = by_path[os.path.abspath(path)]
                    tagged = dict(
                        evidence,
                        source_key=source_key,
                        source_status=source["status"],
                        source_complete=source["complete"],
                    )
                    if tagged not in app["evidence"]:
                        app["evidence"].append(tagged)
    for item in sources["mas"]["items"]:
        if not isinstance(item, dict) or not item.get("bundle_id"):
            continue
        matches = [
            app for app in instances if app.get("bundle_id") == item["bundle_id"]
        ]
        if len(matches) == 1:
            evidence = {
                "kind": "mas",
                "store_id": item.get("store_id"),
                "bundle_id": item["bundle_id"],
                "path": matches[0]["path"],
                "source_key": "mas",
                "source_status": sources["mas"]["status"],
                "source_complete": sources["mas"]["complete"],
            }
            if evidence not in matches[0]["evidence"]:
                matches[0]["evidence"].append(evidence)
    # Retain identity-bound ownership claims until their own source completely
    # covers and disproves them. Incomplete evidence is never fresh authority.
    for app in instances:
        old = old_apps.get(app["path"])
        if not old or old["instance_id"] != app["instance_id"]:
            continue
        for evidence in old.get("evidence", []):
            if not isinstance(evidence, dict) or evidence.get("kind") not in (
                "homebrew",
                "mas",
            ):
                continue
            key = evidence.get("source_key")
            source = sources.get(key) if isinstance(key, str) else None
            if source and source["status"] == "ok" and source["complete"]:
                continue
            stale = copy.deepcopy(evidence)
            stale.update(
                freshness="stale",
                source_status=source["status"] if source else "unavailable",
                source_complete=False,
            )
            if not any(
                all(
                    current.get(k) == stale.get(k)
                    for k in (
                        "kind",
                        "source_key",
                        "token",
                        "prefix",
                        "artifact_path",
                        "store_id",
                        "bundle_id",
                    )
                )
                for current in app["evidence"]
            ):
                app["evidence"].append(stale)
    for path, old in old_apps.items():
        if path in seen_apps:
            continue
        covering = [
            s
            for k, s in sources.items()
            if k.startswith("filesystem:") and _inside(path, k[len("filesystem:") :])
        ]
        complete = any(s["status"] == "ok" and s["complete"] for s in covering)
        record = copy.deepcopy(old)
        record.update(
            presence="absent" if complete else "unobserved",
            freshness="fresh" if complete else "stale",
        )
        instances.append(record)
    for key, old in old_packages.items():
        if key in seen_packages:
            continue
        prefix = old["prefix"]
        source_kind = (
            "brew"
            if old["manager"] in ("homebrew", "brew", "brew_formula", "brew_cask")
            else "cli"
        )
        candidates = [sources.get(source_kind + ":" + prefix)]
        complete = old.get("installed_receipt") is not None and any(
            s and s["status"] == "ok" and s["complete"] for s in candidates
        )
        record = copy.deepcopy(old)
        record.update(
            presence="absent" if complete else "unobserved",
            freshness="fresh" if complete else "stale",
        )
        packages.append(record)
    return dict(
        schema_version=1,
        snapshot_id=str(uuid.uuid4()),
        profile_id=(previous or {}).get("profile_id", str(uuid.uuid4())),
        created_at=timestamp,
        generation=(previous or {}).get("generation", 0),
        previous_snapshot_id=(previous or {}).get("snapshot_id"),
        sources=sources,
        instances=instances,
        packages=packages,
    )


def reconcile_inventory(previous, snapshot):
    """Pure reconciliation for externally collected, typed local observations.

    Records from unknown coverage remain stale. Only a complete source covering
    the original root/prefix establishes absence. Display names never match IDs.
    """
    from inventory_model import validate_snapshot
    validate_snapshot(snapshot)
    result = copy.deepcopy(snapshot)
    if previous is None:
        return result
    validate_snapshot(previous)
    if (result['profile_id'] != previous['profile_id'] or result['generation'] != previous['generation']
            or result['previous_snapshot_id'] != previous['snapshot_id']):
        raise ValueError('profile or ancestry mismatch')
    sources = result['sources']
    old_apps = {x['path']: x for x in previous['instances']}
    paths = {x['path'] for x in result['instances']}
    for app in result['instances']:
        old = old_apps.get(app['path'])
        if old and old.get('bundle_id') and all(old.get(k) == app.get(k) for k in ('bundle_id', 'team_id', 'real_path', 'channel')):
            app['instance_id'] = old['instance_id']
    for path, old in old_apps.items():
        if path in paths:
            continue
        complete = any(key.startswith('filesystem:') and source['status'] == 'ok' and source['complete']
                       and any(_inside(path, covered) for covered in source['covered_roots'])
                       for key, source in sources.items())
        result['instances'].append(dict(copy.deepcopy(old), presence='absent' if complete else 'unobserved',
                                        freshness='fresh' if complete else 'stale'))
    def unique(records, key):
        groups = {}
        for record in records:
            value = key(record)
            if value is not None:
                groups.setdefault(value, []).append(record)
        return groups
    old_exact = unique(previous['packages'], _package_key)
    old_lineage = unique(previous['packages'], _receipt_lineage)
    current_lineage = unique(result['packages'], _receipt_lineage)
    used = set()
    for package in result['packages']:
        candidates = old_exact.get(_package_key(package), []) if (package.get('installed_receipt') or _file_identity(package['evidence'])) else []
        if len(candidates) != 1:
            lineage = _receipt_lineage(package)
            candidates = old_lineage.get(lineage, []) if lineage is not None and len(current_lineage.get(lineage, [])) == 1 else []
            if package['freshness'] != 'fresh' or package['presence'] != 'present':
                candidates = []
        if len(candidates) == 1:
            package['package_id'] = candidates[0]['package_id']
        used.add(package['package_id'])
    for old in previous['packages']:
        if old['package_id'] in used:
            continue
        kind = 'brew' if old['manager'] in ('homebrew', 'brew', 'brew_formula', 'brew_cask') else 'cli'
        source = sources.get(kind + ':' + old['prefix'])
        complete = bool(old.get('installed_receipt') is not None and source and source['status'] == 'ok' and source['complete'])
        result['packages'].append(dict(copy.deepcopy(old), presence='absent' if complete else 'unobserved',
                                       freshness='fresh' if complete else 'stale'))
    return validate_snapshot(result)
