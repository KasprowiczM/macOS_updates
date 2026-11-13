"""User-facing planning; local observation is separate from permission to act."""

import json
import os
import select
import sys
from pathlib import Path

from inventory_migration import collect_local_snapshot, rebuild_inventory
from inventory_store import StoreError, default_root, load_snapshot
from app_recipes import load_recipes
from policy_runtime import build_runtime_plan, record_plan_decisions, save_plan


def message(key, fallback):
    return os.environ.get(key) or fallback


def safe_text(value):
    return "".join(c for c in str(value or "") if c.isprintable())[:500]


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
            if action["kind"] not in ("update", "open_native_updater", "check") or any(
                r not in ("consent_required",) for r in action["reason_codes"]
            ):
                raise ValueError("action_not_eligible")
            choice = {
                "manager_update": "allow_update_same_source",
                "direct_update": "allow_update_same_source",
                "native_launch": "allow_native_launch",
                "network_check": "allow_check",
            }.get(action["action_scope"])
            if choice is None:
                raise ValueError("action_not_eligible")
        if action["action_id"] in choices:
            raise ValueError("duplicate_selection")
        choices[action["action_id"]] = choice
    return choices


def review_choices(plan, stream, output, timeout=120):
    actions = (
        plan["actions"]
        if os.environ.get("MAC_UPDATE_PREFERENCES") == "1"
        else [
            a
            for a in plan["actions"]
            if "consent_required" in a["reason_codes"]
            or (
                "source_conflict" in a["reason_codes"]
                and not any(
                    r in a["reason_codes"]
                    for r in (
                        "manual_by_policy",
                        "ignored_by_policy",
                        "deferred_by_user",
                    )
                )
            )
        ]
    )
    print(message("L_PLAN_TITLE", "Local update plan"), file=output)
    if not actions:
        print(
            message(
                "L_PLAN_NO_CHOICES",
                "No new decisions required. Use --preferences to review saved choices.",
            ),
            file=output,
        )
        return {}
    for index, action in enumerate(actions, 1):
        target = action["expected_target"]
        name = (
            target.get("name")
            or target.get("source_identity")
            or target.get("bundle_id")
        )
        print(
            "{}: {} | {} | {} | {}".format(
                index,
                safe_text(name),
                safe_text(action["target_path"]),
                safe_text(action["expected_resolution"]["source"]),
                safe_text(action["action_scope"]),
            ),
            file=output,
        )
        if action["artifact_effects"]:
            print(
                "   " + ", ".join(safe_text(p) for p in action["artifact_effects"]),
                file=output,
            )
        if action["reason_codes"]:
            print("   " + ", ".join(action["reason_codes"]), file=output)
    if (
        not stream.isatty()
        or os.environ.get("MAC_UPDATE_YES") == "1"
        or os.environ.get("MAC_UPDATE_NONINTERACTIVE") == "1"
    ):
        print(
            message(
                "L_PLAN_NO_CONSENT",
                "No new permission granted. Pending choices remain deferred.",
            ),
            file=output,
        )
        return {}
    print(
        message(
            "L_PLAN_CHOICES",
            "Choose explicit entries: a1,a3 allow the shown scope; d2 defer 7 days; i4 ignore; m5 manual. Empty cancels.",
        ),
        file=output,
        flush=True,
    )
    ready, _, _ = select.select([stream], [], [], timeout)
    if not ready:
        return {}
    answer = stream.readline(4097)
    if len(answer) > 4096:
        return {}
    try:
        return parse_choices(answer, actions)
    except ValueError:
        print(
            message("L_PLAN_INVALID", "Invalid selection. No permissions changed."),
            file=output,
        )
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
    choices = review_choices(plan, stream, output) if scan_code == 0 else {}
    if choices:
        plan = record_plan_decisions(plan, choices)
    save_plan(plan, str(Path(session_dir) / "update-plan.json"))
    (Path(session_dir) / "inventory_status.txt").write_text(
        str(scan_code), encoding="utf-8"
    )
    return scan_code


def main(script_dir, mode, session_dir=None):
    try:
        if mode == "preview":
            print(
                json.dumps(
                    apply_filters(build_runtime_plan(script_dir)), ensure_ascii=True
                )
            )
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
