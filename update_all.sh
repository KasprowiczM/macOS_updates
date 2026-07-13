#!/usr/bin/env bash
# ============================================================
# SKRYPT MASTER: Aktualizacja całego MacBooka
# ============================================================
# Autor: Antigravity AI

# Catch failures in pipelines (e.g. `cmd1 | cmd2` where cmd1 dies).
# We deliberately do NOT use `set -e` — orchestrator runs every step
# even on partial failure and reports per-step status at the end.
set -o pipefail

# Data:  2026-04-18 (zaktualizowano)
# Opis:  Uruchamia wszystkie skrypty aktualizacji po kolei:
#        0. Skanowanie i inwentarz wstępny
#        1. App Store
#        2. Native CLI + npm
#        3. Homebrew
#        4. Aplikacje z Internetu
#        5. Aktualizacja APPLICATIONS.md i UPDATES.md z wynikami
#        6. System macOS na końcu (restart-safe, zawsze z -R)
# Kompatybilność: bash 3.2+ (macOS domyślny shell)
# ============================================================

# Kolory
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Katalog z skryptami (ten sam co lokalizacja skryptu master)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── Shared libraries ─────────────────────────────────────────
. "$SCRIPT_DIR/lib/cli.sh"
. "$SCRIPT_DIR/lib/ui.sh"
. "$SCRIPT_DIR/lib/internet_apps.sh"
. "$SCRIPT_DIR/lib/platform.sh"
. "$SCRIPT_DIR/lib/version.sh"

export UI_START_EPOCH=$(date +%s)
mac_update_parse_cli "$@"

mac_update_require_supported_platform || exit 1

# ── i18n: load language strings ──────────────────────────────
. "$SCRIPT_DIR/i18n/loader.sh"

print_banner() {
    # Dynamically size the box to fit the longest line (title or subtitle)
    local title="$L_BANNER_TITLE"
    local subtitle="$L_BANNER_SUBTITLE"
    local title_len=${#title}
    local subtitle_len=${#subtitle}
    local max_len=$title_len
    [ "$subtitle_len" -gt "$max_len" ] && max_len=$subtitle_len
    # Add 6 chars padding on each side (3 spaces + content + 3 spaces = inner_width)
    local inner_width=$((max_len + 6))

    # Build horizontal border: ═ repeated inner_width times
    local border=""
    local i=0
    while [ "$i" -lt "$inner_width" ]; do
        border="${border}═"
        i=$((i + 1))
    done

    # Center title and subtitle with padding
    local title_pad_total=$((inner_width - title_len))
    local title_pad_left=$((title_pad_total / 2))
    local title_pad_right=$((title_pad_total - title_pad_left))

    local sub_pad_total=$((inner_width - subtitle_len))
    local sub_pad_left=$((sub_pad_total / 2))
    local sub_pad_right=$((sub_pad_total - sub_pad_left))

    # Build padding strings
    local empty_line=""
    i=0; while [ "$i" -lt "$inner_width" ]; do empty_line="${empty_line} "; i=$((i + 1)); done

    local tl_pad=""; i=0; while [ "$i" -lt "$title_pad_left" ]; do tl_pad="${tl_pad} "; i=$((i + 1)); done
    local tr_pad=""; i=0; while [ "$i" -lt "$title_pad_right" ]; do tr_pad="${tr_pad} "; i=$((i + 1)); done
    local sl_pad=""; i=0; while [ "$i" -lt "$sub_pad_left" ]; do sl_pad="${sl_pad} "; i=$((i + 1)); done
    local sr_pad=""; i=0; while [ "$i" -lt "$sub_pad_right" ]; do sr_pad="${sr_pad} "; i=$((i + 1)); done

    echo ""
    echo -e "${BLUE}${BOLD}╔${border}╗${NC}"
    echo -e "${BLUE}${BOLD}║${empty_line}║${NC}"
    echo -e "${BLUE}${BOLD}║${tl_pad}${title}${tr_pad}║${NC}"
    echo -e "${BLUE}${BOLD}║${sl_pad}${subtitle}${sr_pad}║${NC}"
    echo -e "${BLUE}${BOLD}║${empty_line}║${NC}"
    echo -e "${BLUE}${BOLD}╚${border}╝${NC}"
    echo ""
}

print_section() {
    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

print_ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
print_info() { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
print_warn() { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
print_error(){ echo -e "  ${RED}❌ $1${NC}"; }

# ============================================================
# START
# ============================================================
print_banner
MAC_UPDATE_VER="$(mac_update_version)"
print_info "macOS Updates v${MAC_UPDATE_VER}"

if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "DRY-RUN mode — no system mutations will be performed"
fi

echo -e "  ${BOLD}$L_UPDATE_ALL_INTRO${NC}"
printf "%b\n" "$L_UPDATE_ALL_STEPS" | sed 's/^/    /'
echo ""
echo -e "  ${YELLOW}$L_UPDATE_ALL_DURATION${NC}"
echo ""

START_TIME=$(date +%s)

if [ "${MAC_UPDATE_YES:-0}" != "1" ]; then
    read -r -p "  $L_CONFIRM_UPDATE [T/n]: " CONFIRM
    CONFIRM="${CONFIRM:-T}"
    if [[ "$CONFIRM" =~ ^[Nn] ]]; then
        print_info "$L_UPDATE_CANCELED"
        exit 0
    fi
fi

# ============================================================
# SESJA — katalog tymczasowy
# ============================================================
SESSION_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mac_update.XXXXXX")"
chmod 700 "$SESSION_DIR" 2>/dev/null || true
export MAC_UPDATE_SESSION_DIR="$SESSION_DIR"
export MAS_NO_AUTO_INDEX=1
print_info "$L_ALL_SESSION_DIR_MSG $SESSION_DIR"

# ============================================================
# LOGS — persisted run log (~/Dev_Env/macOS_updates/logs/)
# ============================================================
# Each invocation appends stdout+stderr to a timestamped file in logs/
# so failed runs can be diagnosed after the session dir is cleaned.
# Rotation keeps the last MAX_LOGS files (default 30).
LOGS_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOGS_DIR" 2>/dev/null || true
chmod 700 "$LOGS_DIR" 2>/dev/null || true
LOG_TS="$(date +%Y%m%d_%H%M%S)"
LOG_FILE="$LOGS_DIR/update_all_${LOG_TS}.log"
MAX_LOGS="${MAC_UPDATE_MAX_LOGS:-30}"
case "$MAX_LOGS" in
    ''|*[!0-9]*|0)
        print_error "MAC_UPDATE_MAX_LOGS must be a positive integer (received: $MAX_LOGS)"
        rm -rf "$SESSION_DIR" 2>/dev/null || true
        exit 2
        ;;
esac

# Create the diagnostic log with private permissions before tee opens it.
# The directory is already mode 700, but an explicit 600 file mode also
# protects copied logs and non-standard umask configurations.
: > "$LOG_FILE" || {
    print_error "Cannot create run log: $LOG_FILE"
    rm -rf "$SESSION_DIR" 2>/dev/null || true
    exit 1
}
chmod 600 "$LOG_FILE" 2>/dev/null || {
    print_error "Cannot protect run log: $LOG_FILE"
    rm -f "$LOG_FILE" 2>/dev/null || true
    rm -rf "$SESSION_DIR" 2>/dev/null || true
    exit 1
}

# Rotate: prune oldest beyond MAX_LOGS
if [ -d "$LOGS_DIR" ]; then
    # shellcheck disable=SC2012  # ls -t is fine; filenames are controlled
    ls -1t "$LOGS_DIR"/update_all_*.log 2>/dev/null \
        | tail -n +$((MAX_LOGS + 1)) \
        | while IFS= read -r old_log; do
            [ -n "$old_log" ] && rm -f "$old_log"
        done
fi

print_info "Run log: $LOG_FILE"

# Tee everything from this point to the log file. Note: this MUST come
# AFTER the interactive confirmation read above (tee on FD 0 is fine but
# we already consumed user input).
exec > >(tee -a "$LOG_FILE") 2>&1

cleanup_session_dir() {
    if [ "${MAC_UPDATE_JSON_SUMMARY:-0}" = "1" ]; then
        python3 - <<'PYJSON' 2>/dev/null || true
import json, os
print(json.dumps({
    "exit_code": int(os.environ.get("MAC_UPDATE_OVERALL_EXIT", "0")),
    "duration_sec": int(os.environ.get("MAC_UPDATE_DURATION_SEC", "0")),
    "dry_run": os.environ.get("MAC_UPDATE_DRY_RUN", "0") == "1",
    "results": {
        "prescan": os.environ.get("MAC_UPDATE_RESULT_SCAN", ""),
        "system": os.environ.get("MAC_UPDATE_RESULT_SYSTEM", ""),
        "appstore": os.environ.get("MAC_UPDATE_RESULT_APPSTORE", ""),
        "npm": os.environ.get("MAC_UPDATE_RESULT_NPMCLI", ""),
        "brew": os.environ.get("MAC_UPDATE_RESULT_BREW", ""),
        "internet": os.environ.get("MAC_UPDATE_RESULT_INTERNET", ""),
        "postupdate": os.environ.get("MAC_UPDATE_RESULT_MD", ""),
    },
    "log_file": os.environ.get("MAC_UPDATE_LOG_FILE", ""),
}, indent=2))
PYJSON
    fi
    # If we failed, dump session dir snapshots into the run log before wipe.
    if [ -d "${SESSION_DIR:-/nonexistent}" ] && [ "${OVERALL_EXIT:-0}" -ne 0 ]; then
        {
            echo ""
            echo "=========================================="
            echo "SESSION DIR SNAPSHOTS (preserved on failure)"
            echo "Path: $SESSION_DIR"
            echo "=========================================="
            for f in "$SESSION_DIR"/*.txt "$SESSION_DIR"/appstore_diag.txt; do
                [ -f "$f" ] || continue
                echo ""
                echo "--- ${f##*/} ---"
                # Cap each snapshot at 200 lines to keep logs reasonable.
                head -n 200 "$f" 2>/dev/null
            done
        } 2>/dev/null || true
    fi
    case "${SESSION_DIR:-}" in
        "${TMPDIR:-/tmp}"/mac_update.*|/tmp/mac_update.*)
            rm -rf "$SESSION_DIR" 2>/dev/null || true
            ;;
    esac
}
trap cleanup_session_dir EXIT
trap 'cleanup_session_dir; exit 130' INT TERM

# ============================================================
# Track wyników
# ============================================================
RESULT_SCAN="$L_ALL_RESULT_SKIPPED"
RESULT_SYSTEM="$L_ALL_RESULT_SKIPPED"
RESULT_APPSTORE="$L_ALL_RESULT_SKIPPED"
RESULT_INTERNET="$L_ALL_RESULT_SKIPPED"
RESULT_NPMCLI="$L_ALL_RESULT_SKIPPED"
RESULT_BREW="$L_ALL_RESULT_SKIPPED"
RESULT_MD="$L_ALL_RESULT_SKIPPED"
SYSTEM_HISTORY_PENDING="⏳ pending final step"
SYSTEM_DEFERRED=0
OVERALL_EXIT=0

# ============================================================
# STEP 0: Scan new applications
# ============================================================
ui_master_progress 0 6
if [ "${MAC_UPDATE_SKIP_PRESCAN:-0}" = "1" ]; then
    print_info "Skipped step 0 (--skip-prescan)"
    RESULT_SCAN="$L_ALL_RESULT_SKIPPED"
elif mac_update_dry_run_msg "prescan.py (APPLICATIONS.md scan)"; then
    RESULT_SCAN="[DRY-RUN] skipped"
else
ui_step_header 0 6 "$L_ALL_STEP0"

# Write the pre-scan Python script to session dir
cat > "$SESSION_DIR/prescan.py" << 'PYEOF'
import os
import re
import sys
import subprocess
import tempfile

script_dir = sys.argv[1]
session_dir = sys.argv[2]

programy_md_path = os.path.join(script_dir, 'APPLICATIONS.md')

def atomic_write_text(path, text, mode=0o600):
    directory = os.path.dirname(path) or '.'
    fd, tmp_path = tempfile.mkstemp(prefix='.mac-update.', dir=directory, text=True)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        os.chmod(path, mode)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

def read_md():
    if not os.path.exists(programy_md_path):
        import subprocess as _sp0
        from datetime import datetime as _dt0
        _u = os.environ.get('USER', 'user')
        _pv = _sp0.run(['sw_vers', '-productVersion'], capture_output=True, text=True).stdout.strip() or 'unknown'
        _bv = _sp0.run(['sw_vers', '-buildVersion'], capture_output=True, text=True).stdout.strip() or 'unknown'
        # Codename mapping: 13=Ventura, 14=Sonoma, 15=Sequoia, 26=Tahoe
        try:
            _major = int(_pv.split('.', 1)[0])
        except (ValueError, IndexError):
            _major = 0
        _codename = {13: 'Ventura', 14: 'Sonoma', 15: 'Sequoia', 26: 'Tahoe'}.get(_major, '')
        _label = f"macOS {_pv} {_codename}".rstrip()
        _h = os.path.expanduser('~')
        _t = _dt0.now().strftime('%Y-%m-%d')
        _minimal = (
            f"# 📱 ZAINSTALOWANE APLIKACJE — MacBook {_u} ({_label})\n\n"
            f"> **Data analizy:** {_t}\n"
            f"> **Użytkownik:** {_u} | **Home:** `{_h}`\n"
            f"> **System:** {_label} (Build {_bv})\n"
            "> **Architektura:** Apple Silicon (arm64)\n"
            f"> **Folder skryptów:** `{script_dir}`\n\n"
            "---\n\n## GRUPA 1 — Aplikacje Systemowe Apple 🍎\n\n"
            "| Nazwa | Wersja |\n|-------|--------|\n\n---\n\n"
            "## GRUPA 2 — App Store 🛍️\n\n"
            "| Nazwa aplikacji | Apple ID |\n|-----------------|----------|\n\n"
            "> ⚠️ **Aplikacje iPad na Apple Silicon**\n\n---\n\n"
            "## GRUPA 3 — Aplikacje z Internetu 🌐\n\n"
            "### ☁️ Przechowywanie w chmurze\n\n"
            "| Nazwa | Wersja | Strona aktualizacji |\n|-------|--------|---------------------|\n\n---\n\n"
            "## GRUPA 4 — Homebrew 🍺\n\n### 4a. Kluczowe pakiety ⭐\n\n"
            "| Pakiet | Wersja | Opis |\n|--------|--------|------|\n\n"
            "### 4b. Formulae (zależności)\n\n"
            "| Pakiet | Wersja | Opis |\n|--------|--------|------|\n\n"
            "### 4c. Casks (aplikacje GUI)\n\n"
            "| Pakiet | Wersja | Opis |\n|--------|--------|------|\n\n"
            "### 4d. Native CLI + npm global\n\n"
            "| Pakiet | Wersja | Opis |\n|--------|--------|------|\n\n"
            "> **Uwaga:** Casks zarządzane przez Homebrew.\n\n"
            f"## Podsumowanie\n\n*Zaktualizowano: {_t}*\n"
        )
        atomic_write_text(programy_md_path, _minimal)
        print("  ℹ️  APPLICATIONS.md nie istnieje — utworzono minimalny szablon")
    with open(programy_md_path, 'r') as f:
        return f.read()

content = read_md()
any_new_found = False

APP_ALIASES = {
    'OpenCode': ['OpenCode', 'opencode', 'Opencode', 'opencode Desktop'],
    'Ledger Live': ['Ledger Live', 'Ledger Wallet'],
    'Docker': ['Docker', 'Docker Desktop'],
    'Docker Desktop': ['Docker', 'Docker Desktop'],
    'ChatGPT / Codex': ['ChatGPT / Codex', 'ChatGPT', 'Codex', 'Codex Desktop (OpenAI)'],
    'ChatGPT': ['ChatGPT', 'ChatGPT / Codex', 'Codex', 'Codex Desktop (OpenAI)'],
    'Codex': ['Codex', 'ChatGPT', 'ChatGPT / Codex', 'Codex Desktop (OpenAI)'],
    'Comet': ['Comet', 'Comet (Perplexity Browser)'],
    'Perplexity': ['Perplexity', 'Perplexity Desktop'],
    'zoom.us': ['zoom.us', 'Zoom'],
    'Visual Studio Code': ['Visual Studio Code', 'VS Code'],
    'Brave Browser': ['Brave Browser', 'Brave'],
    'Firefox Developer Edition': ['Firefox Developer Edition', 'Firefox Dev Edition'],
    'Keynote Creator Studio': ['Keynote Creator Studio', 'Keynote'],
    'Numbers Creator Studio': ['Numbers Creator Studio', 'Numbers'],
    'Pages Creator Studio': ['Pages Creator Studio', 'Pages'],
}

SKIP_DISCOVERY_APPS = set(['Utilities'])
# Apps explicitly delegated to App Store GUI Track 2 are already covered by
# the registry even though iPad-on-Mac inventory entries are not normal mas
# rows. Do not report them as new internet downloads on every prescan.
methods_path = os.path.join(script_dir, 'config', 'internet_app_methods.txt')
try:
    with open(methods_path, encoding='utf-8') as methods_handle:
        for raw in methods_handle:
            raw = raw.split('#', 1)[0].strip()
            if not raw:
                continue
            fields = raw.split('|')
            if len(fields) >= 2 and fields[1] == 'appstore_gui':
                SKIP_DISCOVERY_APPS.add(fields[0])
except OSError:
    pass

def row_exists(table_content, name):
    for candidate in APP_ALIASES.get(name, [name]):
        # Inventory cells may bold iPad apps or append a marker such as 🆕.
        # Match the exact start of the first cell while allowing that formatting.
        pattern = (
            r'^\|\s*(?:\*\*)?' + re.escape(candidate)
            + r'(?:\*\*)?(?:\s+[^|]+)?\s*\|'
        )
        if re.search(pattern, table_content, re.MULTILINE) is not None:
            return True
    return False

def app_exists(name):
    candidates = APP_ALIASES.get(name, [name])
    for candidate in candidates:
        for applications_dir in ('/Applications', os.path.expanduser('~/Applications')):
            if os.path.exists(os.path.join(applications_dir, candidate + '.app')):
                return True
    return False

print("  Skanowanie /Applications...")

# ── 1. Skanowanie /Applications ──────────────────────────────
# WAŻNE: szukamy tylko w GRUPACH 1-3 (nie w sekcji Homebrew 4),
# aby uniknąć fałszywych dopasowań CLI brew z aplikacjami Desktop
# np. brew formula 'opencode' NIE powinna blokować wykrycia 'opencode.app'
grupo_1_3_match = re.search(r'^(.*?)(?=^## GRUPA 4)', content, re.DOTALL | re.MULTILINE)
grupo_1_3_content = grupo_1_3_match.group(1) if grupo_1_3_match else content

installed_app_paths = {}
for applications_dir in ('/Applications', os.path.expanduser('~/Applications')):
    try:
        for item in os.listdir(applications_dir):
            if item.endswith('.app'):
                installed_app_paths.setdefault(item[:-4], os.path.join(applications_dir, item))
    except Exception:
        pass

installed_apps = sorted(
    name for name in installed_app_paths
    if '|' not in name and not any(ord(char) < 32 or ord(char) == 127 for char in name)
)
new_apps = []

def installed_app_version(app_path):
    for key in ('CFBundleShortVersionString', 'CFBundleVersion'):
        try:
            result = subprocess.run(
                ['defaults', 'read', os.path.join(app_path, 'Contents', 'Info'), key],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
    try:
        result = subprocess.run(
            ['mdls', '-name', 'kMDItemVersion', '-raw', app_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip() not in ('', '(null)'):
            return result.stdout.strip()
    except Exception:
        pass
    return '?'

# Always persist a current installed-app snapshot for the post-scan inventory
# refresh. The session directory is private and removed by the orchestrator.
with open(os.path.join(session_dir, 'installed_apps_after.txt'), 'w', encoding='utf-8') as handle:
    for app in installed_apps:
        if '|' in app or '\n' in app or '\r' in app:
            continue
        handle.write(f"{app}|{installed_app_version(installed_app_paths[app])}\n")

# Aplikacje systemowe Apple — zawsze obecne w GRUPIE 1, pomiń fałszywe wpisy
SYSTEM_APP_FRAGMENTS = [
    'Installer', 'Uninstaller', 'Helper', 'Agent', 'Updater',
    'Shim', 'Launcher', 'Framework', 'Plugin', 'Extension',
    'Service', 'Daemon', 'XPC', 'Feedback', 'Handler',
]

for app in installed_apps:
    # Pomijaj pomocnicze komponenty aplikacji
    if any(frag.lower() in app.lower() for frag in SYSTEM_APP_FRAGMENTS):
        continue
    if app in SKIP_DISCOVERY_APPS:
        continue
    # Szukaj nazwy apki TYLKO w sekcjach GRUPA 1-3 (nie Homebrew)
    if not row_exists(grupo_1_3_content, app):
        new_apps.append(app)

if new_apps:
    any_new_found = True
    print(f"  ⚠️  Nowe aplikacje nieobecne w APPLICATIONS.md ({len(new_apps)} szt.):")
    for app in new_apps:
        print(f"       → {app}")
    with open(os.path.join(session_dir, 'new_apps.txt'), 'w') as f:
        f.write('\n'.join(new_apps) + '\n')
else:
    print("  ✅ Wszystkie aplikacje z /Applications są w APPLICATIONS.md")

# ── 2. Skanowanie Homebrew formulae ──────────────────────────
print("\n  Skanowanie Homebrew formulae...")
try:
    result = subprocess.run(['brew', 'list', '--formula', '--versions'],
                            capture_output=True, text=True, timeout=60)
    formula_lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
    new_formulae = []
    for line in formula_lines:
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        ver = parts[1] if len(parts) > 1 else '?'
        if not re.search(r'\|\s*' + re.escape(name) + r'\s*\|', content):
            new_formulae.append((name, ver))
    if new_formulae:
        any_new_found = True
        print(f"  ⚠️  Nowe formulae Homebrew nieobecne w APPLICATIONS.md ({len(new_formulae)} szt.):")
        for name, ver in new_formulae:
            print(f"       → {name} {ver}")
        with open(os.path.join(session_dir, 'new_brew_formulae.txt'), 'w') as f:
            for name, ver in new_formulae:
                f.write(f"{name} {ver}\n")
    else:
        print("  ✅ Wszystkie formulae Homebrew są w APPLICATIONS.md")
except Exception as e:
    print(f"  ⚠️  Nie można sprawdzić Homebrew formulae: {e}")

# ── 3. Skanowanie Homebrew casks ─────────────────────────────
print("\n  Skanowanie Homebrew casks...")
try:
    result = subprocess.run(['brew', 'list', '--cask', '--versions'],
                            capture_output=True, text=True, timeout=60)
    cask_lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
    new_casks = []
    for line in cask_lines:
        parts = line.split()
        if not parts:
            continue
        name = parts[0]
        ver = parts[1] if len(parts) > 1 else '?'
        if not re.search(r'\|\s*' + re.escape(name) + r'\s*\|', content):
            new_casks.append((name, ver))
    if new_casks:
        any_new_found = True
        print(f"  ⚠️  Nowe casks Homebrew nieobecne w APPLICATIONS.md ({len(new_casks)} szt.):")
        for name, ver in new_casks:
            print(f"       → {name} {ver}")
        with open(os.path.join(session_dir, 'new_brew_casks.txt'), 'w') as f:
            for name, ver in new_casks:
                f.write(f"{name} {ver}\n")
    else:
        print("  ✅ Wszystkie casks Homebrew są w APPLICATIONS.md")
except Exception as e:
    print(f"  ⚠️  Nie można sprawdzić Homebrew casks: {e}")

# ── 4. Skanowanie App Store (mas) ────────────────────────────
print("\n  Skanowanie App Store (mas)...")
try:
    result = subprocess.run(['mas', 'list'],
                            capture_output=True, text=True, timeout=30)
    mas_lines = [l.strip() for l in result.stdout.strip().split('\n') if l.strip()]
    new_mas = []
    for line in mas_lines:
        match = re.match(r'^(\d+)\s+(.+?)\s+\(([^()]+)\)$', line)
        if not match:
            continue
        app_id = match.group(1)
        app_name = match.group(2).strip()
        ver = match.group(3).strip()
        if not row_exists(content, app_name):
            new_mas.append((app_id, app_name, ver))
    if new_mas:
        any_new_found = True
        print(f"  ⚠️  Nowe aplikacje App Store nieobecne w APPLICATIONS.md ({len(new_mas)} szt.):")
        for app_id, name, ver in new_mas:
            print(f"       → {name} (ID: {app_id}, wersja: {ver})")
        with open(os.path.join(session_dir, 'new_mas_apps.txt'), 'w') as f:
            for app_id, name, ver in new_mas:
                f.write(f"{app_id} {name} ({ver})\n")
    else:
        print("  ✅ Wszystkie aplikacje App Store są w APPLICATIONS.md")
except FileNotFoundError:
    print("  ℹ️  mas nie jest zainstalowany — pomijam skan App Store")
except Exception as e:
    print(f"  ℹ️  mas niedostępny: {e}")

# ── 5. Wykryj usunięte aplikacje (są w APPLICATIONS.md GRUPA 3, ale nie ma w /Applications) ──
# Skanuj GRUPĘ 3 tabeli APPLICATIONS.md i sprawdź, czy wciąż są zainstalowane
print("\n  Sprawdzanie usuniętych aplikacji z GRUPY 3...")
removed_apps = []
try:
    # Wyodrębnij GRUPĘ 3 (od ## GRUPA 3 do ## GRUPA 4)
    grupa3_match = re.search(r'^## GRUPA 3.*?(?=^## GRUPA 4)', content, re.DOTALL | re.MULTILINE)
    if grupa3_match:
        grupa3_content = grupa3_match.group(0)
        # Znajdź wiersze tabelki: | Nazwa aplikacji | ... |
        # Pierwszy kolumna to nazwa apki (bez emoji/flag)
        for line in grupa3_content.split('\n'):
            m = re.match(r'^\| ([^|]+?) \|', line)
            if m and not line.startswith('| **') and not line.startswith('| Nazwa') and '---' not in line:
                app_name_raw = m.group(1).strip()
                # Usuń emoji np. ⭐, 🆕 na początku/końcu
                app_name = re.sub(r'^[\U0001F300-\U0001FFFF\s]+|[\U0001F300-\U0001FFFF\s]+$', '', app_name_raw).strip()
                # Pomiń wiersze nagłówkowe i separatory
                if not app_name or app_name.startswith('-') or app_name.startswith('|'):
                    continue
                # Sprawdź czy apka jest zainstalowana
                if not app_exists(app_name):
                    # Dodatkowe sprawdzenie — może nazwa w tabeli to skrócona wersja
                    # np. "Firefox Developer Edition" → "Firefox Developer Edition.app"
                    removed_apps.append(app_name)
    if removed_apps:
        print(f"  ⚠️  Aplikacje z GRUPY 3 nieznalezione w /Applications ({len(removed_apps)} szt.):")
        for app in removed_apps:
            print(f"       🗑️  {app}")
        with open(os.path.join(session_dir, 'removed_apps.txt'), 'w') as f:
            f.write('\n'.join(removed_apps) + '\n')
        any_new_found = True  # trigger update section
    else:
        print("  ✅ Wszystkie aplikacje z GRUPY 3 są nadal zainstalowane")
except Exception as e:
    print(f"  ⚠️  Błąd przy sprawdzaniu usuniętych aplikacji: {e}")

# ── 6. Aktualizuj APPLICATIONS.md o nowe wpisy ───────────────────
if not any_new_found:
    print("\n  ✅ APPLICATIONS.md jest aktualny — nie wykryto zmian.")
    sys.exit(0)

print("\n  📝 Aktualizuję APPLICATIONS.md o nowe wpisy...")

content = read_md()
changes_made = False
from datetime import datetime

# Add new brew formulae (appended at end of 4a table, before blank line + "4b." header)
# POPRAWKA: używamy regex żeby wstawić wiersze NA KOŃCU tabeli 4a (bez blank line gap)
new_formula_file = os.path.join(session_dir, 'new_brew_formulae.txt')
if os.path.exists(new_formula_file):
    with open(new_formula_file) as f:
        items = [l.strip().split(None, 1) for l in f if l.strip()]
    # Deduplikuj — nie dodawaj jeśli już jest w APPLICATIONS.md (w tabeli 4a)
    items = [p for p in items if not re.search(r'\|\s*' + re.escape(p[0]) + r'\s*\|', content)]
    if items:
        new_rows = ''
        for parts in items:
            name = parts[0]
            ver = parts[1] if len(parts) > 1 else '?'
            new_rows += f"| {name} | {ver} | 🆕 NOWY — opis do uzupełnienia |\n"
        # Wstaw NA KOŃCU tabeli 4a (ostatni wiersz |\...\| bezpośrednio przed \n\n### 4b.)
        pattern_4a = r'((?:\| [^\n]+\|\n)+)(\n+### 4b\.)'
        m4a = re.search(pattern_4a, content)
        if m4a:
            insert_pos = m4a.start(2)  # pozycja przed \n\n### 4b.
            content = content[:insert_pos] + new_rows + content[insert_pos:]
            changes_made = True
            print(f"  ✅ Dodano {len(items)} nowych formulae do APPLICATIONS.md (sekcja 4a)")

# Add new brew casks (appended at end of 4c table)
# POPRAWKA: wstawiamy NA KOŃCU tabeli 4c, nie przed uwagą tekstową
new_cask_file = os.path.join(session_dir, 'new_brew_casks.txt')
if os.path.exists(new_cask_file):
    with open(new_cask_file) as f:
        items = [l.strip().split(None, 1) for l in f if l.strip()]
    # Deduplikuj
    items = [p for p in items if not re.search(r'\|\s*' + re.escape(p[0]) + r'\s*\|', content)]
    if items:
        new_rows = ''
        for parts in items:
            name = parts[0]
            ver = parts[1] if len(parts) > 1 else '?'
            new_rows += f"| {name} | {ver} | 🆕 NOWY — opis do uzupełnienia |\n"
        # Znajdź tabelę 4c i wstaw na końcu (przed > **Uwaga lub przed ## Podsumowanie)
        # Wzorzec: ostatni wiersz tabeli 4c przed pustą linią lub uwagą
        pattern_4c = r'(### 4c\..*?)((?:\| [^\n]+\|\n)+)(\n+>|\n+##)'
        m4c = re.search(pattern_4c, content, re.DOTALL)
        if m4c:
            insert_pos = m4c.start(3)  # pozycja przed pustą linią/uwagą
            content = content[:insert_pos] + new_rows + content[insert_pos:]
            changes_made = True
            print(f"  ✅ Dodano {len(items)} nowych casks do APPLICATIONS.md (sekcja 4c)")

# Add new App Store apps (to GRUPA 2, before iPad apps note)
new_mas_file = os.path.join(session_dir, 'new_mas_apps.txt')
if os.path.exists(new_mas_file):
    with open(new_mas_file) as f:
        lines = [l.strip() for l in f if l.strip()]
    if lines:
        new_rows = ''
        for line in lines:
            parts = line.split(None, 1)
            app_id = parts[0]
            name_ver = parts[1] if len(parts) > 1 else '?'
            name = name_ver.split('(')[0].strip()
            new_rows += f"| {name} 🆕 | {app_id} |\n"
        marker = "> ⚠️ **Aplikacje iPad na Apple Silicon**"
        if marker in content:
            content = content.replace(marker, new_rows + "\n" + marker)
            changes_made = True
            print(f"  ✅ Dodano {len(lines)} nowych aplikacji App Store do APPLICATIONS.md (GRUPA 2)")

# Add new /Applications apps not already handled via brew/mas
new_apps_file = os.path.join(session_dir, 'new_apps.txt')
if os.path.exists(new_apps_file):
    with open(new_apps_file) as f:
        new_app_names = [l.strip() for l in f if l.strip()]
    # Collect names already handled via brew or mas
    handled = set()
    for fname in [new_formula_file, new_cask_file]:
        if os.path.exists(fname):
            with open(fname) as f:
                for line in f:
                    parts = line.strip().split()
                    if parts:
                        handled.add(parts[0].lower())
    if os.path.exists(new_mas_file):
        with open(new_mas_file) as f:
            for line in f:
                parts = line.strip().split(None, 1)
                if len(parts) > 1:
                    name_ver = parts[1].split('(')[0].strip()
                    handled.add(name_ver.lower())
    unhandled = [a for a in new_app_names if a.lower() not in handled]
    if unhandled:
        new_rows = ''
        for app in unhandled:
            new_rows += f"| {app} | 🆕 do skategoryzowania | — |\n"
        # POPRAWKA: sprawdź czy sekcja 🆕 już istnieje — jeśli tak, dołącz do niej
        # zamiast tworzyć duplikat sekcji
        existing_new_section = "### 🆕 Nowo wykryte aplikacje (do skategoryzowania)"
        if existing_new_section in content:
            # Znajdź koniec istniejącej tabeli w tej sekcji i wstaw tam
            pattern_nowe = r'(### 🆕 Nowo wykryte aplikacje.*?)((?:\| [^\n]+\|\n)+)(\n+>|\n+###|\n+$)'
            m_nowe = re.search(pattern_nowe, content, re.DOTALL)
            if m_nowe:
                insert_pos = m_nowe.start(3)
                # Dodaj tylko te wpisy, których jeszcze nie ma
                unhandled_dedup = [a for a in unhandled
                                   if not re.search(re.escape(a), content, re.IGNORECASE)]
                if unhandled_dedup:
                    new_rows_dedup = ''.join(f"| {a} | 🆕 do skategoryzowania | — |\n"
                                             for a in unhandled_dedup)
                    content = content[:insert_pos] + new_rows_dedup + content[insert_pos:]
                    changes_made = True
                    print(f"  ✅ Dołączono {len(unhandled_dedup)} nowych aplikacji do istniejącej sekcji 🆕")
            else:
                # Fallback: użyj replace gdy regex nie znalazł tabeli
                content = content.replace(
                    existing_new_section,
                    existing_new_section + "\n\n| Nazwa | Producent | Strona aktualizacji |\n"
                    "|-------|-----------|---------------------|\n" + new_rows
                )
                changes_made = True
                print(f"  ✅ Dodano {len(unhandled)} nowych aplikacji do APPLICATIONS.md (sekcja 🆕)")
        else:
            # Sekcja nie istnieje — utwórz nową przed ☁️ Przechowywanie w chmurze
            new_section = "\n### 🆕 Nowo wykryte aplikacje (do skategoryzowania)\n\n"
            new_section += "| Nazwa | Producent | Strona aktualizacji |\n"
            new_section += "|-------|-----------|---------------------|\n"
            new_section += new_rows
            new_section += "\n> **Uwaga:** Powyższe aplikacje zostały automatycznie wykryte. Przenieś je do właściwej sekcji GRUPY 3.\n"
            marker = "### ☁️ Przechowywanie w chmurze"
            if marker in content:
                content = content.replace(marker, new_section + "\n" + marker)
                changes_made = True
                print(f"  ✅ Dodano {len(unhandled)} nowych aplikacji do APPLICATIONS.md (GRUPA 3 — sekcja 🆕)")

# Update the analysis date
today = datetime.now().strftime('%Y-%m-%d')
content = re.sub(r'(\*\*Data analizy:\*\* )\d{4}-\d{2}-\d{2}', r'\g<1>' + today, content)

# Remove uninstalled apps from APPLICATIONS.md (confirmed policy: inventory
# describes the current Mac and never reinstalls removed applications).
removed_apps_file = os.path.join(session_dir, 'removed_apps.txt')
if os.path.exists(removed_apps_file):
    with open(removed_apps_file) as f:
        removed = [l.strip() for l in f if l.strip()]
    removed_count = 0
    for app in removed:
        pattern = r'^\| ' + re.escape(app) + r' \|[^\n]*\|\s*\n?'
        new_content = re.sub(pattern, '', content, count=1, flags=re.MULTILINE)
        if new_content != content:
            content = new_content
            removed_count += 1
    if removed_count > 0:
        changes_made = True
        print(f"  🗑️  Usunięto {removed_count} odinstalowanych aplikacji z APPLICATIONS.md")

if changes_made:
    atomic_write_text(programy_md_path, content)
    print(f"\n  📝 APPLICATIONS.md zaktualizowany o nowe aplikacje")
else:
    print(f"\n  ℹ️  APPLICATIONS.md — nowe wpisy zostały zgłoszone ale nie wymagały edycji tabel")

PYEOF

if python3 "$SESSION_DIR/prescan.py" "$SCRIPT_DIR" "$SESSION_DIR"; then
    RESULT_SCAN="$L_STATUS_OK"
    if [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" = "1" ]; then
        print_info "Capturing current versions for the inventory refresh..."
        if ! internet_capture_versions "$SESSION_DIR/internet_before.txt"; then
            print_error "Could not capture installed internet-app versions"
            RESULT_SCAN="$L_ALL_RESULT_WARN"
            OVERALL_EXIT=1
        else
            cp "$SESSION_DIR/internet_before.txt" "$SESSION_DIR/internet_after.txt"
        fi
        if command -v brew >/dev/null 2>&1; then
            if brew list --formula --versions > "$SESSION_DIR/brew_formulae_after.txt" 2>/dev/null \
                && brew list --cask --versions > "$SESSION_DIR/brew_casks_after.txt" 2>/dev/null; then
                cp "$SESSION_DIR/brew_formulae_after.txt" "$SESSION_DIR/brew_formulae_before.txt"
                cp "$SESSION_DIR/brew_casks_after.txt" "$SESSION_DIR/brew_casks_before.txt"
            else
                print_error "Could not capture Homebrew versions for inventory"
                RESULT_SCAN="$L_ALL_RESULT_WARN"
                OVERALL_EXIT=1
            fi
        fi
        python3 - "$SCRIPT_DIR/config/npm_global_clis.txt" "$SESSION_DIR/npm_cli_after.txt" <<'PYEOF'
import os
import re
import shutil
import subprocess
import sys

manifest, output = sys.argv[1:3]
home = os.path.expanduser('~')

def candidate_path(command):
    if not re.fullmatch(r'[A-Za-z0-9._+-]+', command):
        return None
    roots = [
        os.path.join(home, '.local', 'share', 'mac-update', 'npm-global', 'bin'),
        os.path.join(home, '.local', 'share', 'mac-update', 'node', 'bin'),
        os.path.join(home, '.local', 'bin'),
        os.path.join(home, '.bun', 'bin'),
    ]
    for root in roots:
        path = os.path.join(root, command)
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    return shutil.which(command)

rows = []
with open(manifest, encoding='utf-8') as handle:
    for raw in handle:
        raw = raw.split('#', 1)[0].strip()
        if not raw:
            continue
        fields = raw.split('|')
        if len(fields) != 5:
            continue
        display, package, _method, _brew_formula, command = fields
        path = candidate_path(command)
        if not path:
            continue
        args = [path, '-v' if display in ('node', 'claude-code') else '--version']
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode != 0:
            continue
        first = (result.stdout or result.stderr).strip().splitlines()
        if not first:
            continue
        version = first[0].strip()
        if display == 'claude-code':
            version = version.split()[0]
        elif display == 'codex-cli':
            version = version.split()[-1]
        elif display != 'node':
            version = version.split()[0]
        if version.startswith('v'):
            version = version[1:]
        rows.append(f'{display}|{package}|{version}|{command}|{path}')

with open(output, 'w', encoding='utf-8') as handle:
    handle.write('\n'.join(rows) + ('\n' if rows else ''))
PYEOF
        CLI_SNAPSHOT_EXIT=$?
        if [ "$CLI_SNAPSHOT_EXIT" -eq 0 ]; then
            cp "$SESSION_DIR/npm_cli_after.txt" "$SESSION_DIR/npm_cli_before.txt"
        else
            print_error "Could not capture native CLI versions for inventory"
            RESULT_SCAN="$L_ALL_RESULT_WARN"
            OVERALL_EXIT=1
        fi
    fi
else
    RESULT_SCAN="$L_ALL_RESULT_WARN"
    OVERALL_EXIT=1
fi
fi

# ============================================================
# Prepare the final system update. It is deliberately not presented as an
# early step: a framework-managed reboot must not interrupt application work.
# ============================================================
if [ "${MAC_UPDATE_SKIP_SYSTEM:-0}" = "1" ]; then
    print_info "Skipped final macOS step (--skip-system)"
    RESULT_SYSTEM="$L_ALL_RESULT_SKIPPED"
else
    SYSTEM_DEFERRED=1
    if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
        RESULT_SYSTEM="[DRY-RUN] pending final step"
    else
        RESULT_SYSTEM="$SYSTEM_HISTORY_PENDING"
    fi
fi

# ============================================================
# STEP 1: App Store update
# ============================================================
ui_master_progress 1 6
if [ "${MAC_UPDATE_SKIP_APPSTORE:-0}" = "1" ]; then
    print_info "Skipped step 1 (--skip-appstore)"
    RESULT_APPSTORE="$L_ALL_RESULT_SKIPPED"
else
ui_step_header 1 6 "$L_SCRIPT_TITLE_APPSTORE"

if [ -f "$SCRIPT_DIR/update_appstore.sh" ]; then
    chmod +x "$SCRIPT_DIR/update_appstore.sh"
    APPSTORE_EXIT=0
    if mac_update_dry_run_msg "update_appstore.sh"; then
        RESULT_APPSTORE="[DRY-RUN] skipped"
    elif bash "$SCRIPT_DIR/update_appstore.sh"; then
        RESULT_APPSTORE="$L_STATUS_OK completed"
    else
        APPSTORE_EXIT=$?
        if [ "$APPSTORE_EXIT" -eq 2 ] && [ "${MAC_UPDATE_TREAT_APPSTORE_AX_AS_WARNING:-0}" = "1" ]; then
            RESULT_APPSTORE="$L_STATUS_WARN Accessibility required"
            print_warn "App Store exit 2 (Accessibility) treated as warning"
        else
            RESULT_APPSTORE="$L_STATUS_ERROR"
            OVERALL_EXIT=1
        fi
    fi
else
    print_error "File not found: update_appstore.sh"
    RESULT_APPSTORE="$L_STATUS_ERROR missing file"
    OVERALL_EXIT=1
fi
fi

# ============================================================
# STEP 2: Native CLI & npm update
# ============================================================
ui_master_progress 2 6
if [ "${MAC_UPDATE_SKIP_NPM:-0}" = "1" ]; then
    print_info "Skipped step 2 (--skip-npm)"
    RESULT_NPMCLI="$L_ALL_RESULT_SKIPPED"
else
ui_step_header 2 6 "Native CLI + npm"
if mac_update_dry_run_msg "update_npm_cli.sh"; then
    RESULT_NPMCLI="[DRY-RUN] skipped"
elif mac_update_run_child "update_npm_cli.sh" "update_npm_cli.sh"; then
    RESULT_NPMCLI="$L_STATUS_OK completed"
else
    RESULT_NPMCLI="$L_STATUS_ERROR"
    OVERALL_EXIT=1
fi
fi

# ============================================================
# STEP 3: Homebrew update
# ============================================================
ui_master_progress 3 6
if [ "${MAC_UPDATE_SKIP_BREW:-0}" = "1" ]; then
    print_info "Skipped step 3 (--skip-brew)"
    RESULT_BREW="$L_ALL_RESULT_SKIPPED"
else
ui_step_header 3 6 "$L_SCRIPT_TITLE_BREW"

if mac_update_dry_run_msg "update_brew.sh"; then
    RESULT_BREW="[DRY-RUN] skipped"
elif [ -f "$SCRIPT_DIR/update_brew.sh" ]; then
    chmod +x "$SCRIPT_DIR/update_brew.sh"
    if bash "$SCRIPT_DIR/update_brew.sh"; then
        RESULT_BREW="$L_STATUS_OK completed"
    else
        RESULT_BREW="$L_STATUS_ERROR"
        OVERALL_EXIT=1
    fi
else
    print_error "File not found: update_brew.sh"
    RESULT_BREW="$L_STATUS_ERROR missing file"
    OVERALL_EXIT=1
fi
fi

# ============================================================
# STEP 4: Internet-downloaded apps update
# ============================================================
ui_master_progress 4 6
if [ "${MAC_UPDATE_SKIP_INTERNET:-0}" = "1" ]; then
    print_info "Skipped step 4 (--skip-internet)"
    RESULT_INTERNET="$L_ALL_RESULT_SKIPPED"
else
ui_step_header 4 6 "$L_SCRIPT_TITLE_INTERNET"

if mac_update_dry_run_msg "update_internet_apps.sh"; then
    RESULT_INTERNET="[DRY-RUN] skipped"
elif [ -f "$SCRIPT_DIR/update_internet_apps.sh" ]; then
    chmod +x "$SCRIPT_DIR/update_internet_apps.sh"
    if bash "$SCRIPT_DIR/update_internet_apps.sh"; then
        RESULT_INTERNET="$L_STATUS_OK completed"
    else
        RESULT_INTERNET="$L_STATUS_ERROR"
        OVERALL_EXIT=1
    fi
else
    print_error "File not found: update_internet_apps.sh"
    RESULT_INTERNET="$L_STATUS_ERROR missing file"
    OVERALL_EXIT=1
fi
fi

# ============================================================
# STEP 5: Update APPLICATIONS.md and UPDATES.md
# ============================================================
ui_master_progress 5 6
if [ "${MAC_UPDATE_SKIP_POSTUPDATE:-0}" = "1" ]; then
    print_info "Skipped step 5 (--skip-postupdate)"
    RESULT_MD="$L_ALL_RESULT_SKIPPED"
else
ui_step_header 5 6 "$L_ALL_STEP5_DESC"
if mac_update_dry_run_msg "postupdate.py (APPLICATIONS.md / UPDATES.md)"; then
    RESULT_MD="[DRY-RUN] skipped"
else

# Write the post-update Python script
cat > "$SESSION_DIR/postupdate.py" << 'PYEOF'
import os
import re
import sys
import tempfile
from datetime import datetime

script_dir  = sys.argv[1]
session_dir = sys.argv[2]
result_system    = sys.argv[3]
result_appstore  = sys.argv[4]
result_internet  = sys.argv[5]
result_npmcli    = sys.argv[6]
result_brew      = sys.argv[7]

programy_md_path    = os.path.join(script_dir, 'APPLICATIONS.md')
aktualizacje_md_path = os.path.join(script_dir, 'UPDATES.md')

def atomic_write_text(path, text, mode=0o600):
    directory = os.path.dirname(path) or '.'
    fd, tmp_path = tempfile.mkstemp(prefix='.mac-update.', dir=directory, text=True)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
        os.chmod(path, mode)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

# ── Helper: read versions file → dict {name: version} ────────
def read_versions(filepath):
    versions = {}
    try:
        with open(filepath) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2:
                    versions[parts[0]] = parts[1]
    except FileNotFoundError:
        pass
    return versions

def read_npm_cli_versions(filepath):
    versions = {}
    paths = {}
    try:
        with open(filepath) as f:
            for line in f:
                parts = line.strip().split('|')
                if len(parts) >= 5:
                    versions[parts[0]] = parts[2]
                    paths[parts[0]] = parts[4]
    except FileNotFoundError:
        pass
    return versions, paths

# ── Load snapshots ────────────────────────────────────────────
brew_formula_before = read_versions(os.path.join(session_dir, 'brew_formulae_before.txt'))
brew_formula_after  = read_versions(os.path.join(session_dir, 'brew_formulae_after.txt'))
brew_cask_before    = read_versions(os.path.join(session_dir, 'brew_casks_before.txt'))
brew_cask_after     = read_versions(os.path.join(session_dir, 'brew_casks_after.txt'))
npm_cli_before, npm_cli_paths_before = read_npm_cli_versions(os.path.join(session_dir, 'npm_cli_before.txt'))
npm_cli_after, npm_cli_paths_after = read_npm_cli_versions(os.path.join(session_dir, 'npm_cli_after.txt'))

# ── Compute what changed ──────────────────────────────────────
formula_upgrades = {}
for name, new_ver in brew_formula_after.items():
    old_ver = brew_formula_before.get(name)
    if old_ver and old_ver != new_ver:
        formula_upgrades[name] = (old_ver, new_ver)

cask_upgrades = {}
for name, new_ver in brew_cask_after.items():
    old_ver = brew_cask_before.get(name)
    if old_ver and old_ver != new_ver:
        cask_upgrades[name] = (old_ver, new_ver)

formula_new = {k: v for k, v in brew_formula_after.items() if k not in brew_formula_before}
cask_new    = {k: v for k, v in brew_cask_after.items()    if k not in brew_cask_before}
npm_cli_upgrades = {}
for name, new_ver in npm_cli_after.items():
    old_ver = npm_cli_before.get(name)
    if old_ver and old_ver != new_ver and old_ver != '?' and new_ver != '?':
        npm_cli_upgrades[name] = (old_ver, new_ver)

npm_cli_new = {k: v for k, v in npm_cli_after.items() if k not in npm_cli_before}

# ── Compute internet app changes ──────────────────────────────
def read_internet_versions(filepath):
    versions = {}
    try:
        with open(filepath) as f:
            for line in f:
                line = line.strip()
                if '|' in line:
                    parts = line.split('|', 1)
                    if len(parts) == 2:
                        versions[parts[0]] = parts[1]
    except FileNotFoundError:
        pass
    return versions

internet_before = read_internet_versions(os.path.join(session_dir, 'internet_before.txt'))
internet_after  = read_internet_versions(os.path.join(session_dir, 'internet_after.txt'))
installed_apps_after = read_internet_versions(os.path.join(session_dir, 'installed_apps_after.txt'))

internet_upgrades = {}
for name, new_ver in internet_after.items():
    old_ver = internet_before.get(name)
    if old_ver and old_ver != new_ver and old_ver != '?' and new_ver != '?':
        internet_upgrades[name] = (old_ver, new_ver)

# Map config/snapshot keys → APPLICATIONS.md table row names
INTERNET_SNAPSHOT_ALIASES = {
    'Perplexity': ['Perplexity', 'Perplexity Desktop'],
    'zoom.us': ['zoom.us', 'Zoom'],
    'Visual Studio Code': ['Visual Studio Code', 'VS Code'],
    'Firefox Developer Edition': ['Firefox Developer Edition', 'Firefox Dev Edition'],
    'Brave Browser': ['Brave Browser', 'Brave'],
    'Ledger Live': ['Ledger Live', 'Ledger Wallet', 'Ledger Live/Wallet'],
    'Ledger Wallet': ['Ledger Live', 'Ledger Wallet', 'Ledger Live/Wallet'],
    'Docker Desktop': ['Docker Desktop', 'Docker'],
    'OpenCode': ['OpenCode', 'OpenCode Desktop', 'opencode'],
    'ChatGPT / Codex': ['ChatGPT / Codex', 'ChatGPT', 'Codex', 'Codex Desktop', 'Codex Desktop (OpenAI)'],
    'Comet': ['Comet', 'Comet (Perplexity Browser)'],
}

def expand_internet_versions(snap_versions):
    expanded = dict(snap_versions)
    for config_key, aliases in INTERNET_SNAPSHOT_ALIASES.items():
        ver = snap_versions.get(config_key)
        if ver is None:
            continue
        for alias in aliases:
            expanded[alias] = ver
    return expanded

def version_for_table_row(table_name, versions):
    if table_name in versions:
        return versions[table_name]
    for config_key, aliases in INTERNET_SNAPSHOT_ALIASES.items():
        if table_name in aliases and config_key in versions:
            return versions[config_key]
    return None

# ── Update APPLICATIONS.md version numbers ───────────────────────
print("  Aktualizuję wersje w APPLICATIONS.md...")

try:
    with open(programy_md_path, 'r') as f:
        content = f.read()
except FileNotFoundError:
    import subprocess as _sp1
    _u1 = os.environ.get('USER', 'user')
    _pv1 = _sp1.run(['sw_vers', '-productVersion'], capture_output=True, text=True).stdout.strip() or 'unknown'
    _bv1 = _sp1.run(['sw_vers', '-buildVersion'], capture_output=True, text=True).stdout.strip() or 'unknown'
    _h1 = os.path.expanduser('~')
    _t1 = datetime.now().strftime('%Y-%m-%d')
    try:
        _major1 = int(_pv1.split('.', 1)[0])
    except (ValueError, IndexError):
        _major1 = 0
    _codenames1 = {13: 'Ventura', 14: 'Sonoma', 15: 'Sequoia', 26: 'Tahoe'}
    _codename1 = _codenames1.get(_major1, '')
    _os_title1 = f"macOS {_pv1}" + (f" {_codename1}" if _codename1 else "")
    content = (
        f"# 📱 ZAINSTALOWANE APLIKACJE — MacBook {_u1} ({_os_title1})\n\n"
        f"> **Data analizy:** {_t1}\n"
        f"> **Użytkownik:** {_u1} | **Home:** `{_h1}`\n"
        f"> **System:** {_os_title1} (Build {_bv1})\n"
        "> **Architektura:** Apple Silicon (arm64)\n"
        f"> **Folder skryptów:** `{script_dir}`\n\n"
        "---\n\n## GRUPA 1 — Aplikacje Systemowe Apple 🍎\n\n"
        "| Nazwa | Wersja |\n|-------|--------|\n\n---\n\n"
        "## GRUPA 2 — App Store 🛍️\n\n"
        "| Nazwa aplikacji | Apple ID |\n|-----------------|----------|\n\n"
        "> ⚠️ **Aplikacje iPad na Apple Silicon**\n\n---\n\n"
        "## GRUPA 3 — Aplikacje z Internetu 🌐\n\n"
        "### ☁️ Przechowywanie w chmurze\n\n"
        "| Nazwa | Wersja | Strona aktualizacji |\n|-------|--------|---------------------|\n\n---\n\n"
        "## GRUPA 4 — Homebrew 🍺\n\n### 4a. Kluczowe pakiety ⭐\n\n"
        "| Pakiet | Wersja | Opis |\n|--------|--------|------|\n\n"
        "### 4b. Formulae (zależności)\n\n"
        "| Pakiet | Wersja | Opis |\n|--------|--------|------|\n\n"
        "### 4c. Casks (aplikacje GUI)\n\n"
        "| Pakiet | Wersja | Opis |\n|--------|--------|------|\n\n"
        "### 4d. Native CLI + npm global\n\n"
        "| Pakiet | Wersja | Opis |\n|--------|--------|------|\n\n"
        "> **Uwaga:** Casks zarządzane przez Homebrew.\n\n"
        f"## Podsumowanie\n\n*Zaktualizowano: {_t1}*\n"
    )
    print("  ℹ️  APPLICATIONS.md nie istnieje — tworzę minimalny szablon")

# Merge all updated versions (brew formulae + casks + internet apps)
all_new_versions = {}
all_new_versions.update(brew_formula_after)
all_new_versions.update(brew_cask_after)
# The all-app snapshot also refreshes system and arbitrary GUI bundles during
# inventory-only runs. Canonical internet snapshots below take precedence.
all_new_versions.update(installed_apps_after)
# Add internet app versions (snapshot keys + APPLICATIONS.md aliases)
all_new_versions.update(expand_internet_versions(internet_after))
all_new_versions.update(npm_cli_after)

updated_count = 0
lines = content.split('\n')
new_lines = []

for line in lines:
    # Match 3-column table row: | name | version | description |
    m = re.match(r'^(\| )(\S.*?\S|\S)( \| )([^\|]+?)( \| )(.+?)( \|)\s*$', line)
    if m:
        name = m.group(2).strip()
        new_ver = version_for_table_row(name, all_new_versions)
        if new_ver is not None:
            old_ver = m.group(4).strip()
            if old_ver != new_ver and new_ver != '?':
                line = f"{m.group(1)}{name}{m.group(3)}{new_ver}{m.group(5)}{m.group(6)}{m.group(7)}"
                updated_count += 1
    new_lines.append(line)

content = '\n'.join(new_lines)

# GRUPA 1 uses a two-column table, unlike the three-column internet/Homebrew
# sections. Restrict replacement to that section so App Store IDs in GRUPA 2
# can never be mistaken for version numbers.
group1_match = re.search(r'(^## GRUPA 1.*?)(?=^## GRUPA 2)', content, re.DOTALL | re.MULTILINE)
if group1_match:
    group1 = group1_match.group(1)
    refreshed = []
    for line in group1.split('\n'):
        match = re.match(r'^(\| )([^|]+?)( \| )([^|]+?)( \|)\s*$', line)
        if match:
            name = match.group(2).strip()
            new_ver = installed_apps_after.get(name)
            if new_ver not in (None, '', '?') and match.group(4).strip() != new_ver:
                line = f"{match.group(1)}{name}{match.group(3)}{new_ver}{match.group(5)}"
                updated_count += 1
        refreshed.append(line)
    content = content[:group1_match.start(1)] + '\n'.join(refreshed) + content[group1_match.end(1):]

# Update the dates in APPLICATIONS.md
today = datetime.now().strftime('%Y-%m-%d')
content = re.sub(r'(\*\*Data analizy:\*\* )\d{4}-\d{2}-\d{2}', r'\g<1>' + today, content)
content = re.sub(r'(\*Zaktualizowano: )\d{4}-\d{2}-\d{2}', r'\g<1>' + today, content)

# ── Auto-update macOS version strings if OS was upgraded ─────
import subprocess as _sp
try:
    _pv = _sp.run(['sw_vers', '-productVersion'], capture_output=True, text=True).stdout.strip()
    _bv = _sp.run(['sw_vers', '-buildVersion'], capture_output=True, text=True).stdout.strip()
    if _pv:
        _mac_user = os.environ.get('USER', 'user')
        try:
            _major = int(_pv.split('.', 1)[0])
        except (ValueError, IndexError):
            _major = 0
        _codenames = {13: 'Ventura', 14: 'Sonoma', 15: 'Sequoia', 26: 'Tahoe'}
        _codename = _codenames.get(_major, '')
        _os_label = f'macOS {_pv}' + (f' {_codename}' if _codename else '')
        content = re.sub(
            r'^# 📱 ZAINSTALOWANE APLIKACJE — MacBook .*$',
            f'# 📱 ZAINSTALOWANE APLIKACJE — MacBook {_mac_user} ({_os_label})',
            content, count=1, flags=re.MULTILINE)
        content = re.sub(
            r'(\*\*System:\*\* macOS )[\d.]+(?: [A-Za-z]+)? \(Build [A-Z0-9]+\)',
            r'\g<1>' + _os_label + f' (Build {_bv})', content)
        content = re.sub(
            r'(\| macOS )[\d.]+(?: [A-Za-z]+)?( arm64)',
            lambda m: m.group(1) + _pv + (f' {_codename}' if _codename else '') + m.group(2), content)
except Exception:
    pass

# Add new brew formulae to APPLICATIONS.md if any (in case they weren't in prescan)
# POPRAWKA: wstawiamy NA KOŃCU tabeli 4a przy użyciu regex (bez blank line gap)
if formula_new:
    new_rows = ''
    for name in sorted(formula_new.keys()):
        ver = formula_new[name]
        if not re.search(r'\|\s*' + re.escape(name) + r'\s*\|', content):
            new_rows += f"| {name} | {ver} | 🆕 NOWY — opis do uzupełnienia |\n"
    if new_rows:
        pattern_4a = r'((?:\| [^\n]+\|\n)+)(\n+### 4b\.)'
        m4a = re.search(pattern_4a, content)
        if m4a:
            insert_pos = m4a.start(2)
            content = content[:insert_pos] + new_rows + content[insert_pos:]
            print(f"  ✅ Dodano nowych formulae do APPLICATIONS.md (sekcja 4a)")
        else:
            marker = "### 4b. Formulae"
            if marker in content:
                content = content.replace(marker, new_rows + "\n" + marker)

if cask_new:
    new_rows = ''
    for name in sorted(cask_new.keys()):
        ver = cask_new[name]
        if not re.search(r'\|\s*' + re.escape(name) + r'\s*\|', content):
            new_rows += f"| {name} | {ver} | 🆕 NOWY — opis do uzupełnienia |\n"
    if new_rows:
        pattern_4c = r'(### 4c\..*?)((?:\| [^\n]+\|\n)+)(\n+>|\n+##)'
        m4c = re.search(pattern_4c, content, re.DOTALL)
        if m4c:
            insert_pos = m4c.start(3)
            content = content[:insert_pos] + new_rows + content[insert_pos:]
            print(f"  ✅ Dodano nowych casks do APPLICATIONS.md (sekcja 4c)")

if npm_cli_new:
    new_rows = ''
    for name in sorted(npm_cli_new.keys()):
        ver = npm_cli_new[name]
        if not re.search(r'\|\s*' + re.escape(name) + r'\s*\|', content):
            new_rows += f"| {name} | {ver} | 🆕 NOWY — aktualizowany przez npm/native/self-update |\n"
    if new_rows:
        pattern_4d = r'(### 4d\..*?)((?:\| [^\n]+\|\n)+)(\n+>|\n+##|\Z)'
        m4d = re.search(pattern_4d, content, re.DOTALL)
        if m4d:
            insert_pos = m4d.start(3)
            content = content[:insert_pos] + new_rows + content[insert_pos:]
            print(f"  ✅ Dodano nowych CLI do APPLICATIONS.md (sekcja 4d)")

atomic_write_text(programy_md_path, content)

print(f"  ✅ APPLICATIONS.md zaktualizowany (zmieniono {updated_count} wersji)")

if os.environ.get('MAC_UPDATE_INVENTORY_ONLY') == '1':
    print("  ✅ Tryb inwentarza: pominięto wpis do UPDATES.md")
    sys.exit(0)

# ── Build UPDATES.md history entry ──────────────────────
print("\n  Aktualizuję historię sesji w UPDATES.md...")

now = datetime.now().strftime('%Y-%m-%d %H:%M')
total_upgrades = len(formula_upgrades) + len(cask_upgrades) + len(internet_upgrades) + len(npm_cli_upgrades)

history_lines = [
    f"\n### 🔄 Sesja aktualizacji: {now}\n",
    f"| Krok | Wynik |",
    f"|------|-------|",
    f"| 🍎 System macOS | {result_system} |",
    f"| 🛍️ App Store | {result_appstore} |",
    f"| 🌐 Aplikacje z Internetu | {result_internet} |",
    f"| 🧰 Native CLI + npm | {result_npmcli} |",
    f"| 🍺 Homebrew | {result_brew} |",
    f"",
]

if formula_upgrades or cask_upgrades:
    history_lines.append("**🍺 Homebrew — zaktualizowane pakiety:**\n")
    history_lines.append("| Pakiet | Poprzednia wersja | Nowa wersja |")
    history_lines.append("|--------|-------------------|-------------|")
    for name, (old, new) in sorted(formula_upgrades.items()):
        history_lines.append(f"| `{name}` | {old} | {new} |")
    for name, (old, new) in sorted(cask_upgrades.items()):
        history_lines.append(f"| `{name}` *(cask)* | {old} | {new} |")
    history_lines.append("")

if formula_new or cask_new:
    history_lines.append("**🆕 Nowe pakiety Homebrew w tej sesji:**")
    for name, ver in sorted(formula_new.items()):
        history_lines.append(f"- `{name}` {ver}")
    for name, ver in sorted(cask_new.items()):
        history_lines.append(f"- `{name}` {ver} *(cask)*")
    history_lines.append("")

if internet_upgrades:
    history_lines.append("**🌐 Aplikacje internetowe — wykryte zmiany wersji:**\n")
    history_lines.append("| Aplikacja | Poprzednia wersja | Nowa wersja |")
    history_lines.append("|-----------|-------------------|-------------|")
    for name, (old, new) in sorted(internet_upgrades.items()):
        history_lines.append(f"| {name} | {old} | {new} |")
    history_lines.append("")

if npm_cli_upgrades:
    history_lines.append("**🧰 Native CLI + npm — wykryte zmiany wersji:**\n")
    history_lines.append("| Narzędzie | Poprzednia wersja | Nowa wersja |")
    history_lines.append("|-----------|-------------------|-------------|")
    for name, (old, new) in sorted(npm_cli_upgrades.items()):
        history_lines.append(f"| `{name}` | {old} | {new} |")
    history_lines.append("")

if npm_cli_new:
    history_lines.append("**🆕 Nowe natywne CLI / npm global w tej sesji:**")
    for name, ver in sorted(npm_cli_new.items()):
        history_lines.append(f"- `{name}` {ver}")
    history_lines.append("")

# Check for new apps from pre-scan
new_apps_file = os.path.join(session_dir, 'new_apps.txt')
if os.path.exists(new_apps_file):
    with open(new_apps_file) as f:
        new_apps = [l.strip() for l in f if l.strip()]
    if new_apps:
        history_lines.append("**🔍 Nowe aplikacje wykryte i dodane do APPLICATIONS.md:**")
        for app in new_apps:
            history_lines.append(f"- {app}")
        history_lines.append("")

# Check for removed apps from pre-scan
removed_apps_file = os.path.join(session_dir, 'removed_apps.txt')
if os.path.exists(removed_apps_file):
    with open(removed_apps_file) as f:
        removed_apps = [l.strip() for l in f if l.strip()]
    if removed_apps:
        history_lines.append("**🗑️ Aplikacje do usunięcia z listy (odinstalowane):**")
        for app in removed_apps:
            history_lines.append(f"- {app} *(usunięto automatycznie z APPLICATIONS.md)*")
        history_lines.append("")

if total_upgrades == 0 and not formula_new and not cask_new and not npm_cli_new:
    history_lines.append("*Brak zaktualizowanych pakietów w tej sesji.*\n")

history_entry = '\n'.join(history_lines) + '\n'

# Update UPDATES.md
try:
    with open(aktualizacje_md_path, 'r') as f:
        ak_content = f.read()
except FileNotFoundError:
    ak_content = ''

HISTORY_MARKER = "## 📅 Historia sesji aktualizacji"
if HISTORY_MARKER not in ak_content:
    # Add history section at the end of the file
    ak_content = ak_content.rstrip() + f"\n\n---\n\n{HISTORY_MARKER}\n{history_entry}"
else:
    # Prepend newest entry right after the marker (most recent at top)
    ak_content = ak_content.replace(
        HISTORY_MARKER + '\n',
        HISTORY_MARKER + '\n' + history_entry
    )

# Update the date in UPDATES.md header
ak_content = re.sub(r'(\*\*Data:\*\* )\d{4}-\d{2}-\d{2}', r'\g<1>' + today, ak_content)
ak_content = re.sub(r'(\*Zaktualizowano: )\d{4}-\d{2}-\d{2}', r'\g<1>' + today, ak_content)
# Auto-update macOS version strings in UPDATES.md
if '_pv' in vars() and _pv:
    try:
        _major_updates = int(_pv.split('.', 1)[0])
    except (ValueError, IndexError):
        _major_updates = 0
    _updates_codename = {13: 'Ventura', 14: 'Sonoma', 15: 'Sequoia', 26: 'Tahoe'}.get(_major_updates, '')
    ak_content = re.sub(
        r'(\*\*System:\*\* macOS )[\d.]+(?: Ventura| Sonoma| Sequoia| Tahoe)?',
        lambda m: m.group(1) + _pv + (f' {_updates_codename}' if _updates_codename else ''),
        ak_content)
    ak_content = re.sub(
        r'(\| macOS )[\d.]+(?: Ventura| Sonoma| Sequoia| Tahoe)?( arm64)',
        lambda m: m.group(1) + _pv + (f' {_updates_codename}' if _updates_codename else '') + m.group(2),
        ak_content)

atomic_write_text(aktualizacje_md_path, ak_content)

print(f"  ✅ UPDATES.md zaktualizowany")
print(f"")
print(f"  📊 Podsumowanie zmian:")
print(f"     Formulae Homebrew zaktualizowane: {len(formula_upgrades)}")
print(f"     Casks Homebrew zaktualizowane:    {len(cask_upgrades)}")
print(f"     Nowe pakiety Homebrew:            {len(formula_new) + len(cask_new)}")
print(f"     Native CLI + npm:                 {len(npm_cli_upgrades) + len(npm_cli_new)}")
print(f"     Zmiany wersji aplikacji inet.:    {len(internet_upgrades)}")
print(f"     Łącznie zmiany wersji:            {updated_count}")

PYEOF

if python3 "$SESSION_DIR/postupdate.py" \
    "$SCRIPT_DIR" \
    "$SESSION_DIR" \
    "$RESULT_SYSTEM" \
    "$RESULT_APPSTORE" \
    "$RESULT_INTERNET" \
    "$RESULT_NPMCLI" \
    "$RESULT_BREW"; then
    RESULT_MD="$L_STATUS_OK completed"
else
    RESULT_MD="$L_STATUS_ERROR"
    OVERALL_EXIT=1
fi
fi
fi

# ============================================================
# FINAL MUTATING STEP: macOS system update
# ============================================================
if [ "$SYSTEM_DEFERRED" -eq 1 ]; then
    ui_master_progress 6 6
    ui_step_header 6 6 "$L_SYSTEM_UPDATE_TITLE"
    if mac_update_dry_run_msg "update_system.sh (final step)"; then
        RESULT_SYSTEM="[DRY-RUN] skipped"
    elif [ "$OVERALL_EXIT" -ne 0 ]; then
        RESULT_SYSTEM="⏭️ skipped because an earlier update step failed"
        print_warn "Skipping the final macOS update because an earlier step failed; fix it and rerun."
    elif mac_update_run_child "update_system.sh" "update_system.sh (final step)"; then
        RESULT_SYSTEM="$L_STATUS_OK completed"
    else
        RESULT_SYSTEM="$L_STATUS_ERROR"
        OVERALL_EXIT=1
    fi

    # Postupdate runs before the reboot-capable system step. If softwareupdate
    # returns normally, replace the pending marker in the newest history entry.
    if [ -f "$SCRIPT_DIR/UPDATES.md" ] && [ "$RESULT_MD" = "$L_STATUS_OK completed" ]; then
        if ! python3 - "$SCRIPT_DIR/UPDATES.md" "$SYSTEM_HISTORY_PENDING" "$RESULT_SYSTEM" <<'PYEOF'
import os
import sys
import tempfile

path, pending, result = sys.argv[1:4]
with open(path, encoding='utf-8') as handle:
    content = handle.read()
old = f"| 🍎 System macOS | {pending} |"
new = f"| 🍎 System macOS | {result} |"
if old in content:
    content = content.replace(old, new, 1)
    fd, temp_path = tempfile.mkstemp(prefix='.mac-update.', dir=os.path.dirname(path), text=True)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
PYEOF
        then
            print_error "Could not finalize the macOS result in UPDATES.md."
            OVERALL_EXIT=1
        fi
    fi
fi

ui_master_progress 6 6

# ============================================================
# Final summary
# ============================================================
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
MINUTES=$((DURATION / 60))
# Use DURATION_SECS instead of SECONDS — SECONDS is a bash built-in that
# auto-increments and would be clobbered by this assignment on some shells.
DURATION_SECS=$((DURATION % 60))

echo ""
_summary_msg="$L_UPDATE_ALL_SUCCESS"
[ "$OVERALL_EXIT" -ne 0 ] && _summary_msg="UPDATE COMPLETED WITH ERRORS"
ui_print_box "$_summary_msg"
echo ""
echo -e "  0. Scan new apps:           $RESULT_SCAN"
echo -e "  1. App Store:               $RESULT_APPSTORE"
echo -e "  2. Native CLI + npm:        $RESULT_NPMCLI"
echo -e "  3. Homebrew:                $RESULT_BREW"
echo -e "  4. Internet apps:           $RESULT_INTERNET"
echo -e "  5. $L_ALL_UPDATE_APPS_LABEL $RESULT_MD"
echo -e "  6. macOS System:            $RESULT_SYSTEM"
echo ""
echo -e "  Duration: ${MINUTES} min ${DURATION_SECS} sek"
echo ""
if [ "$OVERALL_EXIT" -eq 0 ]; then
    print_ok "$L_UPDATE_ALL_SUCCESS"
else
    print_error "One or more update steps failed. Review the step summary above and session logs before rerunning."
fi
if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_info "DRY-RUN: no applications, inventory, or history files were changed."
elif [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" = "1" ]; then
    print_info "Inventory refreshed: APPLICATIONS.md (UPDATES.md history intentionally unchanged)."
else
    print_info "$L_ALL_FILES_UPDATED_MSG"
fi
if [ "${MAC_UPDATE_INVENTORY_ONLY:-0}" != "1" ]; then
    print_info "$L_ALL_RESTART_CHECK_MSG"
fi
echo ""

export MAC_UPDATE_OVERALL_EXIT="$OVERALL_EXIT"
export MAC_UPDATE_DURATION_SEC="$DURATION"
export MAC_UPDATE_RESULT_SCAN="$RESULT_SCAN"
export MAC_UPDATE_RESULT_SYSTEM="$RESULT_SYSTEM"
export MAC_UPDATE_RESULT_APPSTORE="$RESULT_APPSTORE"
export MAC_UPDATE_RESULT_INTERNET="$RESULT_INTERNET"
export MAC_UPDATE_RESULT_NPMCLI="$RESULT_NPMCLI"
export MAC_UPDATE_RESULT_BREW="$RESULT_BREW"
export MAC_UPDATE_RESULT_MD="$RESULT_MD"
export MAC_UPDATE_LOG_FILE="$LOG_FILE"

_ui_summary=$(cat <<EOS
0. Scan:      $RESULT_SCAN
1. App Store: $RESULT_APPSTORE
2. npm/CLI:   $RESULT_NPMCLI
3. Homebrew:  $RESULT_BREW
4. Internet:  $RESULT_INTERNET
5. Inventory: $RESULT_MD
6. System:    $RESULT_SYSTEM
Duration:     ${MINUTES}m ${DURATION_SECS}s
EOS
)
ui_summary_table "$_ui_summary"

exit "$OVERALL_EXIT"
