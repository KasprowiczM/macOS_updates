"""Render local observations through the common resolver, retaining notes safely."""

import re
from inventory_model import validate_snapshot
from source_resolver import resolve_snapshot

_KEYS = (
    "title",
    "observation",
    "unknown_help",
    "apps",
    "packages",
    "notes",
    "name",
    "version",
    "path",
    "presence",
    "freshness",
    "identity",
    "manager",
    "prefix",
    "source",
    "capability",
)
_LABELS = {
    "en": (
        "Local inventory",
        "Observations do not grant permission to update.",
        "An unknown source is a normal manual review state. Status and capability codes describe observations, not consent.",
        "Applications",
        "Packages",
        "Preserved notes",
        "Name",
        "Version",
        "Path",
        "Presence",
        "Freshness",
        "Source identity",
        "Manager",
        "Prefix",
        "Source",
        "Capability",
    ),
    "pl": (
        "Lokalny inwentarz",
        "Obserwacje nie stanowią zgody na aktualizacje.",
        "Nieznane źródło oznacza zwykłą ręczną weryfikację. Kody stanu i możliwości opisują obserwacje, a nie zgodę.",
        "Aplikacje",
        "Pakiety",
        "Zachowane notatki",
        "Nazwa",
        "Wersja",
        "Ścieżka",
        "Obecność",
        "Aktualność",
        "Tożsamość źródła",
        "Menedżer",
        "Prefiks",
        "Źródło",
        "Możliwości",
    ),
    "es": (
        "Inventario local",
        "Las observaciones no conceden permiso para actualizar.",
        "Un origen desconocido requiere una revisión manual normal. Los códigos de estado y capacidad describen observaciones, no permisos.",
        "Aplicaciones",
        "Paquetes",
        "Notas conservadas",
        "Nombre",
        "Versión",
        "Ruta",
        "Presencia",
        "Vigencia",
        "Identidad del origen",
        "Gestor",
        "Prefijo",
        "Origen",
        "Capacidad",
    ),
    "it": (
        "Inventario locale",
        "Le osservazioni non autorizzano gli aggiornamenti.",
        "Un’origine sconosciuta richiede una normale verifica manuale. I codici di stato e capacità descrivono osservazioni, non autorizzazioni.",
        "Applicazioni",
        "Pacchetti",
        "Note conservate",
        "Nome",
        "Versione",
        "Percorso",
        "Presenza",
        "Attualità",
        "Identità di origine",
        "Gestore",
        "Prefisso",
        "Origine",
        "Capacità",
    ),
    "pt": (
        "Inventário local",
        "As observações não concedem permissão para atualizar.",
        "Uma origem desconhecida requer uma revisão manual normal. Os códigos de estado e capacidade descrevem observações, não permissões.",
        "Aplicações",
        "Pacotes",
        "Notas preservadas",
        "Nome",
        "Versão",
        "Caminho",
        "Presença",
        "Atualidade",
        "Identidade da origem",
        "Gestor",
        "Prefixo",
        "Origem",
        "Capacidade",
    ),
    "de": (
        "Lokales Inventar",
        "Beobachtungen erteilen keine Erlaubnis für Aktualisierungen.",
        "Eine unbekannte Quelle erfordert eine normale manuelle Prüfung. Status- und Fähigkeitscodes beschreiben Beobachtungen, keine Zustimmung.",
        "Anwendungen",
        "Pakete",
        "Erhaltene Notizen",
        "Name",
        "Version",
        "Pfad",
        "Anwesenheit",
        "Aktualität",
        "Quellenidentität",
        "Paketverwaltung",
        "Präfix",
        "Quelle",
        "Fähigkeit",
    ),
    "fr": (
        "Inventaire local",
        "Les observations ne donnent pas l’autorisation de mettre à jour.",
        "Une source inconnue nécessite une vérification manuelle normale. Les codes d’état et de capacité décrivent des observations, pas un consentement.",
        "Applications",
        "Paquets",
        "Notes conservées",
        "Nom",
        "Version",
        "Chemin",
        "Présence",
        "Actualité",
        "Identité de la source",
        "Gestionnaire",
        "Préfixe",
        "Source",
        "Capacité",
    ),
}


def _cell(value):
    return (
        str(value if value is not None else "?")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def render_inventory(inventory, notes, locale="en", recipes=None):
    validate_snapshot(inventory)
    labels = dict(zip(_KEYS, _LABELS.get(locale, _LABELS["en"])))
    resolutions = {
        (r["target"]["kind"], r["target"]["id"]): r
        for r in resolve_snapshot(
            inventory,
            recipes if recipes is not None else {"schema_version": 1, "recipes": []},
        )
    }
    rows = [
        "# " + labels["title"],
        "",
        "<!-- local-inventory schema=1 generation="
        + str(inventory["generation"])
        + " -->",
        "",
        labels["observation"],
        "",
        labels["unknown_help"],
        "",
        "## " + labels["apps"],
        "",
    ]

    def table(headers):
        rows.append("| " + " | ".join(labels[x] for x in headers) + " |")
        rows.append("|" + "---|" * len(headers))

    table(("name", "version", "path", "presence", "freshness", "source", "capability"))
    for app in sorted(inventory["instances"], key=lambda x: x["path"]):
        if app["presence"] == "absent":
            continue
        resolved = resolutions[("app", app["instance_id"])]
        values = (
            app["name"],
            app["short_version"],
            app["path"],
            app["presence"],
            app["freshness"],
            resolved["source"],
            resolved["capability"],
        )
        rows.append("| " + " | ".join(_cell(x) for x in values) + " |")
    rows += ["", "## " + labels["packages"], ""]
    table(
        (
            "identity",
            "manager",
            "version",
            "prefix",
            "presence",
            "freshness",
            "source",
            "capability",
        )
    )
    for pkg in sorted(
        inventory["packages"],
        key=lambda x: (x["prefix"], x.get("source_identity") or ""),
    ):
        if pkg["presence"] == "absent":
            continue
        resolved = resolutions[("package", pkg["package_id"])]
        values = (
            pkg["source_identity"],
            pkg["manager"],
            pkg["version"],
            pkg["prefix"],
            pkg["presence"],
            pkg["freshness"],
            resolved["source"],
            resolved["capability"],
        )
        rows.append("| " + " | ".join(_cell(x) for x in values) + " |")
    rows += ["", "## " + labels["notes"], ""]
    # JSON keeps exact original bytes/text. Fences keep imported tables separate
    # from current membership, including hostile embedded Markdown fences.
    for note in notes.get("orphans", []) + notes.get("mapped", []):
        text = note["text"]
        fence = "~" * max(
            3, max((len(run) for run in re.findall(r"~+", text)), default=0) + 1
        )
        rows += [fence, text, fence, ""]
    return "\n".join(rows).rstrip() + "\n"
