"""User-facing planning; local observation is separate from permission to act."""

import json
import math
import os
import select
import sys
import time
from collections import Counter
from pathlib import Path

from tui_events import emit_plan
from inventory_migration import collect_local_snapshot, rebuild_inventory
from inventory_store import StoreError, default_root, load_snapshot
from app_recipes import load_recipes
from policy_runtime import (
    build_runtime_plan, record_plan_decisions, save_plan, load_policies,
    set_installed_update_default, rebind_plan_policies,
)
from user_policy import installed_update_default


def message(key, fallback):
    return os.environ.get(key) or fallback


def safe_text(value):
    return "".join(c for c in str(value or "") if c.isprintable())[:500]


def approval_choice(action):
    """Use the identical narrow grant predicate in the menu and its parser."""
    if action["kind"] not in ("update", "open_native_updater", "check") or any(
        r != "consent_required" for r in action["reason_codes"]
    ):
        return None
    return {
        "manager_update": "allow_update_same_source",
        "direct_update": "allow_update_same_source",
        "legacy_same_source_update": "allow_update_same_source",
        "native_launch": "allow_native_launch",
        "delegated_native_update": "allow_native_launch",
        "network_check": "allow_check",
    }.get(action["action_scope"])


def batch_approval_choice(action):
    """The engine owns eligibility; UI mode and metadata cannot create authority."""
    from installed_native_updaters import batch_approval_choice as eligible_choice
    choice = eligible_choice(action)
    return choice if choice in ('allow_native_launch', 'allow_update_same_source') else None


def internet_batch_requested():
    return (os.environ.get('MAC_UPDATE_AUTOMATIC_INTERNET_BATCH') == '1'
            and os.environ.get('MAC_UPDATE_SKIP_INTERNET') != '1')


def review_installed_update_agreement(stream, output, timeout=120):
    """One explicit saved-profile agreement; unattended flags cannot accept."""
    print(message('L_PLAN_DEFAULT_SCOPE',
        'Enable updates for supported apps and packages already installed in this profile, '
        'using their current sources. Native updaters may open apps; approved handlers may '
        'download and replace them. Google updater groups may update ALL registered Google '
        'products, including products outside this catalog; the complete registration list '
        'is unknown. Saved manual, ignored and deferred choices stay in force. DeepSeek, '
        'source conflicts and protected apps remain blocked. This does not install catalog '
        'apps or grant permission to quit or restart apps.'), file=output)
    if (not stream.isatty() or os.environ.get('MAC_UPDATE_YES') == '1'
            or os.environ.get('MAC_UPDATE_NONINTERACTIVE') == '1'):
        print(message('L_PLAN_NO_CONSENT', 'No new permission granted. Pending choices remain deferred.'), file=output)
        return False
    print(message('L_PLAN_DEFAULT_QUESTION',
        'Type ENABLE to save this agreement for future runs. Empty or q leaves it disabled. '
        'Change it later in Preferences.'), file=output, flush=True)
    if os.environ.get('MAC_UPDATE_TUI_CHILD') == '1':
        print('@@MAC_UPDATE_PROMPT installed_updates', file=output, flush=True)
    try:
        ready, _, _ = select.select([stream], [], [], max(0, timeout))
    except (OSError, ValueError):
        return False
    if not ready:
        print(message('L_PLAN_TIMEOUT', 'Choice timed out. No new permissions changed.'), file=output)
        return False
    try:
        answer = stream.readline(4097)
    except (OSError, ValueError):
        return False
    return len(answer) <= 4096 and answer.strip() == 'ENABLE'


def review_internet_batch(plan, stream, output, timeout=120):
    """One exact, fresh batch approval; all displayed pages precede a grant."""
    choices = {a['action_id']: batch_approval_choice(a) for a in plan['actions']}
    actions = [a for a in plan['actions'] if choices[a['action_id']] is not None]
    print(message('L_PLAN_BATCH_TITLE_FMT', 'Automatic Internet batch: %s eligible apps.') % len(actions), file=output)
    if not actions:
        print(message('L_PLAN_BATCH_NONE', 'No eligible automatic Internet apps. Unsupported apps and DeepSeek stay manual; exclusions and source checks remain in force.'), file=output)
        return {}
    print(message('L_PLAN_BATCH_SCOPE', 'Review each listed scope, including any explicitly disclosed vendor-manager group. Their native windows or approved same-source handlers may run concurrently. Approving saves automatic permissions for these listed apps, replacing their saved manual choices. Native updaters select releases using their existing channel settings. DeepSeek stays manual. Leave apps open; completion remains unconfirmed until recovery review.'), file=output)
    if (not stream.isatty() or os.environ.get('MAC_UPDATE_YES') == '1'
            or os.environ.get('MAC_UPDATE_NONINTERACTIVE') == '1'):
        print(message('L_PLAN_NO_CONSENT', 'No new permission granted. Pending choices remain deferred.'), file=output)
        return {}
    page, page_size, seen = 0, 10, set()
    pages = (len(actions) + page_size - 1) // page_size
    deadline = time.monotonic() + max(0, timeout)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print(message('L_PLAN_TIMEOUT', 'Choice timed out. No new permissions changed.'), file=output)
            return {}
        start, end = page * page_size, min((page + 1) * page_size, len(actions))
        print(message('L_PLAN_PAGE_FMT', 'Page %s/%s. Entries %s-%s of %s.') % (page + 1, pages, start + 1, end, len(actions)), file=output)
        for index in range(start, end):
            action = actions[index]
            seen.add(action['action_id'])
            label = (message('L_PLAN_SCOPE_NATIVE', 'Open the reviewed native updater') if choices[action['action_id']] == 'allow_native_launch' else scope_label(action))
            print('%s: %s | %s | %s' % (index + 1, action_name(action), source_label(action), label), file=output)
            for effect in dict.fromkeys([action['target_path']] + action.get('artifact_effects', [])):
                if effect:
                    print('    ' + safe_text(effect), file=output)
        print(message('L_PLAN_BATCH_QUESTION', 'Type AUTO to approve this exact concurrent batch after viewing every page. DeepSeek stays manual. n next, p previous. Empty or q defers this batch without changing saved permissions.'), file=output)
        print(message('L_PLAN_WAITING_FMT', 'Waiting for your choice (up to %s seconds remaining).') % math.ceil(remaining), file=output, flush=True)
        if os.environ.get('MAC_UPDATE_TUI_CHILD') == '1':
            print('@@MAC_UPDATE_PROMPT native_batch', file=output, flush=True)
        ready, _, _ = select.select([stream], [], [], remaining)
        if not ready:
            print(message('L_PLAN_TIMEOUT', 'Choice timed out. No new permissions changed.'), file=output)
            return {}
        answer = stream.readline(4097)
        if len(answer) > 4096:
            print(message('L_PLAN_INVALID', 'Invalid selection. No permissions changed.'), file=output)
            return {}
        answer = answer.strip()
        if not answer or answer.lower() == 'q':
            print(message('L_PLAN_CANCELLED', 'Choice cancelled. No new permissions changed.'), file=output)
            return {}
        if answer.lower() in ('n', 'p'):
            page = max(0, min(pages - 1, page + (1 if answer.lower() == 'n' else -1)))
            continue
        if answer == 'AUTO' and len(seen) == len(actions):
            return {a['action_id']: choices[a['action_id']] for a in actions}
        if answer == 'AUTO':
            print(message('L_PLAN_BATCH_READ_ALL', 'Review every page before approving the batch. No permission has changed.'), file=output)
            continue
        print(message('L_PLAN_INVALID', 'Invalid selection. No permissions changed.'), file=output)
        return {}


def source_label(action):
    source = action["expected_resolution"]["source"]
    brands = {"homebrew": "Homebrew", "npm": "npm", "app_store": "App Store"}
    labels = {
        "vendor": ("L_PLAN_SOURCE_VENDOR", "Vendor source"),
        "apple_system": ("L_PLAN_SOURCE_SYSTEM", "macOS"),
        "enterprise_managed": ("L_PLAN_SOURCE_MANAGED", "Managed by your organization"),
        "conflict": ("L_PLAN_SOURCE_CONFLICT", "Conflicting sources"),
    }
    if source in brands:
        return brands[source]
    return message(*labels.get(source, ("L_PLAN_SOURCE_UNKNOWN", "Unknown source")))


def action_name(action):
    target = action["expected_target"]
    name = safe_text(target.get("name") or target.get("source_identity")
                     or target.get("bundle_id") or action["target_path"])
    if action["expected_resolution"]["source"] == "homebrew" and name.startswith(("formula:", "cask:")):
        name = name.partition(":")[2]
    return name


def preview_group(action):
    if internet_batch_requested() and batch_approval_choice(action) is not None:
        return 1
    if approval_choice(action) is not None:
        return 1 if "consent_required" in action["reason_codes"] else 0
    if action["kind"] == "skip" or (action["kind"] == "manual" and (
        any(r in action["reason_codes"] for r in ("manual_by_policy", "ignored_by_policy", "deferred_by_user", "deepseek_manual_only"))
        or not action["reason_codes"]
    )):
        return 3
    return 2


def format_preview(plan):
    """Keep the human preview short; full evidence remains in explicit JSON."""
    actions = plan["actions"]
    groups = Counter(preview_group(a) for a in actions)
    lines = [
        message("L_PLAN_TITLE", "Local update plan"),
        message("L_PLAN_PREVIEW_ONLY", "Preview only. No updates, app launches or files changed."),
        message("L_PLAN_PREVIEW_COUNT_FMT", "Local targets: %s") % len(actions),
        message("L_PLAN_PREVIEW_SUMMARY_FMT", "Eligible scopes: %s; need consent: %s; blocked: %s; manual or skipped: %s.")
        % tuple(groups[i] for i in range(4)),
        "",
    ]
    if internet_batch_requested():
        count = sum(batch_approval_choice(action) is not None for action in actions)
        lines[2:2] = [message('L_PLAN_BATCH_TITLE_FMT', 'Automatic Internet batch: %s eligible apps.') % count,
                      message('L_PLAN_BATCH_PREVIEW', 'Requested automatic batch. Run still requires fresh approval for the exact eligible scopes.')]
    labels = {
        0: ("L_PLAN_PREVIEW_ELIGIBLE", "Eligible scope; no update executed"),
        1: ("L_PLAN_PREVIEW_CONSENT", "Consent required for this scope"),
        2: ("L_PLAN_PREVIEW_BLOCKED", "Blocked pending evidence or source review"),
        3: ("L_PLAN_PREVIEW_MANUAL", "Manual review"),
    }
    # A consent-ready scope must not be hidden behind hundreds of partial scans.
    ordered = sorted(actions, key=lambda a: {1: 0, 0: 1, 2: 2, 3: 3}[preview_group(a)])
    names = Counter((action_name(a), source_label(a), a.get("from_version")) for a in actions)
    for action in ordered[:10]:
        name, source = action_name(action), source_label(action)
        label = message(*labels[preview_group(action)])
        if 'unsupported_automatic_method' in action['reason_codes']:
            label = message('L_PLAN_PREVIEW_UNSUPPORTED', 'Automatic update method unavailable; update manually')
        if action["kind"] == "skip":
            label = message("L_PLAN_PREVIEW_SKIPPED", "Skipped by policy")
        version = safe_text(action.get("from_version")) or "?"
        if action.get("to_version"):
            version += " -> " + safe_text(action["to_version"])
        lines.append("  {} ({}) | {} | {}".format(name, version, source, label))
        if names[(name, source, action.get("from_version"))] > 1:
            lines.append("    " + safe_text(action["target_path"]))
    if len(actions) > 10:
        lines.append(message("L_PLAN_PREVIEW_MORE_FMT", "%s more targets in JSON.") % (len(actions) - 10))
    lines.extend(["", message("L_PLAN_PREVIEW_JSON_HINT", "Full plan: --dry-run --json-summary (or --plan).")])
    return "\n".join(lines)


def write_preview(text):
    # Explicit ASCII output settings must not turn an observed Unicode app name
    # into a traceback. Normal UTF-8 terminals retain the original characters.
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    try:
        sys.stdout.write((text + "\n").encode(encoding, "backslashreplace").decode(encoding))
        sys.stdout.flush()  # Observe a closed reader here, before interpreter shutdown.
    except BrokenPipeError:
        # Prevent a second failure when Python flushes stdout on exit (for
        # example when the user pipes a preview to head).
        with open(os.devnull, "w") as sink:
            os.dup2(sink.fileno(), sys.stdout.fileno())


def apply_filters(plan):
    skipped = {
        adapter
        for adapter, flag in [
            ("homebrew", "BREW"),
            ("npm", "NPM"),
            ("app_store", "APPSTORE"),
        ]
        if os.environ.get("MAC_UPDATE_SKIP_" + flag) == "1"
    }
    plan["actions"] = [
        a
        for a in plan["actions"]
        if a["adapter_id"] not in skipped
        and not (
            os.environ.get("MAC_UPDATE_SKIP_INTERNET") == "1"
            and a["expected_resolution"]["source"]
            not in ("homebrew", "npm", "app_store")
        )
    ]
    return plan


def parse_choices(text, actions):
    """A finite explicit list; an empty answer never grants permission."""
    choices = {}
    for token in text.strip().split(","):
        token = token.strip().lower()
        if not token:
            continue
        if token.isdigit():
            token = "a" + token
        prefix = token[0] if token[0] in "adimr" else ""
        if not prefix or not token[1:].isdigit():
            raise ValueError("invalid_selection")
        number = int(token[1:])
        if not 1 <= number <= len(actions):
            raise ValueError("invalid_selection")
        action = actions[number - 1]
        choice = {
            "d": "defer",
            "i": "ignore",
            "m": "preserve_source",
            "r": "reset",
        }.get(prefix)
        if prefix == "a":
            choice = approval_choice(action)
            if choice is None:
                raise ValueError("action_not_eligible")
        if action["action_id"] in choices:
            raise ValueError("duplicate_selection")
        choices[action["action_id"]] = choice
    return choices


def scope_label(action):
    if action.get('whole_registered_manager_scope') == 'google':
        return message('L_PLAN_SCOPE_GOOGLE_GROUP', 'Google updater group: may download or replace ALL registered Google products, including products outside this catalog. The complete registration list is unknown; this scope is broader than the listed apps.')
    scope = action["action_scope"]
    if scope == "manager_update":
        return message("L_PLAN_SCOPE_MANAGER_FMT", "Update using %s") % source_label(action)
    labels = {
        "direct_update": ("L_PLAN_SCOPE_DIRECT", "Replace the existing app with the reviewed candidate"),
        "legacy_same_source_update": ("L_PLAN_SCOPE_LEGACY", "Run the existing same-source handler; it may download and replace the app"),
        "native_launch": ("L_PLAN_SCOPE_NATIVE", "Open the reviewed native updater"),
        "delegated_native_update": ("L_PLAN_SCOPE_DELEGATED", "Open the installed signed vendor app and let its updater choose the offered release using its existing channel settings. Leave the app open. Completion is unconfirmed; other updates wait for recovery confirmation."),
        "network_check": ("L_PLAN_SCOPE_CHECK", "Check the reviewed source"),
    }
    return message(*labels.get(scope, ("L_PLAN_SCOPE_MANUAL", "Manual policy only")))


def review_choices(plan, stream, output, timeout=120):
    preferences = os.environ.get("MAC_UPDATE_PREFERENCES") == "1"
    candidates = [a for a in plan["actions"] if "consent_required" in a["reason_codes"] or (
        "source_conflict" in a["reason_codes"] and not any(
            r in a["reason_codes"] for r in ("manual_by_policy", "ignored_by_policy", "deferred_by_user")
        )
    )]
    blocked = sum(approval_choice(a) is None for a in candidates)
    actions = plan["actions"] if preferences else [a for a in candidates if approval_choice(a) is not None]
    print(message("L_PLAN_TITLE", "Local update plan"), file=output)
    if blocked:
        print(message("L_PLAN_BLOCKED_FMT", "%s targets cannot be approved in this review. Inspect --plan; use --preferences to manage saved choices.") % blocked, file=output)
    if not actions:
        key, fallback = (("L_PLAN_NO_ELIGIBLE", "No actions can be approved now. Saved permissions remain in effect.") if blocked else (
            "L_PLAN_NO_CHOICES", "No new decisions required. Use --preferences to review saved choices."
        ))
        print(message(key, fallback), file=output)
        return {}
    if (not stream.isatty() or os.environ.get("MAC_UPDATE_YES") == "1"
            or os.environ.get("MAC_UPDATE_NONINTERACTIVE") == "1"):
        print(message("L_PLAN_NO_CONSENT", "No new permission granted. Pending choices remain deferred."), file=output)
        return {}
    page, page_size, seen = 0, 10, set()
    pages = (len(actions) + page_size - 1) // page_size
    deadline = time.monotonic() + max(0, timeout)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            print(message("L_PLAN_TIMEOUT", "Choice timed out. No new permissions changed."), file=output)
            return {}
        start = page * page_size
        end = min(start + page_size, len(actions))
        print(message("L_PLAN_PAGE_FMT", "Page %s/%s. Entries %s-%s of %s.") % (page + 1, pages, start + 1, end, len(actions)), file=output)
        for index in range(start, end):
            action = actions[index]
            seen.add(action["action_id"])
            version = safe_text(action.get("from_version"))
            name = action_name(action) + (" (" + version + ")" if version else "")
            label = scope_label(action)
            if approval_choice(action) is None:
                label += " | " + (message("L_PLAN_PREVIEW_MANUAL", "Manual review") if preview_group(action) == 3 else message(
                    "L_PLAN_PREVIEW_BLOCKED", "Blocked pending evidence or source review"
                ))
            print("{}: {} | {}".format(index + 1, name, label), file=output)
            effects = list(dict.fromkeys([action["target_path"]] + action["artifact_effects"]))
            for effect in effects:
                if effect:
                    print("    " + safe_text(effect), file=output)
        question = ("L_PLAN_PREFERENCES_CHOICES", "Choose explicit entries: 1,3 (or a1,a3) allow only those scopes; dN defer, iN ignore, mN manual, rN reset. n next, p previous. Empty or q continues without new consent.") if preferences else (
            "L_PLAN_REVIEW_CHOICES", "Which items do you allow? Enter numbers, for example 1,3 (a1,a3 also works). n next, p previous. Empty or q continues without new consent."
        )
        print(message(*question), file=output)
        print(message("L_PLAN_WAITING_FMT", "Waiting for your choice (up to %s seconds remaining).") % math.ceil(remaining), file=output, flush=True)
        if os.environ.get("MAC_UPDATE_TUI_CHILD") == "1":
            print("@@MAC_UPDATE_PROMPT", file=output, flush=True)
        ready, _, _ = select.select([stream], [], [], remaining)
        if not ready:
            print(message("L_PLAN_TIMEOUT", "Choice timed out. No new permissions changed."), file=output)
            return {}
        answer = stream.readline(4097)
        if len(answer) > 4096:
            print(message("L_PLAN_INVALID", "Invalid selection. No permissions changed."), file=output)
            return {}
        answer = answer.strip().lower()
        if not answer or answer == "q":
            print(message("L_PLAN_CANCELLED", "Choice cancelled. No new permissions changed."), file=output)
            return {}
        if answer in ("n", "p"):
            page = max(0, min(pages - 1, page + (1 if answer == "n" else -1)))
            continue
        try:
            choices = parse_choices(answer, actions)
            if not set(choices).issubset(seen):
                raise ValueError("selection_not_displayed")
            return choices
        except ValueError:
            print(message("L_PLAN_INVALID", "Invalid selection. No permissions changed."), file=output)
            return {}


def inventory_counts(before, after):
    previous = {
        a["instance_id"]: a
        for a in (before or {}).get("instances", [])
        if a["presence"] != "absent"
    }
    current = {
        a["instance_id"]: a for a in after["instances"] if a["presence"] != "absent"
    }
    return dict(
        inventory_entries_added=len(current.keys() - previous.keys()),
        inventory_entries_removed=len(previous.keys() - current.keys()),
        inventory_version_fields_changed=sum(
            previous[k].get("short_version") != current[k].get("short_version")
            for k in current.keys() & previous.keys()
            if current[k]["freshness"] == "fresh"
        ),
        observed_package_changes=0,
    )


def refresh_inventory(script_dir):
    previous = load_snapshot()
    snapshot = collect_local_snapshot(script_dir)
    rebuild_inventory(
        snapshot,
        default_root(),
        str(Path(script_dir) / "APPLICATIONS.md"),
        os.environ.get("MAC_LANG", "en"),
        load_recipes(str(Path(script_dir) / "config/app_recipes.json")),
    )
    session = os.environ.get("MAC_UPDATE_SESSION_DIR")
    if session:
        counts = inventory_counts(previous, snapshot)
        path = Path(session) / "run_counts.json"
        if path.is_file() and not path.is_symlink():
            old = json.loads(path.read_text())
            counts = {key: counts[key] + old.get(key, 0) for key in counts}
        fd = os.open(
            str(path), os.O_CREAT | os.O_TRUNC | os.O_WRONLY | os.O_NOFOLLOW, 0o600
        )
        with os.fdopen(fd, "w") as handle:
            json.dump(counts, handle)
    return snapshot


def prepare_run(script_dir, session_dir, stream=None, output=None):
    stream = sys.stdin if stream is None else stream
    output = sys.stdout if output is None else output
    scan_code = 0
    from update_transaction import recover_pending_transactions

    recovery = recover_pending_transactions()
    if any(item.get("state") == "recovery_required" for item in recovery):
        print("recovery_required", file=output)
        scan_code = 10
    try:
        if os.environ.get("MAC_UPDATE_SKIP_PRESCAN") != "1":
            refresh_inventory(script_dir)
    except (StoreError, OSError, ValueError):
        scan_code = 10
        print(
            message(
                "L_INVENTORY_CONFLICT",
                "Inventory unchanged. Review with build_inventory.sh --migration --preview.",
            ),
            file=output,
        )
    plan = apply_filters(build_runtime_plan(script_dir))
    policies = load_policies()
    agreed = installed_update_default(policies)
    if not agreed and scan_code == 0 and review_installed_update_agreement(stream, output):
        policies = set_installed_update_default(True, allow_registered_vendor_groups=True)
        plan = rebind_plan_policies(plan, policies)
        agreed = True
    emit_plan(plan, output)
    batch_requested = internet_batch_requested() and not agreed
    batch_choices = review_internet_batch(plan, stream, output) if batch_requested and scan_code == 0 else {}
    if batch_choices:
        plan = record_plan_decisions(plan, batch_choices)
    ordinary_plan = dict(plan, actions=[a for a in plan['actions'] if not (
        batch_requested and batch_approval_choice(a) is not None)])
    choices = review_choices(ordinary_plan, stream, output) if scan_code == 0 else {}
    if choices:
        plan = record_plan_decisions(plan, choices)
    if batch_requested and not batch_choices:
        # A declined batch also suspends earlier grants for this run. This
        # ephemeral deferral never changes saved per-target policy.
        for action in plan['actions']:
            if batch_approval_choice(action) is not None:
                action['reason_codes'] = list(dict.fromkeys(action['reason_codes'] + ['deferred_by_user']))
                action['kind'] = 'skip'
    emit_plan(plan, output)
    save_plan(plan, str(Path(session_dir) / "update-plan.json"))
    (Path(session_dir) / "inventory_status.txt").write_text(
        str(scan_code), encoding="utf-8"
    )
    return scan_code


def build_preferences_plan(script_dir):
    """Review the last saved inventory without invoking host tools."""
    from policy_runtime import _recipe_catalog, load_policies, utc_now
    from source_resolver import resolve_snapshot
    from update_plan import build_plan

    root = default_root()
    snapshot = load_snapshot(root)
    if snapshot is None:
        raise StoreError("saved inventory unavailable")
    policies = load_policies(root)
    if policies.get("profile_id") not in (None, snapshot["profile_id"]):
        raise ValueError("policy_profile_mismatch")
    return build_plan(snapshot, resolve_snapshot(snapshot, _recipe_catalog(script_dir)), policies, utc_now())


def main(script_dir, mode, session_dir=None):
    try:
        if mode == "preferences":
            os.environ["MAC_UPDATE_PREFERENCES"] = "1"
            plan = apply_filters(build_preferences_plan(script_dir))
            choices = review_choices(plan, sys.stdin, sys.stdout)
            if choices:
                record_plan_decisions(plan, choices)
            return 0
        if mode == "preview":
            plan = apply_filters(build_runtime_plan(script_dir))
            machine = (os.environ.get("MAC_UPDATE_PLAN_ONLY") == "1"
                       or os.environ.get("MAC_UPDATE_JSON_SUMMARY") == "1")
            if not machine:
                emit_plan(plan)
            write_preview(json.dumps(plan, ensure_ascii=True) if machine else format_preview(plan))
            return 0
        if mode == "prepare":
            return prepare_run(script_dir, session_dir)
        if mode == "refresh":
            refresh_inventory(script_dir)
            return 0
        return 1
    except (OSError, ValueError, StoreError, TypeError):
        print(
            message("L_PLAN_FAILED", "Plan unavailable. No app actions authorized."),
            file=sys.stderr,
        )
        return 10
