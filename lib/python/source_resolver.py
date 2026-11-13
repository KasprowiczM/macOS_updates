"""Pure, conservative provenance resolution for inventory shadow mode."""

import os


def _canonical(path):
    # Pure lexical normalization: no host filesystem reads or symlink resolution.
    return (
        os.path.normpath(path)
        if isinstance(path, str) and path.startswith("/")
        else None
    )


def _inside(path, root):
    return bool(path and (path == root or path.startswith(root + "/")))


def _version(value):
    if not isinstance(value, str):
        return None
    parts = value.split(".")
    if not 1 <= len(parts) <= 3 or any(not p.isdigit() for p in parts):
        return None
    return tuple(int(p) for p in parts) + (0,) * (3 - len(parts))


def resolve_target(target, snapshot, recipes):
    ref = target.get("target")
    if ref is None:
        app_id, package_id = target.get("instance_id"), target.get("package_id")
        if bool(app_id) == bool(package_id):
            raise ValueError("record must have exactly one target identity")
        ref = {"kind": "app" if app_id else "package", "id": app_id or package_id}
    if (
        not isinstance(ref, dict)
        or set(ref) != {"kind", "id"}
        or ref.get("kind") not in ("app", "package")
        or not isinstance(ref.get("id"), str)
        or not ref["id"]
    ):
        raise ValueError("target must include a typed TargetRef")
    id_field = "instance_id" if ref["kind"] == "app" else "package_id"
    if target.get(id_field) != ref["id"]:
        raise ValueError("target identity mismatch")
    evidence = [e for e in target.get("evidence", []) if isinstance(e, dict)]
    kinds = {e.get("kind") for e in evidence}
    path = _canonical(target.get("real_path"))
    sources = set()
    reasons = []
    adapter = None
    ownership_conflict = False
    capability = "inventory_only"
    if ref["kind"] == "app":
        if "app_store_receipt" in kinds or any(
            e.get("kind") == "mas"
            and e.get("store_id")
            and (
                (e.get("bundle_id") and e.get("bundle_id") == target.get("bundle_id"))
                or (path and _canonical(e.get("path")) == path)
            )
            for e in evidence
        ):
            sources.add("app_store")
        brew_claims = {
            (e.get("token"), _canonical(e.get("prefix")))
            for e in evidence
            if e.get("kind") == "homebrew"
            and isinstance(e.get("token"), str)
            and e.get("token")
            and _canonical(e.get("prefix"))
            and e.get("installed_receipt")
            and path
            and _canonical(e.get("artifact_path")) == path
        }
        if brew_claims:
            sources.add("homebrew")
        if len(brew_claims) > 1:
            ownership_conflict = True
            reasons.append("multiple_brew_owners")
        if "protected_root" in kinds and any(
            _inside(path, root)
            for root in (
                "/System/Applications",
                "/System/Library",
                "/usr/bin",
                "/usr/sbin",
            )
        ):
            sources.add("apple_system")
        if "enterprise_managed" in kinds:
            sources.add("enterprise_managed")
        bundle = target.get("bundle_id")
        if bundle and sum(
            1
            for item in snapshot.get("instances", [])
            if item.get("bundle_id") == bundle
            and item.get("instance_id") != ref["id"]
            and item.get("presence") != "absent"
        ):
            reasons.append("duplicate_bundle_id")
        for recipe in recipes.get("recipes", []):
            if bundle not in recipe.get("bundle_ids", []) or not bundle:
                continue
            team = target.get("team_id")
            signed = any(
                e.get("kind") == "vendor_signature"
                and e.get("bundle_id") == bundle
                and e.get("team_id") == team
                and team
                for e in evidence
            )
            if team and team in recipe.get("team_ids", []) and signed:
                # A signature proves identity, not installation provenance.
                if not sources:
                    sources.add("vendor")
                os_version, minimum = _version(snapshot.get("os_version")), _version(
                    recipe.get("minimum_os")
                )
                architectures = target.get("architectures")
                complete = (
                    all(
                        recipe.get(k)
                        for k in (
                            "architectures",
                            "minimum_os",
                            "download_hosts",
                            "allowed_artifacts",
                        )
                    )
                    and isinstance(architectures, list)
                    and bool(architectures)
                    and bool(set(architectures) & set(recipe["architectures"]))
                    and os_version is not None
                    and minimum is not None
                    and os_version >= minimum
                    and recipe.get("adapter_id") in ("github_dmg", "mozilla_dmg")
                )
                if (
                    sources == {"vendor"}
                    and complete
                    and target.get("channel") in recipe.get("channels", [])
                    and target.get("channel") != "testflight"
                ):
                    adapter = recipe.get("adapter_id")
                    capability = "reviewed_direct"
                else:
                    reasons.append("recipe_incomplete_or_channel_unreviewed")
            else:
                reasons.append("recipe_identity_mismatch")
                if team and team not in recipe.get("team_ids", []):
                    ownership_conflict = True
    else:
        manager = target.get("manager")
        prefix = _canonical(target.get("prefix"))
        identity = target.get("source_identity")
        if target.get("installed_receipt") and identity and prefix:
            brew_token = (
                identity.split(":", 1)[1]
                if isinstance(identity, str)
                and identity.startswith(("cask:", "formula:"))
                and identity.split(":", 1)[1]
                else identity
            )
            if manager == "homebrew" and any(
                e.get("kind") == "homebrew"
                and e.get("token") == brew_token
                and _canonical(e.get("prefix")) == prefix
                and e.get("installed_receipt") == target.get("installed_receipt")
                for e in evidence
            ):
                sources.add("homebrew")
            if manager == "npm" and any(
                e.get("kind") == "npm"
                and e.get("name") == identity
                and _canonical(e.get("prefix")) == prefix
                and _inside(_canonical(e.get("manifest_path")), prefix)
                for e in evidence
            ):
                sources.add("npm")
    if target.get("channel") == "testflight":
        reasons.append("testflight_channel")
        capability, adapter = "inventory_only", None
    if len(sources) > 1 or ownership_conflict:
        source, grade, capability, adapter = (
            "conflict",
            "conflicting",
            "inventory_only",
            None,
        )
        reasons.append("conflicting_sources")
    elif sources:
        source = next(iter(sources))
        grade = "probable" if source == "vendor" else "confirmed"
        if source in (
            "app_store",
            "homebrew",
            "npm",
            "apple_system",
            "enterprise_managed",
        ):
            capability, adapter = "native_managed", None
    else:
        source, grade = "unknown", "unknown"
        if "framework" in kinds or any(
            e.get("kind") == "info_plist"
            and (e.get("SUFeedURL") or e.get("su_feed_url"))
            for e in evidence
        ):
            capability = "check_only"
            reasons.append("framework_capability_only")
    degraded = (
        target.get("presence") != "present"
        or target.get("freshness") != "fresh"
        or target.get("source_status") in ("partial", "error", "unavailable")
        or target.get("complete") is False
        or target.get("source_complete") is False
        or any(
            e.get("freshness") == "stale"
            or e.get("status") in ("partial", "error", "unavailable")
            or e.get("source_status") in ("partial", "error", "unavailable")
            or e.get("complete") is False
            or e.get("source_complete") is False
            for e in evidence
        )
    )
    if degraded:
        capability, adapter = "inventory_only", None
        if grade == "confirmed":
            grade = "probable"
        reasons.append("target_or_evidence_incomplete")
    if target.get("channel") == "testflight":
        capability, adapter = "inventory_only", None
    if ref["kind"] == "package" and target.get("related_instance_ids"):
        # One manager action may replace several bundles. A conflicting related
        # installation must not become eligible through the package target.
        apps = {item.get("instance_id"): item for item in snapshot.get("instances", [])}
        for instance_id in target["related_instance_ids"]:
            related = apps.get(instance_id)
            if related is None:
                capability, adapter = "inventory_only", None
                reasons.append("related_target_unobserved")
                continue
            resolution = resolve_target(related, snapshot, recipes)
            if resolution["source"] == "conflict" or resolution["source"] != source:
                sources.update(resolution["candidate_sources"])
                source, grade = "conflict", "conflicting"
                capability, adapter = "inventory_only", None
                reasons.append("related_source_conflict")
            elif resolution["capability"] == "inventory_only":
                capability, adapter = "inventory_only", None
                reasons.append("related_target_unavailable")
    return {
        "target": dict(ref),
        "source": source,
        "capability": capability,
        "adapter_id": adapter,
        "evidence_grade": grade,
        "reason_codes": reasons,
        "candidate_sources": sorted(sources),
    }


def resolve_snapshot(snapshot, recipes):
    """Resolve collector records without adding persistent fields to them."""
    return [
        resolve_target(item, snapshot, recipes)
        for key in ("instances", "packages")
        for item in snapshot.get(key, [])
    ]
