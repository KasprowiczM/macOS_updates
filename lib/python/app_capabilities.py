"""Pure updater capability proposals. Signals never imply ownership or consent."""

import hashlib
import json
import re

CONTRACT_CASES = (
    "absent",
    "current",
    "newer",
    "older_feed_regression",
    "offline",
    "bad_signature",
    "wrong_identity",
    "wrong_arch_min_os",
    "running",
    "source_conflict",
)
_FRAMEWORKS = {
    "sparkle": "sparkle_appcast",
    "electron_updater": "manual",
    "squirrel": "manual",
    "keystone": "keystone",
}


def detect_capabilities(instance, metadata):
    """Consume existing static collector evidence; never read a feed or run code."""
    signals = set()
    for item in instance.get("evidence", []) + metadata.get("evidence", []):
        if not isinstance(item, dict):
            continue
        if item.get("kind") == "framework" and item.get("name") in _FRAMEWORKS:
            signals.add(item["name"])
        if item.get("kind") in ("app_store_receipt", "mas"):
            signals.add("app_store_receipt")
    # Callers with an already parsed plist can reuse this same classifier. No URL
    # is retained: arbitrary feed URLs are not a source of executable recipes.
    for key, signal in (("SUFeedURL", "sparkle"), ("KSUpdateURL", "keystone")):
        if isinstance(metadata.get(key), str) and metadata[key].strip():
            signals.add(signal)
    result = []
    for signal in sorted(signals):
        result.append(
            dict(
                kind=signal,
                adapter_id=_FRAMEWORKS.get(signal, "manual"),
                capability=(
                    "inventory_only" if signal == "app_store_receipt" else "check_only"
                ),
                evidence_grade=(
                    "confirmed" if signal == "app_store_receipt" else "probable"
                ),
                network_allowed=False,
                launch_allowed=False,
                requires_review=True,
            )
        )
    return result


def propose_recipe(instance, capabilities):
    """A local review artifact, deliberately outside executable config schemas."""
    return dict(
        schema_version=1,
        target=dict(kind="app", id=instance.get("instance_id")),
        bundle_id=instance.get("bundle_id"),
        team_id=instance.get("team_id"),
        channel=instance.get("channel", "unknown"),
        capabilities=[dict(item) for item in capabilities],
        review_required=True,
        executable=False,
        verification_state="unreviewed",
        error=False,
        suggested_action="review_check_only" if capabilities else "manual",
        required_contract_cases=list(CONTRACT_CASES),
        completed_contract_cases=[],
    )


def redact_proposal(proposal):
    """Allowlist public identifiers and adapter hints; discard every private field."""
    bundle = proposal.get("bundle_id")
    team = proposal.get("team_id")
    public_id = isinstance(bundle, str) and re.fullmatch(
        r"[A-Za-z0-9][A-Za-z0-9.-]{0,254}", bundle
    )
    public_team = isinstance(team, str) and re.fullmatch(r"[A-Z0-9]{10}", team)
    adapters = sorted(
        {
            item["adapter_id"]
            for item in proposal.get("capabilities", [])
            if isinstance(item, dict)
            and item.get("adapter_id") in set(_FRAMEWORKS.values()) | {"manual"}
        }
    )
    channel = proposal.get("channel")
    return dict(
        schema_version=1,
        bundle_ids=[bundle] if public_id else [],
        team_ids=[team] if public_team else [],
        adapter_candidates=adapters or ["manual"],
        channels=[channel] if channel in ("stable", "beta", "testflight") else [],
        download_hosts=[],
        allowed_artifacts=[],
        review_required=True,
        executable=False,
        verification_state="unreviewed",
        synthetic_example=dict(
            bundle_id="org.example.synthetic",
            installed_version="1.0",
            offered_version="1.1",
        ),
        required_contract_cases=list(CONTRACT_CASES),
    )


def proposal_preview_id(proposal):
    return hashlib.sha256(
        json.dumps(
            redact_proposal(proposal), sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def export_proposal(proposal, accepted_preview_id):
    """Return redacted content only after explicit acceptance of its exact preview."""
    if not isinstance(
        accepted_preview_id, str
    ) or accepted_preview_id != proposal_preview_id(proposal):
        raise ValueError("proposal preview acceptance required")
    return redact_proposal(proposal)
