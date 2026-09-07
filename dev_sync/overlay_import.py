"""Importable overlay plan/validate/commit helpers. Not a pipeline entrypoint."""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Iterable

_LIB_PYTHON = Path(__file__).resolve().parents[1] / "lib" / "python"
if str(_LIB_PYTHON) not in sys.path:
    sys.path.insert(0, str(_LIB_PYTHON))
from run_lock import LockError, acquire as acquire_run_lock, release as release_run_lock

from dev_sync_core import (
    DevSyncConfig,
    DevSyncError,
    RunOptions,
    expand_entries_to_files,
    lexists,
    resolve_under,
    safe_relpath,
    should_include_candidate,
    tracked_files,
    validate_no_newline_paths,
    validate_no_symlink_dest_ancestors,
)


class OverlayRecoveryError(DevSyncError):
    def __init__(self, message: str, recovery_path: Path | str):
        super().__init__(message)
        self.recovery_path = str(recovery_path)


@dataclass
class OverlayPlan:
    source: Path
    dest: Path
    files_to_copy: list[str] = field(default_factory=list)
    skipped_tracked: list[str] = field(default_factory=list)
    skipped_excluded: list[str] = field(default_factory=list)


def validate_source(source_base: Path, relpath: str | Path) -> Path:
    """Reject any source path whose resolved ancestors leave source_base."""
    rel = safe_relpath(relpath)
    base = source_base.resolve()
    current = source_base
    parts = Path(rel).parts
    for index, part in enumerate(parts):
        current = current / part
        if not os.path.lexists(current):
            raise DevSyncError(f"Source path vanished during validation: {rel}")
        if current.is_symlink():
            raw_target = Path(os.readlink(current))
            resolved = (
                raw_target.resolve()
                if raw_target.is_absolute()
                else (current.parent / raw_target).resolve()
            )
            try:
                resolved.relative_to(base)
            except ValueError as exc:
                raise DevSyncError(
                    f"Resolved path escapes base directory: {resolved}"
                ) from exc
            if index < len(parts) - 1:
                continue
    return resolve_under(source_base, rel)


def plan_overlay_import(
    repo_root: Path,
    source: Path,
    config: DevSyncConfig,
    entries: Iterable[str],
) -> OverlayPlan:
    expanded = expand_entries_to_files(source, entries, config)
    tracked = tracked_files(repo_root)
    files_to_copy: list[str] = []
    skipped_tracked: list[str] = []
    skipped_excluded: list[str] = []
    for rel in sorted(expanded):
        validate_source(source, rel)
        if rel in tracked:
            skipped_tracked.append(rel)
            continue
        if not should_include_candidate(rel, config):
            skipped_excluded.append(rel)
            continue
        path = source / rel
        if path.is_dir() and not path.is_symlink():
            raise DevSyncError(
                f"Directory overlay entries must be expanded to files before commit: {rel}"
            )
        files_to_copy.append(rel)
    return OverlayPlan(
        source=source,
        dest=repo_root,
        files_to_copy=files_to_copy,
        skipped_tracked=skipped_tracked,
        skipped_excluded=skipped_excluded,
    )


def compare_snapshots(before: dict[str, str], after: dict[str, str]) -> list[dict[str, str | None]]:
    changes: list[dict[str, str | None]] = []
    for key in sorted(set(before) | set(after)):
        old, new = before.get(key), after.get(key)
        if old != new:
            changes.append({"id": key, "before": old, "after": new})
    return changes


def _symlink_stays_in_dest(dest_base: Path, rel: str, link_target: str) -> None:
    if os.path.isabs(link_target):
        raise DevSyncError(f"Absolute overlay symlink is not allowed: {rel}")
    dest_link = dest_base / rel
    resolved = (dest_link.parent / link_target).resolve()
    try:
        resolved.relative_to(dest_base.resolve())
    except ValueError as exc:
        raise DevSyncError(
            f"Overlay symlink would escape destination: {rel} -> {link_target}"
        ) from exc


def _copy_leaf(source: Path, staging: Path, dest_base: Path, rel: str) -> None:
    staging.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        target = os.readlink(source)
        _symlink_stays_in_dest(dest_base, rel, target)
        os.symlink(target, staging)
        return
    if source.is_dir():
        raise DevSyncError(
            f"Directory overlay entries must be expanded to files before commit: {source}"
        )
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    fd = os.open(source, flags)
    with os.fdopen(fd, "rb") as handle, open(staging, "wb") as out:
        shutil.copyfileobj(handle, out)
    try:
        shutil.copystat(source, staging, follow_symlinks=False)
    except OSError:
        pass


def _write_journal(transaction_root: Path, payload: dict) -> None:
    journal = transaction_root / "JOURNAL.json"
    journal.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    try:
        journal.chmod(0o600)
    except OSError:
        pass


def _remove_path(path: Path) -> None:
    if not lexists(path):
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
        return
    path.unlink()


def commit_overlay(
    source_base: Path,
    dest_base: Path,
    relpaths: Iterable[str],
    logger,
    options: RunOptions,
) -> None:
    paths = sorted({safe_relpath(relpath) for relpath in relpaths})
    for rel in paths:
        logger.verbose(f"copy {source_base / rel} -> {dest_base / rel}")
        validate_source(source_base, rel)
    if options.dry_run or not paths:
        return

    path_set = set(paths)
    for rel in paths:
        parent = PurePosixPath(rel).parent
        while str(parent) not in ("", "."):
            if str(parent) in path_set:
                raise DevSyncError(f"Overlapping overlay paths are not allowed: {parent} and {rel}")
            parent = parent.parent

    dest_base.mkdir(parents=True, exist_ok=True)
    validate_no_newline_paths(paths)
    validate_no_symlink_dest_ancestors(dest_base, paths)
    try:
        acquire_run_lock(dest_base)
    except LockError as exc:
        raise DevSyncError(str(exc)) from exc
    try:
        _commit_overlay_locked(source_base, dest_base, paths, logger, options)
    finally:
        release_run_lock(dest_base)


def _commit_overlay_locked(source_base, dest_base, paths, logger, options):
    transaction_root = Path(tempfile.mkdtemp(prefix=".dev-sync-txn-", dir=dest_base))
    incoming_root = transaction_root / "incoming"
    backup_root = transaction_root / "backup"
    installed: list[tuple[str, bool]] = []
    backed_up: list[str] = []
    _write_journal(transaction_root, {"status": "started", "paths": paths})

    try:
        for rel in paths:
            _copy_leaf(source_base / rel, incoming_root / rel, dest_base, rel)

        for rel in paths:
            staging = incoming_root / rel
            dest = dest_base / rel
            backup = backup_root / rel
            had_dest = lexists(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            if had_dest:
                backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(dest, backup)
                backed_up.append(rel)
                _write_journal(
                    transaction_root,
                    {
                        "status": "backed_up",
                        "backed_up": list(backed_up),
                        "installed": [item for item, _ in installed],
                    },
                )
            try:
                os.replace(staging, dest)
            except Exception as swap_error:
                if had_dest and lexists(backup) and not lexists(dest):
                    try:
                        os.replace(backup, dest)
                        backed_up.remove(rel)
                    except Exception as restore_error:
                        raise OverlayRecoveryError(
                            "Overlay import failed and rollback was incomplete. "
                            f"Recovery data remains at {transaction_root}: {rel}: {restore_error}",
                            recovery_path=transaction_root,
                        ) from restore_error
                raise swap_error
            installed.append((rel, had_dest))
            _write_journal(
                transaction_root,
                {
                    "status": "installed",
                    "backed_up": list(backed_up),
                    "installed": [item for item, _ in installed],
                },
            )
    except OverlayRecoveryError:
        raise
    except Exception as error:
        rollback_errors: list[str] = []
        for rel, had_dest in reversed(installed):
            dest = dest_base / rel
            backup = backup_root / rel
            try:
                _remove_path(dest)
                if had_dest and lexists(backup):
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(backup, dest)
                    if rel in backed_up:
                        backed_up.remove(rel)
            except Exception as rollback_error:
                rollback_errors.append(f"{rel}: {rollback_error}")
        if rollback_errors or backed_up:
            raise OverlayRecoveryError(
                "Overlay import failed and rollback was incomplete. "
                f"Recovery data remains at {transaction_root}: "
                f"{'; '.join(rollback_errors) or 'unrestored backup'}",
                recovery_path=transaction_root,
            ) from error
        shutil.rmtree(transaction_root, ignore_errors=True)
        raise
    else:
        shutil.rmtree(transaction_root)


def recover_overlay_transaction(transaction_root: Path, dest_base: Path) -> None:
    """Best-effort restore from a leftover transaction directory."""
    backup_root = transaction_root / "backup"
    if not backup_root.exists():
        raise OverlayRecoveryError(
            f"No backup directory in {transaction_root}",
            recovery_path=transaction_root,
        )
    for backup in sorted(backup_root.rglob("*")):
        if not backup.is_file() and not backup.is_symlink():
            continue
        rel = backup.relative_to(backup_root).as_posix()
        dest = dest_base / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if lexists(dest):
            continue
        os.replace(backup, dest)
