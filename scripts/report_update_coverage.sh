#!/usr/bin/env bash
# ============================================================
# report_update_coverage.sh — honest update coverage for this Mac
# ============================================================
# Scans /Applications and ~/Applications, deduplicates bundles, and
# distinguishes direct updates, triggered-but-unverified updaters,
# external managers, manual apps, and truly unknown apps.
#
# Usage:
#   bash scripts/report_update_coverage.sh
#   bash scripts/report_update_coverage.sh --json
# ============================================================
set -o pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
JSON_OUT=0
[ "${1:-}" = "--json" ] && JSON_OUT=1

. "$SCRIPT_DIR/i18n/loader.sh"

export L_COVERAGE_TITLE L_COVERAGE_VERSION L_COVERAGE_INSTALLED_COUNT
export L_COVERAGE_INSTALLED_HEADER L_COVERAGE_NOT_INSTALLED_HEADER
export L_COVERAGE_NOT_INSTALLED_NOTE L_COVERAGE_UNKNOWN_HEADER
export L_COVERAGE_UNKNOWN_HINT_INVENTORY L_COVERAGE_UNKNOWN_HINT_SCAFFOLD
export L_COVERAGE_AND_MORE L_COVERAGE_AI_HINT MAC_LANG

exec python3 - "$SCRIPT_DIR" "$JSON_OUT" << 'PYEOF'
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
from pathlib import Path


script_dir = sys.argv[1]
json_out = sys.argv[2] == "1"
lang = os.environ.get("MAC_LANG", "en")

METHOD_LABELS = {
    "en": {
        "keystone": "Google Keystone",
        "github_dmg": "verified direct download",
        "silent_launch": "built-in updater triggered (unverified)",
        "msupdate": "Microsoft AutoUpdate",
        "mau_fallback_self_update": "Teams self-updater + observed MAU fallback",
        "docker_cli": "Docker Desktop CLI",
        "brew_cask": "Homebrew cask",
        "appstore_gui": "App Store GUI (iPad app)",
        "manual": "manual only",
        "sparkle_appcast": "Sparkle appcast verified",
    },
    "pl": {
        "keystone": "Google Keystone",
        "github_dmg": "zweryfikowane pobranie bezpośrednie",
        "silent_launch": "uruchomiony updater (bez weryfikacji)",
        "msupdate": "Microsoft AutoUpdate",
        "mau_fallback_self_update": "updater Teams + obserwowany fallback MAU",
        "docker_cli": "Docker Desktop CLI",
        "brew_cask": "Homebrew cask",
        "appstore_gui": "GUI App Store (aplikacja iPad)",
        "manual": "wyłącznie ręcznie",
        "sparkle_appcast": "weryfikacja Sparkle appcast",
    },
    "de": {
        "keystone": "Google Keystone",
        "github_dmg": "verifizierter Direktdownload",
        "silent_launch": "Updater gestartet (nicht verifiziert)",
        "msupdate": "Microsoft AutoUpdate",
        "mau_fallback_self_update": "Teams-Updater + beobachteter MAU-Fallback",
        "docker_cli": "Docker Desktop CLI",
        "brew_cask": "Homebrew Cask",
        "appstore_gui": "App-Store-GUI (iPad-App)",
        "manual": "nur manuell",
        "sparkle_appcast": "Sparkle Appcast verifiziert",
    },
    "fr": {
        "keystone": "Google Keystone",
        "github_dmg": "téléchargement direct vérifié",
        "silent_launch": "mise à jour déclenchée (non vérifiée)",
        "msupdate": "Microsoft AutoUpdate",
        "mau_fallback_self_update": "updater Teams + repli MAU observé",
        "docker_cli": "Docker Desktop CLI",
        "brew_cask": "Cask Homebrew",
        "appstore_gui": "interface App Store (app iPad)",
        "manual": "manuel uniquement",
        "sparkle_appcast": "vérifié par Sparkle appcast",
    },
    "es": {
        "keystone": "Google Keystone",
        "github_dmg": "descarga directa verificada",
        "silent_launch": "actualizador iniciado (sin verificar)",
        "msupdate": "Microsoft AutoUpdate",
        "mau_fallback_self_update": "actualizador de Teams + fallback MAU observado",
        "docker_cli": "Docker Desktop CLI",
        "brew_cask": "Cask de Homebrew",
        "appstore_gui": "interfaz de App Store (app iPad)",
        "manual": "solo manual",
        "sparkle_appcast": "verificado por Sparkle appcast",
    },
    "it": {
        "keystone": "Google Keystone",
        "github_dmg": "download diretto verificato",
        "silent_launch": "updater avviato (non verificato)",
        "msupdate": "Microsoft AutoUpdate",
        "mau_fallback_self_update": "updater Teams + fallback MAU osservato",
        "docker_cli": "Docker Desktop CLI",
        "brew_cask": "Cask Homebrew",
        "appstore_gui": "GUI App Store (app iPad)",
        "manual": "solo manuale",
        "sparkle_appcast": "verificato da Sparkle appcast",
    },
    "pt": {
        "keystone": "Google Keystone",
        "github_dmg": "download direto verificado",
        "silent_launch": "atualizador iniciado (não verificado)",
        "msupdate": "Microsoft AutoUpdate",
        "mau_fallback_self_update": "atualizador do Teams + fallback MAU observado",
        "docker_cli": "Docker Desktop CLI",
        "brew_cask": "Cask do Homebrew",
        "appstore_gui": "interface da App Store (app iPad)",
        "manual": "apenas manual",
        "sparkle_appcast": "verificado por Sparkle appcast",
    },
}

METHOD_AI_HINT = {
    "en": {
        "keystone": "Add a keystone registry row and handler.",
        "github_dmg": "Add a signed, verified direct-download handler.",
        "silent_launch": "Add a bundle-aware silent-launch handler.",
        "msupdate": "Add the Microsoft product ID to the shared handler.",
        "mau_fallback_self_update": "Use the Teams self-updater and observe a verified TEAMS21 MAU fallback when offered.",
        "docker_cli": "Use the Docker Desktop CLI update path.",
        "brew_cask": "Manage the app as an installed Homebrew cask.",
        "appstore_gui": "Manage the iPad app in App Store Track 2.",
        "manual": "Keep as a documented manual target until a safe updater exists.",
    },
    "pl": {
        "keystone": "Dodaj wpis keystone i handler.",
        "github_dmg": "Dodaj handler bezpośredniego pobrania z weryfikacją podpisu.",
        "silent_launch": "Dodaj handler cichego uruchomienia rozpoznający bundle.",
        "msupdate": "Dodaj identyfikator produktu do wspólnego handlera Microsoft.",
        "mau_fallback_self_update": "Użyj updatera Teams i obserwuj zweryfikowany fallback MAU TEAMS21, gdy zostanie zaoferowany.",
        "docker_cli": "Użyj ścieżki aktualizacji Docker Desktop CLI.",
        "brew_cask": "Zarządzaj aplikacją jako zainstalowanym caskiem Homebrew.",
        "appstore_gui": "Zarządzaj aplikacją iPad przez Track 2 App Store.",
        "manual": "Pozostaw udokumentowany tryb ręczny do czasu bezpiecznej automatyzacji.",
    },
}

CLASS_TEXT = {
    "en": {
        "unique": "Unique installed apps",
        "automatic": "Verified/direct or externally managed",
        "verified_direct": "Verified/direct updater",
        "triggered_unverified": "Updater triggered — result unverified",
        "externally_managed": "Externally managed",
        "manual": "Manual only (not automatic)",
        "unknown": "Unknown / uncovered",
        "known": "Known coverage",
    },
    "pl": {
        "unique": "Unikalne zainstalowane aplikacje",
        "automatic": "Zweryfikowane/bezpośrednie lub zarządzane zewnętrznie",
        "verified_direct": "Updater zweryfikowany/bezpośredni",
        "triggered_unverified": "Updater uruchomiony — wynik niezweryfikowany",
        "externally_managed": "Zarządzane zewnętrznie",
        "manual": "Wyłącznie ręcznie (nie automatycznie)",
        "unknown": "Nieznane / bez pokrycia",
        "known": "Znane pokrycie",
    },
    "de": {
        "unique": "Eindeutig installierte Apps",
        "automatic": "Verifiziert/direkt oder extern verwaltet",
        "verified_direct": "Verifizierter/direkter Updater",
        "triggered_unverified": "Updater gestartet — Ergebnis nicht verifiziert",
        "externally_managed": "Extern verwaltet",
        "manual": "Nur manuell (nicht automatisch)",
        "unknown": "Unbekannt / nicht abgedeckt",
        "known": "Bekannte Abdeckung",
    },
    "fr": {
        "unique": "Apps installées uniques",
        "automatic": "Vérifiées/directes ou gérées en externe",
        "verified_direct": "Mise à jour vérifiée/directe",
        "triggered_unverified": "Mise à jour déclenchée — résultat non vérifié",
        "externally_managed": "Gérées en externe",
        "manual": "Manuel uniquement (non automatique)",
        "unknown": "Inconnues / non couvertes",
        "known": "Couverture connue",
    },
    "es": {
        "unique": "Apps instaladas únicas",
        "automatic": "Verificadas/directas o gestionadas externamente",
        "verified_direct": "Actualizador verificado/directo",
        "triggered_unverified": "Actualizador iniciado — resultado sin verificar",
        "externally_managed": "Gestionadas externamente",
        "manual": "Solo manual (no automático)",
        "unknown": "Desconocidas / sin cobertura",
        "known": "Cobertura conocida",
    },
    "it": {
        "unique": "App installate uniche",
        "automatic": "Verificate/dirette o gestite esternamente",
        "verified_direct": "Updater verificato/diretto",
        "triggered_unverified": "Updater avviato — risultato non verificato",
        "externally_managed": "Gestite esternamente",
        "manual": "Solo manuale (non automatico)",
        "unknown": "Sconosciute / non coperte",
        "known": "Copertura nota",
    },
    "pt": {
        "unique": "Apps instaladas únicas",
        "automatic": "Verificadas/diretas ou geridas externamente",
        "verified_direct": "Atualizador verificado/direto",
        "triggered_unverified": "Atualizador iniciado — resultado não verificado",
        "externally_managed": "Geridas externamente",
        "manual": "Apenas manual (não automático)",
        "unknown": "Desconhecidas / sem cobertura",
        "known": "Cobertura conhecida",
    },
}

# Every entry here is claimed as "verified/direct" in the report, so each one
# must (a) be used by at least one row of config/internet_app_methods.txt and
# (b) be backed by a handler that performs a real remote check. Guarded by
# tests/test_safety_static.py::test_direct_methods_are_used_and_verify.
DIRECT_METHODS = {"keystone", "github_dmg", "msupdate", "docker_cli", "sparkle_appcast"}
TRIGGER_METHODS = {"silent_launch", "mau_fallback_self_update"}
EXTERNAL_METHODS = {"brew_cask", "appstore_gui"}

# Canonical registry targets whose on-disk bundle names changed or differ from
# their product name. ChatGPT / Codex is deliberately bundle-ID-only: the
# legacy com.openai.chat (ChatGPT Classic) must never match this target.
TARGET_ALIASES = {
    "ChatGPT / Codex": {
        "names": [],
        "bundle_ids": ["com.openai.codex"],
    },
    "Docker Desktop": {
        "names": ["Docker Desktop", "Docker"],
        "bundle_ids": ["com.docker.docker"],
    },
    "Ledger Live": {
        "names": ["Ledger Live", "Ledger Wallet"],
        "bundle_ids": ["com.ledger.live"],
    },
    "DJI Assistant 2": {
        "names": ["DJI Assistant 2", "DJI Assistant 2(Consumer Drones Series)"],
        "bundle_ids": ["DJI.Assistant"],
    },
    "OpenCode": {
        "names": ["OpenCode", "opencode", "Opencode", "opencode Desktop"],
        "bundle_ids": ["ai.opencode.desktop"],
    },
    "zoom.us": {
        "names": ["zoom.us", "Zoom"],
        "bundle_ids": ["us.zoom.xos"],
    },
    "Visual Studio Code": {
        "names": ["Visual Studio Code", "VS Code", "Code"],
        "bundle_ids": ["com.microsoft.VSCode", "com.microsoft.VSCodeInsiders"],
    },
    "Brave Browser": {
        "names": ["Brave Browser", "Brave", "Brave Browser Beta", "Brave Browser Nightly"],
        "bundle_ids": ["com.brave.Browser", "com.brave.Browser.beta", "com.brave.Browser.nightly"],
    },
}

PARENT_BUNDLES = {
    "com.google.drivefs.shortcuts.": "Google Drive",
    "com.microsoft.wdav.shim": "Microsoft Defender",
    "com.anthropic.claude-code-url-handler": "Claude Code",
}


def labels_for(lang_code):
    return METHOD_LABELS.get(lang_code, METHOD_LABELS["en"])


def hints_for(lang_code):
    return METHOD_AI_HINT.get(lang_code, METHOD_AI_HINT["en"])


def class_text_for(lang_code):
    return CLASS_TEXT.get(lang_code, CLASS_TEXT["en"])


def read_lines(path):
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.split("#", 1)[0].strip()
            if line:
                out.append(line)
    return out


def clean_app_name(value):
    if not value:
        return ""
    # Strip markdown links [Text](url) -> Text
    value = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', value)
    # Strip bold/italic **text** or *text*
    value = re.sub(r'\*+([^*]+)\*+', r'\1', value)
    # Strip emojis
    value = re.sub(r'[\U0001F300-\U0001FFFF]', '', value)
    return value.strip()


def normalize(value):
    value = clean_app_name(value).casefold()
    if value.endswith(".app"):
        value = value[:-4]
    return re.sub(r"[^a-z0-9]+", "", value)


def run_command(argv, timeout=15):
    try:
        env = os.environ.copy()
        env.setdefault("MAS_NO_AUTO_INDEX", "1")
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return proc.stdout if proc.returncode == 0 else ""


def mdls_value(path, key):
    value = run_command(["mdls", "-raw", "-name", key, str(path)], timeout=5).strip()
    return "" if value in {"", "(null)"} else value.strip('"')


def plist_metadata(path):
    info_path = path / "Contents" / "Info.plist"
    if not info_path.is_file():
        return {}
    try:
        with info_path.open("rb") as handle:
            return plistlib.load(handle)
    except (OSError, plistlib.InvalidFileException, ValueError):
        return {}


def scan_installed_apps():
    found = []
    seen = set()
    roots = [Path("/Applications"), Path.home() / "Applications"]
    for root in roots:
        if not root.is_dir():
            continue
        try:
            entries = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for path in entries:
            if not path.name.casefold().endswith(".app") or not path.is_dir() or path.parent != root:
                continue
            name = path.name[:-4]
            plist = plist_metadata(path)
            bundle_id = str(plist.get("CFBundleIdentifier", "")) or mdls_value(
                path, "kMDItemCFBundleIdentifier"
            )
            version = str(
                plist.get("CFBundleShortVersionString")
                or plist.get("CFBundleVersion")
                or ""
            ) or mdls_value(path, "kMDItemVersion")
            identity = ("bundle", bundle_id.casefold()) if bundle_id else ("name", normalize(name))
            if identity in seen:
                continue
            seen.add(identity)
            receipt = (path / "Contents" / "_MASReceipt" / "receipt").is_file()
            if not receipt:
                receipt = mdls_value(path, "kMDItemAppStoreHasReceipt") == "1"
            found.append(
                {
                    "app": name,
                    "path": str(path),
                    "bundle_id": bundle_id,
                    "version": version or "?",
                    "app_store_receipt": receipt,
                }
            )
    return found


def load_registry():
    cfg = os.path.join(script_dir, "config", "internet_app_methods.txt")
    registry = {}
    for line in read_lines(cfg):
        parts = line.split("|")
        if len(parts) >= 2:
            registry[parts[0]] = parts[1]
    return registry


def load_mas_names():
    mas = shutil.which("mas")
    if not mas:
        return set()
    output = run_command([mas, "list"], timeout=20)
    names = set()
    for line in output.splitlines():
        match = re.match(r"^\s*\d+\s+(.+?)\s+\([^)]*\)\s*$", line)
        if match:
            names.add(normalize(match.group(1)))
    return names


def load_brew_apps():
    brew = shutil.which("brew")
    if not brew:
        return {}
    tokens = [line.strip() for line in run_command([brew, "list", "--cask", "-1"]).splitlines() if line.strip()]
    if not tokens:
        return {}
    raw = run_command([brew, "info", "--cask", "--json=v2"] + tokens, timeout=30)
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return {}
    app_to_token = {}
    for cask in data.get("casks", []):
        token = cask.get("token", "")
        for artifact in cask.get("artifacts", []):
            if not isinstance(artifact, dict) or "app" not in artifact:
                continue
            value = artifact.get("app")
            names = value if isinstance(value, list) else [value]
            for name in names:
                if isinstance(name, str):
                    app_to_token[normalize(os.path.basename(name))] = token
    return app_to_token


def target_for(installed, apps):
    bundle_id = installed["bundle_id"]
    app_name = installed["app"]
    for target in apps:
        aliases = TARGET_ALIASES.get(target, {})
        if bundle_id and bundle_id in aliases.get("bundle_ids", []):
            return target
    for target in apps:
        aliases = TARGET_ALIASES.get(target, {})
        candidate_names = aliases.get("names", [target])
        if normalize(app_name) in {normalize(name) for name in candidate_names}:
            return target
    return ""


def parent_manager(installed):
    bundle_id = installed["bundle_id"]
    for prefix, manager in PARENT_BUNDLES.items():
        if bundle_id == prefix or bundle_id.startswith(prefix):
            return manager
    name = installed["app"]
    lowered = name.casefold()
    if "proton mail" in lowered and "uninstaller" in lowered:
        return "Proton Mail"
    helper_tokens = (" helper", " url handler", " shim", " uninstaller", " updater", " agent")
    if any(token in lowered for token in helper_tokens):
        return "parent app"
    return ""


def classify(installed, target, method, mas_names, brew_apps):
    normalized_name = normalize(installed["app"])
    parent = parent_manager(installed)

    if method == "appstore_gui":
        return "externally_managed", "app_store_gui"
    if installed["app_store_receipt"] or normalized_name in mas_names:
        return "externally_managed", "app_store_mas"
    if method == "brew_cask":
        token = brew_apps.get(normalized_name, "")
        return "externally_managed", "homebrew_cask" + (":" + token if token else "")
    if normalized_name in brew_apps:
        return "externally_managed", "homebrew_cask:" + brew_apps[normalized_name]
    if installed["bundle_id"].startswith("com.apple."):
        return "externally_managed", "macos_system"
    if parent:
        return "externally_managed", "parent_app:" + parent
    if method in DIRECT_METHODS:
        return "verified_direct", method
    if method in TRIGGER_METHODS:
        return "triggered_unverified", method
    if method in EXTERNAL_METHODS:
        return "externally_managed", method
    if method == "manual":
        return "manual", "manual"
    return "unknown", "unknown"


method_labels = labels_for(lang)
method_hints = hints_for(lang)
class_text = class_text_for(lang)
apps = read_lines(os.path.join(script_dir, "config", "internet_apps.txt"))
registry = load_registry()
mas_names = load_mas_names()
brew_apps = load_brew_apps()
installed = scan_installed_apps()

classifications = {
    "verified_direct": [],
    "triggered_unverified": [],
    "externally_managed": [],
    "manual": [],
    "unknown": [],
}
installed_targets = set()
by_method = {}
for app in apps:
    method = registry.get(app, "unknown")
    by_method.setdefault(method, {"installed": [], "not_installed": []})

for item in installed:
    target = target_for(item, apps)
    method = registry.get(target, "unknown") if target else "unknown"
    if target:
        installed_targets.add(target)
    classification, managed_by = classify(item, target, method, mas_names, brew_apps)
    row = dict(item)
    row.update(
        {
            "target": target or None,
            "method": method,
            "classification": classification,
            "managed_by": managed_by,
        }
    )
    classifications[classification].append(row)

for rows in classifications.values():
    rows.sort(key=lambda row: row["app"].casefold())

not_installed_supported = []
for app in apps:
    method = registry.get(app, "unknown")
    if app in installed_targets:
        by_method[method]["installed"].append(app)
    else:
        by_method[method]["not_installed"].append(app)
        not_installed_supported.append({"app": app, "method": method})

verified_direct_count = len(classifications["verified_direct"])
triggered_unverified_count = len(classifications["triggered_unverified"])
externally_managed_count = len(classifications["externally_managed"])
manual_count = len(classifications["manual"])
unknown_count = len(classifications["unknown"])
installed_unique_count = len(installed)
supported_count = verified_direct_count + triggered_unverified_count + externally_managed_count
automatic_count = verified_direct_count + externally_managed_count
known_count = installed_unique_count - unknown_count
supported_percent = round((supported_count * 100.0 / installed_unique_count), 1) if installed_unique_count else 100.0
automatic_percent = round((automatic_count * 100.0 / installed_unique_count), 1) if installed_unique_count else 100.0
known_percent = round((known_count * 100.0 / installed_unique_count), 1) if installed_unique_count else 100.0

# Keep the old keys for consumers, but populate them honestly: manual and
# triggered-unverified entries are not called automatically updatable.
installed_updatable = classifications["verified_direct"] + classifications["externally_managed"]
unknown_names = [row["app"] for row in classifications["unknown"]]
version_path = os.path.join(script_dir, "VERSION")
version = "unknown"
if os.path.isfile(version_path):
    with open(version_path, encoding="utf-8") as handle:
        version = handle.read().strip()

report = {
    "schema_version": 2,
    "version": version,
    "installed_unique_count": installed_unique_count,
    "supported_coverage_count": supported_count,
    "supported_coverage_percent": supported_percent,
    "automatic_coverage_count": automatic_count,
    "automatic_coverage_percent": automatic_percent,
    "known_coverage_count": known_count,
    "known_coverage_percent": known_percent,
    "verified_direct_count": verified_direct_count,
    "triggered_unverified_count": triggered_unverified_count,
    "externally_managed_count": externally_managed_count,
    "manual_count": manual_count,
    "unknown_count": unknown_count,
    "classification_counts": {key: len(value) for key, value in classifications.items()},
    "classifications": classifications,
    "registry_installed_target_count": len(installed_targets),
    "not_installed_supported_count": len(not_installed_supported),
    "not_installed_supported": not_installed_supported,
    "by_method": by_method,
    # Backward-compatible v1 fields:
    "installed_updatable_count": automatic_count,
    "installed_updatable": installed_updatable,
    "unknown_installed_count": unknown_count,
    "unknown_installed_sample": unknown_names[:40],
}

if json_out:
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(0)

title = os.environ.get("L_COVERAGE_TITLE", "macOS Updates — update coverage report")
ver_label = os.environ.get("L_COVERAGE_VERSION", "Version:")
not_inst_hdr = os.environ.get("L_COVERAGE_NOT_INSTALLED_HEADER", "Supported but NOT installed:")
not_inst_note = os.environ.get("L_COVERAGE_NOT_INSTALLED_NOTE", "")
unknown_inv = os.environ.get("L_COVERAGE_UNKNOWN_HINT_INVENTORY", "Run build_inventory.sh")
unknown_scaffold = os.environ.get("L_COVERAGE_UNKNOWN_HINT_SCAFFOLD", "Ask an AI agent or run:")
ai_hint = os.environ.get("L_COVERAGE_AI_HINT", "AI hint:")

print("")
print(f"  {title}")
print(f"  {ver_label} {version}")
print("")
print(f"  📦 {class_text['unique']}: {installed_unique_count}")
print(f"  📊 Update Coverage: {supported_count}/{installed_unique_count} ({supported_percent:.1f}%)")
print(f"  ✅ {class_text['automatic']}: {automatic_count}/{installed_unique_count} ({automatic_percent:.1f}%)")
print(f"  🧭 {class_text['known']}: {known_count}/{installed_unique_count} ({known_percent:.1f}%)")

section_icons = {
    "verified_direct": "✅",
    "triggered_unverified": "⏳",
    "externally_managed": "♻️ ",
    "manual": "🛠️ ",
    "unknown": "❓",
}
for key in ("verified_direct", "triggered_unverified", "externally_managed", "manual", "unknown"):
    rows = classifications[key]
    print("")
    print(f"  {section_icons[key]} {class_text[key]}: {len(rows)}")
    for row in rows:
        target_suffix = ""
        if row["target"] and normalize(row["target"]) != normalize(row["app"]):
            target_suffix = f" → {row['target']}"
        if key == "externally_managed":
            detail = row["managed_by"]
        else:
            detail = method_labels.get(row["method"], row["method"])
        print(f"       · {row['app']}{target_suffix} ({detail})")

print("")
print(f"  ⏭️  {not_inst_hdr} {len(not_installed_supported)}")
if not_inst_note:
    print(f"     ({not_inst_note})")
for method in sorted(by_method):
    missing = by_method[method]["not_installed"]
    if not missing:
        continue
    label = method_labels.get(method, method)
    hint = method_hints.get(method, f"See docs/user/{lang}/GUIDE.md")
    print(f"     [{label}]")
    for app in missing:
        print(f"       · {app}")
    print(f"       → {ai_hint} {hint}")

if classifications["unknown"]:
    print("")
    print(f"     → {unknown_inv}")
    print(f"     → {unknown_scaffold}")
    print('       bash scripts/scaffold_internet_app.sh "App Name" silent_launch')

print("")
PYEOF
