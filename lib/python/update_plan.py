"""Immutable scoped action plans and fail-closed per-mutation authorization."""

import copy
import uuid
from user_policy import (
    target_ref,
    identity_fingerprint,
    source_fingerprint,
    get_decision,
    permits,
    digest,
    timestamp,
)

MAX_PLAN_AGE = 900


def artifact_effects(target):
    if target_ref(target)["kind"] == "app":
        return [target.get("real_path")] if target.get("real_path") else []
    if target.get("manager") == "npm" and target.get("installed_receipt"):
        import os

        return [os.path.dirname(target["installed_receipt"])]
    return sorted(
        set(
            e["artifact_path"]
            for e in target.get("evidence", [])
            if isinstance(e, dict) and e.get("artifact_path")
        )
    )


def build_plan(snapshot, resolutions, policies, now):
    timestamp(now)
    plan = dict(
        schema_version=1,
        plan_id=str(uuid.uuid4()),
        snapshot_id=snapshot["snapshot_id"],
        profile_id=snapshot["profile_id"],
        snapshot_generation=snapshot.get("generation", 0),
        base_snapshot_id=snapshot.get("previous_snapshot_id"),
        created_at=now,
        policy_revision=policies.get("revision", 0),
        policy_fingerprint=digest(policies),
        actions=[],
        readiness="ready",
    )
    resolved = {(r["target"]["kind"], r["target"]["id"]): r for r in resolutions}
    related = {
        i
        for p in snapshot.get("packages", [])
        for i in p.get("related_instance_ids", [])
    }
    for target in snapshot.get("instances", []) + snapshot.get("packages", []):
        ref = target_ref(target)
        resolution = resolved.get(
            (ref["kind"], ref["id"]),
            dict(
                target=ref,
                source="unknown",
                capability="inventory_only",
                adapter_id=None,
                candidate_sources=[],
            ),
        )
        source, cap = resolution.get("source"), resolution.get("capability")
        scope = (
            "manager_update"
            if source in ("homebrew", "npm", "app_store")
            else (
                "direct_update"
                if cap == "reviewed_direct"
                else (
                    "native_launch" if cap == "reviewed_native" else "local_observation"
                )
            )
        )
        kind = "update" if scope != "local_observation" else "manual"
        reasons = []
        if source == "conflict":
            reasons.append("source_conflict")
        elif source == "unknown":
            kind = "manual"
            reasons.append("manual_by_policy")
        elif target.get("presence") != "present":
            reasons.append(
                "removed_since_scan"
                if target.get("presence") == "absent"
                else "scan_partial"
            )
        elif target.get("freshness") != "fresh" or cap == "inventory_only":
            reasons.append(
                "scan_partial" if source != "unknown" else "source_unavailable"
            )
        if ref["kind"] == "app" and source == "homebrew" and ref["id"] in related:
            kind = "skip"
            reasons.append("covered_by_package")
        decision = get_decision(target, resolution, policies, now)
        choice = decision.get("choice") if decision else None
        policy_reason = {
            "preserve_source": "manual_by_policy",
            "ignore": "ignored_by_policy",
            "defer": "deferred_by_user",
        }.get(choice)
        if policy_reason:
            kind = "skip" if choice in ("ignore", "defer") else "manual"
            reasons.append(policy_reason)
        if kind == "update" and not permits(decision, scope):
            reasons.append("consent_required")
        if reasons:
            plan["readiness"] = "decisions_required"
        action = dict(
            action_id=str(uuid.uuid4()),
            target=ref,
            kind=kind,
            action_scope=scope,
            adapter_id=resolution.get("adapter_id") or source,
            target_path=(
                target.get("real_path")
                if ref["kind"] == "app"
                else target.get("prefix")
            ),
            expected_identity=identity_fingerprint(target),
            expected_source=source_fingerprint(target, resolution),
            expected_target=copy.deepcopy(target),
            expected_resolution=copy.deepcopy(resolution),
            from_version=(
                target.get("short_version")
                if ref["kind"] == "app"
                else target.get("version")
            ),
            to_version=None,
            artifact_effects=artifact_effects(target),
            consent_required=scope != "local_observation",
            reason_codes=reasons,
            plan_id=plan["plan_id"],
            plan_created_at=now,
            profile_id=plan["profile_id"],
            snapshot_id=plan["snapshot_id"],
            snapshot_generation=plan["snapshot_generation"],
            base_snapshot_id=plan["base_snapshot_id"],
            expected_policy_fingerprint=plan["policy_fingerprint"],
            related_targets=[
                copy.deepcopy(a)
                for a in snapshot.get("instances", [])
                if a["instance_id"] in target.get("related_instance_ids", [])
            ],
        )
        if resolution.get("verified_recipe"):
            from recipe_acceptance import (
                recipe_fingerprint,
                candidate_binding,
                requirements_fingerprint,
            )

            recipe = copy.deepcopy(resolution["verified_recipe"])
            action.update(
                recipe=recipe,
                recipe_sha256=recipe_fingerprint(recipe),
                candidate_sha256=candidate_binding(recipe["candidate"]),
                requirements_sha256=requirements_fingerprint(recipe),
                to_version=recipe["candidate"]["version"],
                to_build=recipe["candidate"]["build"],
            )
            if scope == "native_launch":
                action.update(
                    kind="open_native_updater",
                    candidate=copy.deepcopy(recipe["candidate"]),
                    allow_native_quit="quit_owned_app"
                    in (decision or {}).get("lifecycle_permissions", []),
                    allow_native_restart="restart_owned_app"
                    in (decision or {}).get("lifecycle_permissions", [])
                    and "restart_owned_app" in recipe["effect_scope"]["lifecycle"],
                )
        plan["actions"].append(action)
    return plan


def authorize_action(action, current, policy, now):
    result = dict(
        target=copy.deepcopy(action.get("target")),
        allowed=False,
        reason_code="invalid_action",
        observed_identity=None,
    )

    def deny(reason):
        result["reason_code"] = reason
        return result

    try:
        age = (timestamp(now) - timestamp(action["plan_created_at"])).total_seconds()
        if age < 0 or age > MAX_PLAN_AGE:
            return deny("plan_expired")
        if not action.get("action_id") or not action.get("plan_id"):
            return deny("invalid_action")
        if action.get("expected_policy_fingerprint") != digest(policy):
            return deny("policy_changed")
        if action.get("kind") not in ("update", "check", "open_native_updater"):
            return deny(
                next(
                    (
                        r
                        for r in action.get("reason_codes", [])
                        if r
                        in (
                            "source_conflict",
                            "scan_partial",
                            "removed_since_scan",
                            "source_unavailable",
                            "ignored_by_policy",
                            "deferred_by_user",
                            "manual_by_policy",
                        )
                    ),
                    "manual_by_policy",
                )
            )
        if not current or current.get("presence") == "absent":
            return deny("removed_since_scan")
        if current.get("presence") != "present" or current.get("freshness") != "fresh":
            return deny("scan_partial")
        if target_ref(current) != action["target"]:
            return deny("identity_changed")
        if current.get("related_identity_valid") is False:
            return deny("related_identity_changed")
        resolution = current.get("resolution", {})
        if resolution.get("source") == "conflict":
            return deny("source_conflict")
        if resolution.get("source") in (None, "unknown") or resolution.get(
            "capability"
        ) in (None, "inventory_only"):
            return deny("source_unavailable")
        result["observed_identity"] = identity_fingerprint(current)
        if result["observed_identity"] != action["expected_identity"]:
            return deny("identity_changed")
        if source_fingerprint(current, resolution) != action["expected_source"]:
            return deny("source_changed")
        if artifact_effects(current) != action.get("artifact_effects"):
            return deny("artifact_effects_changed")
        if current.get("running") is not False:
            return deny(
                "target_running" if current.get("running") else "running_state_unknown"
            )
        decision = get_decision(current, resolution, policy, now)
        if not permits(decision, action["action_scope"]):
            return deny("consent_required")
        if action["action_scope"] == "manager_update" and resolution.get(
            "source"
        ) not in ("homebrew", "npm", "app_store"):
            return deny("scope_mismatch")
        if (
            action["action_scope"] == "direct_update"
            and resolution.get("capability") != "reviewed_direct"
        ):
            return deny("scope_mismatch")
        if (
            action["action_scope"] == "native_launch"
            and resolution.get("capability") != "reviewed_native"
        ):
            return deny("scope_mismatch")
        result.update(allowed=True, reason_code="allowed")
        return result
    except (KeyError, ValueError, TypeError, AttributeError):
        return deny("invalid_action")
