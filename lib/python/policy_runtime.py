"""Bounded execution boundary for scoped plans, local consent and target locks.

No environment variable grants authority. Standalone adapters require the same
immutable plan and fresh observation as orchestration. Native/bootstrap/migration
commands are intentionally outside this executor.
"""

import copy
import contextlib
import datetime
import fcntl
import json
import os
import re
import stat
import subprocess
import tempfile
from pathlib import Path
from app_recipes import load_recipes
from inventory_collect import read_bundle_static
from inventory_providers import (
    read_brew_receipts,
    read_cli_manifests,
    read_mas,
)
from inventory_store import (
    _root,
    _open_regular,
    default_root,
    load_snapshot,
    StoreError,
    locked_state,
)
from source_resolver import resolve_snapshot, resolve_target
from user_policy import (
    identity_fingerprint,
    source_fingerprint,
    digest,
    make_decision,
    record_decision,
    timestamp,
)
from update_plan import build_plan, authorize_action, artifact_effects

MAX_JSON = 16 * 1024 * 1024
SCRIPT_DIR = str(Path(__file__).resolve().parents[2])


def utc_now():
    return (
        datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
    )


def _read_json(path):
    fd = os.open(str(path), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as f:
        info = os.fstat(f.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_size > MAX_JSON
        ):
            raise ValueError("unsafe_json_file")
        raw = f.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError("json_too_large")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("invalid_json_object")
    return value


def _atomic_json(path, value, exclusive=False):
    parent = Path(path).parent
    if parent.is_symlink() or Path(path).is_symlink():
        raise ValueError("unsafe_json_path")
    serialized = json.dumps(value, ensure_ascii=True, sort_keys=True).encode()
    if len(serialized) > MAX_JSON:
        raise ValueError("json_too_large")
    fd, tmp = tempfile.mkstemp(prefix=".policy-", dir=str(parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(serialized)
            f.flush()
            os.fsync(f.fileno())
        if exclusive:
            os.link(tmp, str(path))
        else:
            os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_policies(state_dir=None):
    root = _root(state_dir)
    if root is None or not os.path.exists(os.path.join(root, "policy.json")):
        return {}
    value = _read_json(os.path.join(root, "policy.json"))
    if (
        value.get("schema_version") != 1
        or type(value.get("revision")) is not int
        or value["revision"] < 0
        or not isinstance(value.get("decisions"), list)
    ):
        raise ValueError("invalid_policy")
    return value


def save_policies(policies, state_dir=None):
    with locked_state(state_dir or default_root()) as root:
        current = load_policies(root)
        if current and (
            current.get("profile_id") != policies.get("profile_id")
            or policies.get("revision", 0) <= current.get("revision", 0)
        ):
            raise ValueError("policy_revision_changed")
        _atomic_json(os.path.join(root, "policy.json"), policies)


def save_plan(plan, path):
    # Plans are immutable files: a changed policy produces a new plan and path.
    _atomic_json(path, plan, exclusive=True)
    return path


def load_plan(path):
    plan = _read_json(path)
    if (
        plan.get("schema_version") != 1
        or plan.get("plan_type") not in (None, "update_plan")
        or not isinstance(plan.get("actions"), list)
        or len(plan["actions"]) > 20000
    ):
        raise ValueError("invalid_plan")
    ids = set()
    for action in plan["actions"]:
        if (
            not isinstance(action, dict)
            or not isinstance(action.get("action_id"), str)
            or action["action_id"] in ids
        ):
            raise ValueError("invalid_action")
        ids.add(action["action_id"])
        for outer, inner in [
            ("plan_id", "plan_id"),
            ("created_at", "plan_created_at"),
            ("profile_id", "profile_id"),
            ("snapshot_id", "snapshot_id"),
            ("snapshot_generation", "snapshot_generation"),
            ("base_snapshot_id", "base_snapshot_id"),
            ("policy_fingerprint", "expected_policy_fingerprint"),
        ]:
            if action.get(inner) != plan.get(outer):
                raise ValueError("plan_action_mismatch")
    timestamp(plan.get("created_at"))
    return plan


def build_runtime_plan(script_dir, state_dir=None, filters=None):
    from inventory_migration import collect_current_snapshot

    root = state_dir or default_root()
    snapshot = collect_current_snapshot(script_dir, root)
    policies = load_policies(root)
    if policies.get("profile_id") not in (None, snapshot["profile_id"]):
        raise ValueError("policy_profile_mismatch")
    recipes = load_recipes(os.path.join(script_dir, "config/app_recipes.json"))
    plan = build_plan(
        snapshot, resolve_snapshot(snapshot, recipes), policies, utc_now()
    )
    if filters:
        allowed = {filters} if isinstance(filters, str) else set(filters)
        plan["actions"] = [a for a in plan["actions"] if a["adapter_id"] in allowed]
    return plan


def record_plan_decisions(plan, choices, state_dir=None):
    # Revision check and replacement share the same lock; a concurrent choice
    # cannot be lost between reading a plan and saving its reviewed decisions.
    with locked_state(state_dir or default_root()) as root:
        policies = load_policies(root)
        if policies.get("profile_id") not in (None, plan["profile_id"]):
            raise ValueError("policy_profile_mismatch")
        if digest(policies) != plan["policy_fingerprint"]:
            raise ValueError("policy_changed")
        age = (timestamp(utc_now()) - timestamp(plan["created_at"])).total_seconds()
        if age < 0 or age > 900:
            raise ValueError("plan_expired")
        policies = copy.deepcopy(policies)
        policies["profile_id"] = plan["profile_id"]
        by_id = {a["action_id"]: a for a in plan["actions"]}
        for action_id, choice in choices.items():
            action = by_id[action_id]
            if choice == "reset":
                policies["decisions"] = [
                    d
                    for d in policies.get("decisions", [])
                    if d.get("target") != action["target"]
                ]
                policies.update(
                    schema_version=1, revision=policies.get("revision", 0) + 1
                )
            else:
                decision = make_decision(
                    action["expected_target"],
                    action["expected_resolution"],
                    choice,
                    action["action_scope"],
                    utc_now(),
                )
                policies = record_decision(decision, policies)
        if choices:
            _atomic_json(os.path.join(root, "policy.json"), policies)
    snapshot = dict(
        snapshot_id=plan["snapshot_id"],
        profile_id=plan["profile_id"],
        generation=plan["snapshot_generation"],
        previous_snapshot_id=plan.get("base_snapshot_id"),
        instances=[],
        packages=[],
        sources={},
    )
    resolutions = []
    for action in plan["actions"]:
        group = "instances" if action["target"]["kind"] == "app" else "packages"
        snapshot[group].append(copy.deepcopy(action["expected_target"]))
        resolutions.append(action["expected_resolution"])
    return build_plan(snapshot, resolutions, policies, utc_now())


class TargetLock:
    """Kernel-held, per-user canonical-resource lock shared by every checkout."""

    def __init__(self, target_path, state_dir=None):
        self.target = os.path.realpath(target_path)
        self.root = state_dir
        self.fd = None

    def __enter__(self):
        root = _root(self.root, True)
        directory = os.path.join(root, "target-locks")
        os.makedirs(directory, mode=0o700, exist_ok=True)
        st = os.lstat(directory)
        if (
            not stat.S_ISDIR(st.st_mode)
            or st.st_uid != os.getuid()
            or stat.S_IMODE(st.st_mode) != 0o700
        ):
            raise ValueError("unsafe_lock_directory")
        self.fd = _open_regular(
            os.path.join(directory, digest(self.target) + ".lock"),
            os.O_RDWR | os.O_CREAT,
        )
        try:
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.fd)
            self.fd = None
            raise ValueError("target_locked")
        os.ftruncate(self.fd, 0)
        os.write(
            self.fd,
            json.dumps(
                dict(
                    pid=os.getpid(), started=utc_now(), target_hash=digest(self.target)
                )
            ).encode(),
        )
        return self

    def __exit__(self, *args):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def _run(args, timeout=30, allowed=(0,), env=None):
    child_env = dict(
        os.environ,
        HOMEBREW_NO_AUTO_UPDATE="1",
        HOMEBREW_NO_INSTALL_CLEANUP="1",
        MAS_NO_AUTO_INDEX="1",
    )
    if env:
        child_env.update(env)
    result = subprocess.run(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        env=child_env,
        check=False,
    )
    if len(result.stdout.encode()) > MAX_JSON or result.returncode not in allowed:
        raise ValueError("command_failed")
    return result.stdout


def _running(target):
    try:
        processes = _run(["ps", "-axo", "command="])
        if len(processes) > 1024 * 1024:
            return None
        paths = (
            [target.get("real_path")]
            if "instance_id" in target
            else [
                target.get("installed_receipt"),
                os.path.join(
                    target["prefix"],
                    "lib/node_modules",
                    target.get("source_identity", ""),
                ),
            ]
        )
        for path in paths:
            if path and any(path in line for line in processes.splitlines()):
                return True
        return False
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _current_app(expected):
    path = expected.get("path")
    if not path or not os.path.isdir(path):
        return dict(expected, presence="absent", freshness="fresh")
    raw = read_bundle_static(path)
    result = dict(expected, **(raw.get("items") or [{}])[0])
    result.update(
        real_path=os.path.realpath(path),
        presence="present",
        freshness="fresh" if raw["status"] == "ok" and raw["complete"] else "stale",
        observed_at=utc_now(),
    )
    # A previous team identifier must be checked again, never copied as authority.
    if expected.get("team_id"):
        try:
            # codesign's diagnostics are normally on stderr; use bounded explicit
            # verification below rather than trusting the saved signature.
            checked = subprocess.run(
                ["codesign", "-dv", "--verbose=4", path],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            text = checked.stdout + checked.stderr
            match = re.search(r"^TeamIdentifier=(.+)$", text, re.M)
            if checked.returncode != 0 or len(text) > 1024 * 1024:
                raise ValueError("signature_unavailable")
            result["team_id"] = match.group(1) if match else None
            if result["team_id"]:
                result["evidence"].append(
                    dict(
                        kind="vendor_signature",
                        bundle_id=result.get("bundle_id"),
                        team_id=result["team_id"],
                    )
                )
        except (OSError, ValueError, subprocess.SubprocessError):
            result["team_id"] = None
            result["freshness"] = "stale"
    result["channel"] = expected.get("channel", "unknown")
    return result


def reobserve_action(action):
    expected = action["expected_target"]
    snapshot = dict(instances=[], packages=[], sources={})
    if action["target"]["kind"] == "package":
        source = (
            read_brew_receipts(expected["prefix"])
            if expected.get("manager") == "homebrew"
            else (
                read_cli_manifests(expected["prefix"])
                if expected.get("manager") == "npm"
                else None
            )
        )
        if source is None:
            return dict(
                expected,
                presence="unobserved",
                freshness="stale",
                running=None,
                resolution={},
            )
        matches = [
            p
            for p in source["items"]
            if p.get("source_identity") == expected.get("source_identity")
            and p.get("manager") == expected.get("manager")
        ]
        if len(matches) != 1:
            return dict(
                expected,
                presence=(
                    "absent" if not matches and source["complete"] else "unobserved"
                ),
                freshness="fresh" if source["complete"] else "stale",
                running=None,
                resolution={},
            )
        current = dict(expected, **matches[0])
        current.update(
            prefix=os.path.realpath(expected["prefix"]),
            presence="present",
            freshness=(
                "fresh" if source["status"] == "ok" and source["complete"] else "stale"
            ),
            observed_at=utc_now(),
        )
        related = []
        for old in action.get("related_targets", []):
            app = _current_app(old)
            for e in current["evidence"]:
                if e.get("artifact_path") == app.get("real_path"):
                    app["evidence"].append(copy.deepcopy(e))
            related.append(app)
        snapshot["instances"] = related
        snapshot["packages"] = [current]
    else:
        current = _current_app(expected)
        prefixes = {
            e.get("prefix")
            for e in expected.get("evidence", [])
            if e.get("kind") == "homebrew" and e.get("prefix")
        }
        for prefix in prefixes:
            source = read_brew_receipts(prefix)
            for p in source["items"]:
                for e in p.get("evidence", []):
                    if e.get("artifact_path") == current.get("real_path"):
                        current["evidence"].append(copy.deepcopy(e))
        if any(e.get("kind") == "mas" for e in expected.get("evidence", [])):
            source = read_mas()
            for item in source["items"]:
                for e in item.get("evidence", []):
                    if (
                        e.get("path") == current.get("real_path")
                        or e.get("bundle_id")
                        and e.get("bundle_id") == current.get("bundle_id")
                    ):
                        tagged = copy.deepcopy(e)
                        tagged["path"] = current.get("path")
                        current["evidence"].append(tagged)
            if source["status"] != "ok":
                current["freshness"] = "stale"
        snapshot["instances"] = [current]
    recipes = load_recipes(os.path.join(SCRIPT_DIR, "config/app_recipes.json"))
    current["resolution"] = resolve_target(current, snapshot, recipes)
    current["related_identity_valid"] = True
    if action["target"]["kind"] == "package":
        previous_snapshot = dict(
            instances=action.get("related_targets", []), packages=[expected], sources={}
        )
        for old, related in zip(
            action.get("related_targets", []), snapshot["instances"]
        ):
            old_source = resolve_target(old, previous_snapshot, recipes)
            new_source = resolve_target(related, snapshot, recipes)
            if (
                related.get("presence") != "present"
                or related.get("freshness") != "fresh"
                or identity_fingerprint(old) != identity_fingerprint(related)
                or source_fingerprint(old, old_source)
                != source_fingerprint(related, new_source)
            ):
                current["related_identity_valid"] = False
    current["running"] = _running(current)
    for related in (
        snapshot["instances"] if action["target"]["kind"] == "package" else []
    ):
        if _running(related) is not False:
            current["running"] = True
    return current


def _append(name, value, state_dir=None):
    payload = (json.dumps(value, ensure_ascii=True) + "\n").encode()
    # A preview can write its session diagnostics, never private result history.
    if os.environ.get("MAC_UPDATE_DRY_RUN") != "1":
        with locked_state(state_dir or default_root()) as root:
            fd = _open_regular(
                os.path.join(root, name), os.O_WRONLY | os.O_APPEND | os.O_CREAT
            )
            try:
                os.write(fd, payload)
            finally:
                os.close(fd)
    session = os.environ.get("MAC_UPDATE_SESSION_DIR")
    if session and os.path.isdir(session) and not os.path.islink(session):
        path = os.path.join(session, name)
        fd = os.open(
            path, os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW, 0o600
        )
        try:
            os.write(fd, payload)
        finally:
            os.close(fd)


def _check_binding(plan, policies, state_dir):
    if policies.get("profile_id") not in (None, plan["profile_id"]):
        raise ValueError("profile_changed")
    saved = load_snapshot(state_dir)
    if saved and (
        saved["profile_id"] != plan["profile_id"]
        or saved["snapshot_id"] != plan.get("base_snapshot_id")
        or saved["generation"] != plan["snapshot_generation"]
    ):
        raise ValueError("snapshot_changed")


def guard_action(plan_path, action_id, state_dir=None):
    result = dict(
        target=None, allowed=False, reason_code="invalid_plan", observed_identity=None
    )
    try:
        plan = load_plan(plan_path)
        action = next(a for a in plan["actions"] if a["action_id"] == action_id)
        result["target"] = action["target"]
        policies = load_policies(state_dir)
        _check_binding(plan, policies, state_dir)
        result = authorize_action(action, reobserve_action(action), policies, utc_now())
    except (
        StopIteration,
        OSError,
        ValueError,
        KeyError,
        TypeError,
        StoreError,
        subprocess.SubprocessError,
    ):
        pass
    _append("guard_results.jsonl", result, state_dir)
    return result


def _brew_query(prefix, kind, token):
    # All Homebrew CLI queries use the shared shell layer, with auto-update off.
    output = _run(
        [
            "/bin/bash",
            "-c",
            '. "$1/lib/brew.sh"; mac_update_brew_policy_info "$2" "$3" "$4"',
            "policy",
            SCRIPT_DIR,
            prefix,
            kind,
            token,
        ]
    )
    return json.loads(output)


def _prepare_command(action, current):
    source = current["resolution"]["source"]
    if action.get("kind") != "update" or action.get("action_scope") != "manager_update":
        raise ValueError("adapter_requires_manual_review")
    if source == "npm" and action["target"]["kind"] == "package":
        name = current.get("source_identity", "")
        if not re.fullmatch(r"(?:@[a-zA-Z0-9._-]+/)?[a-zA-Z0-9][a-zA-Z0-9._-]*", name):
            raise ValueError("invalid_package")
        prefix = current["prefix"]
        if (
            os.path.realpath(
                _run(["npm", "prefix", "--global", "--prefix", prefix]).strip()
            )
            != prefix
        ):
            raise ValueError("manager_prefix_changed")
        outdated = json.loads(
            _run(
                ["npm", "outdated", "--json", "--global", "--prefix", prefix, name],
                allowed=(0, 1),
            )
            or "{}"
        )
        row = outdated.get(name)
        if row is None:
            return None, None
        version = row.get("latest")
        if (
            row.get("current") != current.get("version")
            or not isinstance(version, str)
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", version)
        ):
            raise ValueError("manager_metadata_changed")
        before = current.get("version", "")
        if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", before):
            raise ValueError("version_scheme_unknown")
        if tuple(map(int, version.split("."))) <= tuple(map(int, before.split("."))):
            raise ValueError("downgrade_or_not_newer")
        metadata = json.loads(
            _run(["npm", "view", name + "@" + version, "--json"]) or "{}"
        )
        installed = _read_json(current["installed_receipt"])
        effects = (
            "bin",
            "scripts",
            "dependencies",
            "optionalDependencies",
            "peerDependencies",
            "bundleDependencies",
            "bundledDependencies",
        )
        if (
            not isinstance(metadata, dict)
            or metadata.get("name") != name
            or metadata.get("version") != version
        ):
            raise ValueError("manager_metadata_changed")
        if any(record.get(key) for record in (installed, metadata) for key in effects):
            raise ValueError("dependency_effects_require_review")
        return [
            "npm",
            "install",
            "--global",
            "--ignore-scripts",
            "--no-bin-links",
            "--omit=optional",
            "--omit=peer",
            "--prefix",
            prefix,
            name + "@" + version,
        ], version
    if source == "homebrew" and action["target"]["kind"] == "package":
        identity = current.get("source_identity", "")
        kind, sep, token = identity.partition(":")
        if kind not in ("formula", "cask") or not re.fullmatch(
            r"[a-zA-Z0-9@+_.-]+", token
        ):
            raise ValueError("invalid_package")
        info = _brew_query(current["prefix"], kind, token)
        rows = info.get("formulae" if kind == "formula" else "casks", [])
        if len(rows) != 1:
            raise ValueError("manager_metadata_changed")
        row = rows[0]
        version = (
            row.get("versions", {}).get("stable")
            if kind == "formula"
            else row.get("version")
        )
        if not isinstance(version, str) or not version or version == "latest":
            raise ValueError("update_version_unknown")
        if kind == "formula" and any(
            row.get(k)
            for k in (
                "dependencies",
                "build_dependencies",
                "recommended_dependencies",
                "optional_dependencies",
            )
        ):
            raise ValueError("dependency_effects_require_review")
        if kind == "cask":
            dependencies = row.get("depends_on") or {}
            if not isinstance(dependencies, dict) or any(
                value
                for key, value in dependencies.items()
                if key not in ("macos", "arch")
            ):
                raise ValueError("dependency_effects_require_review")
            artifacts = row.get("artifacts", [])
            names = []
            for artifact in artifacts:
                if not isinstance(artifact, dict) or set(artifact) != {"app"}:
                    raise ValueError("opaque_artifact_effects")
                apps = artifact["app"]
                apps = [apps] if isinstance(apps, str) else apps
                if (
                    not isinstance(apps, list)
                    or len(apps) != 1
                    or not isinstance(apps[0], str)
                ):
                    raise ValueError("opaque_artifact_effects")
                names.append(os.path.basename(apps[0]))
            if (
                sorted(names)
                != sorted(os.path.basename(p) for p in action["artifact_effects"])
                or not names
            ):
                raise ValueError("artifact_effects_changed")
            if any(not os.path.isdir(p) for p in action["artifact_effects"]):
                raise ValueError("removed_since_scan")
        if version == current.get("version"):
            return None, None
        from vendor_feeds import version_compare

        if version_compare(version, current.get("version")) != 1:
            raise ValueError("downgrade_or_version_unknown")
        options = []
        if kind == "cask":
            destinations = {
                os.path.dirname(path) for path in action["artifact_effects"]
            }
            if len(destinations) != 1:
                raise ValueError("opaque_artifact_effects")
            options = ["--appdir=" + next(iter(destinations))]
        return [
            os.path.join(current["prefix"], "bin/brew"),
            "upgrade",
            "--" + kind,
        ] + options + [token], version
    if source == "app_store" and action["target"]["kind"] == "app":
        ids = {
            str(e["store_id"])
            for e in current["evidence"]
            if e.get("kind") == "mas" and e.get("store_id")
        }
        if len(ids) != 1:
            raise ValueError("store_id_unknown")
        app_id = next(iter(ids))
        if not app_id.isdigit():
            raise ValueError("invalid_store_id")
        rows = _run(["mas", "outdated"])
        if any(not r.split()[0].isdigit() for r in rows.splitlines() if r.strip()):
            raise ValueError("manager_response_invalid")
        row = next(
            (r for r in rows.splitlines() if r.split() and r.split()[0] == app_id), None
        )
        if row is None:
            return None, None
        match = re.search(r" -> ([^)]+)\)", row)
        version = match.group(1).strip() if match else None
        if not version:
            raise ValueError("update_version_unknown")
        return [
            "sudo",
            "-n",
            "env",
            "MAS_NO_AUTO_INDEX=1",
            "mas",
            "upgrade",
            app_id,
        ], version
    raise ValueError("adapter_requires_manual_review")


def run_adapter(plan_path, adapter, state_dir=None):
    if not plan_path:
        print("deferred_by_user: a reviewed action plan is required.")
        return 10
    try:
        plan = load_plan(plan_path)
    except (OSError, ValueError, TypeError):
        print("invalid_plan")
        return 1
    code = 0
    for action in plan["actions"]:
        if action.get("adapter_id") != adapter and not (
            adapter == "vendor"
            and action.get("expected_resolution", {}).get("source")
            not in ("homebrew", "npm", "app_store")
        ):
            continue
        outcome = dict(
            target=action["target"],
            name=action["expected_target"].get("name")
            or action["expected_target"].get("source_identity")
            or action["expected_target"].get("bundle_id"),
            status="deferred_by_user",
            verified=False,
            before=action.get("from_version"),
            after=None,
            reason_code="consent_required",
            retry_after=None,
            recovery_required=False,
            action_id=action["action_id"],
        )
        try:
            with contextlib.ExitStack() as locks:
                if os.environ.get("MAC_UPDATE_DRY_RUN") != "1":
                    for resource in sorted(
                        set(
                            [action["target_path"]] + action.get("artifact_effects", [])
                        )
                    ):
                        locks.enter_context(TargetLock(resource, state_dir))
                guard = guard_action(plan_path, action["action_id"], state_dir)
                if not guard["allowed"]:
                    outcome["reason_code"] = guard["reason_code"]
                    outcome["status"] = (
                        guard["reason_code"]
                        if guard["reason_code"]
                        in (
                            "manual_by_policy",
                            "ignored_by_policy",
                            "deferred_by_user",
                            "source_conflict",
                            "source_unavailable",
                            "scan_partial",
                            "removed_since_scan",
                        )
                        else "deferred_by_user"
                    )
                    if (
                        outcome["status"]
                        not in ("manual_by_policy", "ignored_by_policy")
                        and code != 1
                    ):
                        code = 10
                else:
                    current = reobserve_action(action)
                    command, version = _prepare_command(action, current)
                    if command is None:
                        outcome.update(
                            status="current_verified",
                            verified=True,
                            after=current.get("version", current.get("short_version")),
                            reason_code="current_verified",
                        )
                    elif os.environ.get("MAC_UPDATE_DRY_RUN") == "1":
                        outcome.update(
                            status="deferred_by_user",
                            reason_code="dry_run",
                            to_version=version,
                        )
                    else:
                        # Reobserve after every check and directly before the mutation.
                        guard = guard_action(plan_path, action["action_id"], state_dir)
                        if not guard["allowed"]:
                            raise ValueError(guard["reason_code"])
                        current = reobserve_action(action)
                        checked_command, checked_version = _prepare_command(action, current)
                        if checked_command != command or checked_version != version:
                            raise ValueError("manager_metadata_changed")
                        guard = guard_action(plan_path, action["action_id"], state_dir)
                        if not guard["allowed"]:
                            raise ValueError(guard["reason_code"])
                        before = current.get("version", current.get("short_version"))
                        try:
                            _run(command, timeout=1800)
                        except (OSError, ValueError, subprocess.SubprocessError):
                            outcome.update(
                                status="update_failed",
                                reason_code="manager_update_failed",
                            )
                            code = 1
                        else:
                            after = reobserve_action(action)
                            actual = after.get("version", after.get("short_version"))
                            if adapter == "app_store" and actual != version:
                                pending = _run(["mas", "outdated"])
                                store_id = command[-1]
                                if any(
                                    row.split() and row.split()[0] == store_id
                                    for row in pending.splitlines()
                                ):
                                    retry_guard = guard_action(
                                        plan_path, action["action_id"], state_dir
                                    )
                                    if retry_guard["allowed"]:
                                        _append(
                                            "appstore_diag.txt",
                                            dict(
                                                branch="TRACK 1 user-session retry",
                                                name=outcome["name"],
                                                store_id=store_id,
                                            ),
                                            state_dir,
                                        )
                                        _run(
                                            [
                                                "env",
                                                "MAS_NO_AUTO_INDEX=1",
                                                "mas",
                                                "upgrade",
                                                store_id,
                                            ],
                                            timeout=1800,
                                        )
                                        after = reobserve_action(action)
                                        actual = after.get(
                                            "version", after.get("short_version")
                                        )
                            verified = (
                                after.get("presence") == "present"
                                and after.get("freshness") == "fresh"
                                and actual == version
                                and identity_fingerprint(after)
                                == action["expected_identity"]
                                and source_fingerprint(
                                    after, after.get("resolution", {})
                                )
                                == action["expected_source"]
                                and after.get("resolution", {}).get("source")
                                not in (None, "unknown", "conflict")
                                and artifact_effects(after)
                                == action["artifact_effects"]
                            )
                            outcome.update(
                                status=(
                                    "current_verified"
                                    if verified
                                    else "update_unverified"
                                ),
                                verified=verified,
                                before=before,
                                after=actual,
                                reason_code=(
                                    "updated_verified"
                                    if verified
                                    else "post_update_unverified"
                                ),
                                to_version=version,
                            )
                            if not verified and code != 1:
                                code = 10
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            StoreError,
            subprocess.SubprocessError,
        ) as exc:
            reason = str(exc)
            outcome["reason_code"] = (
                reason if re.fullmatch("[a-z_]+", reason) else "source_unavailable"
            )
            outcome["status"] = (
                "source_conflict"
                if reason == "source_conflict"
                else (
                    "manual_by_policy"
                    if reason
                    in (
                        "adapter_requires_manual_review",
                        "opaque_artifact_effects",
                        "dependency_effects_require_review",
                    )
                    else "source_unavailable"
                )
            )
            if code != 1 and outcome["status"] != "manual_by_policy":
                code = 10
        _append("action-results.jsonl", outcome, state_dir)
        if os.environ.get("MAC_UPDATE_JSON_RESULTS") == "1":
            print(json.dumps(outcome, ensure_ascii=True))
    return code


def main(argv):
    try:
        if argv[0] == "guard":
            result = guard_action(argv[1], argv[2])
            print(json.dumps(result, ensure_ascii=True))
            return 0 if result["allowed"] else 10
        if argv[0] == "adapter":
            return run_adapter(argv[1], argv[2])
        if argv[0] == "target-lock":
            with TargetLock(argv[1]):
                return subprocess.call(argv[2:], stdin=subprocess.DEVNULL)
    except (OSError, ValueError, TypeError, KeyError, IndexError, StoreError):
        return 1
    return 1
