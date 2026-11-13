"""Bounded, observational providers for the stage B shadow inventory.

Homebrew and npm are read from installed metadata. Ruby casks, package scripts
and discovered executables are never evaluated. No vendor URL is fetched.
"""

from __future__ import annotations

import datetime
import json
import os
import stat
import subprocess
from pathlib import Path

MAX_BYTES = 1024 * 1024
MAX_ENTRIES = 4096


def _result(items=None, status="ok", roots=None, reason=None):
    return dict(
        schema_version=1,
        status=status,
        items=items or [],
        observed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        covered_roots=roots or [],
        complete=status == "ok",
        reason_code=reason,
    )


def _regular_json(path, boundary):
    path, boundary = Path(path), Path(boundary)
    # Check every metadata component, not only the final file.
    current = path
    while current != boundary:
        if current.parent == current or current.is_symlink():
            raise ValueError("unsafe_metadata_path")
        current = current.parent
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_BYTES:
            raise ValueError("invalid_metadata_file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("metadata_too_large")
        value = json.loads(data)
        if not isinstance(value, dict):
            raise ValueError("invalid_metadata_object")
        return value
    finally:
        os.close(fd)


def _entries(path, budget=None):
    if path.is_symlink():
        raise ValueError("linked_metadata_directory")
    with os.scandir(path) as iterator:
        entries = []
        for entry in iterator:
            if budget is not None:
                if budget[0] <= 0:
                    raise ValueError("scan_budget")
                budget[0] -= 1
            entries.append(Path(entry.path))
            if len(entries) > MAX_ENTRIES:
                raise ValueError("record_limit")
    return sorted(entries)


def _text(value):
    return value if isinstance(value, str) and value and len(value) <= 4096 else None


def read_brew_receipts(prefix):
    """Installed cask JSON plus actual staging links, and Cellar receipts.

    The shared brew_casks module and lib/brew.sh expose this provider as well.
    Missing/ambiguous metadata never manufactures /Applications ownership.
    """
    root = Path(os.path.realpath(prefix))
    rooms = [root / "Caskroom", root / "Cellar"]
    if not any(p.exists() or p.is_symlink() for p in rooms):
        return _result(
            status="unavailable", roots=[str(root)], reason="manager_metadata_missing"
        )
    items, partial = [], False
    budget = [MAX_ENTRIES]
    for room in rooms:
        if not room.exists() and not room.is_symlink():
            continue
        try:
            tokens = _entries(room, budget)
        except (OSError, ValueError):
            partial = True
            continue
        for token_dir in tokens:
            try:
                if token_dir.is_symlink() or not token_dir.is_dir():
                    raise ValueError("invalid_manager_directory")
                token = token_dir.name
                if room.name == "Cellar":
                    for version_dir in _entries(token_dir, budget):
                        receipt = version_dir / "INSTALL_RECEIPT.json"
                        data = _regular_json(receipt, root)
                        explicit = data.get("installed_on_request")
                        items.append(
                            dict(
                                name=token,
                                manager="homebrew",
                                version=version_dir.name,
                                installed_receipt=str(receipt),
                                explicitly_installed=(
                                    explicit if isinstance(explicit, bool) else None
                                ),
                                source_identity="formula:" + token,
                                channel="unknown",
                                evidence=[
                                    dict(
                                        kind="homebrew",
                                        token=token,
                                        prefix=str(root),
                                        artifact_path=None,
                                        installed_receipt=str(receipt),
                                    )
                                ],
                            )
                        )
                else:
                    candidates = []
                    for version_dir in _entries(token_dir / ".metadata", budget):
                        if not version_dir.is_dir() or version_dir.is_symlink():
                            continue
                        for timestamp_dir in _entries(version_dir, budget):
                            if (
                                timestamp_dir.is_dir()
                                and not timestamp_dir.is_symlink()
                            ):
                                candidates.append(
                                    (
                                        timestamp_dir.name,
                                        version_dir.name,
                                        timestamp_dir / "Casks" / (token + ".json"),
                                    )
                                )
                    if not candidates:
                        raise ValueError("cask_metadata_missing")
                    _, version, receipt = max(candidates)
                    data = _regular_json(receipt, root)
                    if data.get("token") != token or not isinstance(
                        data.get("artifacts"), list
                    ):
                        raise ValueError("cask_metadata_invalid")
                    evidence = []
                    unresolved = False
                    for artifact in data["artifacts"]:
                        if not isinstance(artifact, dict):
                            unresolved = True
                            continue
                        app = artifact.get("app")
                        if app is None:
                            # pkg/binary/installer effects are deliberately not guessed.
                            unresolved = True
                            continue
                        if isinstance(app, str):
                            app = [app]
                        source = app[0] if isinstance(app, list) and app else None
                        if (
                            not isinstance(source, str)
                            or os.path.isabs(source)
                            or ".." in Path(source).parts
                            or not source.endswith(".app")
                        ):
                            unresolved = True
                            continue
                        staged = token_dir / version / source
                        # Parent directories must remain within this installed cask.
                        if os.path.commonpath(
                            [str(staged.parent.resolve()), str(token_dir)]
                        ) != str(token_dir):
                            unresolved = True
                            continue
                        if not staged.is_symlink():
                            unresolved = True
                            continue
                        target = os.readlink(staged)
                        if not os.path.isabs(target):
                            target = os.path.join(str(staged.parent), target)
                        target = os.path.normpath(target)
                        evidence.append(
                            dict(
                                kind="homebrew",
                                token=token,
                                prefix=str(root),
                                artifact_path=target,
                                installed_receipt=str(receipt),
                            )
                        )
                    if not evidence:
                        evidence = [
                            dict(
                                kind="homebrew",
                                token=token,
                                prefix=str(root),
                                artifact_path=None,
                                installed_receipt=str(receipt),
                            )
                        ]
                    partial = partial or unresolved
                    items.append(
                        dict(
                            name=token,
                            manager="homebrew",
                            version=version,
                            installed_receipt=str(receipt),
                            explicitly_installed=None,
                            source_identity="cask:" + token,
                            channel="unknown",
                            evidence=evidence,
                        )
                    )
                if len(items) > MAX_ENTRIES:
                    return _result(
                        items[:MAX_ENTRIES], "partial", [str(root)], "record_limit"
                    )
            except (OSError, ValueError, TypeError):
                partial = True
    return _result(
        items,
        "partial" if partial else "ok",
        [str(root)],
        "manager_metadata_incomplete" if partial else None,
    )


def read_cli_manifests(prefix):
    root = Path(os.path.realpath(prefix))
    modules = root / "lib/node_modules"
    items, partial = [], False
    budget = [MAX_ENTRIES]
    try:
        candidates = []
        if modules.exists() or modules.is_symlink():
            for entry in _entries(modules, budget):
                candidates.extend(
                    _entries(entry, budget) if entry.name.startswith("@") else [entry]
                )
                if len(candidates) > MAX_ENTRIES:
                    raise ValueError("record_limit")
        for entry in candidates:
            try:
                path = entry / "package.json"
                data = _regular_json(path, root)
                name, version = _text(data.get("name")), _text(data.get("version"))
                expected = str(entry.relative_to(modules))
                if name != expected or version is None:
                    raise ValueError("invalid_package_identity")
                items.append(
                    dict(
                        name=name,
                        manager="npm",
                        version=version,
                        installed_receipt=str(path),
                        explicitly_installed=None,
                        source_identity=name,
                        channel="unknown",
                        evidence=[
                            dict(
                                kind="npm",
                                name=name,
                                prefix=str(root),
                                manifest_path=str(path),
                            )
                        ],
                    )
                )
            except (OSError, ValueError, TypeError):
                partial = True
        binary = root / "bin/node"
        # An unmanaged executable is observable but supplies no version or authority.
        if binary.exists() or binary.is_symlink():
            items.append(
                dict(
                    name="node",
                    manager="unknown",
                    version=None,
                    installed_receipt=None,
                    explicitly_installed=None,
                    source_identity="node",
                    channel="unknown",
                    evidence=[dict(kind="file_metadata", path=str(binary))],
                )
            )
    except (OSError, ValueError):
        partial = True
    if not root.exists():
        return _result(status="unavailable", roots=[str(root)], reason="prefix_missing")
    return _result(
        items,
        "partial" if partial else "ok",
        [str(root)],
        "package_metadata_incomplete" if partial else None,
    )


def read_mas(run=subprocess.run):
    try:
        result = run(
            ["mas", "list", "--json"],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
            timeout=10,
            check=False,
        )
        if result.returncode != 0:
            return _result(status="error", reason="manager_query_failed")
        raw = result.stdout.strip()
        if len(raw.encode("utf-8")) > MAX_BYTES:
            return _result(status="error", reason="metadata_too_large")
        rows = (
            json.loads(raw)
            if raw.startswith("[")
            else [json.loads(x) for x in raw.splitlines() if x.strip()]
        )
        if not isinstance(rows, list) or len(rows) > MAX_ENTRIES:
            raise ValueError("invalid_manager_response")
        items = []
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid_manager_response")
            identity = row.get("adamID") or row.get("id")
            if (
                not isinstance(identity, (str, int))
                or isinstance(identity, bool)
                or not str(identity).isdigit()
            ):
                raise ValueError("invalid_store_id")
            bundle = _text(row.get("bundleID") or row.get("bundleIdentifier"))
            items.append(
                dict(
                    store_id=str(identity),
                    bundle_id=bundle,
                    name=_text(row.get("name")),
                    version=_text(row.get("version")),
                    evidence=[
                        dict(kind="mas", store_id=str(identity), bundle_id=bundle)
                    ],
                )
            )
        return _result(items)
    except FileNotFoundError:
        return _result(status="unavailable", reason="manager_missing")
    except subprocess.TimeoutExpired:
        return _result(status="error", reason="manager_timeout")
    except (OSError, ValueError, TypeError):
        return _result(status="error", reason="manager_response_invalid")


def discover_cli_prefixes(home, env):
    if "MAC_UPDATE_CLI_PREFIXES" in env:
        return list(
            dict.fromkeys(
                os.path.realpath(x)
                for x in env["MAC_UPDATE_CLI_PREFIXES"].split(os.pathsep)
                if x
            )
        )
    roots = [
        str(Path(home) / ".local/share/mac-update/npm-global"),
        str(Path(home) / ".local/share/mac-update/node"),
        "/opt/homebrew",
        "/usr/local",
    ]
    nvm = Path(home) / ".nvm/versions/node"
    try:
        roots.extend(str(x) for x in _entries(nvm) if x.is_dir() and not x.is_symlink())
    except (OSError, ValueError):
        pass
    return list(dict.fromkeys(os.path.realpath(x) for x in roots))
