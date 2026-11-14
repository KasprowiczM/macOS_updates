"""Pure installation-bound consent. Versions are deliberately not authority."""

import copy
import datetime
import hashlib
import json
import os

SCOPES = {
    "local_observation",
    "network_check",
    "manager_update",
    "direct_update",
    "native_launch",
}
CHOICES = {
    "preserve_source",
    "allow_check",
    "allow_update_same_source",
    "allow_native_launch",
    "defer",
    "ignore",
}


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("invalid_timestamp")
    parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() != datetime.timedelta(0):
        raise ValueError("timestamp_not_utc")
    return parsed


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        ).encode()
    ).hexdigest()


def target_ref(target):
    if "target" in target:
        ref = target["target"]
    else:
        app, package = target.get("instance_id"), target.get("package_id")
        if bool(app) == bool(package):
            raise ValueError("ambiguous_target")
        ref = {"kind": "app" if app else "package", "id": app or package}
    if (
        not isinstance(ref, dict)
        or set(ref) != {"kind", "id"}
        or ref.get("kind") not in ("app", "package")
        or not isinstance(ref.get("id"), str)
        or not ref["id"]
    ):
        raise ValueError("invalid_target")
    return dict(ref)


def _path(value):
    return (
        os.path.normpath(value)
        if isinstance(value, str) and value.startswith("/")
        else None
    )


def identity_fingerprint(target):
    ref = target_ref(target)
    if ref["kind"] == "app":
        data = {k: target.get(k) for k in ("bundle_id", "team_id", "channel")}
        data.update(
            path=_path(target.get("path")), real_path=_path(target.get("real_path"))
        )
    else:
        data = {k: target.get(k) for k in ("manager", "source_identity", "channel")}
        data.update(
            prefix=_path(target.get("prefix")),
            receipt_present=bool(target.get("installed_receipt")),
        )
    # Receipt paths contain ordinary versions for Homebrew; installation identity
    # is the verified manager/prefix/token, not that versioned directory.
    return digest(data)


def source_fingerprint(target, resolution):
    fields = (
        "kind",
        "token",
        "prefix",
        "artifact_path",
        "store_id",
        "bundle_id",
        "team_id",
        "manifest_path",
    )
    claims = []
    for e in target.get("evidence", []):
        if isinstance(e, dict) and e.get("kind") in (
            "homebrew",
            "mas",
            "npm",
            "app_store_receipt",
            "vendor_signature",
            "protected_root",
            "enterprise_managed",
        ):
            claims.append({k: e.get(k) for k in fields if e.get(k) is not None})
    return digest(
        dict(
            source=resolution.get("source"),
            adapter_id=resolution.get("adapter_id"),
            candidate_sources=sorted(resolution.get("candidate_sources", [])),
            claims=sorted(claims, key=lambda x: json.dumps(x, sort_keys=True)),
            **(
                {
                    "recipe_fingerprint": resolution["recipe_fingerprint"],
                    "candidate_fingerprint": resolution.get("candidate_fingerprint"),
                }
                if resolution.get("recipe_fingerprint")
                else {}
            ),
        )
    )


def make_decision(
    target,
    resolution,
    choice,
    action_scope,
    now,
    expires_at=None,
    reason=None,
    lifecycle_permissions=None,
):
    lifecycle_permissions = lifecycle_permissions or []
    if (
        not isinstance(lifecycle_permissions, list)
        or any(
            p not in ("quit_owned_app", "restart_owned_app")
            for p in lifecycle_permissions
        )
        or lifecycle_permissions
        and choice != "allow_native_launch"
    ):
        raise ValueError("invalid_lifecycle_permissions")
    if choice not in CHOICES or action_scope not in SCOPES:
        raise ValueError("invalid_decision")
    if choice == "allow_update_same_source" and action_scope not in (
        "manager_update",
        "direct_update",
    ):
        raise ValueError("invalid_update_scope")
    if choice == "allow_native_launch" and action_scope != "native_launch":
        raise ValueError("invalid_launch_scope")
    if choice == "allow_check" and action_scope != "network_check":
        raise ValueError("invalid_check_scope")
    created = timestamp(now)
    if choice == "defer" and expires_at is None:
        expires_at = (
            (created + datetime.timedelta(days=7)).isoformat().replace("+00:00", "Z")
        )
    if expires_at is not None and timestamp(expires_at) <= created:
        raise ValueError("invalid_expiry")
    return dict(
        target=target_ref(target),
        identity_fingerprint=identity_fingerprint(target),
        source_fingerprint=source_fingerprint(target, resolution),
        action_scope=action_scope,
        choice=choice,
        **(
            {"lifecycle_permissions": sorted(set(lifecycle_permissions))}
            if lifecycle_permissions
            else {}
        ),
        created_at=now,
        expires_at=expires_at,
        reason=reason,
    )


def decision_is_valid(decision, target, resolution, now):
    try:
        return bool(
            decision["choice"] in CHOICES
            and decision["action_scope"] in SCOPES
            and decision["target"] == target_ref(target)
            and decision["identity_fingerprint"] == identity_fingerprint(target)
            and decision["source_fingerprint"] == source_fingerprint(target, resolution)
            and timestamp(decision["created_at"]) <= timestamp(now)
            and (
                decision.get("expires_at") is None
                or timestamp(now) < timestamp(decision["expires_at"])
            )
        )
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def get_decision(target, resolution, policies, now):
    candidates = [
        d
        for d in policies.get("decisions", [])
        if isinstance(d, dict) and decision_is_valid(d, target, resolution, now)
    ]
    return (
        copy.deepcopy(max(candidates, key=lambda d: d["created_at"]))
        if candidates
        else None
    )


def record_decision(decision, policies):
    if (
        not isinstance(decision, dict)
        or decision.get("choice") not in CHOICES
        or decision.get("action_scope") not in SCOPES
    ):
        raise ValueError("invalid_decision")
    ref = target_ref({"target": decision.get("target")})
    for field in ("identity_fingerprint", "source_fingerprint"):
        if not isinstance(decision.get(field), str) or len(decision[field]) != 64:
            raise ValueError("invalid_fingerprint")
    timestamp(decision.get("created_at"))
    if decision.get("expires_at") is not None and timestamp(
        decision["expires_at"]
    ) <= timestamp(decision["created_at"]):
        raise ValueError("invalid_expiry")
    if decision["choice"] == "allow_update_same_source" and decision[
        "action_scope"
    ] not in ("manager_update", "direct_update"):
        raise ValueError("invalid_scope")
    if (
        decision["choice"] == "allow_native_launch"
        and decision["action_scope"] != "native_launch"
    ):
        raise ValueError("invalid_scope")
    if (
        decision["choice"] == "allow_check"
        and decision["action_scope"] != "network_check"
    ):
        raise ValueError("invalid_scope")
    updated = copy.deepcopy(policies)
    updated.update(schema_version=1, revision=policies.get("revision", 0) + 1)
    updated["decisions"] = [
        copy.deepcopy(d)
        for d in policies.get("decisions", [])
        if d.get("target") != ref
    ] + [copy.deepcopy(decision)]
    return updated


def permits(decision, scope):
    if not decision or decision.get("action_scope") != scope:
        return False
    return (decision.get("choice"), scope) in {
        ("allow_check", "network_check"),
        ("allow_update_same_source", "manager_update"),
        ("allow_update_same_source", "direct_update"),
        ("allow_native_launch", "native_launch"),
    }
