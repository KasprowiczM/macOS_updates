"""Opt-in shadow inventory integration, independent of the update executor."""

import argparse
import json
import os

from app_recipes import load_recipes, load_legacy_capabilities
from inventory_collect import Providers, collect_snapshot, read_bundle_static
from inventory_model import validate_snapshot
from inventory_providers import read_cli_manifests, read_mas, discover_cli_prefixes
from brew_casks import installed_inventory_source
from inventory_store import StoreError, load_snapshot, save_snapshot
from source_resolver import resolve_snapshot


def run_shadow(script_dir, roots=None, dry_run=False, env=None):
    env = os.environ if env is None else env
    home = env.get("HOME") or os.path.expanduser("~")
    if roots is None:
        override = env.get("MAC_UPDATE_APP_DIRS")
        roots = (
            override.split(os.pathsep)
            if override
            else [
                "/Applications",
                os.path.join(home, "Applications"),
                "/System/Applications",
            ]
        )
    roots = list(dict.fromkeys(x for x in roots if x))
    if not roots or len(roots) > 32:
        raise ValueError("invalid_roots")
    brew_prefixes = env.get(
        "MAC_UPDATE_BREW_PREFIXES", "/opt/homebrew:/usr/local"
    ).split(os.pathsep)
    cli_prefixes = discover_cli_prefixes(home, env)
    if len(brew_prefixes) > 32 or len(cli_prefixes) > 64:
        raise ValueError("prefix_limit")
    state_dir = env.get("MAC_UPDATE_STATE_DIR") or os.path.join(
        env.get("XDG_STATE_HOME") or os.path.join(home, ".local/state"), "mac-update"
    )
    previous = load_snapshot(state_dir)
    providers = Providers(
        read_bundle=read_bundle_static,
        list_mas=read_mas,
        list_brew=installed_inventory_source,
        list_cli=read_cli_manifests,
        brew_prefixes=[p for p in brew_prefixes if p],
        cli_prefixes=cli_prefixes,
    )
    snapshot = validate_snapshot(collect_snapshot(roots, providers, previous))
    recipes = load_recipes(os.path.join(script_dir, "config/app_recipes.json"))
    catalog = load_legacy_capabilities(
        os.path.join(script_dir, "config/internet_app_methods.txt")
    )
    resolutions = resolve_snapshot(snapshot, recipes)
    if not dry_run:
        snapshot = save_snapshot(
            state_dir, snapshot, previous["generation"] if previous else 0
        )
    partial = any(
        s["status"] != "ok" or not s["complete"] for s in snapshot["sources"].values()
    )
    report = dict(
        mode="shadow",
        saved=not dry_run,
        generation=snapshot["generation"],
        snapshot_id=snapshot["snapshot_id"],
        instances=len(snapshot["instances"]),
        packages=len(snapshot["packages"]),
        catalog_capabilities=len(catalog),
        readiness="partial" if partial else "complete",
        resolutions=resolutions,
    )
    report["source_statuses"] = {
        key: {field: source[field] for field in ("status", "complete", "reason_code")}
        for key, source in snapshot["sources"].items()
    }
    return report, 10 if partial else 0


def main(script_dir, argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--root", action="append")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 1
    try:
        report, code = run_shadow(script_dir, args.root, args.dry_run)
        if args.json:
            print(json.dumps(report, ensure_ascii=True))
        else:
            print(
                os.environ.get("L_SHADOW_REPORT", "Shadow inventory")
                + ": "
                + str(report["instances"])
                + " / "
                + str(report["packages"])
            )
            print(
                os.environ.get(
                    "L_SHADOW_NO_ACTIONS", "Observation only; update routing unchanged."
                )
            )
            if code == 10:
                print(
                    os.environ.get(
                        "L_SHADOW_PARTIAL", "Some sources were not completely observed."
                    )
                )
        return code
    except (StoreError, OSError, ValueError, TypeError):
        # Do not print raw metadata, file paths or traceback into terminal reports.
        print(os.environ.get("L_SHADOW_FAILED", "Shadow inventory could not be saved."))
        return 1
