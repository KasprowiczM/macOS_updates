"""Pure, conservative latest-stable advice. Never authorizes installation."""

import datetime
import re


def timestamp(value):
    result = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamp_timezone_required")
    return result


def _key(recipe, value):
    if not isinstance(value, str) or len(value) > 256:
        return None
    policy = recipe.get("version_comparison_policy", "incomparable")
    if policy == "numeric_before_comma":
        value = value.split(",", 1)[0]
    elif policy == "office_release_family":
        match = re.fullmatch(r"(\d+)\.(\d+)(?:[. ,(]+\d+\)?)?", value)
        return tuple(map(int, match.groups())) if match else None
    elif policy == "warp_stable":
        match = re.fullmatch(r"v?(\d+(?:\.\d+)*)\.stable_(\d+)", value)
        return (
            tuple(map(int, match[1].split("."))) + (int(match[2]),) if match else None
        )
    elif policy == "build_b":
        return (int(value[1:]),) if re.fullmatch(r"b\d+", value) else None
    elif policy != "numeric":
        return None
    if not re.fullmatch(r"v?\d+(?:\.\d+)*", value):
        return None
    # No generic zero/build stripping. Only explicitly reviewed policies define
    # cross-source normalization for a product.
    return tuple(map(int, value.lstrip("v").split(".")))


def compare_channel_releases(recipe, left, right):
    for record in (left, right):
        if record.get("product_id") != recipe.get("product_id") or record.get(
            "edition"
        ) != recipe.get("edition"):
            return "incomparable"
    li, ri = left.get("release_identity"), right.get("release_identity")
    if isinstance(li, str) and li.startswith("sha256:") and li == ri:
        return "equal"
    a, b = _key(recipe, left.get("version")), _key(recipe, right.get("version"))
    if a is None or b is None or len(a) != len(b):
        return "incomparable"
    return "newer" if a > b else "older" if a < b else "equal"


def _stable(recipe, record):
    return (
        record.get("product_id") == recipe.get("product_id")
        and record.get("edition") == recipe.get("edition")
        and record.get("fetch_status") == "ok"
        and record.get("stable_confirmed") is True
        and record.get("release_channel") == "stable"
        and _key(recipe, record.get("version")) is not None
    )


def _largest(recipe, rows):
    if not rows:
        return None
    winner = rows[0]
    for row in rows[1:]:
        relation = compare_channel_releases(recipe, row, winner)
        if relation == "incomparable":
            return None
        if relation == "newer":
            winner = row
    return winner


def historical_evidence(history, product_id):
    """Count matched stable releases with real observation dates, never pubDate backfill."""
    groups = {}
    for row in history if isinstance(history, list) else []:
        if (
            row.get("product_id") != product_id
            or row.get("stable_confirmed") is not True
            or not row.get("release_identity")
        ):
            continue
        try:
            observed = timestamp(row["first_observed_at"])
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        entry = groups.setdefault((row.get("edition"), row["release_identity"]), {})
        entry[row.get("source_id")] = observed
    matched = [values for values in groups.values() if len(values) >= 2]
    times = [t for values in matched for t in values.values()]
    days = (max(times) - min(times)).total_seconds() / 86400 if times else 0
    return {
        "sample_size": len(matched),
        "covered_days": days,
        "qualified": len(matched) >= 5 and days >= 30,
    }


def recommend_channel(recipe, observations, installed, user_preference):
    rows = [
        r
        for r in observations
        if r.get("product_id") == recipe.get("product_id")
        and r.get("edition") == recipe.get("edition")
    ]
    stable = [r for r in rows if _stable(recipe, r)]
    compatible = [
        r for r in stable if r.get("compatibility", {}).get("status") == "compatible"
    ]
    available = [
        r for r in compatible if r.get("availability") in ("listed", "offered")
    ]
    offered = [r for r in available if r.get("availability") == "offered"]
    global_latest = _largest(recipe, stable)
    compatible_latest = _largest(recipe, compatible)
    selectable = _largest(recipe, available)
    reasons = []
    uncertainty = []
    if any(r.get("fetch_status") != "ok" for r in rows):
        reasons.append("source_unavailable")
        uncertainty.append("incomplete_source_observations")
    if any(r.get("compatibility", {}).get("status") == "unknown" for r in stable):
        uncertainty.append("compatibility_unknown")
    if any(
        r.get("source_id") == "app_store"
        and (r.get("region") is None or r.get("availability") != "offered")
        for r in rows
    ):
        uncertainty.append("storefront_or_offer_unknown")
    if any(r.get("availability") == "staged" for r in stable):
        uncertainty.append("staged_rollout")
    if stable and global_latest is None:
        reasons.append("incomparable")
    if not stable:
        reasons.append("stable_not_established")
    if not compatible:
        reasons.append("compatible_stable_unknown")
    if installed and (
        installed.get("product_id") != recipe.get("product_id")
        or installed.get("edition") != recipe.get("edition")
    ):
        installed = None
        uncertainty.append("installed_identity_unmatched")
    if installed and installed.get("source_id") == "conflict":
        selectable = None
        reasons.append("source_conflict")
    selected = selectable
    if selected:
        tied = [
            r
            for r in available
            if compare_channel_releases(recipe, r, selected) == "equal"
        ]
        current_source = installed.get("source_id") if installed else None
        preferred = user_preference.get("source_id")
        same = [r for r in tied if r.get("source_id") == current_source]
        chosen = [r for r in tied if r.get("source_id") == preferred]
        selected = (same or chosen or tied)[0]
        reasons.append(
            "current_source_preserved" if same else "compatible_stable_listed"
        )
    updater = selected.get("updater_id") if selected else None
    if (
        installed
        and selected
        and selected.get("source_id") == installed.get("source_id")
    ):
        updater = installed.get("updater_id") or updater
        desired = user_preference.get("preferred_updater_id")
        if (
            desired
            and any(
                r.get("updater_id") == desired
                and compare_channel_releases(recipe, r, selected) == "equal"
                for r in available
            )
            and any(
                c.get("installation_source") == installed.get("source_id")
                and c.get("updater_id") == desired
                and c.get("reviewed") is True
                for c in recipe.get("compatible_updaters", [])
            )
        ):
            updater = desired
    history = historical_evidence(
        user_preference.get("history", []), recipe.get("product_id")
    )
    if not history["qualified"]:
        uncertainty.append("historical_evidence_insufficient")
    dates = [
        r.get("observed_at") for r in rows if isinstance(r.get("observed_at"), str)
    ]
    return {
        "product_id": recipe.get("product_id"),
        "edition": recipe.get("edition"),
        "latest_global_stable": global_latest,
        "latest_compatible_stable": compatible_latest,
        "actually_offered": _largest(recipe, offered),
        "recommended_release": selected,
        "recommended_source_id": selected.get("source_id") if selected else None,
        "recommended_updater_id": updater,
        "reason_codes": reasons,
        "evidence": rows,
        "as_of": max(dates) if dates else None,
        "uncertainty": uncertainty,
        "migration_required": bool(
            installed
            and selected
            and installed.get("source_id") != selected.get("source_id")
        ),
        "historical_sample_size": history["sample_size"],
        "historical_covered_days": history["covered_days"],
        "historical_timing_basis": "local_first_observed_intervals",
        "historical_speed_claim": None,
    }
