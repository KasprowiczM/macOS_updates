"""Explicit delegation to an already installed, signed vendor application.

This trust model authorizes a launch, with the installed vendor choosing its
offered release. It grants no toolkit payload installation or lifecycle control,
and is deliberately independent of exact-candidate recipe acceptance.
"""

import copy
import json
import os
import re
import select
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from inventory_store import _root, StoreError
from user_policy import digest


# Claude Desktop owns its auto-update policy; launching permits it to run.
# No immediate check or completion is guaranteed by this contract. Documentation:
# https://support.claude.com/en/articles/12622667-enterprise-configuration-for-claude-desktop
# This is a product/launch contract, not a live update acceptance record.
# The iOS App Store identifier com.anthropic.claude is intentionally excluded.
CONTRACTS = {
    "claude-desktop": dict(
        contract_id="claude-desktop", revision=1,
        bundle_id="com.anthropic.claudefordesktop", team_id="Q6L2SF6YDW",
        scope_complete=False, parallel_safe=False,
        shared_resources=["installed-native:unknown-effects"],
        release_selection="installed_vendor_policy",
        execution_kind="native_window", legacy_manager_group=None,
    )
}

# Closed identifiers select reviewed code paths, never commands from inventory.
# Generic entries trust the *installed* verified signer after explicit consent;
# they do not assert that an unknown installation came from a known vendor.
LEGACY_HANDLERS = {
    "Google Chrome": "iu_google_chrome", "Google Drive": "iu_google_drive", "Gemini": "iu_gemini",
    "Firefox Developer Edition": "iu_firefox_developer_edition", "KeePassXC": "iu_keepassxc",
    "Visual Studio Code": "iu_visual_studio_code", "CodeEdit": "iu_codeedit",
    "Ledger Live": "iu_ledger", "Ledger Wallet": "iu_ledger", "Trezor Suite": "iu_trezor_suite",
    "ChatGPT": "iu_chatgpt", "Codex": "iu_chatgpt", "Cursor": "iu_cursor", "OpenCode": "iu_opencode_desktop",
    "Proton Mail": "iu_proton_mail", "Proton Drive": "iu_proton_drive",
    "HyperFrames": "iu_hyperframes", "Superset": "iu_superset",
    "Remote Desktop Manager": "iu_remote_desktop_manager", "Docker": "iu_docker_desktop",
    "Microsoft Excel": "iu_microsoft_365", "Microsoft Word": "iu_microsoft_365",
    "Microsoft Outlook": "iu_microsoft_365", "Microsoft PowerPoint": "iu_microsoft_365",
    "Microsoft OneNote": "iu_microsoft_365",
}
NATIVE_WINDOWS = {
    "Warp", "Antigravity", "Antigravity IDE", "Comet", "Microsoft Teams", "Grok Bot",
    "Brave Browser", "Perplexity", "LM Studio", "Obsidian", "ProtonVPN", "zoom.us", "MEGAsync",
    "AppCleaner", "Spotify", "CapCut", "Inkscape",
}
LEGACY_RELEASE_SELECTORS = {
    "iu_keepassxc": "github_latest_non_prerelease", "iu_codeedit": "github_latest_non_prerelease",
    "iu_ledger": "github_latest_non_prerelease", "iu_trezor_suite": "github_latest_non_prerelease",
    "iu_opencode_desktop": "github_latest_non_prerelease", "iu_superset": "github_latest_non_prerelease",
    "iu_visual_studio_code": "vscode_stable_arm64", "iu_cursor": "cursor_stable_arm64",
    "iu_firefox_developer_edition": "mozilla_developer_product_release",
    "iu_chatgpt": "installed_product_default_appcast", "iu_proton_mail": "proton_product_release_json",
    "iu_proton_drive": "proton_product_release_json", "iu_hyperframes": "hyperframes_product_release_json",
    "iu_remote_desktop_manager": "devolutions_product_release_info", "iu_docker_desktop": "docker_main_arm64_appcast",
}


def _registered_name(target):
    path = target.get("real_path") or target.get("path")
    if not isinstance(path, str) or not path.endswith(".app"):
        return None
    name = os.path.basename(path)[:-4]
    return name if name in LEGACY_HANDLERS or name in NATIVE_WINDOWS else None


def _product(target):
    pinned = next((c for c in CONTRACTS.values()
                   if c["bundle_id"] == target.get("bundle_id")), None)
    if pinned:
        return copy.deepcopy(pinned)
    name = _registered_name(target)
    bundle = target.get("bundle_id")
    if not name or not isinstance(bundle, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", bundle):
        return None
    group = ("google" if name in ("Google Chrome", "Google Drive", "Gemini")
             else "mau" if LEGACY_HANDLERS.get(name) == "iu_microsoft_365" else None)
    return dict(contract_id="installed-"+re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"),
                revision=1, bundle_id=bundle, team_id=target.get("team_id"),
                installed_signer_trust=True, registered_name=name,
                execution_kind="legacy_handler" if name in LEGACY_HANDLERS else "native_window",
                legacy_handler=LEGACY_HANDLERS.get(name), legacy_manager_group=group,
                legacy_release_selector=LEGACY_RELEASE_SELECTORS.get(LEGACY_HANDLERS.get(name)),
                whole_registered_manager_scope="google" if group == "google" else None,
                scope_complete=False, parallel_safe=False,
                shared_resources=["installed-native:consented-batch"] + (["legacy-manager:"+group] if group else []),
                release_selection="installed_vendor_policy")


def installed_updater_contract(target):
    """Pure eligibility. A framework marker or display name is insufficient."""
    contract = _product(target)
    if (not contract or target.get("team_id") != contract["team_id"]
            or not isinstance(target.get("team_id"), str)
            or not re.fullmatch(r"[A-Z0-9]{10}", target["team_id"])
            or target.get("channel") not in ("stable", "unknown")
            or target.get("presence") != "present"
            or target.get("freshness") != "fresh"):
        return None
    evidence = target.get("evidence", [])
    if not any(e.get("kind") == "vendor_signature"
               and e.get("bundle_id") == contract["bundle_id"]
               and e.get("team_id") == contract["team_id"]
               and e.get("verification") == "installed_code_valid"
               for e in evidence if isinstance(e, dict)):
        return None
    return copy.deepcopy(contract)


def inspect_installed_target(target):
    """Bounded read-only signature inspection of code-owned product candidates."""
    result = copy.deepcopy(target)
    contract = _product(result)
    if not contract:
        return result
    result["team_id"] = None
    result["evidence"] = [e for e in result.get("evidence", [])
                          if e.get("kind") not in ("vendor_signature", "installed_native_updater")]
    path = result.get("real_path")
    if (result.get("presence") != "present" or result.get("freshness") != "fresh"
            or result.get("channel") not in ("stable", "unknown")
            or not isinstance(path, str) or not os.path.isabs(path)
            or not os.path.isdir(path) or os.path.realpath(path) != path
            or result.get("path") != path
            or any(e.get("kind") in ("homebrew", "mas", "app_store_receipt", "enterprise_managed", "protected_root")
                   for e in result["evidence"])):
        return result
    deadline = time.monotonic() + 20
    try:
        signed = None
        for argv in (("codesign", "--verify", "--deep", "--strict", path),
                     ("spctl", "--assess", "--type", "execute", path),
                     ("codesign", "-dv", "--verbose=4", path)):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return result
            signed = subprocess.run(argv, stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, check=True,
                                    timeout=min(10, remaining))
        output = signed.stdout + signed.stderr
        teams = re.findall(r"^TeamIdentifier=(.+)$", output, re.M)
        if (len(output) > 1024 * 1024
                or re.findall(r"^Identifier=(.+)$", output, re.M) != [contract["bundle_id"]]
                or len(teams) != 1 or not re.fullmatch(r"[A-Z0-9]{10}", teams[0])
                or (not contract.get("installed_signer_trust") and teams != [contract["team_id"]])):
            return result
        result["team_id"] = teams[0]
        result["evidence"].extend([
            dict(kind="vendor_signature", bundle_id=contract["bundle_id"],
                 team_id=teams[0], verification="installed_code_valid"),
            dict(kind="installed_native_updater", contract_id=contract["contract_id"],
                 revision=contract["revision"]),
        ])
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return result


def enrich_installed_updater_identities(snapshot):
    """Only known candidates incur signature checks; never launch an application."""
    result = copy.deepcopy(snapshot)
    rows = result.get("instances", [])
    candidates = [(index, row) for index, row in enumerate(rows) if _product(row)]
    if not candidates:
        return result
    # These are independent read-only checks, with a strict per-target deadline.
    # Submit together and assign by original index so completion order cannot
    # change target/consent row numbering.
    with ThreadPoolExecutor(max_workers=min(8, len(candidates))) as pool:
        futures = [(index, pool.submit(inspect_installed_target, row)) for index, row in candidates]
        for index, future in futures:
            try:
                rows[index] = future.result()
            except Exception:
                failed = rows[index]
                failed.update(team_id=None, freshness="stale")
                failed["evidence"] = [e for e in failed.get("evidence", [])
                                      if e.get("kind") not in ("vendor_signature", "installed_native_updater")]
    return result


def verify_installed_updater_executable(path, team_id):
    """Read-only verification for a bridge-selected existing vendor helper."""
    if (not isinstance(path, str) or not os.path.isabs(path) or not os.path.isfile(path)
            or not os.access(path, os.X_OK) or not isinstance(team_id, str)
            or not re.fullmatch(r"[A-Z0-9]{10}", team_id)):
        return False
    deadline = time.monotonic() + 15
    try:
        for argv in (("codesign", "--verify", "--strict", path),
                     ("codesign", "-dv", "--verbose=4", path)):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            result = subprocess.run(argv, stdin=subprocess.DEVNULL, capture_output=True,
                                    text=True, check=True, timeout=min(10, remaining))
        output = result.stdout + result.stderr
        return len(output) <= 1024 * 1024 and re.findall(r"^TeamIdentifier=(.+)$", output, re.M) == [team_id]
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def probe_brew_app_ownership(prefix, target_path, max_entries=4096):
    """Bounded cask-link observation, independent of unrelated receipt errors."""
    if not isinstance(prefix, str) or not os.path.isabs(prefix) or not isinstance(target_path, str):
        return "unknown"
    root = os.path.realpath(prefix)
    target = os.path.realpath(target_path)
    if target == root or target.startswith(root + os.sep):
        return "claimed"
    room = os.path.join(root, "Caskroom")
    try:
        os.lstat(room)
    except FileNotFoundError:
        return "clear"
    except OSError:
        return "unknown"
    if os.path.islink(room) or not os.path.isdir(room):
        return "unknown"
    remaining = max_entries
    pending = [(room, 0)]
    try:
        while pending:
            directory, depth = pending.pop()
            if depth > 5:
                return "unknown"
            with os.scandir(directory) as entries:
                for entry in entries:
                    remaining -= 1
                    if remaining < 0:
                        return "unknown"
                    if entry.name == ".metadata":
                        continue
                    if entry.name.endswith(".app"):
                        if os.path.realpath(entry.path) == target:
                            return "claimed"
                        if entry.is_dir(follow_symlinks=False) and entry.name == os.path.basename(target):
                            return "unknown"
                        continue  # An application's contents do not establish ownership.
                    if entry.is_symlink():
                        return "unknown"
                    if entry.is_dir(follow_symlinks=False):
                        pending.append((entry.path, depth+1))
        return "clear"
    except (OSError, ValueError):
        return "unknown"


def batch_approval_choice(action):
    """Fresh displayed batch consent may supersede a previous manual choice."""
    contract = installed_updater_contract(action.get("expected_target", {}))
    expected_scope = "legacy_same_source_update" if contract and contract["execution_kind"] == "legacy_handler" else "delegated_native_update"
    if (not contract or action.get("action_scope") != expected_scope
            or action.get("installed_updater_contract_sha256") != digest(contract)
            or action.get("whole_registered_manager_scope") != contract.get("whole_registered_manager_scope")
            or action.get("kind") not in ("update", "open_native_updater", "manual")
            or any(r not in ("consent_required", "manual_by_policy") for r in action.get("reason_codes", []))):
        return None
    return "allow_update_same_source" if expected_scope == "legacy_same_source_update" else "allow_native_launch"


def legacy_handler_for(action):
    """Return a closed function identifier; inventory cannot supply commands."""
    contract = installed_updater_contract(action.get("expected_target", {}))
    if (not contract or contract["execution_kind"] != "legacy_handler"
            or action.get("action_scope") != "legacy_same_source_update"
            or action.get("installed_updater_contract_sha256") != digest(contract)):
        raise ValueError("legacy_handler_not_authorized")
    return LEGACY_HANDLERS[contract["registered_name"]]


def legacy_registry_name(action):
    contract = installed_updater_contract(action.get("expected_target", {}))
    if not contract:
        raise ValueError("legacy_product_unknown")
    name = contract.get("registered_name") or "Claude"
    return {"ChatGPT": "ChatGPT / Codex", "Codex": "ChatGPT / Codex", "Docker": "Docker Desktop",
            "Ledger Wallet": "Ledger Live"}.get(name, name)


def legacy_group_members(plan_path, action_id, owner_action_id, *, state_dir=None):
    """Shared updaters need consent for every installed product they may touch."""
    from policy_runtime import load_plan, guard_action
    plan = load_plan(plan_path)
    leader = next(a for a in plan["actions"] if a["action_id"] == action_id)
    contract = installed_updater_contract(leader["expected_target"])
    group = contract.get("legacy_manager_group") if contract else None
    if group is None:
        return [leader]
    if group == "google" and leader.get("whole_registered_manager_scope") != "google":
        raise ValueError("google_whole_manager_scope_not_consented")
    selected = json.loads(os.environ.get("MAC_UPDATE_LEGACY_GROUP_ACTION_IDS", "[]"))
    if not isinstance(selected, list) or any(not isinstance(x, str) for x in selected):
        raise ValueError("invalid_legacy_group")
    members = []
    for action in plan["actions"]:
        candidate = _product(action.get("expected_target", {}))
        if not candidate or candidate.get("legacy_manager_group") != group:
            continue
        if group == "mau" and action["action_id"] not in selected:
            continue
        if (action["action_id"] not in selected
                or action.get("action_scope") != "legacy_same_source_update"
                or not guard_action(plan_path, action["action_id"], state_dir, owner_action_id).get("allowed")):
            raise ValueError("legacy_shared_scope_not_consented")
        members.append(action)
    if not members:
        raise ValueError("legacy_shared_scope_empty")
    return members


def execute_legacy_replacement(plan_path, action_id, source, destination, owner_action_id, *, state_dir=None):
    """Retain the existing signed, idle, rollback-capable bundle transaction."""
    from policy_runtime import load_plan, reobserve_action, guard_action
    from update_transaction import execute_transaction, observe_bundle, TransactionDeferred
    try:
        action = next(a for a in load_plan(plan_path)["actions"] if a["action_id"] == action_id)
        legacy_handler_for(action)
        contract = installed_updater_contract(action["expected_target"])
        if not contract or not contract.get("legacy_release_selector"):
            return 10
        if destination != action.get("target_path") or os.environ.get("MAC_UPDATE_DRY_RUN") == "1":
            return 10
        def authorized():
            return guard_action(plan_path, action_id, state_dir, owner_action_id).get("allowed") is True
        if not authorized():
            return 10
        internal = dict(action, action_scope="direct_update", adapter_id="legacy_verified_bundle",
                        legacy_release_selector=contract["legacy_release_selector"])
        directory = _root(os.path.join(_root(state_dir, True), "transactions"), True)
        execute_transaction(internal, source, directory, lambda: reobserve_action(action),
                            authorized, observe_bundle)
        return 0
    except (TransactionDeferred, StopIteration):
        return 10
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return 1


def legacy_replacement_channel_allowed(action, current):
    """Preserve unknown installed channel only on the closed legacy selector."""
    contract = installed_updater_contract(action.get("expected_target", {}))
    return bool(
        contract and contract["execution_kind"] == "legacy_handler"
        and contract.get("legacy_release_selector")
        and action.get("adapter_id") == "legacy_verified_bundle"
        and action.get("action_scope") == "direct_update"
        and action.get("installed_updater_contract_sha256") == digest(contract)
        and action.get("legacy_release_selector") == contract["legacy_release_selector"]
        and current.get("channel") == action["expected_target"].get("channel") == "unknown"
    )


def _probe_legacy_writer(pid, expected_start_token=None):
    """A PID is authority only with its freshly observed process start token."""
    if type(pid) is not int or pid <= 0:
        return dict(state="unknown", start_token=None)
    try:
        result = subprocess.run(("ps", "-p", str(pid), "-o", "lstart="),
                                stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=5, check=False,
                                env=dict(os.environ, LC_ALL="C"))
        value = result.stdout.strip()
        if result.returncode == 1 and not value and not result.stderr.strip():
            return dict(state="absent", start_token=None)
        if result.returncode != 0 or not value or len(value) > 256 or "\n" in value:
            return dict(state="unknown", start_token=None)
        token = digest(dict(pid=pid, started=value))
        return dict(state="reused" if expected_start_token and token != expected_start_token else "running",
                    start_token=token)
    except (OSError, ValueError, subprocess.SubprocessError):
        return dict(state="unknown", start_token=None)


def record_legacy_writer_start():
    """The child must durably identify itself before any updater mutation."""
    from policy_runtime import _read_json, _atomic_json
    from update_scheduler import assert_active_batch_member, pending_sessions
    try:
        directory = _root(os.environ.get("MAC_UPDATE_SESSION_DIR"), False)
        action_id = os.environ.get("MAC_UPDATE_ACTION_ID")
        owner = os.environ.get("MAC_UPDATE_BATCH_OWNER") or os.environ.get("MAC_UPDATE_BATCH_OWNER_ACTION_ID")
        if directory is None or not action_id or not owner:
            return False
        assert_active_batch_member(owner, action_id)
        path = directory + ".json"
        journal = _read_json(path)
        active = next((r for r in pending_sessions() if r["action_id"] == owner), None)
        if (journal.get("action", {}).get("action_id") != action_id
                or (journal.get("batch_action_id") or action_id) != owner
                or journal.get("state") != "trigger_attempted"
                or active is None or journal.get("lease_id") != active["lease_id"]):
            return False
        pid = os.getppid()
        observed = _probe_legacy_writer(pid)
        if observed["state"] != "running":
            return False
        existing = journal.get("legacy_writer", {})
        if existing.get("pid") not in (None, pid) or existing.get("completed") is True:
            return False
        journal["legacy_writer"] = dict(pid=pid, start_token=observed["start_token"],
                                        started=True, completed=False)
        _atomic_json(path, journal)
        # Recheck the barrier after durable preparation. Recovery cannot release
        # this lease while the recorded writer is live or not yet understood.
        assert_active_batch_member(owner, action_id)
        return True
    except (OSError, ValueError, KeyError, TypeError, StoreError):
        return False


def _legacy_writer_recovery_safe(journal):
    contract = installed_updater_contract(journal["action"].get("expected_target", {}))
    if (not contract or contract["execution_kind"] != "legacy_handler") and "legacy_writer" not in journal:
        return True
    writer = journal.get("legacy_writer")
    if not isinstance(writer, dict):
        return False
    if writer.get("completed") is True:
        return True
    observed = _probe_legacy_writer(writer.get("pid"), writer.get("start_token"))
    return observed["state"] in ("absent", "reused")


def execute_legacy_handler(action, *, plan_path, batch_owner_action_id, action_session_dir):
    """Run one scoped legacy handler; its existing download/identity guards stay."""
    from policy_runtime import SCRIPT_DIR, guard_action, _atomic_json, _read_json
    legacy_handler_for(action)
    if not plan_path or os.environ.get("MAC_UPDATE_DRY_RUN") == "1":
        return dict(status="deferred_by_user", reason_code="dry_run", mutation_started=False, verified=False)
    directory = _root(action_session_dir, True)
    journal_path = directory + ".json"
    journal = _read_json(journal_path)
    journal["legacy_writer"] = dict(pid=None, start_token=None, started=False, completed=False)
    _atomic_json(journal_path, journal)
    group_ids = [a["action_id"] for a in action.get("batch_group_actions", [action])]
    env = dict(os.environ, MAC_UPDATE_PLAN_PATH=plan_path,
               MAC_UPDATE_SESSION_DIR=directory, MAC_UPDATE_ACTION_ID=action["action_id"],
               MAC_UPDATE_BATCH_OWNER_ACTION_ID=batch_owner_action_id,
               MAC_UPDATE_LEGACY_GROUP_ACTION_IDS=json.dumps(group_ids),
               MAC_UPDATE_STAGE_WAIT="0", MAC_UPDATE_INTERNET_SETTLE_SECONDS="0")
    try:
        process = subprocess.Popen(("/bin/bash", os.path.join(SCRIPT_DIR, "update_internet_apps.sh"),
                                    "--scoped-legacy", plan_path, action["action_id"], batch_owner_action_id),
                                   stdin=subprocess.DEVNULL, env=env, close_fds=True)
    except OSError:
        journal = _read_json(journal_path)
        journal.update(state="not_triggered", legacy_writer=dict(pid=None, start_token=None, started=False, completed=True))
        _atomic_json(journal_path, journal)
        return dict(status="update_failed", reason_code="legacy_writer_not_started", verified=False,
                    mutation_started=False, recovery_required=False)
    # Record immediately even if the child has not reached its own pre-mutation
    # barrier yet. A missing token remains uncertain, never proof of completion.
    pid = process.pid
    observed = _probe_legacy_writer(pid)
    journal = _read_json(journal_path)
    journal["legacy_writer"] = dict(pid=pid, start_token=observed["start_token"], started=True, completed=False)
    _atomic_json(journal_path, journal)
    try:
        code = process.wait(timeout=1800)
    except subprocess.TimeoutExpired:
        return dict(status="recovery_required", reason_code="legacy_handler_deadline", verified=False,
                    mutation_started=True, recovery_required=True)
    journal = _read_json(journal_path)
    journal["legacy_writer"]["completed"] = True
    journal["legacy_writer"]["exit_code"] = code
    _atomic_json(journal_path, journal)
    marker = os.path.join(directory, "native_launch_requested")
    if os.path.isfile(marker):
        # The bridge requests a tracked launch instead of creating an unobserved
        # GUI child. Recheck current policy/source after any direct install.
        if not guard_action(plan_path, action["action_id"], None, batch_owner_action_id).get("allowed"):
            return dict(status="deferred_by_user", reason_code="native_fallback_guard_failed", verified=False,
                        mutation_started=True, recovery_required=True)
        journal_path = directory + ".json"
        journal = _read_json(journal_path)
        journal["native_launch_requested"] = True
        _atomic_json(journal_path, journal)
        subprocess.Popen(("open", "-g", action["target_path"]), stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         close_fds=True, start_new_session=True)
    return dict(status="legacy_handler_completed_unconfirmed" if code in (0, 10) else "update_failed",
                reason_code="legacy_result_requires_observation" if code in (0, 10) else "legacy_handler_failed",
                verified=False, mutation_started=True, recovery_required=True,
                native_launch_requested=os.path.isfile(marker))


def observe_batch_versions(actions, results, *, timeout=30, deadline=None,
                           clock=time.monotonic, sleep=time.sleep, observe=None, emit=None):
    """One bounded observation window, with no readiness or latest-version claim."""
    from inventory_collect import read_bundle_static
    if type(timeout) not in (int, float) or not 0 <= timeout <= 120:
        raise ValueError("invalid_observation_budget")
    observe = observe or read_bundle_static
    started = clock()
    end = min(started + timeout, deadline) if deadline is not None else started + timeout
    outcomes = [dict(r, vendor_completion="unconfirmed") for r in results]
    by_id = {r["action_id"]: r for r in outcomes}
    waiting = {a["action_id"]: a for a in actions if a["action_id"] in by_id
               and by_id[a["action_id"]].get("status") != "update_failed"}
    if emit and timeout > 0:
        for key, action in waiting.items():
            emit(action, dict(by_id[key], status="vendor_updater_observing", verified=False))
    while waiting:
        for key, action in list(waiting.items()):
            before = action["expected_target"]
            try:
                observed = observe(action["target_path"])
                rows = observed.get("items", [])
                if observed.get("status") != "ok" or observed.get("complete") is not True or len(rows) != 1:
                    continue
                current = rows[0]
                version = current.get("short_version")
                build = current.get("build_version")
                if (current.get("bundle_id") != before.get("bundle_id") or not isinstance(version, str)
                        or not version or (version == before.get("short_version") and build == before.get("build_version"))):
                    continue
                by_id[key].update(status="observed_version_changed", verified=False,
                                  reason_code="native_version_observed_changed", after=version, after_build=build,
                                  evidence_type="static_installed_metadata", vendor_completion="unconfirmed")
                if emit:
                    emit(action, by_id[key])
                waiting.pop(key)
            except (OSError, ValueError, KeyError, TypeError):
                continue
        remaining = end - clock()
        if not waiting or remaining <= 0:
            break
        sleep(min(1.0, remaining))
    for outcome in outcomes:
        outcome["observation_elapsed_seconds"] = max(0.0, clock() - started)
    return outcomes


def run_delegated_update(action, lease, *, authorize, batch_managed=False, plan_path=None,
                         observation_timeout=0):
    """Issue one code-owned launch and retain its unknown vendor effects lease."""
    from policy_runtime import _atomic_json, _read_json

    outcome = dict(verified=False, status="deferred_by_user", mutation_started=False,
                   reason_code="delegated_native_consent_required", recovery_required=False)
    if lease is None:
        return dict(outcome, reason_code="dry_run" if os.environ.get("MAC_UPDATE_DRY_RUN") == "1" else "mutation_lease_required")
    contract = installed_updater_contract(action.get("expected_target", {}))
    expected_scope = "legacy_same_source_update" if contract and contract["execution_kind"] == "legacy_handler" else "delegated_native_update"
    if (not contract or action.get("action_scope") != expected_scope
            or action.get("adapter_id") != "installed_native:" + contract["contract_id"]
            or action.get("installed_updater_contract_sha256") != digest(contract)
            or os.environ.get("MAC_UPDATE_DRY_RUN") == "1"
            or authorize() is not True):
        if not batch_managed:
            lease.finish("not_triggered", helpers_complete=True)
        return outcome
    path = action.get("target_path")
    if (path != action["expected_target"].get("real_path")
            or not os.path.isdir(path) or os.path.realpath(path) != path):
        if not batch_managed:
            lease.finish("not_triggered", helpers_complete=True)
        return dict(outcome, reason_code="target_changed")
    directory = _root(os.path.join(_root(lease.state_dir, True), "delegated-native"), True)
    session_id = str(uuid.uuid4())
    journal_path = os.path.join(directory, session_id + ".json")
    journal = dict(schema_version=1, session_id=session_id, action=copy.deepcopy(action),
                   lease_id=lease.lease_id, state="prepared", evidence_type="none",
                   batch_action_id=lease.action_id if batch_managed else None)
    _atomic_json(journal_path, journal, exclusive=True)
    # Recheck after durable preparation: a changed policy must not start a launch.
    if authorize() is not True:
        journal["state"] = "not_triggered"
        _atomic_json(journal_path, journal)
        if not batch_managed:
            lease.finish("not_triggered", helpers_complete=True)
        return outcome
    journal["state"] = "trigger_attempted"
    _atomic_json(journal_path, journal)
    try:
        if contract["execution_kind"] == "legacy_handler":
            legacy_result = execute_legacy_handler(action, plan_path=plan_path,
                                                  batch_owner_action_id=lease.action_id,
                                                  action_session_dir=os.path.join(directory, session_id))
        else:
            subprocess.Popen(("open", "-g", path), stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             close_fds=True, start_new_session=True)
            legacy_result = None
    except OSError:
        if contract["execution_kind"] == "legacy_handler":
            journal = _read_json(journal_path)
            journal.update(state="recovery_required", evidence_type="legacy_writer_uncertain")
            _atomic_json(journal_path, journal)
            if not batch_managed:
                lease.pending("legacy_writer_state_unconfirmed")
            return dict(outcome, status="recovery_required", reason_code="legacy_writer_state_unconfirmed",
                        mutation_started=True, recovery_required=True, lease_managed=True,
                        native_session_id=session_id, evidence_type="legacy_writer_uncertain")
        journal["state"] = "not_triggered"
        _atomic_json(journal_path, journal)
        if not batch_managed:
            lease.finish("launch_failed", helpers_complete=True)
        return dict(outcome, status="update_failed", reason_code="native_launch_failed")
    # LaunchServices exit and app PID absence cannot prove helper completion.
    started = legacy_result is None or legacy_result.get("mutation_started") is not False
    if not batch_managed:
        if started:
            lease.pending("delegated_vendor_completion_unconfirmed")
        else:
            lease.finish("not_triggered", helpers_complete=True)
    journal = _read_json(journal_path)
    journal.update(state="vendor_completion_unconfirmed" if started else "not_triggered", evidence_type="launch_requested" if started else "none")
    _atomic_json(journal_path, journal)
    result = dict(outcome, status="triggered_unconfirmed", mutation_started=True,
                reason_code="delegated_vendor_completion_unconfirmed", recovery_required=True,
                lease_managed=True, native_session_id=session_id, evidence_type="launch_requested")
    if legacy_result is not None:
        result.update(legacy_result)
    from tui_events import emit_target
    timeout = observation_timeout if contract["execution_kind"] == "native_window" or result.get("native_launch_requested") else 0
    observed = observe_batch_versions(
        [action], [dict(result, action_id=action["action_id"])], timeout=timeout,
        deadline=action.get("batch_observation_deadline_monotonic"), emit=emit_target,
    )[0]
    return observed


def pending_delegated_sessions(state_dir=None):
    """Return only journals whose unresolved lease still exists."""
    from policy_runtime import _read_json
    from update_scheduler import pending_sessions
    root = _root(state_dir, False)
    if root is None:
        return []
    directory = os.path.join(root, "delegated-native")
    if not os.path.lexists(directory):
        return []
    _root(directory, False)
    leases = {r["lease_id"]: r for r in pending_sessions(state_dir)}
    names = sorted(os.listdir(directory))
    if len(names) > 256:
        raise ValueError("delegated_journal_limit")
    rows = []
    for name in names:
        if not re.fullmatch(r"[0-9a-f-]{36}\.json", name):
            continue
        journal = _read_json(os.path.join(directory, name))
        lease = leases.get(journal.get("lease_id"))
        if (journal.get("schema_version") != 1
                or journal.get("session_id") + ".json" != name):
            raise ValueError("invalid_delegated_journal")
        if (lease and lease["action_id"] == (journal.get("batch_action_id") or journal.get("action", {}).get("action_id"))
                and journal.get("state") not in ("reconciled", "not_triggered")):
            rows.append(journal)
    return rows


def reconcile_delegated_update(session_id, *, state_dir=None, confirmed=False):
    """Fresh target identity plus explicit human completion attestation.

    This is recovery evidence supplied by the user, never product live acceptance
    or proof that the installed version is the latest release.
    """
    if confirmed is not True:
        return False
    rows = pending_delegated_sessions(state_dir)
    journal = next((r for r in rows
                    if r["session_id"] == session_id), None)
    if journal is None:
        return False
    if len([r for r in rows if r["lease_id"] == journal["lease_id"]]) != 1:
        return False
    return reconcile_delegated_batch([session_id], state_dir=state_dir, confirmed=True)


def reconcile_delegated_batch(session_ids, *, state_dir=None, confirmed=False):
    """Reobserve every member before releasing a shared batch lease once."""
    from policy_runtime import reobserve_action, _atomic_json
    from user_policy import identity_fingerprint, source_fingerprint
    from update_scheduler import reconcile_session, pending_sessions
    if confirmed is not True or not isinstance(session_ids, list) or not session_ids:
        return False
    rows = pending_delegated_sessions(state_dir)
    selected = [r for r in rows if r["session_id"] in session_ids]
    if len(selected) != len(set(session_ids)) or len({r["lease_id"] for r in selected}) != 1:
        return False
    lease_id = selected[0]["lease_id"]
    members = [r for r in rows if r["lease_id"] == lease_id]
    if set(session_ids) != {r["session_id"] for r in members}:
        return False
    lease = next((r for r in pending_sessions(state_dir) if r["lease_id"] == lease_id), None)
    if lease is None or lease.get("status") == "active":
        return False
    if any(not _legacy_writer_recovery_safe(journal) for journal in members):
        return False
    for journal in members:
        actions = [journal["action"]] + journal["action"].get("batch_group_actions", [])
        seen = set()
        for action in actions:
            if action["action_id"] in seen:
                continue
            seen.add(action["action_id"])
            current = reobserve_action(action)
            resolution = current.get("resolution", {})
            if (not installed_updater_contract(current)
                    or current.get("presence") != "present" or current.get("freshness") != "fresh"
                    or identity_fingerprint(current) != action.get("expected_identity")
                    or source_fingerprint(current, resolution) != action.get("expected_source")):
                return False
    directory = os.path.join(_root(state_dir, False), "delegated-native")
    for journal in members:
        journal.update(state="user_confirmed_vendor_finished", verified=False,
                       evidence_type="user_reported_vendor_finished")
        _atomic_json(os.path.join(directory, journal["session_id"]+".json"), journal)
    if not reconcile_session(lease_id, dict(action_id=lease["action_id"],
            helpers_complete=True, target_reobserved=True,
            evidence_type="user_reported_vendor_finished"), state_dir):
        return False
    for journal in members:
        journal["state"] = "reconciled"
        _atomic_json(os.path.join(directory, journal["session_id"]+".json"), journal)
    return True


def native_recovery_cli(*, state_dir=None, stream=None, output=None):
    """Interactive, default-cancel recovery; -y and closed stdin never consent."""
    stream = stream if stream is not None else sys.stdin
    output = output if output is not None else sys.stdout

    def message(key, fallback):
        return os.environ.get(key) or fallback

    sessions = pending_delegated_sessions(state_dir)
    groups = {}
    for row in sessions:
        groups.setdefault(row["lease_id"], []).append(row)
    rows = list(groups.values())
    print(message("L_NATIVE_RECOVERY_TITLE", "Unconfirmed vendor updater sessions"), file=output)
    if not rows:
        print(message("L_NATIVE_RECOVERY_NONE", "No delegated vendor updater session needs recovery."), file=output)
        return 0
    for index, group in enumerate(rows, 1):
        names = [r["action"]["expected_target"].get("name") or r["action"]["expected_target"]["bundle_id"] for r in group]
        label = "{} | {}".format(", ".join(names), group[0]["batch_action_id"] or group[0]["session_id"])
        print(str(index) + ": " + "".join(c for c in label if c.isprintable())[:1000], file=output)
    cancelled = message("L_NATIVE_RECOVERY_CANCELLED", "No recovery confirmed. Vendor resources remain reserved.")
    if (not stream.isatty() or os.environ.get("MAC_UPDATE_YES") == "1"
            or os.environ.get("MAC_UPDATE_NONINTERACTIVE") == "1"):
        print(cancelled, file=output)
        return 10
    deadline = time.monotonic() + 120

    def answer(prompt):
        print(prompt, file=output, flush=True)
        if os.environ.get("MAC_UPDATE_TUI_CHILD") == "1":
            print("@@MAC_UPDATE_PROMPT", file=output, flush=True)
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([stream], [], [], remaining)[0]:
            return ""
        value = stream.readline(4097)
        return value.strip() if len(value) <= 4096 else ""

    selection = answer(message("L_NATIVE_RECOVERY_SELECT", "Select one session number to review, or press Enter to cancel."))
    if not selection.isdigit() or not 1 <= int(selection) <= len(rows):
        print(cancelled, file=output)
        return 10
    selected = rows[int(selection) - 1]
    print(message("L_NATIVE_RECOVERY_SCOPE", "This confirms only that the vendor updater and its installers have finished. It does not confirm the latest version."), file=output)
    for member in selected:
        app = member["action"]["expected_target"]
        detail = "{} | {} | {}".format(app.get("name") or app["bundle_id"], app["real_path"], member["action"]["expected_resolution"].get("source", "unknown"))
        print("".join(c for c in detail if c.isprintable())[:1000], file=output)
    value = answer(message("L_NATIVE_RECOVERY_CONFIRM", "After checking the app and vendor updater, type FINISHED to confirm no installer or download is still running. Enter cancels."))
    if value != "FINISHED":
        print(cancelled, file=output)
        return 10
    if not reconcile_delegated_batch([r["session_id"] for r in selected], state_dir=state_dir, confirmed=True):
        print(message("L_NATIVE_RECOVERY_REJECTED", "Fresh identity or source checks failed. The session remains unresolved."), file=output)
        return 10
    print(message("L_NATIVE_RECOVERY_DONE", "Your completion report was recorded and the resource reservation was released. No update was verified."), file=output)
    return 0
