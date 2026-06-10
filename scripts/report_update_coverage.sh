#!/usr/bin/env bash
# ============================================================
# report_update_coverage.sh — What this Mac can vs cannot update
# ============================================================
# Compares config/internet_apps.txt against installed apps.
# Does not install anything. Use after build_inventory.sh.
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
import sys

script_dir = sys.argv[1]
json_out = sys.argv[2] == "1"
lang = os.environ.get("MAC_LANG", "en")

METHOD_LABELS = {
    "en": {
        "keystone": "Google Keystone (Chrome, Drive)",
        "github_dmg": "GitHub release + verified DMG",
        "silent_launch": "Built-in auto-updater (open app)",
        "msupdate": "Microsoft AutoUpdate (msupdate)",
        "docker_cli": "Docker Desktop CLI",
        "manual": "Manual — notification only",
    },
    "pl": {
        "keystone": "Google Keystone (Chrome, Drive)",
        "github_dmg": "GitHub release + zweryfikowany DMG",
        "silent_launch": "Wbudowany auto-updater (otwórz aplikację)",
        "msupdate": "Microsoft AutoUpdate (msupdate)",
        "docker_cli": "Docker Desktop CLI",
        "manual": "Ręcznie — tylko powiadomienie",
    },
    "de": {
        "keystone": "Google Keystone (Chrome, Drive)",
        "github_dmg": "GitHub-Release + verifiziertes DMG",
        "silent_launch": "Integrierter Auto-Updater (App öffnen)",
        "msupdate": "Microsoft AutoUpdate (msupdate)",
        "docker_cli": "Docker Desktop CLI",
        "manual": "Manuell — nur Hinweis",
    },
    "fr": {
        "keystone": "Google Keystone (Chrome, Drive)",
        "github_dmg": "Release GitHub + DMG vérifié",
        "silent_launch": "Auto-updater intégré (ouvrir l'app)",
        "msupdate": "Microsoft AutoUpdate (msupdate)",
        "docker_cli": "Docker Desktop CLI",
        "manual": "Manuel — notification seulement",
    },
    "es": {
        "keystone": "Google Keystone (Chrome, Drive)",
        "github_dmg": "Release de GitHub + DMG verificado",
        "silent_launch": "Auto-actualizador integrado (abrir app)",
        "msupdate": "Microsoft AutoUpdate (msupdate)",
        "docker_cli": "Docker Desktop CLI",
        "manual": "Manual — solo notificación",
    },
    "it": {
        "keystone": "Google Keystone (Chrome, Drive)",
        "github_dmg": "Release GitHub + DMG verificato",
        "silent_launch": "Auto-updater integrato (apri app)",
        "msupdate": "Microsoft AutoUpdate (msupdate)",
        "docker_cli": "Docker Desktop CLI",
        "manual": "Manuale — solo notifica",
    },
    "pt": {
        "keystone": "Google Keystone (Chrome, Drive)",
        "github_dmg": "Release GitHub + DMG verificado",
        "silent_launch": "Auto-atualizador integrado (abrir app)",
        "msupdate": "Microsoft AutoUpdate (msupdate)",
        "docker_cli": "Docker Desktop CLI",
        "manual": "Manual — apenas notificação",
    },
}

METHOD_AI_HINT = {
    "en": {
        "keystone": "Add to config/internet_apps.txt + internet_app_methods.txt as keystone; handler in lib/internet_app_updates.sh (iu_* keystone pattern).",
        "github_dmg": "Run scripts/scaffold_internet_app.sh \"App\" github_dmg; add GitHub repo slug and DMG verify block.",
        "silent_launch": "Run scripts/scaffold_internet_app.sh \"App\" silent_launch; add bundle path in lib/internet_apps.sh if non-standard name.",
        "msupdate": "Microsoft 365 family — add Product ID to msupdate handler if new Office app.",
        "docker_cli": "Docker Desktop only — requires docker desktop update CLI.",
        "manual": "Listed for inventory only; user updates manually or add a new method.",
    },
    "pl": {
        "keystone": "Dodaj do config/internet_apps.txt + internet_app_methods.txt jako keystone; handler w lib/internet_app_updates.sh.",
        "github_dmg": "Uruchom scripts/scaffold_internet_app.sh \"App\" github_dmg; dodaj slug repo GitHub i blok weryfikacji DMG.",
        "silent_launch": "Uruchom scripts/scaffold_internet_app.sh \"App\" silent_launch; dodaj ścieżkę bundle w lib/internet_apps.sh.",
        "msupdate": "Rodzina Microsoft 365 — dodaj Product ID do handlera msupdate.",
        "docker_cli": "Tylko Docker Desktop — wymaga docker desktop update CLI.",
        "manual": "Tylko inwentaryzacja; użytkownik aktualizuje ręcznie lub dodaj nową metodę.",
    },
}

def labels_for(lang_code):
    if lang_code in METHOD_LABELS:
        return METHOD_LABELS[lang_code]
    return METHOD_LABELS["en"]

def hints_for(lang_code):
    if lang_code in METHOD_AI_HINT:
        return METHOD_AI_HINT[lang_code]
    return METHOD_AI_HINT["en"]

def read_lines(path):
    if not os.path.isfile(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.split("#", 1)[0].strip()
            if line:
                out.append(line)
    return out


def app_installed(name):
    from pathlib import Path
    aliases = {
        "OpenCode": ["OpenCode", "opencode", "Opencode", "opencode Desktop"],
        "Ledger Live": ["Ledger Live", "Ledger Wallet"],
        "Docker Desktop": ["Docker", "Docker Desktop"],
        "Firefox Developer Edition": ["Firefox Developer Edition"],
        "zoom.us": ["zoom.us", "Zoom"],
        "Visual Studio Code": ["Visual Studio Code", "VS Code"],
        "Brave Browser": ["Brave Browser", "Brave"],
    }
    for candidate in aliases.get(name, [name]):
        if Path(f"/Applications/{candidate}.app").is_dir():
            return True
    return False


def load_registry(script_dir):
    cfg = os.path.join(script_dir, "config", "internet_app_methods.txt")
    reg = {}
    for line in read_lines(cfg):
        parts = line.split("|")
        if len(parts) >= 2:
            reg[parts[0]] = parts[1]
    return reg


method_labels = labels_for(lang)
method_hints = hints_for(lang)

apps = read_lines(os.path.join(script_dir, "config", "internet_apps.txt"))
registry = load_registry(script_dir)

installed_updatable = []
not_installed_supported = []
by_method = {}

for app in apps:
    method = registry.get(app, "unknown")
    bucket = by_method.setdefault(method, {"installed": [], "not_installed": []})
    if app_installed(app):
        installed_updatable.append({"app": app, "method": method})
        bucket["installed"].append(app)
    else:
        not_installed_supported.append({"app": app, "method": method})
        bucket["not_installed"].append(app)

unknown_installed = []
try:
    for item in sorted(os.listdir("/Applications")):
        if not item.endswith(".app"):
            continue
        name = item[:-4]
        if name in apps:
            continue
        skip_frags = ("Helper", "Uninstaller", "Agent", "Updater", "Plugin")
        if any(f.lower() in name.lower() for f in skip_frags):
            continue
        unknown_installed.append(name)
except OSError:
    pass

report = {
    "version": open(os.path.join(script_dir, "VERSION"), encoding="utf-8").read().strip()
    if os.path.isfile(os.path.join(script_dir, "VERSION"))
    else "unknown",
    "installed_updatable_count": len(installed_updatable),
    "not_installed_supported_count": len(not_installed_supported),
    "unknown_installed_count": len(unknown_installed),
    "installed_updatable": installed_updatable,
    "not_installed_supported": not_installed_supported,
    "unknown_installed_sample": unknown_installed[:40],
    "by_method": by_method,
}

if json_out:
    print(json.dumps(report, indent=2))
    sys.exit(0)

title = os.environ.get("L_COVERAGE_TITLE", "macOS Updates — update coverage report")
ver_label = os.environ.get("L_COVERAGE_VERSION", "Version:")
installed_hdr = os.environ.get("L_COVERAGE_INSTALLED_HEADER", "Installed and auto-updatable:")
not_inst_hdr = os.environ.get("L_COVERAGE_NOT_INSTALLED_HEADER", "Supported but NOT installed:")
not_inst_note = os.environ.get("L_COVERAGE_NOT_INSTALLED_NOTE", "")
unknown_hdr = os.environ.get("L_COVERAGE_UNKNOWN_HEADER", "Installed apps not in registry:")
unknown_inv = os.environ.get("L_COVERAGE_UNKNOWN_HINT_INVENTORY", "Run build_inventory.sh")
unknown_scaffold = os.environ.get("L_COVERAGE_UNKNOWN_HINT_SCAFFOLD", "Ask an AI agent or run:")
and_more = os.environ.get("L_COVERAGE_AND_MORE", "… and %s more.")
ai_hint = os.environ.get("L_COVERAGE_AI_HINT", "AI hint:")

print("")
print(f"  {title}")
print(f"  {ver_label} {report['version']}")
print("")
print(f"  ✅ {installed_hdr} {report['installed_updatable_count']}")
for row in installed_updatable:
    label = method_labels.get(row["method"], row["method"])
    print(f"       · {row['app']} ({label})")

print("")
print(f"  ⏭️  {not_inst_hdr} {report['not_installed_supported_count']}")
if not_inst_note:
    print(f"     ({not_inst_note})")
for method in sorted(by_method.keys()):
    missing = by_method[method]["not_installed"]
    if not missing:
        continue
    label = method_labels.get(method, method)
    hint = method_hints.get(method, f"See docs/user/{lang}/GUIDE.md")
    print(f"     [{label}]")
    for app in missing:
        print(f"       · {app}")
    print(f"       → {ai_hint} {hint}")

if unknown_installed:
    print("")
    print(f"  🆕 {unknown_hdr} (first {min(40, len(unknown_installed))}):")
    for name in unknown_installed[:40]:
        print(f"       · {name}")
    print(f"     → {unknown_inv}")
    print(f"     → {unknown_scaffold}")
    print('       bash scripts/scaffold_internet_app.sh "App Name" silent_launch')
    if len(unknown_installed) > 40:
        print(f"     {and_more % (len(unknown_installed) - 40,)}")

print("")
PYEOF
