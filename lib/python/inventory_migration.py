"""Explicit, reversible local report migration with a recoverable multi-file journal.

The generation marker is written last. A crash before that commit marker rolls
back; a crash after it completes on recovery. Notes never authorize operations.
"""

import base64
import copy
import hashlib
import json
import os
import shutil
import stat
import uuid

from inventory_model import validate_snapshot
from inventory_render import render_inventory
from inventory_store import (
    StoreError,
    MAX_SNAPSHOT_BYTES,
    _root,
    _load,
    locked_state,
)

MAX_BYTES = MAX_SNAPSHOT_BYTES
MAX_JOURNAL = 128 * 1024 * 1024
JOURNAL = ".migration-journal.json"
FILES = ("inventory.json", "inventory-notes.json", "generation.json")


def _checkpoint(label):
    """Durable boundary, kept separate for fault-injection verification."""


def _sha(data):
    return hashlib.sha256(data).hexdigest() if data is not None else None


def _encode(data):
    return base64.b64encode(data).decode("ascii") if data is not None else None


def _decode(value):
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > MAX_BYTES * 2:
        raise StoreError("invalid encoded bytes")
    try:
        result = base64.b64decode(value, validate=True)
    except (ValueError, TypeError) as exc:
        raise StoreError("invalid encoded bytes") from exc
    if len(result) > MAX_BYTES:
        raise StoreError("data too large")
    return result


def _json(value):
    try:
        result = json.dumps(
            value, ensure_ascii=True, separators=(",", ":"), allow_nan=False
        ).encode()
    except (TypeError, ValueError, RecursionError) as exc:
        raise StoreError("invalid JSON value") from exc
    if len(result) > MAX_JOURNAL:
        raise StoreError("data too large")
    return result


def _parse(data):
    if not isinstance(data, bytes):
        raise StoreError("missing JSON data")
    try:
        return json.loads(data.decode("utf-8"))
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise StoreError("corrupt JSON") from exc


def _report_path(path):
    path = os.path.abspath(path)
    if path.startswith("/var/"):
        path = "/private" + path
    parent = os.path.dirname(path)
    for index in range(1, len(path.split(os.sep))):
        component = os.sep.join(path.split(os.sep)[: index + 1]) or os.sep
        if os.path.islink(component):
            raise StoreError("unsafe report ancestor")
    st = os.stat(parent)
    if (
        not stat.S_ISDIR(st.st_mode)
        or st.st_uid != os.getuid()
        or not st.st_mode & stat.S_IWUSR
    ):
        raise StoreError("unsafe report directory")
    return path


def _read(path, private=True, limit=MAX_BYTES):
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    if (
        not stat.S_ISREG(st.st_mode)
        or st.st_uid != os.getuid()
        or st.st_nlink != 1
        or (private and stat.S_IMODE(st.st_mode) != 0o600)
    ):
        raise StoreError("unsafe data file")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as file:
        current = os.fstat(file.fileno())
        if (current.st_ino, current.st_dev) != (st.st_ino, st.st_dev):
            raise StoreError("file changed during read")
        result = file.read(limit + 1)
    if len(result) > limit:
        raise StoreError("data too large")
    return result


def _atomic(path, data, expected, private=True):
    """Atomic single-file CAS. Parent and target are checked at replace time."""
    parent, name = os.path.split(path)
    if private:
        _root(parent)
    else:
        _report_path(path)
    directory = os.open(
        parent,
        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    temporary = ".migration-" + uuid.uuid4().hex
    try:
        if data is not None:
            fd = os.open(
                temporary,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0),
                0o600,
                dir_fd=directory,
            )
            with os.fdopen(fd, "wb") as file:
                file.write(data)
                file.flush()
                os.fsync(file.fileno())
        if (
            _sha(_read(path, private, MAX_JOURNAL if name == JOURNAL else MAX_BYTES))
            != expected
        ):
            raise StoreError("compare-and-swap conflict")
        opened, current = os.fstat(directory), os.stat(parent, follow_symlinks=False)
        if (opened.st_ino, opened.st_dev) != (
            current.st_ino,
            current.st_dev,
        ) or stat.S_ISLNK(current.st_mode):
            raise StoreError("directory changed")
        if data is None:
            if expected is not None:
                os.unlink(name, dir_fd=directory)
        else:
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
        os.fsync(directory)
    finally:
        try:
            os.unlink(temporary, dir_fd=directory)
        except FileNotFoundError:
            pass
        os.close(directory)


def _notes(value):
    if (
        not isinstance(value, dict)
        or type(value.get("schema_version")) is not int
        or value["schema_version"] != 1
        or not isinstance(value.get("mapped"), list)
        or not isinstance(value.get("orphans"), list)
    ):
        raise StoreError("unknown notes schema")
    for note in value["mapped"] + value["orphans"]:
        if not isinstance(note, dict) or not isinstance(note.get("text"), str):
            raise StoreError("invalid note")
    return value


def prepare_migration(markdown, snapshot, notes=None):
    try:
        validate_snapshot(snapshot)
    except (ValueError, TypeError) as exc:
        raise StoreError("invalid snapshot") from exc
    original = markdown.encode("utf-8") if isinstance(markdown, str) else markdown
    if not isinstance(original, bytes) or len(original) > MAX_BYTES:
        raise StoreError("invalid report bytes")
    try:
        text = original.decode("utf-8")
    except UnicodeError as exc:
        raise StoreError("report is not UTF-8") from exc
    preserved = (
        copy.deepcopy(_notes(notes))
        if notes is not None
        else dict(schema_version=1, mapped=[], orphans=[])
    )
    if text and not any(item["text"] == text for item in preserved["orphans"]):
        preserved["orphans"].append(
            dict(
                text=text,
                reason="legacy_report_requires_review",
                original_sha256=_sha(original),
            )
        )
    return dict(
        schema_version=1,
        proposal_id=str(uuid.uuid4()),
        original_sha256=_sha(original),
        original_base64=_encode(original),
        snapshot=copy.deepcopy(snapshot),
        notes=preserved,
        summary=dict(
            instances=sum(x["presence"] == "present" for x in snapshot["instances"]),
            packages=sum(x["presence"] == "present" for x in snapshot["packages"]),
            orphan_notes=len(preserved["orphans"]),
            consents_created=0,
        ),
    )


def _validate_proposal(proposal):
    try:
        if (
            not isinstance(proposal, dict)
            or type(proposal.get("schema_version")) is not int
            or proposal["schema_version"] != 1
        ):
            raise ValueError("schema")
        uuid.UUID(proposal["proposal_id"])
        validate_snapshot(proposal["snapshot"])
        _notes(proposal["notes"])
        if _sha(_decode(proposal["original_base64"])) != proposal["original_sha256"]:
            raise ValueError("hash")
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        raise StoreError("invalid migration proposal") from exc


def _minimum_scan(snapshot):
    return any(
        key.startswith("filesystem:")
        and source["status"] == "ok"
        and source["complete"]
        and key[len("filesystem:") :] in source["covered_roots"]
        for key, source in snapshot["sources"].items()
    )


def _ancestry(current, snapshot):
    generation = current["generation"] if current else 0
    if snapshot["generation"] != generation:
        raise StoreError("generation mismatch")
    if current and (
        current["profile_id"] != snapshot["profile_id"]
        or current["snapshot_id"] != snapshot["previous_snapshot_id"]
    ):
        raise StoreError("profile or ancestry mismatch")
    if not current and snapshot["previous_snapshot_id"] is not None:
        raise StoreError("foreign snapshot")


def _validate_journal_side(side):
    """Never restore unvalidated bytes from a damaged or future-schema journal."""
    snapshot = None
    if side["inventory.json"] is not None:
        snapshot = _parse(side["inventory.json"])
        try:
            validate_snapshot(snapshot)
        except (ValueError, TypeError) as exc:
            raise StoreError("invalid journal snapshot") from exc
    if side["inventory-notes.json"] is not None:
        _notes(_parse(side["inventory-notes.json"]))
    if side["generation.json"] is not None:
        generation = _parse(side["generation.json"])
        if (
            not isinstance(generation, dict)
            or type(generation.get("schema_version")) is not int
            or generation["schema_version"] != 1
            or not snapshot
            or generation.get("generation") != snapshot["generation"]
            or generation.get("profile_id") != snapshot["profile_id"]
            or generation.get("snapshot_id") != snapshot["snapshot_id"]
            or not isinstance(generation.get("report_sha256"), str)
        ):
            raise StoreError("invalid journal generation")
    return snapshot


def _recover(root, report):
    if os.path.commonpath((root, report)) == root:
        raise StoreError("report must remain outside private state")
    path = os.path.join(root, JOURNAL)
    raw = _read(path, limit=MAX_JOURNAL)
    if raw is None:
        return False
    journal = _parse(raw)
    if (
        not isinstance(journal, dict)
        or type(journal.get("schema_version")) is not int
        or journal["schema_version"] != 1
        or journal.get("report_path") != report
        or not isinstance(journal.get("before"), dict)
        or not isinstance(journal.get("after"), dict)
        or set(journal["before"]) != set(FILES + ("report",))
        or set(journal["after"]) != set(FILES + ("report",))
    ):
        raise StoreError("invalid recovery journal")
    before = {name: _decode(value) for name, value in journal["before"].items()}
    after = {name: _decode(value) for name, value in journal["after"].items()}
    previous = _validate_journal_side(before)
    following = _validate_journal_side(after)
    if (
        following is None
        or after["generation.json"] is None
        or after["inventory-notes.json"] is None
    ):
        raise StoreError("incomplete journal generation")
    _ancestry(previous, dict(following, generation=following["generation"] - 1))
    if _parse(after["generation.json"])["report_sha256"] != _sha(after["report"]):
        raise StoreError("journal report hash mismatch")
    marker = _read(os.path.join(root, "generation.json"))
    committed = marker == after["generation.json"]
    conflict = False
    # A last-written generation marker completes only if all files agree.
    if committed:
        for name in FILES + ("report",):
            dest = report if name == "report" else os.path.join(root, name)
            if _read(dest, private=name != "report") != after[name]:
                committed = False
                break
    if not committed:
        # Validate everything first, so corrupt state never causes a partial rollback.
        for name in FILES:
            if _read(os.path.join(root, name)) not in (before[name], after[name]):
                raise StoreError("recovery state conflict")
        for name in FILES + ("report",):
            dest = report if name == "report" else os.path.join(root, name)
            current = _read(dest, private=name != "report")
            if current == before[name]:
                continue
            if current != after[name]:
                conflict = True  # Human report edits are preserved byte-for-byte.
                continue
            _atomic(dest, before[name], _sha(current), private=name != "report")
    _atomic(path, None, _sha(raw))
    if conflict:
        raise StoreError("report edited during recovery; notes import required")
    return committed


def recover_migration(state_dir, report_path):
    report = _report_path(report_path)
    with locked_state(state_dir) as root:
        return _recover(root, report)


def _commit(proposal, state_dir, report_path, migration, locale, recipes=None):
    _validate_proposal(proposal)
    report = _report_path(report_path)
    with locked_state(state_dir) as root:
        _recover(root, report)
        current = _load(root)
        snapshot = proposal["snapshot"]
        _ancestry(current, snapshot)
        if migration and not _minimum_scan(snapshot):
            raise StoreError("minimum local scan incomplete")
        original = _read(report, private=False)
        expected = proposal["original_sha256"]
        # An absent fresh report is distinct from an existing empty report.
        if _sha(original) != expected:
            raise StoreError("report changed since preview")
        if original is not None and not os.stat(report).st_mode & stat.S_IWUSR:
            raise StoreError("report not writable")
        before = {name: _read(os.path.join(root, name)) for name in FILES}
        policy = _read(os.path.join(root, "policy.json"))
        if policy is not None:
            value = _parse(policy)
            if (
                not isinstance(value, dict)
                or type(value.get("schema_version")) is not int
                or value["schema_version"] != 1
            ):
                raise StoreError("unknown policy schema")
        # Existing notes and marker are validated before a single durable write.
        if before["inventory-notes.json"] is not None:
            _notes(_parse(before["inventory-notes.json"]))
        if before["generation.json"] is not None:
            marker = _parse(before["generation.json"])
            if (
                not isinstance(marker, dict)
                or marker.get("schema_version") != 1
                or not current
                or marker.get("profile_id") != current["profile_id"]
                or marker.get("generation") != current["generation"]
                or marker.get("snapshot_id") != current["snapshot_id"]
            ):
                raise StoreError("generation marker mismatch")
        saved = copy.deepcopy(snapshot)
        saved["generation"] += 1
        rendered = render_inventory(saved, proposal["notes"], locale, recipes).encode(
            "utf-8"
        )
        if len(rendered) > MAX_BYTES:
            raise StoreError("report too large")
        after = {
            "inventory.json": _json(saved),
            "inventory-notes.json": _json(proposal["notes"]),
            "generation.json": _json(
                dict(
                    schema_version=1,
                    generation=saved["generation"],
                    profile_id=saved["profile_id"],
                    snapshot_id=saved["snapshot_id"],
                    report_sha256=_sha(rendered),
                )
            ),
            "report": rendered,
        }
        if any(len(data) > MAX_BYTES for data in after.values()):
            raise StoreError("state too large")
        before["report"] = original
        journal = _json(
            dict(
                schema_version=1,
                report_path=report,
                before={name: _encode(data) for name, data in before.items()},
                after={name: _encode(data) for name, data in after.items()},
            )
        )
        required = (
            2
            * (
                len(journal)
                + sum(len(data) for data in after.values())
                + len(original or b"")
            )
            + 1024 * 1024
        )
        if (
            min(
                shutil.disk_usage(root).free,
                shutil.disk_usage(os.path.dirname(report)).free,
            )
            < required
        ):
            raise StoreError("insufficient space")
        if migration and len(_json(proposal)) > MAX_BYTES:
            raise StoreError("proposal too large")
        if migration:
            archive = _root(os.path.join(root, "migration"), True)
            backup_path = os.path.join(archive, proposal["proposal_id"] + ".original")
            proposal_path = os.path.join(archive, proposal["proposal_id"] + ".json")
            for dest, content, label in (
                (backup_path, original, "backup"),
                (proposal_path, _json(proposal), "proposal"),
            ):
                existing = _read(dest)
                if existing is not None and existing != content:
                    raise StoreError("migration archive conflict")
                if existing is None and content is not None:
                    _atomic(dest, content, None)
                _checkpoint(label)
        path = os.path.join(root, JOURNAL)
        _atomic(path, journal, None)
        try:
            _checkpoint("journal")
            for name in (
                "inventory.json",
                "inventory-notes.json",
                "report",
                "generation.json",
            ):
                dest = report if name == "report" else os.path.join(root, name)
                if name == "report":
                    _checkpoint("before_report_replace")
                _atomic(dest, after[name], _sha(before[name]), private=name != "report")
                _checkpoint("committed" if name == "generation.json" else name)
            _atomic(path, None, _sha(journal))
        except (OSError, StoreError):
            _recover(root, report)
            raise
        return saved


def commit_migration(proposal, state_dir, report_path, locale="en", recipes=None):
    return _commit(proposal, state_dir, report_path, True, locale, recipes)


def rebuild_inventory(snapshot, state_dir, report_path, locale="en", recipes=None):
    """Regenerate from a fresh collection, preserving notes and identity-bound policy.

    Legacy or manually edited reports require the separate preview/accept path.
    A partial later scan can retain stale membership; initial activation requires
    at least one complete local filesystem source.
    """
    report = _report_path(report_path)
    with locked_state(state_dir) as root:
        _recover(root, report)
        original = _read(report, private=False)
        raw_notes = _read(os.path.join(root, "inventory-notes.json"))
        raw_marker = _read(os.path.join(root, "generation.json"))
        if original is not None:
            if raw_marker is None:
                raise StoreError(
                    "legacy report requires migration preview and acceptance"
                )
            marker = _parse(raw_marker)
            if (
                not isinstance(marker, dict)
                or marker.get("schema_version") != 1
                or marker.get("report_sha256") != _sha(original)
            ):
                raise StoreError("report edited; notes import preview required")
        if raw_marker is None and not _minimum_scan(snapshot):
            raise StoreError("minimum local scan incomplete")
        notes = (
            _notes(_parse(raw_notes))
            if raw_notes is not None
            else dict(schema_version=1, mapped=[], orphans=[])
        )
    # _commit rechecks the current generation and report hash under the same lock.
    proposal = prepare_migration(original or b"", snapshot, notes)
    proposal["notes"] = notes
    if original is None:
        proposal["original_base64"] = None
        proposal["original_sha256"] = None
    return _commit(proposal, state_dir, report, False, locale, recipes)


def preview_migration(snapshot, state_dir, report_path):
    """Persist a private review proposal, leaving the report and inventory intact."""
    report = _report_path(report_path)
    with locked_state(state_dir) as root:
        _recover(root, report)
        _ancestry(_load(root), snapshot)
        original = _read(report, private=False)
        raw_notes = _read(os.path.join(root, "inventory-notes.json"))
        notes = _notes(_parse(raw_notes)) if raw_notes is not None else None
        proposal = prepare_migration(original or b"", snapshot, notes)
        if original is None:
            proposal.update(original_sha256=None, original_base64=None)
        archive = _root(os.path.join(root, "migration"), True)
        path = os.path.join(archive, "pending.json")
        content = _json(proposal)
        if len(content) > MAX_BYTES:
            raise StoreError("proposal too large")
        _atomic(path, content, _sha(_read(path)))
        return proposal


def collect_current_snapshot(script_dir, state_dir=None, env=None, roots=None):
    """Shared read-only local collection with explicit test/profile environment."""
    from inventory_collect import Providers, collect_snapshot, read_bundle_static
    from inventory_providers import read_cli_manifests, read_mas, discover_cli_prefixes
    from brew_casks import installed_inventory_source
    from inventory_store import load_snapshot

    env = os.environ if env is None else env
    home = env.get("HOME") or os.path.expanduser("~")
    state_dir = (
        state_dir
        or env.get("MAC_UPDATE_STATE_DIR")
        or os.path.join(
            env.get("XDG_STATE_HOME") or os.path.join(home, ".local/state"),
            "mac-update",
        )
    )
    if roots is None:
        override = env.get("MAC_UPDATE_APP_DIRS")
        roots = (
            override.split(os.pathsep)
            if override
            else [
                "/Applications",
                os.path.join(home, "Applications"),
                "/System/Applications",
            ]
        )
    roots = list(dict.fromkeys(x for x in roots if x))
    prefixes = [
        x
        for x in env.get("MAC_UPDATE_BREW_PREFIXES", "/opt/homebrew:/usr/local").split(
            os.pathsep
        )
        if x
    ]
    cli = discover_cli_prefixes(home, env)
    if not roots or len(roots) > 32 or len(prefixes) > 32 or len(cli) > 64:
        raise StoreError("invalid roots or prefixes")
    providers = Providers(
        read_bundle=read_bundle_static,
        list_mas=read_mas,
        list_brew=installed_inventory_source,
        list_cli=read_cli_manifests,
        brew_prefixes=prefixes,
        cli_prefixes=cli,
    )
    return collect_snapshot(roots, providers, load_snapshot(state_dir))


def collect_local_snapshot(script_dir, roots=None):
    return collect_current_snapshot(script_dir, roots=roots)


def builder_main(script_dir, argv):
    import argparse
    from inventory_store import default_root

    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuild", action="store_true")
    parser.add_argument("--migration", action="store_true")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--accept")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", action="append")
    parser.add_argument("-y", "--yes", action="store_true")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1
    root = default_root()
    report = os.environ.get("MAC_UPDATE_REPORT_PATH") or os.path.join(
        script_dir, "APPLICATIONS.md"
    )
    locale = os.environ.get("MAC_UPDATE_LANG") or os.environ.get("MAC_LANG", "en")

    def message(key, fallback):
        print(os.environ.get(key, fallback))

    try:
        if args.preview or args.accept:
            if not args.migration or (args.preview and args.accept):
                raise StoreError("migration mode required")
        if args.migration and not (args.preview or args.accept):
            raise StoreError("preview or acceptance required")
        if args.accept and (args.yes or os.environ.get("MAC_UPDATE_YES") == "1"):
            message(
                "L_INVENTORY_NO_AUTO_MIGRATION",
                "Automatic acceptance cannot migrate inventory. Review the proposal and accept it explicitly.",
            )
            return 10
        from app_recipes import load_recipes

        recipes = load_recipes(os.path.join(script_dir, "config/app_recipes.json"))
        if args.accept:
            # Recovery runs before reading a pending proposal so interrupted commits
            # never become a foreign/stale generation by accident.
            recover_migration(root, report)
            with locked_state(root) as safe_root:
                archive = _root(os.path.join(safe_root, "migration"))
                if archive is None:
                    raise StoreError("no migration preview")
                proposal = _parse(_read(os.path.join(archive, "pending.json")))
            _validate_proposal(proposal)
            if proposal["proposal_id"] != args.accept:
                raise StoreError("proposal ID mismatch")
            if args.dry_run:
                message(
                    "L_INVENTORY_DRY_RUN", "Inventory preview only. No files changed."
                )
                return 0
            commit_migration(proposal, root, report, locale, recipes)
            message(
                "L_INVENTORY_SAVED",
                "Local inventory saved. Notes and existing policy choices retained.",
            )
            return 0
        # Dry-run never creates a root, lock, backup or pending proposal.
        if not args.dry_run:
            recover_migration(root, report)
        snapshot = collect_local_snapshot(script_dir, args.root)
        if args.dry_run:
            summary = dict(
                mode="preview",
                instances=len(snapshot["instances"]),
                packages=len(snapshot["packages"]),
                changed=False,
            )
            if args.json:
                print(json.dumps(summary))
            else:
                message(
                    "L_INVENTORY_DRY_RUN", "Inventory preview only. No files changed."
                )
            return 0
        if args.preview:
            proposal = preview_migration(snapshot, root, report)
            message(
                "L_INVENTORY_MIGRATION_PREVIEW",
                "Migration preview ready. Original bytes are retained; all legacy text stays in orphan notes. No update permission is inferred.",
            )
            print(
                json.dumps(
                    dict(
                        proposal_id=proposal["proposal_id"],
                        original_sha256=proposal["original_sha256"],
                        summary=proposal["summary"],
                    )
                )
            )
            message(
                "L_INVENTORY_MIGRATION_ACCEPT",
                "To accept this preview: bash build_inventory.sh --migration --accept PROPOSAL_ID",
            )
            return 0
        rebuild_inventory(snapshot, root, report, locale, recipes)
        message(
            "L_INVENTORY_SAVED",
            "Local inventory saved. Notes and existing policy choices retained.",
        )
        return 0
    except (StoreError, OSError, ValueError, TypeError):
        message(
            "L_INVENTORY_CONFLICT",
            "Inventory unchanged. A complete local scan or an explicit notes migration preview may be required. Run build_inventory.sh --migration --preview.",
        )
        return 10
