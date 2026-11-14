"""Separate first-install previews and explicit dependency graphs. No I/O."""

import copy
import os
import re
import uuid
import datetime
from user_policy import digest, timestamp
from vendor_feeds import version_compare
from setup_catalog import safe_official_url, match_catalog_snapshot

DEFAULT_REQUIREMENTS = {
    "homebrew": dict(
        kind="tool", dependencies=[], minimum_version=None, automatic=False
    ),
    "python": dict(
        kind="tool", dependencies=[], minimum_version="3.9.0", automatic=False
    ),
    "clt": dict(kind="tool", dependencies=[], minimum_version=None, automatic=False),
    "rosetta": dict(
        kind="permission", dependencies=[], minimum_version=None, automatic=False
    ),
}


def verified_install_bindings(recipe):
    from recipe_acceptance import (
        recipe_fingerprint,
        candidate_binding,
        requirements_fingerprint,
    )

    value = recipe["verified_recipe"]
    return dict(
        recipe_sha256=recipe_fingerprint(value),
        candidate_sha256=candidate_binding(value["candidate"]),
        requirements_sha256=requirements_fingerprint(value),
    )


def verified_install_recipe_eligible(recipe, environment=None, now=None):
    """Planning evidence only: no signature or consent for an absent target.

    A live install record must bind the exact v2 candidate. Full acceptance is
    evaluated again with actual staged observations after consent/acquisition.
    """
    from app_recipes import validate_recipe, _os
    from recipe_acceptance import _record_matches

    try:
        value = recipe["verified_recipe"]
        validate_recipe(value)
        names = [value["id"], value["product"]] + value["matrix_ids"]
        if any(
            n.casefold().replace("-", "").replace(" ", "").startswith("deepseek")
            for n in names
        ):
            return False
        if (
            recipe.get("install_adapter") != "verified_recipe_zip"
            or value["channel"] != "stable"
            or value["installation_source"] != "vendor"
            or value["update_mechanism"] != "direct_artifact"
            or value["adapter_id"] not in ("github_dmg", "mozilla_dmg")
            or value["candidate"]["artifact_type"] != "zip"
            or value["effect_scope"]["install"] != ["install_app"]
            or any(
                n["kind"] == "dependency" for n in value["requirement_graph"]["nodes"]
            )
            or recipe.get("destination") is None
            or not os.path.isabs(recipe["destination"])
            or recipe.get("artifact_effects") != [recipe["destination"]]
        ):
            return False
        candidate = value["candidate"]
        if (
            recipe.get("product_id") not in value["matrix_ids"]
            or recipe.get("edition") != value["edition"]
            or recipe.get("channel") != value["channel"]
            or recipe.get("installation_source") != value["installation_source"]
            or recipe.get("requires_administrator") is not False
            or recipe.get("architectures") != value["architectures"]
            or recipe.get("download_hosts") != value["download_hosts"]
            or os.path.basename(recipe["destination"]) != candidate["bundle_name"]
            or any(
                recipe.get(key) != candidate[key]
                for key in (
                    "version",
                    "build",
                    "bundle_id",
                    "team_id",
                    "minimum_os",
                    "artifact_type",
                )
            )
        ):
            return False
        permissions = {
            n["value"]
            for n in value["requirement_graph"]["nodes"]
            if n["kind"] == "permission" and "install" in n["operations"]
        }
        if not permissions.issubset({"install_app"}):
            return False
        moment = timestamp(now) if now else datetime.datetime.now(datetime.timezone.utc)
        for record in value["acceptance_records"]["install"]:
            host = (
                environment
                if environment is not None
                else dict(os_version=record["os_version"], architecture="arm64")
            )
            if (
                _os(host.get("os_version")) < _os(candidate["minimum_os"])
                or host.get("architecture") != candidate["architecture"]
            ):
                continue
            facts = dict(
                host,
                now=moment.strftime("%Y-%m-%dT%H:%M:%SZ"),
                granted_permissions=sorted(permissions),
            )
            if _record_matches(record, value, "install", facts, permissions):
                return True
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    return False


def install_recipe_eligible(recipe, environment=None, now=None):
    if "verified_recipe" in recipe:
        return verified_install_recipe_eligible(recipe, environment, now)
    acceptance = recipe.get("first_install_acceptance")
    return bool(
        recipe.get("install_adapter") == "vendor_bundle"
        and recipe.get("requirements_known") is True
        and isinstance(acceptance, dict)
        and acceptance.get("status") == "passed"
        and acceptance.get("recipe_revision") == recipe.get("revision")
        and acceptance.get("version") == recipe.get("version")
        and acceptance.get("source_id") == recipe.get("installation_source")
        and recipe.get("channel") == "stable"
        and recipe.get("bundle_id")
        and recipe.get("team_id")
        and "arm64" in recipe.get("architectures", [])
        and recipe.get("minimum_os")
        and isinstance(recipe.get("download_hosts"), list)
        and recipe["download_hosts"]
        and recipe.get("artifact_type") in ("app", "dmg", "zip")
        and recipe.get("requires_administrator") is False
        and recipe.get("destination")
        and os.path.isabs(recipe["destination"])
        and recipe.get("artifact_effects") == [recipe["destination"]]
    )


def _safe_payload(value, depth=0):
    from urllib.parse import urlsplit, parse_qs

    if depth > 32:
        raise ValueError("plan_nesting_limit")
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).lower() in (
                "password",
                "secret",
                "api_key",
                "authorization",
                "access_token",
            ):
                raise ValueError("credential_in_plan")
            _safe_payload(item, depth + 1)
    elif isinstance(value, list):
        for item in value:
            _safe_payload(item, depth + 1)
    elif isinstance(value, str) and value.startswith(("https://", "http://")):
        parsed = urlsplit(value)
        if (
            parsed.username is not None
            or parsed.password is not None
            or parsed.scheme != "https"
            or any(
                re.search(r"token|secret|credential|signature|api.?key", key, re.I)
                for key in parse_qs(parsed.query)
            )
        ):
            raise ValueError("credential_in_plan")


def _recipe_map(recipes):
    result = {}
    for recipe in recipes.get("recipes", []):
        pid = recipe.get("product_id")
        if (
            not isinstance(pid, str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,127}", pid)
            or pid in result
        ):
            raise ValueError("invalid_catalog_product")
        result[pid] = recipe
    return result


def _selection(selection, by_id):
    recipe = by_id.get(selection.get("product_id"))
    if not recipe or selection.get("edition") != recipe.get("edition"):
        raise ValueError("edition_mismatch")
    source = next(
        (
            s
            for s in recipe.get("sources", [])
            if s.get("source_id") == selection.get("source_id")
        ),
        None,
    )
    if source is None:
        raise ValueError("unknown_source")
    architecture = selection.get("architecture", "arm64")
    if (
        architecture != "arm64"
        or source.get("architectures")
        and architecture not in source["architectures"]
    ):
        raise ValueError("architecture_mismatch")
    return recipe, source


def resolve_requirements(selections, environment, recipes):
    by_id = _recipe_map(recipes)
    definitions = dict(DEFAULT_REQUIREMENTS)
    definitions.update(recipes.get("requirements", {}))
    needed = []
    optional = []
    for selection in selections:
        recipe, _ = _selection(selection, by_id)
        needed.extend(recipe.get("requirements", []))
        if selection.get("source_id") == "homebrew":
            needed.append("homebrew")
        allowed_optional = recipe.get("optional_requirements", [])
        for req in selection.get("optional_requirements", []):
            if req not in allowed_optional:
                raise ValueError("unknown_optional_requirement")
            needed.append(req)
            optional.append(req)
    nodes = []
    edges = []
    visiting = set()
    visited = set()

    def visit(key):
        if key in visited:
            return
        if key in visiting:
            raise ValueError("requirement_cycle")
        spec = definitions.get(key)
        if not isinstance(spec, dict) or spec.get("kind") not in (
            "tool",
            "permission",
            "license",
            "account",
            "mdm",
        ):
            raise ValueError("unknown_requirement")
        if not isinstance(spec.get("dependencies", []), list):
            raise ValueError("invalid_requirement_dependencies")
        visiting.add(key)
        for child in spec.get("dependencies", []):
            edges.append([child, key])
            visit(child)
        visiting.remove(key)
        visited.add(key)
        observed = environment.get(key, {})
        if not isinstance(observed, dict):
            observed = {}
        version = observed.get("version")
        minimum = spec.get("minimum_version")
        satisfied = (
            observed.get("satisfied") is True
            or isinstance(version, str)
            and (minimum is None or version_compare(version, minimum) in (0, 1))
        )
        status = (
            "satisfied"
            if satisfied
            else "manual" if spec["kind"] != "tool" else "missing"
        )
        nodes.append(
            dict(
                id=key,
                kind=spec["kind"],
                status=status,
                minimum_version=minimum,
                observed_version=version,
                requires_administrator=spec.get("requires_administrator", "unknown"),
                automatic=False,
                optional=key in optional,
            )
        )

    for requirement in needed:
        visit(requirement)
    return dict(
        nodes=nodes,
        edges=edges,
        missing_conditions=[n["id"] for n in nodes if n["status"] != "satisfied"],
        optional=sorted(set(optional)),
        complete=all(n["status"] == "satisfied" for n in nodes),
    )


def _digest_value(plan):
    value = copy.deepcopy(plan)
    value.pop("plan_digest", None)
    for action in value.get("actions", []):
        action.pop("plan_digest", None)
    return value


def plan_digest(plan):
    return digest(_digest_value(plan))


def build_install_plan(selections, snapshot, recipes, now):
    timestamp(now)
    _safe_payload(recipes)
    by_id = _recipe_map(recipes)
    snapshot = match_catalog_snapshot(snapshot, recipes)
    if not isinstance(selections, list) or len(selections) > 1000:
        raise ValueError("invalid_selections")
    if len({s.get("product_id") for s in selections}) != len(selections):
        raise ValueError("duplicate_selection")
    requirements = resolve_requirements(
        selections, snapshot.get("environment", {}), recipes
    )
    plan = dict(
        schema_version=1,
        plan_type="install_plan",
        plan_id=str(uuid.uuid4()),
        created_at=now,
        profile_id=snapshot.get("profile_id"),
        snapshot_generation=snapshot.get("generation"),
        selections=copy.deepcopy(selections),
        recipe_fingerprint=digest(recipes),
        requirements=requirements,
        requirement_graph_digest=digest(requirements),
        actions=[],
        optional_additions=requirements["optional"],
    )
    for selection in selections:
        recipe, source = _selection(selection, by_id)
        installed = [
            t
            for key in ("instances", "packages")
            for t in snapshot.get(key, [])
            if t.get("product_id") == selection["product_id"]
            and t.get("edition") == selection["edition"]
            and t.get("presence") == "present"
        ]
        own_requirements = resolve_requirements(
            [selection], snapshot.get("environment", {}), recipes
        )
        eligible = (
            install_recipe_eligible(recipe, snapshot.get("environment", {}), now)
            and own_requirements["complete"]
            and selection["source_id"] == recipe.get("installation_source")
            and selection["source_id"] != "app_store"
        )
        reason = (
            "already_installed_manual_migration"
            if installed
            else (
                "first_install_acceptance_missing"
                if not eligible
                else "approved_recipe_requires_fresh_consent"
            )
        )
        kind = (
            "manual_migration"
            if installed
            else "install" if eligible else "manual_acquisition"
        )
        action = dict(
            action_id=str(uuid.uuid4()),
            plan_id=plan["plan_id"],
            plan_created_at=now,
            profile_id=plan["profile_id"],
            snapshot_generation=plan["snapshot_generation"],
            product_id=recipe["product_id"],
            name=recipe["name"],
            edition=recipe["edition"],
            kind=kind,
            source_id=selection["source_id"],
            adapter_id=(
                recipe.get("install_adapter") if eligible else "manual_acquisition"
            ),
            version=recipe.get("version"),
            build=recipe.get("build"),
            destination=recipe.get("destination"),
            artifact_effects=(
                copy.deepcopy(recipe.get("artifact_effects", [])) if eligible else []
            ),
            recipe=copy.deepcopy(recipe),
            recipe_fingerprint=digest(recipe),
            requirement_graph_digest=plan["requirement_graph_digest"],
            requirement_ids=[node["id"] for node in own_requirements["nodes"]],
            requirements_complete=own_requirements["complete"],
            official_url=safe_official_url(source.get("official_url")),
            requires_administrator=recipe.get("requires_administrator", "unknown"),
            license=recipe.get("license_review", "unknown"),
            size_estimate=recipe.get("size_estimate"),
            permissions=copy.deepcopy(recipe.get("permissions", [])),
            reason_codes=[reason],
            installed=copy.deepcopy(installed),
        )
        if eligible and "verified_recipe" in recipe:
            action["verified_recipe_bindings"] = verified_install_bindings(recipe)
            action["verified_environment"] = copy.deepcopy(
                snapshot.get("environment", {})
            )
        plan["actions"].append(action)
    plan["plan_digest"] = plan_digest(plan)
    for action in plan["actions"]:
        action["plan_digest"] = plan["plan_digest"]
    return validate_install_plan(plan)


def validate_install_plan(plan):
    if (
        not isinstance(plan, dict)
        or type(plan.get("schema_version")) is not int
        or plan["schema_version"] != 1
        or plan.get("plan_type") != "install_plan"
    ):
        raise ValueError("invalid_install_plan")
    timestamp(plan.get("created_at"))
    _safe_payload(plan)
    try:
        uuid.UUID(plan.get("plan_id"))
    except (ValueError, TypeError, AttributeError):
        raise ValueError("invalid_plan_id")
    if (
        not isinstance(plan.get("actions"), list)
        or len(plan["actions"]) > 1000
        or plan.get("plan_digest") != plan_digest(plan)
    ):
        raise ValueError("install_plan_changed")
    if digest(plan.get("requirements")) != plan.get("requirement_graph_digest"):
        raise ValueError("requirements_changed")
    seen = set()
    destinations = set()
    for action in plan["actions"]:
        if (
            not isinstance(action, dict)
            or not isinstance(action.get("action_id"), str)
            or not action["action_id"]
            or action.get("action_id") in seen
            or action.get("kind")
            not in ("install", "manual_acquisition", "manual_migration")
        ):
            raise ValueError("invalid_install_action")
        seen.add(action["action_id"])
        if action.get("kind") == "install":
            path = action.get("destination")
            if not isinstance(path, str) or path.casefold() in destinations:
                raise ValueError("overlapping_install_targets")
            destinations.add(path.casefold())
        if (
            action.get("plan_id") != plan.get("plan_id")
            or action.get("plan_created_at") != plan.get("created_at")
            or action.get("plan_digest") != plan["plan_digest"]
            or digest(action.get("recipe")) != action.get("recipe_fingerprint")
        ):
            raise ValueError("install_action_changed")
        if action["kind"] == "install" and (
            not install_recipe_eligible(
                action["recipe"], action.get("verified_environment"), plan["created_at"]
            )
            or action.get("destination") != action["recipe"]["destination"]
            or action.get("version") != action["recipe"]["version"]
            or action.get("artifact_effects") != [action["destination"]]
            or action.get("requirements_complete") is not True
            or any(
                node["status"] != "satisfied"
                for node in plan["requirements"]["nodes"]
                if node["id"] in action.get("requirement_ids", [])
            )
        ):
            raise ValueError("install_recipe_unreviewed")
        if (
            action["kind"] == "install"
            and "verified_recipe" in action["recipe"]
            and (
                action.get("verified_recipe_bindings")
                != verified_install_bindings(action["recipe"])
                or action.get("build") != action["recipe"]["build"]
            )
        ):
            raise ValueError("install_candidate_changed")
    return plan
