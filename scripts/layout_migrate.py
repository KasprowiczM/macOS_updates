#!/usr/bin/env python3
"""Bring user data from an older git-clone install into the config folder.

Explicit and reversible. Nothing here runs by itself.

    layout_migrate.py --preview            show what would be copied, change nothing
    layout_migrate.py --apply              copy it, with a backup and a manifest
    layout_migrate.py --undo MANIFEST      put everything back from the manifest

The original checkout is only ever read: it is never changed, renamed or deleted.

What is copied (always as copies, never moves):
    state  user_overrides.tsv         -> <config>/overrides.tsv
    clone  .mac_update_prefs          -> <config>/legacy/mac_update_prefs  (+ <config>/lang from MAC_LANG)
    clone  APPLICATIONS.md, UPDATES.md-> <config>/legacy/
    clone  config/*.txt that you edited, or added, compared with the shipped
           copy -> <config>/legacy/config/   (unchanged shipped files are skipped)

A destination that already exists with different content is a conflict: it is
left alone unless --overwrite is given, and then the old file is backed up first.
Every apply writes <state>/backups/layout-<timestamp>/manifest.json (sha256 of
each file) plus copies of anything it overwrote. Undo refuses to touch a file
that changed after the migration.

Exit codes: 0 done or nothing to do, 1 failed or refused, 2 bad usage.
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

_HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "lib", "python"))
import mu_paths  # noqa: E402

FORMAT = "mac-update-layout-migration"
LANGS = ("pl", "en", "es", "it", "pt", "de", "fr")
MAX_BYTES = 5 * 1024 * 1024


class MigrateError(Exception):
    """One sentence, ready to print."""


# ---------------------------------------------------------------- helpers

def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _atomic_write(dest, data=None, src=None, mode=0o600):
    """Write dest via a temp file in the same folder and an atomic rename."""
    folder = os.path.dirname(dest)
    fd, tmp = tempfile.mkstemp(prefix=".migrate-", dir=folder)
    try:
        with os.fdopen(fd, "wb") as out:
            if src is not None:
                with open(src, "rb") as handle:
                    shutil.copyfileobj(handle, out)
            else:
                out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, dest)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _write_json(path, value):
    _atomic_write(path, data=(json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8"))


def _is_clone(path):
    return bool(path) and os.path.isdir(path) and os.path.exists(os.path.join(path, ".git")) \
        and os.path.isfile(os.path.join(path, "update_all.sh")) and os.path.isfile(os.path.join(path, "VERSION"))


def _version_of(path):
    try:
        with open(os.path.join(path, "VERSION")) as handle:
            return handle.read().strip() or "unknown"
    except OSError:
        return "unknown"


def _now():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def _inside(path, parent):
    return path == parent or path.startswith(parent.rstrip("/") + "/")


def find_source(explicit, env):
    candidates = []
    if explicit:
        candidates.append(explicit)
    elif env.get("MAC_UPDATE_LEGACY_DIR"):
        candidates.append(env["MAC_UPDATE_LEGACY_DIR"])
    else:
        root = mu_paths.toolkit_root()
        if os.path.exists(os.path.join(root, ".git")):
            candidates.append(root)
        candidates.append(os.path.join(env.get("HOME", ""), "Dev_Env", "macOS_updates"))
    for candidate in candidates:
        if _is_clone(candidate):
            return os.path.realpath(candidate)
    return None


def _git_usable():
    path = shutil.which("git")
    if not path:
        return False
    if path == "/usr/bin/git":
        # Apple's shim opens an installer dialog when the Command Line Tools are missing.
        try:
            done = subprocess.run(["xcode-select", "-p"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  stdin=subprocess.DEVNULL, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return False
        return done.returncode == 0
    return True


def _shipped_bytes(name, source, defaults_dir):
    """(known, bytes-or-None). None with known=True means no shipped copy exists."""
    if defaults_dir:
        path = os.path.join(defaults_dir, "config", name)
        if os.path.isfile(path) and not os.path.islink(path):
            with open(path, "rb") as handle:
                return True, handle.read()
        return True, None
    if not _git_usable():
        return False, None
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_TERMINAL_PROMPT="0")
    try:
        head = subprocess.run(["git", "-C", source, "rev-parse", "--verify", "HEAD"], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=15)
        if head.returncode != 0:
            return False, None
        blob = subprocess.run(["git", "-C", source, "show", "HEAD:config/" + name], env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False, None
    return True, (blob.stdout if blob.returncode == 0 else None)


# ---------------------------------------------------------------- planning

def build_plan(source, paths, defaults_dir=None, overwrite=False):
    """Return a list of entry dicts. action is one of
    copy, create, overwrite, same, conflict, skip."""
    config = paths["config"]
    entries = []

    def add(kind, src, rel, data=None, note=""):
        dest = os.path.join(config, rel)
        entry = {"kind": kind, "src": src, "dest": dest, "rel": rel, "note": note, "action": "copy",
                 "sha256_src": None, "sha256_before": None, "data": data}
        if data is not None:
            entry["sha256_src"] = _sha256_bytes(data)
            entry["action"] = "create"
        else:
            if os.path.islink(src):
                entry.update(action="skip", note="it is a link")
                entries.append(entry)
                return
            if not os.path.isfile(src):
                return
            if os.path.getsize(src) > MAX_BYTES:
                entry.update(action="skip", note="it is larger than 5 MB")
                entries.append(entry)
                return
            entry["sha256_src"] = _sha256(src)
        if os.path.islink(dest):
            entry.update(action="skip", note="the destination is a link")
        elif os.path.exists(dest):
            if not os.path.isfile(dest):
                entry.update(action="skip", note="the destination is not a file")
            else:
                entry["sha256_before"] = _sha256(dest)
                if entry["sha256_before"] == entry["sha256_src"]:
                    entry["action"] = "same"
                elif overwrite:
                    entry["action"] = "overwrite"
                else:
                    entry["action"] = "conflict"
        entries.append(entry)

    add("overrides", os.path.join(paths["state"], "user_overrides.tsv"), "overrides.tsv")

    prefs = os.path.join(source, ".mac_update_prefs")
    add("prefs", prefs, "legacy/mac_update_prefs")
    if os.path.isfile(prefs) and not os.path.islink(prefs):
        lang = None
        try:
            with open(prefs, encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    key, _, value = line.partition("=")
                    if key.strip() == "MAC_LANG":
                        lang = value.strip()
                        break
        except OSError:
            pass
        if lang in LANGS:
            add("lang", prefs, "lang", data=(lang + "\n").encode("utf-8"))

    add("applications", os.path.join(source, "APPLICATIONS.md"), "legacy/APPLICATIONS.md")
    add("updates", os.path.join(source, "UPDATES.md"), "legacy/UPDATES.md")

    cfg_dir = os.path.join(source, "config")
    names = sorted(n for n in os.listdir(cfg_dir) if n.endswith(".txt")) if os.path.isdir(cfg_dir) else []
    for name in names:
        src = os.path.join(cfg_dir, name)
        if os.path.islink(src) or not os.path.isfile(src):
            continue
        known, shipped = _shipped_bytes(name, source, defaults_dir)
        if not known:
            entries.append({"kind": "config", "src": src, "dest": os.path.join(config, "legacy/config", name),
                            "rel": "legacy/config/" + name, "action": "skip", "data": None,
                            "note": "it could not be compared with the shipped copy", "sha256_src": None,
                            "sha256_before": None})
            continue
        with open(src, "rb") as handle:
            mine = handle.read()
        if shipped is not None and mine == shipped:
            entries.append({"kind": "config", "src": src, "dest": os.path.join(config, "legacy/config", name),
                            "rel": "legacy/config/" + name, "action": "skip", "data": None,
                            "note": "it matches the shipped copy", "sha256_src": None, "sha256_before": None})
            continue
        add("config", src, "legacy/config/" + name,
            note="edited" if shipped is not None else "added by you")
    return entries


def _describe(entry):
    action = entry["action"]
    rel = entry["rel"]
    src = entry["kind"] if entry["src"] is None else os.path.basename(entry["src"])
    if action == "copy" or action == "create":
        return "copy      %s -> %s" % (src, rel)
    if action == "overwrite":
        return "replace   %s -> %s (the existing file is backed up first)" % (src, rel)
    if action == "same":
        return "same      %s is already in place" % rel
    if action == "conflict":
        return "differs   %s already exists with other content; it stays unless you add --overwrite" % rel
    return "skip      %s: %s" % (os.path.basename(entry["src"] or rel), entry.get("note", ""))


def _print_entries(plan, out, skip_actions=None):
    matched = 0
    for entry in plan:
        if skip_actions is not None and entry["action"] not in skip_actions:
            continue
        if entry["action"] == "skip" and entry.get("note") == "it matches the shipped copy":
            matched += 1
            continue
        print("  " + _describe(entry), file=out)
    if matched:
        print("  skip      %d config/*.txt file(s) match the shipped copy and are not needed" % matched, file=out)


# ---------------------------------------------------------------- commands

def cmd_preview(source, paths, args, out):
    plan = build_plan(source, paths, args.defaults, args.overwrite)
    print("Found a git-based install: %s (version %s)." % (source, _version_of(source)), file=out)
    print("Your settings folder is %s." % paths["config"], file=out)
    if not plan:
        print("There is no user data to bring over.", file=out)
        return 0
    _print_entries(plan, out)
    todo = [e for e in plan if e["action"] in ("copy", "create", "overwrite")]
    if todo:
        print("Nothing was changed. Run with --apply to copy these %d file(s); your original folder is never "
              "deleted and --undo puts everything back." % len(todo), file=out)
    else:
        print("Nothing would change.", file=out)
    return 0


def cmd_apply(source, paths, args, out):
    plan = build_plan(source, paths, args.defaults, args.overwrite)
    todo = [e for e in plan if e["action"] in ("copy", "create", "overwrite")]
    _print_entries(plan, out, skip_actions=("conflict", "skip"))
    if not todo:
        print("Nothing to do: everything is already in place.", file=out)
        return 0

    config_existed = os.path.isdir(paths["config"])
    state = mu_paths.ensure_dir("state")
    config = mu_paths.ensure_dir("config")
    stamp = _now()
    backup_dir = os.path.join(state, "backups", "layout-" + stamp)
    suffix = 0
    while os.path.exists(backup_dir):
        suffix += 1
        backup_dir = os.path.join(state, "backups", "layout-%s-%d" % (stamp, suffix))
    os.makedirs(os.path.join(backup_dir, "files"), mode=0o700)
    manifest_path = os.path.join(backup_dir, "manifest.json")

    created_dirs = []
    records = []
    for index, entry in enumerate(todo):
        record = {"kind": entry["kind"], "src": entry["src"], "dest": entry["dest"], "rel": entry["rel"],
                  "action": entry["action"], "sha256_src": entry["sha256_src"],
                  "sha256_before": entry["sha256_before"], "sha256_after": None, "backup": None}
        if entry["action"] == "overwrite":
            record["backup"] = "files/%d-%s" % (index, os.path.basename(entry["dest"]))
            shutil.copy2(entry["dest"], os.path.join(backup_dir, record["backup"]))
            if _sha256(os.path.join(backup_dir, record["backup"])) != entry["sha256_before"]:
                raise MigrateError("A backup copy did not verify, so nothing was changed.")
        records.append(record)
    manifest = {"format": FORMAT, "format_version": 1, "status": "in_progress", "created": stamp,
                "source": source, "config_dir": config, "state_dir": state,
                "toolkit_version": _version_of(mu_paths.toolkit_root()), "entries": records, "created_dirs": [],
                "config_created": not config_existed}
    _write_json(manifest_path, manifest)

    for entry, record in zip(todo, records):
        folder = os.path.dirname(entry["dest"])
        missing = []
        probe = folder
        while not os.path.isdir(probe) and probe != config:
            missing.append(probe)
            probe = os.path.dirname(probe)
        os.makedirs(folder, mode=0o700, exist_ok=True)
        created_dirs.extend(reversed(missing))
        if entry["data"] is not None:
            _atomic_write(entry["dest"], data=entry["data"])
        else:
            _atomic_write(entry["dest"], src=entry["src"])
        record["sha256_after"] = _sha256(entry["dest"])
        if record["sha256_after"] != entry["sha256_src"]:
            raise MigrateError("%s did not copy correctly; run --undo %s to put things back." % (entry["rel"], manifest_path))
        manifest["created_dirs"] = created_dirs
        _write_json(manifest_path, manifest)
    manifest["status"] = "applied"
    _write_json(manifest_path, manifest)
    print("Copied %d file(s) into %s." % (len(todo), config), file=out)
    print("Manifest and backups: %s" % backup_dir, file=out)
    print("To undo: mac-update migrate --undo %s" % manifest_path, file=out)
    print("Your original folder %s was not changed." % source, file=out)
    return 0


def _load_manifest(arg):
    path = arg
    if os.path.isdir(path):
        path = os.path.join(path, "manifest.json")
    try:
        with open(path, encoding="utf-8") as handle:
            manifest = json.load(handle)
    except (OSError, ValueError):
        raise MigrateError("The manifest %s cannot be read." % arg)
    if not isinstance(manifest, dict) or manifest.get("format") != FORMAT or not isinstance(manifest.get("entries"), list):
        raise MigrateError("%s is not a mac-update migration manifest." % arg)
    return os.path.realpath(path), manifest


def cmd_undo(arg, args, out):
    manifest_path, manifest = _load_manifest(arg)
    if manifest.get("status") == "undone":
        print("This migration was already undone.", file=out)
        return 0
    backup_dir = os.path.dirname(manifest_path)
    config = os.path.realpath(str(manifest.get("config_dir", "")))
    if not config or config == "/":
        raise MigrateError("The manifest names no settings folder.")

    plans = []
    problems = []
    for entry in manifest["entries"]:
        dest = entry.get("dest")
        if not isinstance(dest, str) or not _inside(os.path.realpath(dest), config) or os.path.realpath(dest) == config:
            raise MigrateError("The manifest lists a file outside the settings folder, so it will not be used.")
        expected = entry.get("sha256_after") or entry.get("sha256_src")
        before = entry.get("sha256_before")
        exists = os.path.isfile(dest) and not os.path.islink(dest)
        current = _sha256(dest) if exists else None
        action = entry.get("action")
        if os.path.lexists(dest) and not exists:
            problems.append("%s is no longer a regular file" % entry.get("rel", dest))
            continue
        if action in ("copy", "create"):
            if current is None or current == expected:
                plans.append(("remove", dest, None))
            else:
                problems.append("%s changed after the migration" % entry.get("rel", dest))
        elif action == "overwrite":
            backup = entry.get("backup")
            backup_file = os.path.realpath(os.path.join(backup_dir, backup)) if isinstance(backup, str) else None
            if backup_file is None or not _inside(backup_file, os.path.realpath(backup_dir)) or not os.path.isfile(backup_file):
                problems.append("the backup of %s is missing" % entry.get("rel", dest))
            elif _sha256(backup_file) != before:
                problems.append("the backup of %s no longer matches" % entry.get("rel", dest))
            elif current == before:
                continue  # the write never happened
            elif current == expected:
                plans.append(("restore", dest, backup_file))
            else:
                problems.append("%s changed after the migration" % entry.get("rel", dest))
        else:
            raise MigrateError("The manifest holds an action this version does not understand.")
    if problems and not args.force:
        raise MigrateError("Undo stopped and changed nothing: %s. Restore those files by hand or pass --force." %
                           "; ".join(problems))

    for kind, dest, backup_file in plans:
        if kind == "remove":
            if os.path.lexists(dest):
                os.unlink(dest)
        else:
            _atomic_write(dest, src=backup_file)
    for folder in sorted(manifest.get("created_dirs", []), key=len, reverse=True):
        real = os.path.realpath(folder)
        if _inside(real, config) and real != config:
            try:
                os.rmdir(folder)
            except OSError:
                pass
    if manifest.get("config_created"):
        try:
            os.rmdir(config)
        except OSError:
            pass
    manifest["status"] = "undone"
    manifest["undone"] = _now()
    _write_json(manifest_path, manifest)
    print("Undone: %d file(s) restored or removed in %s. Your original folder was never touched." %
          (len(plans), config), file=out)
    return 0


def main(argv=None, out=None):
    out = out or sys.stdout
    parser = argparse.ArgumentParser(prog="mac-update migrate", description="Bring user data from an older git-based copy into the settings folder.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--preview", action="store_true", help="show what would be copied (default)")
    group.add_argument("--apply", action="store_true", help="copy it, with backup and manifest")
    group.add_argument("--undo", metavar="MANIFEST", help="restore from a manifest.json (or its folder)")
    parser.add_argument("--source", help="the older git-based folder (default: found automatically)")
    parser.add_argument("--defaults", help="folder holding the shipped config/ to compare against (default: this program)")
    parser.add_argument("--overwrite", action="store_true", help="replace differing files in the settings folder after backing them up")
    parser.add_argument("--force", action="store_true", help="with --undo: continue even if a file changed since")
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 2
    try:
        if args.undo:
            return cmd_undo(args.undo, args, out)
        paths = mu_paths.resolve()
        source = find_source(args.source, os.environ)
        if not source:
            print("No older git-based install was found, so there is nothing to migrate. "
                  "If it lives somewhere unusual, pass --source FOLDER.", file=out)
            return 0
        if args.defaults is None:
            root = mu_paths.toolkit_root()
            if os.path.realpath(root) != source and os.path.isdir(os.path.join(root, "config")):
                args.defaults = root
        if args.apply:
            return cmd_apply(source, paths, args, out)
        return cmd_preview(source, paths, args, out)
    except (MigrateError, mu_paths.PathError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        print("The migration stopped because of a file problem (%s). Nothing further was changed; "
              "use --undo with the manifest if one was written." % (exc.strerror or exc.__class__.__name__), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
