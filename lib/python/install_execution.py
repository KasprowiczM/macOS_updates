"""Explicit first-install execution. Existing targets are never replaced/adopted.

The vendor adapter consumes a separately staged, verified bundle. Public catalog
entries have no first-install acceptance and therefore only offer manual links.
No generic package installer, vendor shell, launch or manager bootstrap runs here.
"""

import copy
import datetime
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import uuid
from download_policy import validate_download_url
from install_plan import (
    validate_install_plan,
    resolve_requirements,
    install_recipe_eligible,
)
from inventory_collect import read_bundle_static
from inventory_store import _root, StoreError
from policy_runtime import TargetLock, utc_now, _read_json, _atomic_json
from update_transaction import observe_bundle, _rename_exclusive
from user_policy import digest, timestamp
from vendor_feeds import version_compare


def make_install_consent(plan, action_ids, now):
    validate_install_plan(plan)
    timestamp(now)
    ids = {action["action_id"] for action in plan["actions"]}
    if (
        not isinstance(action_ids, list)
        or not action_ids
        or len(set(action_ids)) != len(action_ids)
        or not set(action_ids) <= ids
    ):
        raise ValueError("explicit_action_list_required")
    return dict(
        plan_digest=plan["plan_digest"],
        action_ids=list(action_ids),
        granted_at=now,
        expires_at=(timestamp(now) + datetime.timedelta(minutes=15))
        .isoformat()
        .replace("+00:00", "Z"),
    )


def authorize_install(action, current, consent, now):
    result = dict(
        action_id=action.get("action_id"),
        product_id=action.get("product_id"),
        allowed=False,
        reason_code="invalid_install_consent",
    )

    def deny(reason):
        result["reason_code"] = reason
        return result

    try:
        moment = timestamp(now)
        age = (moment - timestamp(action["plan_created_at"])).total_seconds()
        if not 0 <= age <= 900:
            return deny("install_plan_expired")
        if not timestamp(action["plan_created_at"]) <= timestamp(
            consent["granted_at"]
        ) <= moment or moment >= timestamp(consent["expires_at"]):
            return deny("install_consent_expired")
        if (
            timestamp(consent["expires_at"]) - timestamp(consent["granted_at"])
        ).total_seconds() > 900:
            return deny("install_consent_expired")
        if (
            action["action_id"] not in consent.get("action_ids", [])
            or consent.get("plan_digest") != action.get("plan_digest")
            or current.get("plan_digest") != action["plan_digest"]
        ):
            return deny("install_plan_changed")
        if current.get("recipe_fingerprint") != action.get(
            "recipe_fingerprint"
        ) or current.get("requirement_graph_digest") != action.get(
            "requirement_graph_digest"
        ):
            return deny("install_requirements_changed")
        if action.get("profile_id") is not None and (
            current.get("profile_id") != action["profile_id"]
            or current.get("snapshot_generation") != action.get("snapshot_generation")
        ):
            return deny("install_profile_changed")
        if current.get("source_conflict") is not False:
            return deny("source_conflict")
        if action["kind"] == "manual_migration":
            return deny("manual_migration_only")
        if current.get("presence") != "absent":
            return deny("target_appeared_since_preview")
        if action["kind"] == "manual_acquisition":
            if not action.get("official_url"):
                return deny("official_link_unreviewed")
            result.update(allowed=True, reason_code="manual_acquisition_selected")
            return result
        if (
            action["kind"] != "install"
            or action.get("adapter_id") != "vendor_bundle"
            or not install_recipe_eligible(action.get("recipe", {}))
        ):
            return deny("install_adapter_unreviewed")
        if current.get("destination_symlink") or current.get(
            "canonical_destination"
        ) != action.get("destination"):
            return deny("destination_changed")
        if current.get("requirements_complete") is not True:
            return deny("requirements_missing")
        result.update(allowed=True, reason_code="allowed")
        return result
    except (KeyError, TypeError, ValueError, AttributeError):
        return result


def record_install_result(action, observed, journal):
    value = copy.deepcopy(journal)
    recipe = action.get("recipe", {})
    verified = bool(
        observed.get("exists") is True
        and observed.get("good") is True
        and observed.get("receipt_present") is False
        and observed.get("bundle_id") == recipe.get("bundle_id")
        and observed.get("team_id") == recipe.get("team_id")
        and observed.get("version") == action.get("version")
        and "arm64" in observed.get("architectures", [])
        and version_compare(observed.get("host_os"), observed.get("minimum_os"))
        in (0, 1)
        and journal.get("snapshot_id")
    )
    value.update(
        status="installed_verified" if verified else "recovery_required",
        verified=verified,
        observed_identity={
            key: observed.get(key)
            for key in (
                "bundle_id",
                "team_id",
                "version",
                "architectures",
                "minimum_os",
            )
        },
        recovery_required=not verified,
    )
    return value


def _roots(allowed_roots):
    roots = (
        allowed_roots
        if allowed_roots is not None
        else ["/Applications", os.path.expanduser("~/Applications")]
    )
    return [
        os.path.realpath(root)
        for root in roots
        if os.path.isdir(root) and not os.path.islink(root)
    ]


def _current(action, plan, recipes, environment, snapshot, roots):
    recipe = next(
        (
            r
            for r in recipes.get("recipes", [])
            if r.get("product_id") == action["product_id"]
        ),
        {},
    )
    graph = resolve_requirements(plan["selections"], environment, recipes)
    destination = action.get("destination")
    exists = bool(destination and os.path.lexists(destination))
    current = dict(
        plan_digest=plan["plan_digest"],
        recipe_fingerprint=digest(recipe),
        requirement_graph_digest=digest(graph),
        requirements_complete=all(
            node["status"] == "satisfied"
            for node in graph["nodes"]
            if node["id"] in action.get("requirement_ids", [])
        ),
        profile_id=snapshot.get("profile_id"),
        snapshot_generation=snapshot.get("generation"),
        presence="present" if exists else "absent",
        destination_symlink=bool(destination and os.path.islink(destination)),
        canonical_destination=os.path.realpath(destination) if destination else None,
        source_conflict=False,
    )
    installed = [
        target
        for group in ("instances", "packages")
        for target in snapshot.get(group, [])
        if target.get("presence") == "present"
        and (
            target.get("product_id") == action["product_id"]
            or recipe.get("bundle_id")
            and target.get("bundle_id") == recipe["bundle_id"]
        )
    ]
    if installed:
        current["source_conflict"] = True
    # Re-read supported roots immediately; an app created outside the planned
    # destination must not become an invisible duplicate/adoption fallback.
    if recipe.get("bundle_id"):
        try:
            for root in roots:
                with os.scandir(root) as entries:
                    for index, entry in enumerate(entries):
                        if index >= 4096:
                            raise ValueError("root_scan_partial")
                        if entry.name.endswith(".app"):
                            facts = read_bundle_static(entry.path)
                            if facts["status"] != "ok":
                                current["source_conflict"] = None
                            if any(
                                row.get("bundle_id") == recipe["bundle_id"]
                                for row in facts["items"]
                            ):
                                current["source_conflict"] = True
        except OSError:
            current["source_conflict"] = None
    return current


def _destination(action, roots, require_absent=True):
    dest = action.get("destination")
    if (
        not isinstance(dest, str)
        or not os.path.isabs(dest)
        or not dest.endswith(".app")
        or os.path.normpath(dest) != dest
    ):
        raise ValueError("absolute_app_destination_required")
    parent = os.path.dirname(dest)
    if (
        parent not in roots
        or os.path.realpath(parent) != parent
        or os.path.islink(parent)
    ):
        raise ValueError("destination_root_unreviewed")
    if require_absent and os.path.lexists(dest):
        raise ValueError("target_appeared_since_preview")
    if not require_absent and os.path.islink(dest):
        raise ValueError("destination_changed")
    return dest


def _candidate(action, observed):
    recipe = action["recipe"]
    if observed.get("good") is not True or observed.get("receipt_present") is not False:
        raise ValueError("candidate_signature_or_source_unknown")
    if (
        observed.get("bundle_id") != recipe["bundle_id"]
        or observed.get("team_id") != recipe["team_id"]
    ):
        raise ValueError("candidate_identity_changed")
    if observed.get("version") != action["version"]:
        raise ValueError("candidate_version_changed")
    if "arm64" not in observed.get("architectures", []) or version_compare(
        observed.get("host_os"), observed.get("minimum_os")
    ) not in (0, 1):
        raise ValueError("candidate_incompatible")
    if version_compare(observed.get("minimum_os"), recipe["minimum_os"]) is None:
        raise ValueError("candidate_minimum_os_unknown")


def _validate_bundle_tree(source):
    if not os.path.isdir(source) or os.path.islink(source):
        raise ValueError("staged_bundle_missing")
    count = 0
    size = 0
    canonical = os.path.realpath(source)
    for root, dirs, files in os.walk(source, followlinks=False):
        for name in dirs + files:
            path = os.path.join(root, name)
            metadata = os.lstat(path)
            count += 1
            if count > 100000:
                raise ValueError("bundle_entry_budget")
            if stat.S_ISLNK(metadata.st_mode):
                if os.path.commonpath([canonical, os.path.realpath(path)]) != canonical:
                    raise ValueError("bundle_external_symlink")
            elif not stat.S_ISDIR(metadata.st_mode) and not stat.S_ISREG(
                metadata.st_mode
            ):
                raise ValueError("bundle_special_file")
            if stat.S_ISREG(metadata.st_mode):
                size += metadata.st_size
            if size > 8 * 1024 * 1024 * 1024:
                raise ValueError("bundle_size_budget")


def _copy_bundle(source, destination):
    _validate_bundle_tree(source)
    shutil.copytree(source, destination, symlinks=True)
    _validate_bundle_tree(destination)


def _capture_snapshot(action, observed, state_dir):
    from inventory_migration import collect_current_snapshot, rebuild_inventory

    script_dir = str(Path(__file__).resolve().parents[2])
    snapshot = collect_current_snapshot(script_dir, state_dir)
    matched = [
        item
        for item in snapshot["instances"]
        if item.get("real_path") == action["destination"]
        and item.get("bundle_id") == observed["bundle_id"]
        and item.get("presence") == "present"
        and item.get("freshness") == "fresh"
    ]
    if len(matched) != 1:
        raise ValueError("installed_snapshot_not_verified")
    matched[0]["team_id"] = observed["team_id"]
    matched[0]["channel"] = action["recipe"]["channel"]
    matched[0]["product_id"] = action["product_id"]
    matched[0]["edition"] = action["edition"]
    matched[0]["evidence"].append(
        dict(
            kind="vendor_signature",
            bundle_id=observed["bundle_id"],
            team_id=observed["team_id"],
        )
    )
    rebuild_inventory(snapshot, state_dir, str(Path(script_dir) / "APPLICATIONS.md"))
    return dict(
        snapshot_id=snapshot["snapshot_id"], verified_path=action["destination"]
    )


def execute_install_action(
    plan,
    action_id,
    consent,
    recipes,
    environment,
    staged_app=None,
    observe=None,
    snapshot=None,
    allowed_roots=None,
    state_dir=None,
    snapshot_writer=None,
    opener=None,
    fault=None,
):
    observer = observe or observe_bundle
    snapshot = snapshot or {}
    roots = _roots(allowed_roots)
    action = None
    journal = None
    journal_path = None
    stage_root = None
    stage_owner = None
    committed = False

    def persist():
        if journal_path:
            _atomic_json(journal_path, journal)

    def fail(reason):
        status = "recovery_required" if committed else "deferred"
        result = dict(
            action_id=action_id,
            product_id=action.get("product_id") if action else None,
            name=action.get("name") if action else None,
            status=status,
            verified=False,
            reason_code=reason,
            recovery_required=committed,
        )
        if journal is not None:
            journal.update(result)
            persist()
        return result

    try:
        validate_install_plan(plan)
        action = next(a for a in plan["actions"] if a["action_id"] == action_id)
        if digest(recipes) != plan["recipe_fingerprint"]:
            return fail("recipe_catalog_changed")
        current = _current(action, plan, recipes, environment, snapshot, roots)
        guard = authorize_install(action, current, consent, utc_now())
        if not guard["allowed"]:
            return fail(guard["reason_code"])
        root = _root(state_dir, True)
        directory = os.path.join(root, "installation-transactions")
        os.makedirs(directory, mode=0o700, exist_ok=True)
        st = os.lstat(directory)
        if (
            not stat.S_ISDIR(st.st_mode)
            or st.st_uid != os.getuid()
            or stat.S_IMODE(st.st_mode) != 0o700
        ):
            raise ValueError("unsafe_install_journal_directory")
        journal = dict(
            schema_version=1,
            transaction_id=str(uuid.uuid4()),
            action_id=action_id,
            product_id=action["product_id"],
            name=action["name"],
            plan_digest=plan["plan_digest"],
            destination=action.get("destination"),
            action=copy.deepcopy(action),
            action_fingerprint=digest(action),
            status="prepared",
            created_paths=[],
            existing_paths=[],
            verified=False,
            recovery_required=False,
        )
        journal_path = os.path.join(directory, journal["transaction_id"] + ".json")
        persist()
        if action["kind"] == "manual_acquisition":
            url = action["official_url"]
            validate_download_url(
                url,
                [
                    __import__("urllib.parse", fromlist=["urlsplit"])
                    .urlsplit(url)
                    .hostname
                ],
            )
            if opener:
                opener(url)
            else:
                subprocess.run(
                    ["open", url],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    check=True,
                )
            journal.update(
                status="manual_acquisition_opened",
                verified=False,
                reason_code="user_must_acquire_and_rescan",
            )
            persist()
            return copy.deepcopy(journal)
        destination = _destination(action, roots)
        with TargetLock(destination, root):
            current = _current(action, plan, recipes, environment, snapshot, roots)
            guard = authorize_install(action, current, consent, utc_now())
            if not guard["allowed"]:
                return fail(guard["reason_code"])
            if not staged_app:
                raise ValueError("reviewed_staged_bundle_required")
            _candidate(action, observer(staged_app))
            stage_root = tempfile.mkdtemp(
                prefix=".macupd-install-", dir=os.path.dirname(destination)
            )
            os.chmod(stage_root, 0o700)
            stage_info = os.lstat(stage_root)
            stage_owner = (stage_info.st_dev, stage_info.st_ino)
            stage = os.path.join(stage_root, os.path.basename(destination))
            journal["created_paths"] = [stage_root]
            journal["stage_owner"] = list(stage_owner)
            persist()
            _copy_bundle(staged_app, stage)
            _candidate(action, observer(stage))
            if fault:
                fault("before_commit", journal)
            current = _current(action, plan, recipes, environment, snapshot, roots)
            guard = authorize_install(action, current, consent, utc_now())
            if not guard["allowed"]:
                return fail(guard["reason_code"])
            _destination(action, roots)
            _rename_exclusive(stage, destination)
            committed = True
            journal["created_paths"].append(destination)
            journal["status"] = "installed_unverified"
            persist()
            if fault:
                fault("after_commit", journal)
            observed = observer(destination)
            _candidate(action, observed)
            capture = (snapshot_writer or (lambda a, o: _capture_snapshot(a, o, root)))(
                action, observed
            )
            if (
                not isinstance(capture, dict)
                or not capture.get("snapshot_id")
                or capture.get("verified_path") != destination
            ):
                raise ValueError("installed_snapshot_not_verified")
            journal["snapshot_id"] = capture["snapshot_id"]
            journal = record_install_result(action, observed, journal)
            persist()
            return copy.deepcopy(journal)
    except (
        ValueError,
        OSError,
        KeyError,
        TypeError,
        StopIteration,
        StoreError,
        subprocess.SubprocessError,
    ) as exc:
        reason = str(exc)
        if not reason or any(c not in "abcdefghijklmnopqrstuvwxyz_" for c in reason):
            reason = "install_unverified"
        return fail(reason)
    finally:
        # Only this attempt's private, unfinalized staging is removed. A newly
        # appeared destination or a partially successful install is preserved.
        if stage_root and os.path.isdir(stage_root) and not os.path.islink(stage_root):
            info = os.lstat(stage_root)
            if stage_owner == (info.st_dev, info.st_ino):
                try:
                    shutil.rmtree(stage_root)
                except OSError:
                    pass


def load_install_plan(path):
    return validate_install_plan(_read_json(path))


def shell_execute(argv):
    from setup_catalog import load_setup_catalog
    from inventory_store import load_snapshot, default_root

    try:
        plan = load_install_plan(argv[0])
        action = next(a for a in plan["actions"] if a["action_id"] == argv[1])
        consent = _read_json(argv[2])
        if len(argv) > 4 and argv[4] != action.get("destination"):
            return 10
        recipes = load_setup_catalog()
        snapshot = load_snapshot(default_root()) or {}
        result = execute_install_action(
            plan,
            action["action_id"],
            consent,
            recipes,
            snapshot.get("environment", {}),
            staged_app=argv[3] if len(argv) > 3 else None,
            snapshot=snapshot,
        )
        print(json.dumps(result, ensure_ascii=True))
        return (
            0
            if result["status"] in ("installed_verified", "manual_acquisition_opened")
            else 1
            if result["status"] == "recovery_required"
            else 10
        )
    except (ValueError, OSError, KeyError, TypeError, IndexError, StopIteration):
        return 10


def recover_installations(
    state_dir=None, observe=None, allowed_roots=None, snapshot_writer=None
):
    """Reconcile interrupted journals by observation only. Never resume install.

    No destination, dependency or saved staging directory is deleted. An absent
    destination requires a new preview; ambiguous state stays recovery_required.
    """
    root = _root(state_dir)
    if root is None:
        return []
    directory = Path(root) / "installation-transactions"
    if not directory.exists():
        return []
    metadata = os.lstat(directory)
    if (
        not stat.S_ISDIR(metadata.st_mode)
        or metadata.st_uid != os.getuid()
        or stat.S_IMODE(metadata.st_mode) != 0o700
    ):
        return [
            dict(
                status="recovery_required",
                reason_code="unsafe_install_journal_directory",
            )
        ]
    observer = observe or observe_bundle
    roots = _roots(allowed_roots)
    results = []
    entries = []
    with os.scandir(directory) as iterator:
        for entry in iterator:
            if len(entries) >= 1000:
                return [
                    dict(
                        status="recovery_required", reason_code="install_journal_budget"
                    )
                ]
            if entry.name.endswith(".json"):
                entries.append(entry.path)
    for path in sorted(entries):
        journal = None
        try:
            info = os.lstat(path)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise ValueError("unsafe_install_journal")
            journal = _read_json(path)
            if journal.get("schema_version") != 1 or journal.get("status") not in (
                "prepared",
                "installed_unverified",
                "recovery_required",
                "installed_verified",
                "deferred",
                "manual_acquisition_opened",
            ):
                raise ValueError("invalid_install_journal")
            if journal["status"] in (
                "installed_verified",
                "deferred",
                "manual_acquisition_opened",
            ):
                continue
            action = journal.get("action")
            if (
                not isinstance(action, dict)
                or digest(action) != journal.get("action_fingerprint")
                or journal.get("destination") != action.get("destination")
                or action.get("kind") != "install"
                or not install_recipe_eligible(action.get("recipe", {}))
            ):
                raise ValueError("invalid_install_journal_action")
            destination = _destination(action, roots, require_absent=False)
            with TargetLock(destination, root):
                if not os.path.lexists(destination):
                    journal.update(
                        status="deferred",
                        verified=False,
                        recovery_required=False,
                        reason_code="interrupted_install_requires_new_preview",
                    )
                else:
                    observed = observer(destination)
                    _candidate(action, observed)
                    capture = (
                        snapshot_writer or (lambda a, o: _capture_snapshot(a, o, root))
                    )(action, observed)
                    if (
                        not isinstance(capture, dict)
                        or not capture.get("snapshot_id")
                        or capture.get("verified_path") != destination
                    ):
                        raise ValueError("installed_snapshot_not_verified")
                    journal["snapshot_id"] = capture["snapshot_id"]
                    journal = record_install_result(action, observed, journal)
                    journal["reason_code"] = "interrupted_install_observed_verified"
                _atomic_json(path, journal)
                results.append(copy.deepcopy(journal))
        except (
            ValueError,
            OSError,
            KeyError,
            TypeError,
            StoreError,
            subprocess.SubprocessError,
        ):
            result = dict(
                status="recovery_required",
                verified=False,
                recovery_required=True,
                reason_code="interrupted_install_requires_review",
            )
            if (
                isinstance(journal, dict)
                and journal.get("action_fingerprint")
                and isinstance(journal.get("action"), dict)
                and digest(journal["action"]) == journal["action_fingerprint"]
            ):
                journal.update(result)
                _atomic_json(path, journal)
                result = copy.deepcopy(journal)
            results.append(result)
    return results
