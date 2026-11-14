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
import time
from pathlib import Path
from tui_events import emit_target
from app_recipes import load_recipes, load_verified_recipes
from inventory_collect import read_bundle_static
from inventory_providers import (
    read_brew_receipts,
    read_cli_manifests,
    read_mas,
    package_observation_complete,
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
    get_decision,
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


def set_installed_update_default(enabled, state_dir=None, *, allow_registered_vendor_groups=False):
    """Persist one explicit profile agreement without creating per-app grants."""
    if type(enabled) is not bool or type(allow_registered_vendor_groups) is not bool:
        raise ValueError("invalid_installed_update_agreement")
    with locked_state(state_dir or default_root()) as root:
        policies = copy.deepcopy(load_policies(root))
        snapshot = load_snapshot(root)
        if enabled and snapshot is None:
            raise StoreError("saved_inventory_required")
        profile = snapshot["profile_id"] if snapshot else policies.get("profile_id")
        if policies.get("profile_id") not in (None, profile):
            raise ValueError("policy_profile_mismatch")
        policies.update(schema_version=1, revision=policies.get("revision", 0)+1,
                        profile_id=profile, decisions=policies.get("decisions", []),
                        installed_updates=dict(enabled=enabled, scope="same_source_existing_only",
                            allow_registered_vendor_groups=allow_registered_vendor_groups,
                            confirmed_at=utc_now()))
        _atomic_json(os.path.join(root, "policy.json"), policies)
        return policies


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


def _recipe_catalog(script_dir):
    catalog = load_recipes(os.path.join(script_dir, "config/app_recipes.json"))
    path = os.path.join(script_dir, "config/verified_recipes.json")
    catalog["verified_recipes"] = (
        load_verified_recipes(path)["recipes"] if os.path.exists(path) else []
    )
    return catalog


def build_runtime_plan(script_dir, state_dir=None, filters=None):
    from inventory_migration import collect_current_snapshot

    root = state_dir or default_root()
    snapshot = collect_current_snapshot(script_dir, root)
    from installed_native_updaters import enrich_installed_updater_identities
    snapshot = enrich_installed_updater_identities(snapshot)
    policies = load_policies(root)
    if policies.get("profile_id") not in (None, snapshot["profile_id"]):
        raise ValueError("policy_profile_mismatch")
    recipes = _recipe_catalog(script_dir)
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
    return rebind_plan_policies(plan, policies)


def rebind_plan_policies(plan, policies):
    """Rebuild an observed plan after a saved policy change without host reads."""
    if policies.get("profile_id") not in (None, plan["profile_id"]):
        raise ValueError("policy_profile_mismatch")
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

    def __init__(self, target_path, state_dir=None, owner_action_id=None):
        self.owner_action_id = owner_action_id
        self.target = os.path.realpath(target_path)
        self.root = state_dir
        self.fd = None

    def __enter__(self):
        from update_scheduler import assert_resources_available

        assert_resources_available(
            ["path:" + self.target], self.root, self.owner_action_id
        )
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
        try:
            assert_resources_available(
                ["path:" + self.target], self.root, self.owner_action_id
            )
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise
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


def _run_mutation(args, timeout=1800):
    child_env = dict(
        os.environ,
        HOMEBREW_NO_AUTO_UPDATE="1",
        HOMEBREW_NO_INSTALL_CLEANUP="1",
        MAS_NO_AUTO_INDEX="1",
    )
    deadline = time.monotonic() + timeout
    process = subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=child_env,
    )
    while process.poll() is None:
        if time.monotonic() >= deadline:
            # Child/helper remains alive; the persistent lease blocks writers.
            raise ValueError("mutation_observation_timeout")
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    if process.returncode != 0:
        raise ValueError("mutation_command_failed")


def _execute_reviewed_recipe(plan_path, action, state_dir, lease):
    from recipe_adapters import prepare_recipe_action, execute_recipe_action
    from recipe_acceptance import recipe_fingerprint
    from update_transaction import observe_bundle

    if os.environ.get("MAC_UPDATE_DRY_RUN") == "1":
        return dict(status="deferred_by_user", reason_code="dry_run", verified=False)
    recipe = action["recipe"]
    native = recipe["update_mechanism"] == "native_updater"
    root = _root(state_dir, True)
    directory = os.path.join(root, "transactions")
    os.makedirs(directory, mode=0o700, exist_ok=True)

    def prepare():
        current = reobserve_action(action)
        fresh = current.get("resolution", {}).get("verified_recipe")
        if not fresh or recipe_fingerprint(fresh) != action.get("recipe_sha256"):
            return dict(allowed=False, reason_code="recipe_changed")
        observed = observe_bundle(action["target_path"])
        target = dict(
            product=recipe["product"],
            edition=recipe["edition"],
            bundle_id=observed.get("bundle_id"),
            team_id=observed.get("team_id"),
            installation_source=current.get("resolution", {}).get("source"),
            channel=current.get("channel"),
            presence=current.get("presence"),
            signature_valid=observed.get("good"),
            app_store_receipt=observed.get("receipt_present"),
            real_path=current.get("real_path"),
            running=observed.get("running"),
            freshness=current.get("freshness"),
            version=observed.get("version"),
            build=observed.get("build"),
        )
        permissions = ["replace_existing_app"]
        if native:
            decision = get_decision(
                current,
                current.get("resolution", {}),
                load_policies(state_dir),
                utc_now(),
            )
            permissions = ["native_update", "launch_app"]
            if "quit_owned_app" in (decision or {}).get("lifecycle_permissions", []):
                permissions.append("quit_owned_app")
            if "restart_owned_app" in (decision or {}).get("lifecycle_permissions", []):
                permissions.append("restart_owned_app")
        env = dict(
            target=target,
            candidate=recipe["candidate"],
            now=datetime.datetime.now(datetime.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
            os_version=observed.get("host_os"),
            architecture=(
                "arm64" if "arm64" in observed.get("architectures", []) else None
            ),
            granted_permissions=permissions,
            granted_effects=permissions,
            available_requirements=[],
            approved_recipe_sha256=action.get("recipe_sha256"),
            approved_candidate_sha256=action.get("candidate_sha256"),
            approved_requirements_sha256=action.get("requirements_sha256"),
        )
        return prepare_recipe_action(recipe, target, "update", env)

    prepared = prepare()
    if not prepared.get("allowed"):
        return dict(
            status="manual_by_policy",
            reason_code=prepared.get("reason_code", "recipe_not_accepted"),
            verified=False,
        )

    class Observer:
        transaction_action = action

        def authorize(self):
            allowed = guard_action(
                plan_path,
                action["action_id"],
                state_dir,
                action["action_id"] if lease else None,
            )["allowed"]
            return allowed and prepare().get("allowed") is True

        def current(self):
            return reobserve_action(action)

        def observe_bundle(self, path):
            return observe_bundle(path)

        def native_authorize(self, native_action, observation):
            # Initial launch passed the normal closed-target guard. A driver
            # cannot authorize another launch. Subsequent control additionally
            # requires the lifecycle core's exact owned-process observation.
            from update_scheduler import assert_resources_available, resource_keys

            assert_resources_available(
                resource_keys(action), state_dir, action["action_id"]
            )
            policies = load_policies(state_dir)
            plan = load_plan(plan_path)
            _check_binding(plan, policies, state_dir)
            current = reobserve_action(action)
            current["running"] = False
            allowed = (
                authorize_action(action, current, policies, utc_now())["allowed"]
                and prepare().get("allowed") is True
            )
            decision = (
                get_decision(
                    current, current.get("resolution", {}), policies, utc_now()
                )
                or {}
            )
            controls = decision.get("lifecycle_permissions", [])
            return dict(
                allowed=allowed,
                consent_valid=allowed,
                source_verified=allowed,
                candidate_verified=allowed,
                authorized_candidate=recipe["candidate"],
                quit_authorized=allowed and "quit_owned_app" in controls,
                restart_authorized=allowed
                and "restart_owned_app" in controls
                and "restart_owned_app" in recipe["effect_scope"]["lifecycle"],
            )

    observer = Observer()
    observer.lease = lease
    observer.state_dir = state_dir
    observer.receipt_dir = os.environ.get("MAC_UPDATE_SESSION_DIR") or root
    return execute_recipe_action(prepared, observer, directory)


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
    if any(e.get("kind") == "installed_native_updater" for e in expected.get("evidence", [])):
        from installed_native_updaters import inspect_installed_target
        result = inspect_installed_target(result)
    elif expected.get("team_id"):
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
        receipt_complete = package_observation_complete(source, current)
        current.update(
            prefix=os.path.realpath(expected["prefix"]),
            presence="present",
            freshness=(
                "fresh" if (source["status"] == "ok" and source["complete"])
                or receipt_complete else "stale"
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
        if action.get("action_scope") in ("delegated_native_update", "legacy_same_source_update"):
            configured = [p for p in os.environ.get(
                "MAC_UPDATE_BREW_PREFIXES", "/opt/homebrew:/usr/local"
            ).split(os.pathsep) if p]
            if len(configured) > 32 or any(not os.path.isabs(p) for p in configured):
                current["freshness"] = "stale"
            else:
                prefixes.update(configured)
        for prefix in prefixes:
            source = read_brew_receipts(prefix)
            if action.get("action_scope") in ("delegated_native_update", "legacy_same_source_update") and (
                source.get("status") != "ok" or source.get("complete") is not True
            ):
                from installed_native_updaters import probe_brew_app_ownership
                # Missing manager roots and unrelated package errors do not
                # invalidate this signed application's metadata. Incomplete
                # ownership of the actual target still fails closed.
                if probe_brew_app_ownership(prefix, current.get("real_path")) != "clear":
                    current["freshness"] = "stale"
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
    recipes = _recipe_catalog(SCRIPT_DIR)
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
            path,
            os.O_APPEND | os.O_CREAT | os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o600,
        )
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            info = os.fstat(fd)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_nlink != 1
            ):
                raise ValueError("unsafe_result_file")
            if os.write(fd, payload) != len(payload):
                raise OSError("incomplete_result_write")
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


def guard_action(plan_path, action_id, state_dir=None, owner_action_id=None):
    result = dict(
        target=None, allowed=False, reason_code="invalid_plan", observed_identity=None
    )
    try:
        plan = load_plan(plan_path)
        action = next(a for a in plan["actions"] if a["action_id"] == action_id)
        result["target"] = action["target"]
        from update_scheduler import assert_resources_available, assert_active_batch_member, resource_keys

        try:
            if owner_action_id is not None:
                assert_active_batch_member(owner_action_id, action_id, state_dir)
            assert_resources_available(
                resource_keys(action), state_dir, owner_action_id
            )
        except ValueError:
            result["reason_code"] = "pending_updater_session"
            return result
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


def _execute_action(
    plan_path, adapter, action, state_dir=None, lease=None, allow_mutation=True,
    batch_managed=False,
):
    code = 0
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
            if os.environ.get("MAC_UPDATE_DRY_RUN") != "1" and allow_mutation:
                for resource in sorted(
                    set([action["target_path"]] + action.get("artifact_effects", []))
                ):
                    locks.enter_context(
                        TargetLock(
                            resource, state_dir, lease.action_id if lease else None
                        )
                    )
            guard = guard_action(
                plan_path,
                action["action_id"],
                state_dir,
                lease.action_id if lease else None,
            )
            if not guard["allowed"]:
                outcome["mutation_started"] = False
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
                    outcome["status"] not in ("manual_by_policy", "ignored_by_policy")
                    and code != 1
                ):
                    code = 10
            elif not allow_mutation:
                outcome.update(
                    status="deferred_by_user", reason_code="plan_requires_refresh", mutation_started=False
                )
                code = 10
            else:
                if action.get("action_scope") in ("delegated_native_update", "legacy_same_source_update"):
                    from installed_native_updaters import run_delegated_update
                    outcome.update(run_delegated_update(
                        action, lease,
                        batch_managed=batch_managed, plan_path=plan_path,
                        observation_timeout=30 if batch_managed else 0,
                        authorize=lambda: guard_action(
                            plan_path, action["action_id"], state_dir,
                            lease.action_id if lease else None,
                        )["allowed"],
                    ))
                    return outcome, 1 if outcome.get("status") == "update_failed" else 10
                if action.get("recipe"):
                    outcome.update(
                        _execute_reviewed_recipe(plan_path, action, state_dir, lease)
                    )
                    return outcome, 0 if outcome.get("verified") else 10
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
                    guard = guard_action(
                        plan_path,
                        action["action_id"],
                        state_dir,
                        action["action_id"] if lease else None,
                    )
                    if not guard["allowed"]:
                        raise ValueError(guard["reason_code"])
                    current = reobserve_action(action)
                    checked_command, checked_version = _prepare_command(action, current)
                    if checked_command != command or checked_version != version:
                        raise ValueError("manager_metadata_changed")
                    guard = guard_action(
                        plan_path,
                        action["action_id"],
                        state_dir,
                        action["action_id"] if lease else None,
                    )
                    if not guard["allowed"]:
                        raise ValueError(guard["reason_code"])
                    before = current.get("version", current.get("short_version"))
                    try:
                        outcome["mutation_started"] = True
                        _run_mutation(command, timeout=1800)
                        outcome["mutation_process_completed"] = True
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
                                    plan_path,
                                    action["action_id"],
                                    state_dir,
                                    action["action_id"] if lease else None,
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
                                    outcome["mutation_process_completed"] = False
                                    _run_mutation(
                                        [
                                            "env",
                                            "MAS_NO_AUTO_INDEX=1",
                                            "mas",
                                            "upgrade",
                                            store_id,
                                        ],
                                        timeout=1800,
                                    )
                                    outcome["mutation_process_completed"] = True
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
                            and source_fingerprint(after, after.get("resolution", {}))
                            == action["expected_source"]
                            and after.get("resolution", {}).get("source")
                            not in (None, "unknown", "conflict")
                            and artifact_effects(after) == action["artifact_effects"]
                        )
                        outcome.update(
                            status=(
                                "current_verified" if verified else "update_unverified"
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
    outcome.setdefault(
        "evidence_type",
        "installed_version_observation" if outcome.get("verified") else "none",
    )
    from operation_receipts import evidence_freshness

    outcome["evidence_freshness"] = evidence_freshness(outcome["evidence_type"])
    return outcome, code


def run_adapter(plan_path, adapter, state_dir=None):
    return run_adapters(plan_path, (adapter,), state_dir)


def run_adapters(plan_path, adapters, state_dir=None):
    adapters = tuple(adapters)
    if not adapters or len(set(adapters)) != len(adapters) or any(
        adapter not in ("app_store", "npm", "homebrew", "vendor") for adapter in adapters
    ):
        return 1
    if not plan_path:
        print("deferred_by_user: a reviewed action plan is required.")
        return 10
    try:
        plan = load_plan(plan_path)
    except (OSError, ValueError, TypeError):
        print("invalid_plan")
        return 1
    from update_scheduler import execute_queue, execute_exclusive_batch, resource_keys
    from operation_receipts import phase_receipt
    from tui_events import emit_phase
    import threading

    phase_lock = threading.Lock()
    phase_started = set()

    def phase_start(adapter):
        with phase_lock:
            if adapter not in phase_started:
                phase_started.add(adapter)
                emit_phase(adapter, "running")

    def phase_finish(adapter, current_results):
        action_ids = {a["action_id"] for a in selected if adapter_for(a) == adapter}
        if not action_ids:
            emit_phase(adapter, "skipped")
            return
        codes = [r.get("_exit_code", 10) for r in current_results if r.get("action_id") in action_ids]
        status = "error" if 1 in codes else "warn" if len(codes) != len(action_ids) or any(c != 0 for c in codes) else "ok"
        emit_phase(adapter, status)

    def adapter_for(action):
        adapter = action.get("adapter_id")
        if adapter in ("app_store", "npm", "homebrew"):
            return adapter
        if action.get("expected_resolution", {}).get("source") not in (
            "homebrew", "npm", "app_store"
        ):
            return "vendor"
        return None

    selected = [a for a in plan["actions"] if adapter_for(a) in adapters]
    results = []
    queued = []
    delegated = []
    for action in selected:
        adapter = adapter_for(action)
        # Report blocked entries without fsyncing hundreds of mutation leases.
        # A changed fresh guard cannot promote these entries without readmission.
        if os.environ.get("MAC_UPDATE_DRY_RUN") == "1" or action.get("reason_codes"):
            phase_start(adapter)
            outcome, code = _execute_action(
                plan_path,
                adapter,
                action,
                state_dir,
                allow_mutation=os.environ.get("MAC_UPDATE_DRY_RUN") == "1",
            )
            emit_target(action, outcome)
            results.append(dict(outcome, _exit_code=code))
        else:
            entry = dict(
                action, resources=resource_keys(action),
                scope_complete=action.get("scope_complete", True), parallel_safe=False,
            )
            if action.get("action_scope") in ("delegated_native_update", "legacy_same_source_update"):
                delegated.append(entry)
            else:
                queued.append(entry)

    def execute(action, lease, batch_managed=False):
        adapter = adapter_for(action)
        phase_start(adapter)
        emit_target(action)
        with phase_receipt(
            os.environ.get("MAC_UPDATE_SESSION_DIR") or _root(state_dir, True),
            run_id=plan["plan_id"],
            action_id=action["action_id"],
            recipe_revision=str(action.get("recipe", {}).get("revision", "manager")),
            phase="action",
        ) as event:
            if batch_managed:
                outcome, code = _execute_action(
                    plan_path, adapter, action, state_dir, lease, batch_managed=True
                )
            else:
                outcome, code = _execute_action(
                    plan_path, adapter, action, state_dir, lease
                )
            emit_target(action, outcome)
            event["outcome"] = outcome["status"]
            event["evidence_type"] = outcome.get("evidence_type", "none")
        if batch_managed:
            return dict(outcome, _exit_code=code)
        if lease.closed:
            pass  # The native supervisor already proved completion and released it.
        elif outcome.get("lease_managed"):
            lease.pending("native_completion_unconfirmed")
        elif (
            not outcome.get("mutation_started")
            or outcome.get("verified")
            or outcome.get("mutation_process_completed")
            and outcome.get("status") != "recovery_required"
        ):
            lease.finish(outcome["status"], helpers_complete=True)
        else:
            lease.pending("mutation_unconfirmed")
        return dict(outcome, _exit_code=code)

    results.extend(execute_queue(queued, execute, state_dir))
    delegated_adapters = {adapter_for(action) for action in delegated}
    for adapter in adapters:
        if adapter not in delegated_adapters:
            phase_finish(adapter, results)
    native_batch_pending = False
    if delegated:
        try:
            batch_results = execute_exclusive_batch(
                delegated, lambda action, lease: execute(action, lease, True), state_dir
            )
        except ValueError:
            batch_results = [dict(action_id=a["action_id"], status="deferred_by_user",
                                  reason_code="resources_pending", verified=False,
                                  mutation_started=False, recovery_required=False, _exit_code=10)
                             for a in delegated]
        native_batch_pending = any(r.get("mutation_started") is not False or
                                   r.get("recovery_required") is not False for r in batch_results)
        delegated_by_id = {a["action_id"]: a for a in delegated}
        for outcome in batch_results:
            if outcome.get("reason_code") in ("shared_manager_requested_unconfirmed", "resources_pending", "executor_interrupted"):
                emit_target(delegated_by_id[outcome["action_id"]], outcome)
        results.extend(batch_results)
    for adapter in adapters:
        if adapter in delegated_adapters:
            phase_finish(adapter, results)
    code = 0
    adapter_codes = {adapter: 0 for adapter in adapters}
    action_adapters = {action["action_id"]: adapter_for(action) for action in selected}
    selected_by_id = {action["action_id"]: action for action in selected}
    for outcome in results:
        emit_target(selected_by_id[outcome["action_id"]], outcome)
        current_code = outcome.pop("_exit_code", 10)
        current_code = 1 if current_code == 1 else 0 if current_code == 0 else 10
        adapter = action_adapters[outcome["action_id"]]
        previous = adapter_codes[adapter]
        adapter_codes[adapter] = 1 if 1 in (previous, current_code) else max(previous, current_code)
        code = 1 if code == 1 or current_code == 1 else max(code, current_code)
        _append("action-results.jsonl", outcome, state_dir)
        if os.environ.get("MAC_UPDATE_JSON_RESULTS") == "1":
            print(json.dumps(outcome, ensure_ascii=True))
    report_path = os.environ.get("MAC_UPDATE_ADAPTER_REPORT")
    if report_path:
        directory = os.path.dirname(os.path.abspath(report_path))
        fd, temporary = tempfile.mkstemp(prefix=".adapter-report-", dir=directory)
        try:
            with os.fdopen(fd, "w") as stream:
                json.dump({"schema_version": 1, "adapters": adapter_codes,
                           "native_batch_pending": native_batch_pending}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, report_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return code


def main(argv):
    try:
        if argv[0] == "reconcile-native" and len(argv) == 1:
            from installed_native_updaters import native_recovery_cli
            return native_recovery_cli()
        if argv[0] == "native-sessions" and len(argv) == 1:
            from installed_native_updaters import pending_delegated_sessions
            print(json.dumps(pending_delegated_sessions(), ensure_ascii=True))
            return 0
        if argv[0] == "guard":
            result = guard_action(argv[1], argv[2])
            print(json.dumps(result, ensure_ascii=True))
            return 0 if result["allowed"] else 10
        if argv[0] == "adapter":
            return run_adapter(argv[1], argv[2])
        if argv[0] == "adapters":
            return run_adapters(argv[1], argv[2:])
        if argv[0] == "target-lock":
            with TargetLock(argv[1]):
                return subprocess.call(argv[2:], stdin=subprocess.DEVNULL)
    except (OSError, ValueError, TypeError, KeyError, IndexError, StoreError):
        return 1
    return 1
