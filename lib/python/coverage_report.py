"""Schema-2 coverage views from the common collector and source resolver only."""

import argparse
import json
import os
from pathlib import Path

from app_capabilities import (
    detect_capabilities,
    propose_recipe,
    redact_proposal,
    proposal_preview_id,
    export_proposal,
)
from app_recipes import load_recipes, load_legacy_capabilities
from inventory_model import validate_snapshot
from inventory_migration import collect_current_snapshot
from inventory_store import StoreError
from source_resolver import resolve_snapshot

CLASSIFICATIONS = (
    "verified_direct",
    "triggered_unverified",
    "externally_managed",
    "manual",
    "excluded",
    "unknown",
)
_TEXT = {
    "en": (
        "Local update coverage",
        "{count} detected, {possible} with a possible updater. Choose handling.",
        "No update permission is inferred.",
        "Catalog adapter recipes",
        "Unknown sources are normal manual review items.",
        "Proposal preview; export requires --export --accept PREVIEW_ID.",
        "Read-only observation unavailable.",
    ),
    "pl": (
        "Lokalne pokrycie aktualizacji",
        "Wykryto {count}, {possible} z możliwym updaterem. Wybierz obsługę.",
        "Nie utworzono zgód na aktualizacje.",
        "Katalog recept adapterów",
        "Nieznane źródła wymagają zwykłej ręcznej weryfikacji.",
        "Podgląd propozycji; eksport wymaga --export --accept PREVIEW_ID.",
        "Obserwacja tylko do odczytu jest niedostępna.",
    ),
    "es": (
        "Cobertura local de actualizaciones",
        "{count} detectadas, {possible} con posible actualizador. Elija cómo gestionarlas.",
        "No se deducen permisos para actualizar.",
        "Catálogo de recetas de adaptadores",
        "Los orígenes desconocidos requieren una revisión manual normal.",
        "Vista previa; la exportación requiere --export --accept PREVIEW_ID.",
        "La observación de solo lectura no está disponible.",
    ),
    "it": (
        "Copertura locale degli aggiornamenti",
        "{count} rilevate, {possible} con un possibile updater. Scegli come gestirle.",
        "Non vengono dedotte autorizzazioni di aggiornamento.",
        "Catalogo delle ricette degli adattatori",
        "Le origini sconosciute richiedono una normale verifica manuale.",
        "Anteprima; l’esportazione richiede --export --accept PREVIEW_ID.",
        "Osservazione in sola lettura non disponibile.",
    ),
    "pt": (
        "Cobertura local de atualizações",
        "{count} detetadas, {possible} com possível atualizador. Escolha como gerir.",
        "Não são inferidas permissões para atualizar.",
        "Catálogo de receitas de adaptadores",
        "As origens desconhecidas requerem uma revisão manual normal.",
        "Pré-visualização; exportar requer --export --accept PREVIEW_ID.",
        "A observação só de leitura não está disponível.",
    ),
    "de": (
        "Lokale Aktualisierungsabdeckung",
        "{count} erkannt, {possible} mit möglichem Updater. Behandlung auswählen.",
        "Es wird keine Aktualisierungserlaubnis abgeleitet.",
        "Katalog der Adapterrezepte",
        "Unbekannte Quellen erfordern eine normale manuelle Prüfung.",
        "Vorschau; Export erfordert --export --accept PREVIEW_ID.",
        "Schreibgeschützte Beobachtung ist nicht verfügbar.",
    ),
    "fr": (
        "Couverture locale des mises à jour",
        "{count} détectées, {possible} avec une mise à jour possible. Choisissez le traitement.",
        "Aucune autorisation de mise à jour n’est déduite.",
        "Catalogue des recettes d’adaptateurs",
        "Les sources inconnues nécessitent une vérification manuelle normale.",
        "Aperçu; l’exportation nécessite --export --accept PREVIEW_ID.",
        "Observation en lecture seule indisponible.",
    ),
}


def labels(locale):
    return _TEXT.get(locale, _TEXT["en"])


def _display(value):
    return "".join(
        character if character.isprintable() else " " for character in str(value)
    )[:512]


def _classification(resolution):
    if resolution["source"] == "conflict":
        return "manual"
    if (
        resolution["capability"] == "reviewed_direct"
        and resolution["evidence_grade"] == "confirmed"
    ):
        return "verified_direct"
    if (
        resolution["capability"] == "native_managed"
        and resolution["evidence_grade"] == "confirmed"
    ):
        return "externally_managed"
    if resolution["capability"] == "check_only" or resolution["source"] != "unknown":
        return "manual"
    return "unknown"


def build_coverage_report(snapshot, recipes, catalog, version="unknown"):
    validate_snapshot(snapshot)
    resolved = {
        (r["target"]["kind"], r["target"]["id"]): r
        for r in resolve_snapshot(snapshot, recipes)
    }
    groups = {key: [] for key in CLASSIFICATIONS}
    package_rows, possible, conflicts = [], 0, 0
    intel = []
    for kind, records, field in (
        ("app", snapshot["instances"], "instance_id"),
        ("package", snapshot["packages"], "package_id"),
    ):
        for record in records:
            if record["presence"] == "absent":
                continue
            resolution = resolved[(kind, record[field])]
            classification = _classification(resolution)
            capabilities = detect_capabilities(record, {}) if kind == "app" else []
            row = dict(
                app=_display(
                    record.get("name")
                    or (
                        Path(record["path"]).stem
                        if kind == "app"
                        else record.get("source_identity")
                    )
                ),
                target=resolution["target"],
                path=record.get("path"),
                bundle_id=record.get("bundle_id"),
                presence=record["presence"],
                freshness=record["freshness"],
                source=resolution["source"],
                capability=resolution["capability"],
                resolution=resolution,
                method=resolution["adapter_id"] or "manual",
                classification=classification,
                managed_by=(
                    "source_unmanaged"
                    if resolution["source"] == "unknown"
                    else resolution["source"]
                ),
                label=resolution["source"] + " / " + resolution["capability"],
                possible_updater=bool(capabilities),
            )
            if kind == "package":
                package_rows.append(row)
                continue
            possible += bool(capabilities)
            conflicts += resolution["source"] == "conflict"
            if record.get("architectures") == ["x86_64"]:
                intel.append(row["app"])
            groups[classification].append(row)
    for rows in groups.values():
        rows.sort(key=lambda row: (row["app"].casefold(), row["path"]))
    counts = {key: len(value) for key, value in groups.items()}
    total = sum(counts.values())
    automatic = counts["verified_direct"] + counts["externally_managed"]
    supported = automatic + counts["triggered_unverified"]
    known = supported + counts["manual"]

    def percent(count):
        return round(count * 100.0 / total, 1) if total else 100.0

    # Catalog rows are capabilities only. No name/alias asserts local presence.
    catalog_rows = [
        dict(app=row["name"], method=row["adapter_id"], presence="not_evaluated")
        for row in catalog
    ]
    by_method = {}
    for row in catalog_rows:
        by_method.setdefault(
            row["method"], dict(installed=[], not_installed=[], catalog=[])
        )["catalog"].append(row["app"])
    partial = any(
        source["status"] != "ok" or not source["complete"]
        for source in snapshot["sources"].values()
    )
    return dict(
        schema_version=2,
        version=version,
        installed_unique_count=total,
        installed_package_count=len(package_rows),
        supported_coverage_count=supported,
        supported_coverage_percent=percent(supported),
        automatic_coverage_count=automatic,
        automatic_coverage_percent=percent(automatic),
        known_coverage_count=known,
        known_coverage_percent=percent(known),
        classification_counts=counts,
        classifications=groups,
        package_classifications=package_rows,
        verified_direct_count=counts["verified_direct"],
        triggered_unverified_count=counts["triggered_unverified"],
        externally_managed_count=counts["externally_managed"],
        manual_count=counts["manual"],
        excluded_count=counts["excluded"],
        unknown_count=counts["unknown"],
        intel_only_count=len(intel),
        intel_only_apps=sorted(intel),
        possible_updater_count=possible,
        source_conflict_count=conflicts,
        catalog_count=len(catalog_rows),
        registry_installed_target_count=0,
        not_installed_supported_count=0,
        not_installed_supported=[],
        catalog_capability_count=len(catalog_rows),
        catalog_capabilities=catalog_rows,
        by_method=by_method,
        installed_updatable_count=automatic,
        installed_updatable=groups["verified_direct"] + groups["externally_managed"],
        unknown_installed_count=counts["unknown"],
        unknown_installed_sample=[row["app"] for row in groups["unknown"]][:40],
        readiness="partial" if partial else "complete",
        errors=[],
        source_statuses={
            key: {
                field: source[field] for field in ("status", "complete", "reason_code")
            }
            for key, source in snapshot["sources"].items()
        },
    )


def main(script_dir, argv, mode="coverage"):
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--show-supported", action="store_true")
    parser.add_argument("--root", action="append")
    if mode == "scaffold":
        parser.add_argument("app_path")
        parser.add_argument("adapter", nargs="?", default="manual")
        parser.add_argument("--export", action="store_true")
        parser.add_argument("--accept")
    args = parser.parse_args(argv)
    locale = os.environ.get("MAC_UPDATE_LANG") or os.environ.get("MAC_LANG", "en")
    text = labels(locale)
    try:
        snapshot = collect_current_snapshot(script_dir, roots=args.root)
        recipes = load_recipes(os.path.join(script_dir, "config/app_recipes.json"))
        if mode == "scaffold":
            # Exact observed path is the only selector. Names cannot create identity.
            matches = [
                item
                for item in snapshot["instances"]
                if item["path"] == os.path.abspath(args.app_path)
                and item["presence"] == "present"
            ]
            if len(matches) != 1:
                raise ValueError("select one exact observed application path")
            proposal = propose_recipe(matches[0], detect_capabilities(matches[0], {}))
            public = (
                export_proposal(proposal, args.accept)
                if args.export
                else redact_proposal(proposal)
            )
            print(
                json.dumps(
                    dict(preview_id=proposal_preview_id(proposal), proposal=public),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            if not args.json:
                print(text[5])
            return 0
        catalog = load_legacy_capabilities(
            os.path.join(script_dir, "config/internet_app_methods.txt")
        )
        version_path = os.path.join(script_dir, "VERSION")
        with open(version_path, "r", encoding="utf-8") as stream:
            version = _display(stream.read(100).strip())
        report = build_coverage_report(snapshot, recipes, catalog, version)
        if mode == "feeds":
            proposals = [
                dict(
                    target=item["instance_id"],
                    capabilities=detect_capabilities(item, {}),
                    proposal=redact_proposal(
                        propose_recipe(item, detect_capabilities(item, {}))
                    ),
                )
                for item in snapshot["instances"]
                if item["presence"] != "absent"
            ]
            if args.json:
                print(
                    json.dumps(
                        dict(
                            schema_version=1,
                            detected=report["installed_unique_count"],
                            possible_updaters=report["possible_updater_count"],
                            proposals=proposals,
                        ),
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            else:
                print(
                    text[1].format(
                        count=report["installed_unique_count"],
                        possible=report["possible_updater_count"],
                    )
                )
                print(text[2])
            return 0
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        print(text[0] + ": " + version)
        print(
            text[1].format(
                count=report["installed_unique_count"],
                possible=report["possible_updater_count"],
            )
        )
        print(text[2])
        print(text[4])
        for rows in report["classifications"].values():
            for row in rows:
                print("  " + row["app"] + ": " + row["label"])
        print(text[3] + ": " + str(len(catalog)))
        if args.show_supported:
            for row in catalog:
                print("  " + _display(row["name"]) + ": " + _display(row["adapter_id"]))
        return 0
    except (StoreError, OSError, ValueError, TypeError):
        print(text[6])
        return 10
