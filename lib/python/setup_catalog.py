"""Public, unselected catalog views. Metadata never grants install authority."""

import copy
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from channel_probes import load_channel_sources, match_installed_products
from download_policy import validate_download_url


def safe_official_url(value):
    if not isinstance(value, str):
        return None
    try:
        host = urlsplit(value).hostname
        return validate_download_url(value, [host])
    except (ValueError, TypeError):
        return None


def load_setup_catalog(script_dir=None):
    root = Path(script_dir) if script_dir else Path(__file__).resolve().parents[2]
    manifest = load_channel_sources(str(root / "config/channel_sources.json"))
    evidence_path = root / "config/catalog_source_evidence.json"
    with evidence_path.open("rb") as stream:
        raw = stream.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("research_too_large")
    observations = json.loads(raw).get("observations", [])
    evidence = {row.get("key"): row for row in observations if isinstance(row, dict)}
    recipes = []
    for product in manifest["products"]:
        sources = []
        for source in product["sources"]:
            record = evidence.get(source.get("evidence_key"), {})
            metadata = record.get("metadata", {})
            link = metadata.get("homepage") if isinstance(metadata, dict) else None
            if not link and isinstance(metadata, list):
                matches = [
                    row.get("trackViewUrl")
                    for row in metadata
                    if isinstance(row, dict) and row.get("trackViewUrl")
                ]
                link = matches[0] if len(matches) == 1 else None
            if not link and source["source_id"] == "app_store":
                link = source.get("store_url")
                if not link and source.get("store_id"):
                    link = "https://apps.apple.com/app/id" + str(source["store_id"])
            if not link and source["url"].startswith("https://api.github.com/repos/"):
                link = (
                    source["url"]
                    .replace("https://api.github.com/repos/", "https://github.com/")
                    .replace("/releases/latest", "/releases")
                )
            # Only actual observed public pages may be fallback manual links.
            if not link and source["url"].endswith(
                ("/overview/", "/comet", "/download/mac")
            ):
                link = source["url"]
            sources.append(
                dict(
                    source_id=source["source_id"],
                    official_url=safe_official_url(link),
                    architectures=source.get("architectures", []),
                    evidence=(
                        "reviewed_metadata"
                        if source.get("identity_reviewed")
                        else "unknown"
                    ),
                    observed_at=source.get("observed_at"),
                    updater_id=source.get("updater_id"),
                )
            )
        homepage = next(
            (
                item["official_url"]
                for item in sources
                if item["source_id"] == "homebrew" and item.get("official_url")
            ),
            None,
        )
        for item, original in zip(sources, product["sources"]):
            if (
                item["source_id"] == "vendor"
                and item.get("official_url") is None
                and homepage
            ):
                item["official_url"] = homepage
            if item["source_id"] == "homebrew" and original.get("token"):
                item["official_url"] = safe_official_url(
                    "https://formulae.brew.sh/cask/" + original["token"]
                )
        recipes.append(
            dict(
                id=product["product_id"],
                product_id=product["product_id"],
                name=product["name"],
                edition=product["edition"],
                sources=sources,
                architectures=[],
                minimum_os=None,
                channel="unknown",
                license_review=product.get("license_review", "unknown"),
                install_adapter=None,
                first_install_acceptance=None,
                requirements_known=False,
                requirements=[],
                research_evidence=product.get("research_evidence"),
                research_summary=product.get("research_summary"),
                revision=manifest.get("reviewed_at"),
            )
        )
    # A closed manager contract grants no vendor-artifact acceptance. The live
    # official cask and exact metadata are reviewed again for selected previews.
    for row in recipes:
        if row["product_id"] == "keepassxc-gui":
            stable = evidence.get("keepassxc", {})
            record = stable.get("metadata", {})
            if record.get("prerelease") is False and record.get("draft") is False:
                row.update(manager_delegation=dict(token="keepassxc", stable_version=record.get("tag_name"),
                                                  reviewed_at=stable.get("observed_at")),
                           install_adapter="homebrew_cask", installation_source="homebrew", channel="stable",
                           bundle_id="org.keepassxc.keepassxc",
                           version=record.get("tag_name"), destination="/Applications/KeePassXC.app",
                           artifact_effects=["/Applications/KeePassXC.app"], permissions=["manager_delegated_install"])
    catalog = dict(
        schema_version=1,
        recipes=recipes,
        requirements={},
        registry_rows=len(manifest["registry_rows"]),
        channel_manifest=manifest,
    )
    from app_recipes import load_verified_recipes

    return attach_verified_install_recipes(
        catalog, load_verified_recipes(str(root / "config/verified_recipes.json"))
    )


def attach_verified_install_recipes(
    catalog, verified_catalog, applications_root="/Applications"
):
    """Attach reviewed v2 candidates without minting legacy acceptance flags.

    This is metadata preparation only. Eligibility, consent, acquisition and
    staged-candidate observation remain independent execution gates.
    """
    from app_recipes import validate_recipe

    value = copy.deepcopy(catalog)
    candidates = {}
    for recipe in verified_catalog.get("recipes", []):
        validate_recipe(recipe)
        for product_id in recipe["matrix_ids"]:
            candidates.setdefault(product_id, []).append(recipe)
    for row in value.get("recipes", []):
        matches = [
            r
            for r in candidates.get(row["product_id"], [])
            if r["edition"] == row["edition"]
            and r["channel"] == "stable"
            and r["installation_source"] == "vendor"
        ]
        # Ambiguous editions/channels never select the first matching recipe.
        if len(matches) != 1 or len(matches[0]["matrix_ids"]) != 1:
            continue
        recipe = matches[0]
        candidate = recipe["candidate"]
        destination = str(Path(applications_root) / candidate["bundle_name"])
        row.update(
            verified_recipe=copy.deepcopy(recipe),
            install_adapter="verified_recipe_zip",
            installation_source=recipe["installation_source"],
            revision=recipe["revision"],
            version=candidate["version"],
            build=candidate["build"],
            channel=recipe["channel"],
            bundle_id=candidate["bundle_id"],
            team_id=candidate["team_id"],
            architectures=recipe["architectures"][:],
            minimum_os=candidate["minimum_os"],
            download_hosts=recipe["download_hosts"][:],
            artifact_type=candidate["artifact_type"],
            destination=destination,
            artifact_effects=[destination],
            requires_administrator=False,
            requirements_known=True,
            requirements=[],
            permissions=[
                n["value"]
                for n in recipe["requirement_graph"]["nodes"]
                if n["kind"] == "permission" and "install" in n["operations"]
            ],
        )
    return value


def match_catalog_snapshot(snapshot, recipes):
    value = copy.deepcopy(snapshot)
    manifest = recipes.get("channel_manifest")
    if manifest:
        matched = match_installed_products(snapshot, manifest)
        for pid, record in matched.items():
            for group, id_key in (
                ("instances", "instance_id"),
                ("packages", "package_id"),
            ):
                for target in value.get(group, []):
                    if record.get(id_key) and target.get(id_key) == record[id_key]:
                        target.update(
                            product_id=pid,
                            edition=record["edition"],
                            source_id=record.get("source_id"),
                            updater_id=record.get("updater_id"),
                        )
    return value


def build_catalog_view(snapshot, recipes, recommendations, filters):
    snapshot = match_catalog_snapshot(snapshot, recipes)
    from install_plan import install_recipe_eligible
    from catalog_manager_install import manager_recipe_eligible

    recommendations = {r["product_id"]: r for r in recommendations}
    installed = {}
    for group in ("instances", "packages"):
        for target in snapshot.get(group, []):
            if target.get("presence") == "present" and target.get("product_id"):
                installed.setdefault(
                    (target["product_id"], target.get("edition")), []
                ).append(target)
    rows = []
    for recipe in recipes.get("recipes", []):
        pid = recipe["product_id"]
        if (
            filters.get("query")
            and filters["query"].casefold() not in recipe["name"].casefold()
        ):
            continue
        present = installed.get((pid, recipe["edition"]), [])
        if filters.get("installed") is True and not present:
            continue
        recommendation = recommendations.get(pid, {})
        rows.append(
            dict(
                product_id=pid,
                name=recipe["name"],
                edition=recipe["edition"],
                selected=False,
                installed=copy.deepcopy(present),
                installation_status=(
                    "already_installed"
                    if present
                    else (
                        "manager_delegated" if manager_recipe_eligible(recipe) else ("automatic"
                        if install_recipe_eligible(
                            recipe, snapshot.get("environment", {})
                        )
                        else "manual")
                    )
                ),
                sources=copy.deepcopy(recipe.get("sources", [])),
                recommendation=copy.deepcopy(recommendation),
                recommended_source_id=recommendation.get("recommended_source_id"),
                recommended_updater_id=recommendation.get("recommended_updater_id"),
                recommended_release=recommendation.get("recommended_release"),
                latest_compatible_stable=recommendation.get("latest_compatible_stable"),
                as_of=recommendation.get("as_of"),
                evidence_level=(
                    "manager_delegation" if manager_recipe_eligible(recipe) else ("first_install_verified"
                    if install_recipe_eligible(recipe, snapshot.get("environment", {}))
                    else "metadata_only")
                ),
                license_review=recipe.get("license_review", "unknown"),
                limitations=["manual_migration_only"] if present else [],
            )
        )
    return dict(
        schema_version=1,
        rows=rows,
        registry_rows=recipes.get("registry_rows", len(rows)),
        selected=[],
        unmatched_installations=[
            copy.deepcopy(target)
            for group in ("instances", "packages")
            for target in snapshot.get(group, [])
            if target.get("presence") == "present" and not target.get("product_id")
        ],
        unmatched_installed=sum(
            1
            for group in ("instances", "packages")
            for target in snapshot.get(group, [])
            if target.get("presence") == "present" and not target.get("product_id")
        ),
    )



def prepare_catalog_selections(pairs, snapshot, recipes, now):
    """Build a plan only for explicit, canonical product and source selections."""
    from install_plan import build_install_plan
    if not isinstance(pairs, (list, tuple)) or len(pairs) > 1000:
        raise ValueError("invalid_selections")
    by_id = {item["product_id"]: item for item in recipes.get("recipes", [])}
    selected = []
    seen = set()
    for pair in pairs:
        if not isinstance(pair, (tuple, list)) or len(pair) != 2:
            raise ValueError("invalid_selection")
        product_id, source_id = pair
        if not isinstance(product_id, str) or not isinstance(source_id, str) or product_id in seen:
            raise ValueError("invalid_selection")
        recipe = by_id.get(product_id)
        if not recipe or source_id not in {source.get("source_id") for source in recipe.get("sources", [])}:
            raise ValueError("unknown_source")
        seen.add(product_id)
        selected.append(dict(product_id=product_id, edition=recipe["edition"],
                             source_id=source_id, architecture="arm64"))
    return build_install_plan(selected, snapshot, recipes, now)


def parse_selections(text, view):
    text = text.strip().lower()
    if text in ("", "cancel", "back", "q", "quit"):
        return []
    selections = []
    seen = set()
    for token in re.split(r"[,\s]+", text):
        if not re.fullmatch(r"[1-9][0-9]*(?::[a-z_]+)?", token):
            raise ValueError("invalid_selection")
        number, _, source = token.partition(":")
        index = int(number) - 1
        if index >= len(view["rows"]):
            raise ValueError("invalid_selection")
        row = view["rows"][index]
        sources = {s["source_id"] for s in row["sources"]}
        source = (
            source
            or row.get("recommended_source_id")
            or next(iter(s["source_id"] for s in row["sources"]), None)
        )
        if source not in sources or row["product_id"] in seen:
            raise ValueError("invalid_source_or_duplicate")
        seen.add(row["product_id"])
        selections.append(
            dict(product_id=row["product_id"], source_id=source, edition=row["edition"])
        )
    return selections


# The terminal menu keeps choices local until the user approves one digest.
def _message(key, fallback):
    import os

    return os.environ.get(key) or fallback


def _text(value):
    if value is None or value == "unknown":
        return _message("L_CATALOG_UNKNOWN", "Unknown")
    if value is True:
        return _message("L_INSTALL_YES", "Yes")
    if value is False:
        return _message("L_INSTALL_NO", "No")
    return "".join(c for c in str(value) if c.isprintable())[:1000]


def _label(value):
    names = {
        "already_installed": (
            "L_CATALOG_ALREADY_INSTALLED",
            "Already installed; source changes are manual.",
        ),
        "manual": ("L_CATALOG_MANUAL", "Manual acquisition"),
        "automatic": ("L_CATALOG_AUTOMATIC", "Reviewed first-install adapter"),
        "manager_delegated": ("L_CATALOG_MANAGER", "Optional Homebrew installation with explicit permission"),
        "manager_delegation": ("L_CATALOG_MANAGER_METADATA", "Reviewed Homebrew manager contract"),
        "gui": ("L_CATALOG_GUI", "Desktop application"),
        "cli": ("L_CATALOG_CLI", "Command-line tool"),
        "suite": ("L_CATALOG_SUITE", "Application suite"),
        "vendor": ("L_CATALOG_VENDOR", "Vendor"),
        "unknown": ("L_CATALOG_SOURCE_UNKNOWN", "Unknown source"),
        "conflict": ("L_CATALOG_SOURCE_CONFLICT", "Source conflict"),
        "reviewed_metadata": ("L_CATALOG_METADATA_ONLY", "Public metadata reviewed"),
        "metadata_only": ("L_CATALOG_METADATA_ONLY", "Public metadata reviewed"),
        "first_install_verified": (
            "L_CATALOG_FIRST_INSTALL_VERIFIED",
            "First installation verified",
        ),
        "manual_acquisition": ("L_CATALOG_MANUAL", "Manual acquisition"),
        "manual_migration": ("L_INSTALL_MIGRATION", "Manual source migration"),
        "install": ("L_CATALOG_AUTOMATIC", "Reviewed first-install adapter"),
        "manual_acquisition_opened": (
            "L_INSTALL_RESULT_OPENED",
            "Official page opened. Acquire the application yourself, then rescan.",
        ),
        "installed_verified": ("L_INSTALL_RESULT_VERIFIED", "Installed and verified"),
        "manager_installed_verified": ("L_INSTALL_MANAGER_VERIFIED", "Installed; Homebrew receipt verified"),
        "deferred": (
            "L_INSTALL_RESULT_DEFERRED",
            "Deferred. Review a new preview before retrying.",
        ),
        "recovery_required": (
            "L_INSTALL_RESULT_RECOVERY",
            "Recovery requires review. Existing applications were preserved.",
        ),
    }
    if value in names:
        return _message(*names[value])
    if value == "stable":
        return _message("L_CATALOG_STABLE", "Stable")
    if value == "beta":
        return _message("L_CATALOG_BETA", "Beta")
    if value in ("native", "native_managed"):
        return _message("L_CATALOG_NATIVE", "Native updater")
    return {
        "homebrew": "Homebrew",
        "app_store": "App Store",
        "npm": "npm",
        "testflight": "TestFlight",
    }.get(value, _text(value))


def print_catalog(view, output):
    print(_message("L_CATALOG_TITLE", "Optional application catalog"), file=output)
    for index, row in enumerate(view["rows"], 1):
        print(
            "{} [ ] {} | {} | {}".format(
                index,
                _text(row["name"]),
                _label(row["edition"]),
                _label(
                    "already_installed"
                    if row["installed"]
                    else row["installation_status"]
                ),
            ),
            file=output,
        )
        for current in row["installed"]:
            print(
                "    "
                + _label(current.get("source_id") or current.get("source") or "unknown")
                + " | "
                + _label(current.get("channel", "unknown"))
                + " | "
                + _text(current.get("short_version") or current.get("version"))
                + " | "
                + _text(current.get("path") or current.get("prefix")),
                file=output,
            )
        for source in row["sources"]:
            print(
                "    {} | {} | {} | {}".format(
                    _label(source["source_id"]),
                    _label(source.get("evidence")),
                    _text(source.get("observed_at")),
                    (
                        _text(source.get("official_url"))
                        if source.get("official_url")
                        else _message(
                            "L_CATALOG_LINK_PENDING", "Official link pending review"
                        )
                    ),
                ),
                file=output,
            )
        if row["recommendation"]:
            print(
                "    {}: {} | {}: {} | {}".format(
                    _message("L_CATALOG_SOURCE", "Source"),
                    _label(row["recommended_source_id"]),
                    _message("L_CATALOG_UPDATER", "Updater"),
                    _label(row["recommended_updater_id"]),
                    _text(row.get("as_of")),
                ),
                file=output,
            )
            release = row.get("recommended_release") or row.get(
                "latest_compatible_stable"
            )
            print(
                "    "
                + _message("L_CATALOG_LATEST_STABLE", "Latest compatible stable")
                + ": "
                + _text(
                    release.get("version") if isinstance(release, dict) else release
                ),
                file=output,
            )
        print(
            "    {}: {}".format(
                _message("L_CATALOG_LICENSE", "License"), _text(row["license_review"])
            ),
            file=output,
        )
    if view.get("unmatched_installed"):
        print(
            _message(
                "L_CATALOG_INSTALLED_UNMATCHED",
                "Local installations awaiting a reviewed product match",
            ),
            file=output,
        )
        for target in view.get("unmatched_installations", []):
            print(
                "    "
                + _text(
                    target.get("name")
                    or target.get("source_identity")
                    or target.get("bundle_id")
                )
                + " | "
                + _text(target.get("path") or target.get("prefix"))
                + " | "
                + _label(target.get("source_id") or "unknown"),
                file=output,
            )


def print_install_preview(plan, output):
    print(_message("L_INSTALL_PLAN_TITLE", "First-install preview"), file=output)
    for action in plan["actions"]:
        print(
            "{} | {} | {} | {} | {}".format(
                _text(action["name"]),
                _label(action["kind"]),
                _label(action["source_id"]),
                _text(action["version"]),
                _text(action["destination"]),
            ),
            file=output,
        )
        print(
            "    {}: {} | {}: {} | {}: {}".format(
                _message("L_CATALOG_LICENSE", "License"),
                _text(action["license"]),
                _message("L_INSTALL_ADMIN", "Administrator permission"),
                _text(action["requires_administrator"]),
                _message("L_INSTALL_SIZE", "Estimated size"),
                _text(action["size_estimate"]),
            ),
            file=output,
        )
        if action.get("adapter_id") == "homebrew_cask":
            print(_message("L_INSTALL_MANAGER_PERMISSION", "Permission: the existing Homebrew manager may execute this selected official cask, its app, CLI links, manual pages and declared dependencies. Verification covers the manager receipt."), file=output)
            print("    " + _message("L_INSTALL_MANAGER_DEPENDENCIES", "Declared Homebrew dependencies") + ": " + _text(action["manager_preview"]["metadata"].get("depends_on", {})), file=output)
        if action["permissions"]:
            print(
                "    " + ", ".join(_message("L_INSTALL_MANAGER_EFFECTS", "Install selected cask through Homebrew") if x == "manager_delegated_install" else _text(x) for x in action["permissions"]), file=output
            )
        if action["official_url"]:
            print("    " + action["official_url"], file=output)
    for node in plan["requirements"]["nodes"]:
        print(
            "    {} | {} | {} | {}".format(
                _message("L_INSTALL_REQUIREMENT", "Requirement"),
                _text(node["id"]),
                (
                    _message("L_INSTALL_SATISFIED", "Already satisfied")
                    if node["status"] == "satisfied"
                    else _message("L_INSTALL_MISSING", "Manual prerequisite required")
                ),
                _text(node.get("observed_version") or node.get("minimum_version")),
            ),
            file=output,
        )
    print("plan_digest=" + plan["plan_digest"], file=output)


def _interactive(stream):
    import os

    return bool(
        stream.isatty()
        and os.environ.get("MAC_UPDATE_YES") != "1"
        and os.environ.get("MAC_UPDATE_NONINTERACTIVE") != "1"
    )


def _answer(stream, timeout=120):
    import select
    import os
    import sys

    if os.environ.get("MAC_UPDATE_TUI_CHILD") == "1":
        print("\n@@MAC_UPDATE_PROMPT", file=sys.stdout, flush=True)

    ready, _, _ = select.select([stream], [], [], timeout)
    if not ready:
        return ""
    answer = stream.readline(4097)
    return answer.strip() if len(answer) <= 4096 else ""


def _save_install_plan(plan):
    from inventory_store import _root, default_root
    from policy_runtime import _atomic_json

    root = _root(default_root(), True)
    directory = Path(root) / "install-plans"
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_mode & 0o777 != 0o700:
        raise ValueError("unsafe_install_plan_directory")
    path = directory / (plan["plan_id"] + ".json")
    _atomic_json(str(path), plan, exclusive=True)
    return path


def _fresh_catalog_snapshot(recipes, preview_snapshot, script_dir=None):
    from inventory_migration import collect_current_snapshot
    from inventory_store import default_root, load_snapshot

    root = default_root()
    current = collect_current_snapshot(
        script_dir or str(Path(__file__).resolve().parents[2]), root
    )
    # A read-only first preview has no stored profile yet. Keep its random local
    # profile for this UI session while replacing every observed target/source.
    # A saved profile or generation is never replaced by the preview's values.
    if load_snapshot(root) is None and preview_snapshot.get("profile_id") is not None:
        current["profile_id"] = preview_snapshot["profile_id"]
        current["generation"] = preview_snapshot.get("generation", 0)
    return match_catalog_snapshot(current, recipes)


def _rescan_requested(stream, timeout=120):
    import select
    import os
    import sys

    if os.environ.get("MAC_UPDATE_TUI_CHILD") == "1":
        print("\n@@MAC_UPDATE_PROMPT", file=sys.stdout, flush=True)

    ready, _, _ = select.select([stream], [], [], timeout)
    if not ready:
        return False
    # EOF/timeout/cancel do not count as pressing Enter after acquisition.
    return stream.readline(4097) in ("\n", "\r\n")


def approve_install_preview(plan, recipes, snapshot, stream, output, environment=None):
    from install_execution import make_install_consent, execute_install_action
    from policy_runtime import utc_now

    print_install_preview(plan, output)
    if not plan["actions"] or not _interactive(stream):
        print(
            _message(
                "L_CATALOG_NO_PERMISSION", "No new installation permission granted."
            ),
            file=output,
        )
        return 10
    print(
        _message("L_INSTALL_CONFIRM", "Approve only this preview by typing:")
        + " approve "
        + plan["plan_digest"][:12],
        file=output,
        flush=True,
    )
    if _answer(stream) != "approve " + plan["plan_digest"][:12]:
        return 10
    consent = make_install_consent(
        plan, [action["action_id"] for action in plan["actions"]], utc_now()
    )
    code = 0
    manual_opened = False
    for action in plan["actions"]:
        current = _fresh_catalog_snapshot(recipes, snapshot)
        result = execute_install_action(
            plan,
            action["action_id"],
            consent,
            recipes,
            environment or current.get("environment", {}),
            snapshot=current,
        )
        print(_text(action["name"]) + ": " + _label(result["status"]), file=output)
        if result["status"] == "manual_acquisition_opened":
            manual_opened = True
        if result["status"] == "recovery_required":
            code = 1
        elif (
            result["status"] not in ("manual_acquisition_opened", "installed_verified", "manager_installed_verified")
            and code != 1
        ):
            code = 10
    if manual_opened and _interactive(stream):
        print(
            _message(
                "L_CATALOG_RESCAN",
                "Press Enter after manual acquisition to rescan, or type back to return.",
            ),
            file=output,
            flush=True,
        )
        if _rescan_requested(stream):
            current = _fresh_catalog_snapshot(recipes, snapshot)
            view = build_catalog_view(current, recipes, [], {})
            selected = {action["product_id"] for action in plan["actions"]}
            view["rows"] = [
                row for row in view["rows"] if row["product_id"] in selected
            ]
            # This is observation, not an installation receipt. Keep every
            # acquisition journal unverified until independent identity proof.
            print_catalog(view, output)
    return code


def catalog_main(script_dir, mode="catalog", plan_path=None, stream=None, output=None):
    import sys
    from inventory_store import default_root, StoreError
    from install_plan import build_install_plan
    from install_execution import load_install_plan
    from policy_runtime import utc_now

    stream = sys.stdin if stream is None else stream
    output = sys.stdout if output is None else output
    try:
        from inventory_migration import collect_current_snapshot
        from install_execution import recover_installations

        from catalog_manager_install import recover_manager_installations
        recovery = recover_installations(state_dir=default_root()) + recover_manager_installations(state_dir=default_root())
        if recovery:
            print(
                _message("L_INSTALL_RECOVERY", "Interrupted installation review")
                + ": "
                + str(len(recovery)),
                file=output,
            )
        recipes = load_setup_catalog(script_dir)
        snapshot = collect_current_snapshot(script_dir, default_root())
        if mode == "install-plan":
            plan = load_install_plan(plan_path)
            if plan["recipe_fingerprint"] != __import__("user_policy").digest(recipes):
                raise ValueError("recipe_catalog_changed")
            return approve_install_preview(plan, recipes, snapshot, stream, output)
        recommendations = []
        for attempt in range(100):
            view = build_catalog_view(snapshot, recipes, recommendations, {})
            print_catalog(view, output)
            if not _interactive(stream):
                print(
                    _message(
                        "L_CATALOG_NO_PERMISSION",
                        "No new installation permission granted.",
                    ),
                    file=output,
                )
                return 10
            print(
                _message(
                    "L_CATALOG_SELECTION_PROMPT",
                    "Choose numbers and optional sources, for example 1,3:vendor. check 1 compares selected channels. Enter/back/cancel returns.",
                ),
                file=output,
                flush=True,
            )
            answer = _answer(stream)
            if answer.lower().startswith("check "):
                selections = parse_selections(answer[6:], view)
                from channel_probes import compare_selected_channels

                # The advisor reads OS/CPU facts and only the selected public
                # sources. Missing compatibility evidence remains unknown.
                report = compare_selected_channels(
                    snapshot,
                    [s["product_id"] for s in selections],
                    environment=snapshot.get("environment", {}),
                    state_dir=default_root(),
                    manifest_path=str(Path(script_dir) / "config/channel_sources.json"),
                )
                recommendations = report["recommendations"]
                continue
            try:
                selections = parse_selections(answer, view)
            except ValueError:
                print(
                    _message(
                        "L_CATALOG_INVALID", "Invalid selection. No changes made."
                    ),
                    file=output,
                )
                continue
            if not selections:
                return 0
            plan = build_install_plan(selections, snapshot, recipes, utc_now())
            _save_install_plan(plan)
            return approve_install_preview(plan, recipes, snapshot, stream, output)
        return 10
    except (ValueError, OSError, TypeError, KeyError, StoreError):
        print(
            _message(
                "L_CATALOG_UNAVAILABLE",
                "Catalog or plan unavailable. No installation started.",
            ),
            file=output,
        )
        return 10
