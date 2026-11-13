"""Journalled replacement of an existing authorized application, never adoption.

Native observation is deliberately separate from filesystem operations so fixture
transactions exercise every real rename without touching host applications.
"""

import fcntl
import ctypes
import errno
import sys
import hashlib
import json
import os
import pathlib
import plistlib
import re
import shutil
import stat
import subprocess
import tempfile
import uuid


class TransactionDeferred(Exception):
    pass


def _require(condition, reason):
    if not condition:
        raise TransactionDeferred(reason)


def _canonical_existing(path):
    _require(
        isinstance(path, str) and os.path.isabs(path),
        "absolute_existing_target_required",
    )
    _require(os.path.isdir(path) and not os.path.islink(path), "removed_since_scan")
    _require(os.path.realpath(path) == os.path.normpath(path), "target_symlink")
    return path


def prepare_transaction(action, current):
    dest = _canonical_existing(action.get("target_path"))
    _require(
        action.get("action_scope") == "direct_update"
        and action.get("target", {}).get("kind") == "app"
        and bool(action.get("action_id")),
        "direct_action_required",
    )
    _require(
        current.get("path") == dest
        and current.get("presence") == "present"
        and current.get("freshness") == "fresh",
        "target_changed",
    )
    _require(current.get("running") is False, "running_or_unknown")
    _require(
        action.get("adapter_id") in ("github_dmg", "mozilla_dmg"),
        "artifact_adapter_unreviewed",
    )
    expected = action.get("expected_target", {})
    for field in ("bundle_id", "team_id", "channel"):
        _require(
            expected.get(field) not in (None, "", "unknown")
            and current.get(field) == expected[field],
            "identity_changed",
        )
    # Policy authorization additionally compares canonical identity/source
    # fingerprints, receipt evidence, profile, generation and decision expiry.
    return {
        "schema_version": 1,
        "transaction_id": str(uuid.uuid4()),
        "action_id": action["action_id"],
        "target": action["target"],
        "destination": dest,
        "state": "prepared",
        "expected_identity": {
            k: expected[k] for k in ("bundle_id", "team_id", "channel")
        },
    }


def _version(value):
    _require(
        isinstance(value, str) and bool(re.fullmatch(r"[0-9]+(?:\.[0-9]+)*", value)),
        "version_unknown",
    )
    return tuple(int(v) for v in value.split("."))


def _version_cmp(left, right):
    l, r = _version(left), _version(right)
    length = max(len(l), len(r))
    return (l + (0,) * (length - len(l))) > (r + (0,) * (length - len(r)))


def _replacement(candidate, previous):
    _require(
        candidate.get("good") is True and previous.get("good") is True,
        "signature_unknown_or_rejected",
    )
    _require(
        candidate.get("receipt_present") is False
        and previous.get("receipt_present") is False,
        "receipt_source_changed",
    )
    for field in ("bundle_id", "team_id"):
        _require(
            bool(previous.get(field)) and candidate.get(field) == previous[field],
            "replacement_identity_changed",
        )
    _require("arm64" in candidate.get("architectures", []), "architecture_unsupported")
    _require(
        not _version_cmp(candidate.get("minimum_os"), candidate.get("host_os")),
        "minimum_os_unsupported",
    )
    _require(
        _version_cmp(candidate.get("version"), previous.get("version")),
        "version_not_newer",
    )


def _rename_exclusive(source, destination):
    # A user recreating the destination between our observation and the rename
    # must never be overwritten. Both supported kernels offer no-replace rename.
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        call = libc.renamex_np
        call.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        result = call(os.fsencode(source), os.fsencode(destination), 4)  # RENAME_EXCL
    elif hasattr(libc, "renameat2"):
        call = libc.renameat2
        call.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        result = call(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    else:
        raise TransactionDeferred("exclusive_rename_unavailable")
    if result:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def _write(path, journal):
    fd, tmp = tempfile.mkstemp(prefix=".journal-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump(journal, stream, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
        _sync_dir(os.path.dirname(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _private_directory(path):
    st = os.lstat(path)
    _require(
        stat.S_ISDIR(st.st_mode)
        and st.st_uid == os.getuid()
        and stat.S_IMODE(st.st_mode) == 0o700
        and os.path.realpath(path) == path,
        "unsafe_journal_directory",
    )


def _allowed(dest, roots):
    _require(os.path.isabs(dest) and dest == os.path.realpath(dest), "target_symlink")
    _require(
        any(os.path.dirname(dest) == os.path.realpath(root) for root in roots),
        "target_root_not_approved",
    )


def approved_roots():
    return ["/Applications", os.path.expanduser("~/Applications")]


def _validate_journal(journal, roots):
    _require(journal.get("schema_version") == 1, "invalid_journal")
    dest = journal.get("destination", "")
    _allowed(dest, roots)
    parent = os.path.dirname(dest)
    for name in ("staging", "backup"):
        value = journal.get(name, "")
        _require(
            isinstance(value, str)
            and os.path.isabs(value)
            and os.path.basename(value) == os.path.basename(dest),
            "invalid_journal_paths",
        )
        root = os.path.dirname(value)
        _require(
            os.path.dirname(root) == parent
            and os.path.basename(root).startswith(".macupd-"),
            "invalid_journal_paths",
        )
        _require(
            not os.path.islink(root) and not os.path.islink(value),
            "invalid_journal_paths",
        )
    return journal


def recover_transaction(journal, observed):
    """Select a conservative recovery from actual bundles, not journal phase."""
    dest = observed.get("destination", {})
    backup = observed.get("backup", {})
    if dest.get("good") is True:
        return dict(
            journal,
            state=(
                "verified"
                if dest.get("version") == journal.get("candidate_version")
                else "rolled_back"
            ),
            recovery_action="preserve",
        )
    if (
        dest.get("exists") is False
        and backup.get("good") is True
        and backup.get("running") is False
    ):
        return dict(journal, state="rolled_back", recovery_action="restore_backup")
    if (
        dest.get("good") is False
        and dest.get("exists") is True
        and dest.get("running") is False
        and backup.get("good") is True
        and backup.get("running") is False
    ):
        return dict(
            journal, state="rolled_back", recovery_action="quarantine_and_restore"
        )
    return dict(journal, state="recovery_required", recovery_action="preserve")


def recover_journal(path, observe, allowed_roots=None):
    _require(
        not os.path.islink(path) and os.path.getsize(path) <= 65536, "invalid_journal"
    )
    with open(path) as stream:
        journal = json.load(stream)
    _validate_journal(journal, allowed_roots or approved_roots())
    observed = {}
    for name, key in (
        ("destination", "destination"),
        ("backup", "backup"),
        ("staging", "staging"),
    ):
        value = journal[key]
        if os.path.lexists(value):
            record = dict(observe(value))
            record["exists"] = True
            identity = journal["expected_identity"]
            if any(
                record.get(k) != identity.get(k) for k in ("bundle_id", "team_id")
            ) or record.get("receipt_present") is not journal.get("receipt_present"):
                record["good"] = False
            observed[name] = record
        else:
            observed[name] = {"exists": False, "good": False, "running": False}
    result = recover_transaction(journal, observed)
    if result["recovery_action"] == "quarantine_and_restore":
        rejected = journal["staging"] + ".rejected-" + str(uuid.uuid4())
        _rename_exclusive(journal["destination"], rejected)
        result["rejected"] = rejected
    if result["recovery_action"] in ("restore_backup", "quarantine_and_restore"):
        # Never clobber an app recreated by the user after the observation.
        _require(
            not os.path.lexists(journal["destination"]), "recovery_destination_changed"
        )
        _rename_exclusive(journal["backup"], journal["destination"])
        _sync_dir(os.path.dirname(journal["destination"]))
    _write(path, result)
    return result


def execute_transaction(
    action,
    source,
    journal_dir,
    current,
    authorize,
    observe,
    allowed_roots=None,
    fault=None,
):
    roots = allowed_roots or approved_roots()
    dest = action.get("target_path", "")
    _allowed(dest, roots)
    _private_directory(journal_dir)
    # A lock covers both recovery and replacement for this exact destination.
    lock_path = os.path.join(
        journal_dir, hashlib.sha256(dest.encode()).hexdigest() + ".lock"
    )
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(lock_path, flags, 0o600)
    try:
        st = os.fstat(fd)
        _require(
            stat.S_ISREG(st.st_mode)
            and st.st_uid == os.getuid()
            and stat.S_IMODE(st.st_mode) == 0o600
            and st.st_nlink == 1,
            "unsafe_transaction_lock",
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise TransactionDeferred("transaction_in_progress")
        for path in pathlib.Path(journal_dir).glob("*.json"):
            _require(
                not path.is_symlink() and path.stat().st_size <= 65536,
                "invalid_journal",
            )
            with path.open() as stream:
                old = json.load(stream)
            if old.get("destination") == dest and old.get("state") not in (
                "verified",
                "rolled_back",
            ):
                recovered = recover_journal(str(path), observe, roots)
                _require(recovered["state"] != "recovery_required", "recovery_required")
        _require(authorize() is True, "authorization_deferred")
        journal = prepare_transaction(action, current())
        previous = observe(dest)
        _require(previous.get("running") is False, "running_or_unknown")
        candidate = observe(source)
        _replacement(candidate, previous)
        initial = os.stat(dest)
        parent = os.path.dirname(dest)
        staging_root = tempfile.mkdtemp(prefix=".macupd-stage-", dir=parent)
        backup_root = tempfile.mkdtemp(prefix=".macupd-backup-", dir=parent)
        staging = os.path.join(staging_root, os.path.basename(dest))
        backup = os.path.join(backup_root, os.path.basename(dest))
        journal.update(
            staging=staging,
            backup=backup,
            candidate_version=candidate["version"],
            previous_version=previous["version"],
            expected_source=action.get("expected_source"),
            receipt_present=previous["receipt_present"],
        )
        path = os.path.join(journal_dir, journal["transaction_id"] + ".json")
        journal["journal_path"] = path
        _write(path, journal)
        if fault:
            fault("journal_created", journal)
        # ditto preserves macOS bundle metadata; injectable pure filesystem copy
        # is used off macOS and does not change production verification rules.
        if sys_platform_darwin():
            subprocess.run(
                ["ditto", source, staging],
                check=True,
                timeout=300,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            shutil.copytree(source, staging, symlinks=True)
        _replacement(observe(staging), previous)
        if fault:
            fault("prepared", journal)
        _require(authorize() is True, "authorization_deferred")
        prepare_transaction(action, current())
        latest = observe(dest)
        _require(
            latest.get("running") is False and latest.get("good") is True,
            "running_or_unknown",
        )
        _require(
            all(
                latest.get(k) == previous.get(k)
                for k in ("bundle_id", "team_id", "version")
            ),
            "target_changed",
        )
        before_swap = os.stat(dest)
        _require(
            (initial.st_dev, initial.st_ino)
            == (before_swap.st_dev, before_swap.st_ino),
            "target_changed",
        )
        _rename_exclusive(dest, backup)
        _sync_dir(parent)
        if fault:
            fault("backup_renamed", journal)
        journal["state"] = "backed_up"
        _write(path, journal)
        if fault:
            fault("backed_up", journal)
        try:
            _require(not os.path.lexists(dest), "target_recreated")
            _rename_exclusive(staging, dest)
            _sync_dir(parent)
            if fault:
                fault("swap_renamed", journal)
            journal["state"] = "swapped"
            _write(path, journal)
            if fault:
                fault("swapped", journal)
            _replacement(observe(dest), previous)
            journal["state"] = "verified"
            _write(path, journal)
            if fault:
                fault("verified", journal)
            return journal
        except Exception:
            # Preserve both copies on failed verification. Restore only when
            # destination is absent; a present uncertain app needs review.
            recover_journal(path, observe, roots)
            raise
    finally:
        os.close(fd)


def sys_platform_darwin():
    import sys

    return sys.platform == "darwin"


def observe_bundle(path):
    result = {
        "good": None,
        "running": None,
        "exists": os.path.isdir(path),
        "receipt_present": None,
    }
    if not result["exists"]:
        return result
    try:
        result["receipt_present"] = os.path.lexists(
            os.path.join(path, "Contents", "_MASReceipt", "receipt")
        )
        with open(os.path.join(path, "Contents", "Info.plist"), "rb") as stream:
            info = plistlib.load(stream)

        def native(args):
            return subprocess.run(
                args,
                check=True,
                timeout=15,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

        native(["codesign", "--verify", "--deep", "--strict", path])
        native(["spctl", "--assess", "--type", "execute", path])
        signed = native(["codesign", "-dv", "--verbose=4", path]).stderr
        teams = re.findall(r"^TeamIdentifier=(.+)$", signed, re.M)
        identifiers = re.findall(r"^Identifier=(.+)$", signed, re.M)
        _require(
            len(teams) == 1
            and teams[0] not in ("", "not set")
            and identifiers == [info.get("CFBundleIdentifier")],
            "signature_identity_unknown",
        )
        bid = identifiers[0]
        _require(bool(re.fullmatch(r"[A-Za-z0-9._-]+", bid)), "invalid_bundle_id")
        executable = info.get("CFBundleExecutable")
        _require(
            isinstance(executable, str) and "/" not in executable, "invalid_executable"
        )
        arch = native(
            ["lipo", "-archs", os.path.join(path, "Contents", "MacOS", executable)]
        ).stdout.split()
        host = native(["sw_vers", "-productVersion"]).stdout.strip()
        running = native(
            [
                "osascript",
                "-e",
                "on run argv",
                "-e",
                "return application id (item 1 of argv) is running",
                "-e",
                "end run",
                "--",
                bid,
            ]
        ).stdout.strip()
        result.update(
            good=True,
            bundle_id=bid,
            team_id=teams[0],
            version=info.get("CFBundleShortVersionString"),
            architectures=arch,
            minimum_os=info.get("LSMinimumSystemVersion")
            or info.get("LSMinimumSystemVersionByArchitecture", {}).get("arm64"),
            host_os=host,
            running=(
                False if running == "false" else True if running == "true" else None
            ),
        )
    except (
        OSError,
        ValueError,
        subprocess.SubprocessError,
        TransactionDeferred,
        plistlib.InvalidFileException,
    ):
        pass
    return result


def recover_pending_transactions(
    state_dir=None, observe=None, allowed_roots=None, lock=None
):
    """Run before inventory collection, including targets absent after a crash.

    No new action is manufactured. Only existing authorized transaction journals
    can restore their retained, freshly verified backup. Uncertainty is returned
    explicitly and all copies remain available for manual recovery.
    """
    from inventory_store import _root

    if lock is None:
        from policy_runtime import TargetLock

        lock = TargetLock
    root = _root(state_dir)
    if root is None:
        return []
    directory = os.path.join(root, "transactions")
    if not os.path.lexists(directory):
        return []
    _private_directory(directory)
    observe = observe or observe_bundle
    results = []
    paths = list(pathlib.Path(directory).glob("*.json"))
    _require(len(paths) <= 10000, "transaction_journal_limit")
    for path in paths:
        try:
            _require(
                not path.is_symlink() and path.stat().st_size <= 65536,
                "invalid_journal",
            )
            with path.open() as stream:
                journal = json.load(stream)
            if journal.get("state") in ("verified", "rolled_back"):
                continue
            _validate_journal(journal, allowed_roots or approved_roots())
            with lock(journal["destination"], root):
                results.append(recover_journal(str(path), observe, allowed_roots))
        except (OSError, ValueError, TypeError, KeyError, TransactionDeferred):
            results.append(
                {
                    "state": "recovery_required",
                    "reason_code": "transaction_recovery_deferred",
                }
            )
    return results
