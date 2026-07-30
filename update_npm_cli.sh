#!/usr/bin/env bash
# ============================================================
# SKRYPT 3: Aktualizacja natywnych runtime'ów i CLI przez npm
# ============================================================
# Autor: mk | Data: 2026-04-18
set -o pipefail

# Kompatybilność: bash 3.2+ (macOS domyślny shell)
# Opis:
#   - Instaluje/aktualizuje Node.js latest przez `n` (bez Homebrew)
#   - Instaluje/aktualizuje npm, pnpm i wybrane CLI przez `npm`
#   - Instaluje/aktualizuje Bun natywnie (bez Homebrew)
#   - Aktualizuje CLI z własnym updaterem, np. Agy (`agy update`)
#   - Migruje wybrane CLI z Homebrew do npm/native
#   - Zapisuje snapshoty wersji przed i po aktualizacji
# ============================================================

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFEST_PATH="$SCRIPT_DIR/config/npm_global_clis.txt"
BUN_VERSION_PATH="$SCRIPT_DIR/config/bun_version.txt"

. "$SCRIPT_DIR/lib/platform.sh"
mac_update_require_supported_platform || exit 1

. "$SCRIPT_DIR/lib/cli.sh"
. "$SCRIPT_DIR/lib/ui.sh"
. "$SCRIPT_DIR/lib/severity.sh"
mac_update_severity_init

TOOLCHAIN_HOME="${MAC_UPDATE_TOOLCHAIN_HOME:-$HOME/.local/share/mac-update}"
N_PREFIX="$TOOLCHAIN_HOME/node"
NPM_GLOBAL_PREFIX="$TOOLCHAIN_HOME/npm-global"
NPM_GLOBAL_BIN="$NPM_GLOBAL_PREFIX/bin"
LOCAL_BIN="$HOME/.local/bin"

cleanup_npm_cli() {
    rm -rf "${TMPDIR:-/tmp}"/mac_update_node.* 2>/dev/null || true
    rm -rf "$TOOLCHAIN_HOME"/node.staging.* 2>/dev/null || true
}
BUN_HOME="${BUN_INSTALL:-$HOME/.bun}"
BUN_BIN="$BUN_HOME/bin"
NPMRC_PATH="$HOME/.npmrc"

print_header() { ui_print_header "$1"; }

print_ok()   { echo -e "  ${GREEN}✅ $1${NC}"; }
print_info() { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
print_warn() { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
print_error(){ echo -e "  ${RED}❌ $1${NC}"; }

sanitize_npm_stderr() {
    awk '
        {
            lower = tolower($0)
            if (lower ~ /(_authtoken|_auth[[:space:]]*[:=]|authorization[[:space:]]*[:=]|npm_token[[:space:]]*[:=]|password[[:space:]]*[:=]|token[[:space:]]*[:=])/) {
                print "[REDACTED sensitive diagnostic line]"
                next
            }
            if ($0 ~ /https?:\/\/[^[:space:]\/@]+@/) {
                print "[REDACTED URL credentials]"
                next
            }
            print substr($0, 1, 500)
        }
    '
}

run_quiet_with_error_log() {
    local label="$1"
    shift
    local log_root="${TMPDIR:-/tmp}"
    local stderr_file
    local command_exit

    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
        log_root="$MAC_UPDATE_SESSION_DIR"
    fi
    stderr_file="$(mktemp "$log_root/npm_cli_stderr.XXXXXX")" || return 1

    "$@" </dev/null >/dev/null 2>"$stderr_file"
    command_exit=$?
    if [ "$command_exit" -ne 0 ]; then
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -d "$MAC_UPDATE_SESSION_DIR" ]; then
            {
                printf '=== %s (exit=%s) ===\n' "$label" "$command_exit"
                # Keep diagnostics useful but bounded: npm can emit thousands of lines.
                tail -n 30 "$stderr_file" | sanitize_npm_stderr
                echo ""
            } >> "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log" 2>/dev/null || true
        else
            printf '  Diagnostic (%s):\n' "$label" >&2
            tail -n 12 "$stderr_file" | sanitize_npm_stderr >&2
        fi
    fi
    rm -f "$stderr_file" 2>/dev/null || true
    return "$command_exit"
}

find_shell_profile() {
    local default_shell
    default_shell="$(dscl . -read /Users/"$USER" UserShell 2>/dev/null | awk '{print $2}' || echo "$SHELL")"
    if echo "$default_shell" | grep -q "zsh"; then
        echo "$HOME/.zshrc"
    elif echo "$default_shell" | grep -q "bash"; then
        echo "$HOME/.bash_profile"
    else
        echo "$HOME/.zshrc"
    fi
}

ensure_line_in_file() {
    local file_path="$1"
    local line="$2"
    touch "$file_path" || return 1
    if ! grep -Fqx "$line" "$file_path" 2>/dev/null; then
        printf '%s\n' "$line" >> "$file_path"
    fi
}
remove_line_from_file() {
    local file_path="$1"
    local line="$2"
    [ -f "$file_path" ] || return 0
    local tmpfile
    tmpfile="$(mktemp "${TMPDIR:-/tmp}/mac_update_profile.XXXXXX")" || return 1
    grep -Fvx "$line" "$file_path" > "$tmpfile" 2>/dev/null || true
    if ! mv "$tmpfile" "$file_path"; then
        rm -f "$tmpfile"
        return 1
    fi
}

remove_npmrc_prefix() {
    [ -f "$NPMRC_PATH" ] || return 0
    local tmpfile
    tmpfile="$(mktemp "${TMPDIR:-/tmp}/mac_update_npmrc.XXXXXX")" || return 1
    # grep -Ev exits 1 when *all* lines match the filter (i.e., the file would become empty);
    # treat that as success so the empty result still replaces the original.
    grep -Ev '^(prefix|globalconfig) *=' "$NPMRC_PATH" > "$tmpfile" 2>/dev/null || true
    if ! mv "$tmpfile" "$NPMRC_PATH"; then
        rm -f "$tmpfile"
        return 1
    fi
    [ -s "$NPMRC_PATH" ] || rm -f "$NPMRC_PATH"
}

ensure_toolchain_paths() {
    local profile

    mkdir -p "$TOOLCHAIN_HOME" "$N_PREFIX" "$NPM_GLOBAL_PREFIX" "$NPM_GLOBAL_BIN" "$BUN_HOME" "$LOCAL_BIN" || return 1
    remove_npmrc_prefix || return 1

    export N_PREFIX
    export BUN_INSTALL="$BUN_HOME"
    export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true

    profile="$(find_shell_profile)"
    remove_line_from_file "$profile" "# Managed by macOS Updates — native CLI toolchain" || return 1
    remove_line_from_file "$profile" "export N_PREFIX=\"$N_PREFIX\"" || return 1
    remove_line_from_file "$profile" "export PATH=\"$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:\$PATH\"" || return 1
    remove_line_from_file "$profile" "export PATH=\"$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:\$PATH\"" || return 1
    remove_line_from_file "$profile" "# Managed by macOS Updates — Bun only (nvm owns Node/npm)" || return 1
    remove_line_from_file "$profile" "export BUN_INSTALL=\"$BUN_HOME\"" || return 1
    remove_line_from_file "$profile" "export PATH=\"$BUN_BIN:\$PATH\"" || return 1
    remove_line_from_file "$profile" "export PATH=\"$LOCAL_BIN:$BUN_BIN:\$PATH\"" || return 1
    remove_line_from_file "$profile" "[ -n \"\$NVM_BIN\" ] && export PATH=\"\$NVM_BIN:\$PATH\"" || return 1
    ensure_line_in_file "$profile" "" || return 1
    if [ -s "$HOME/.nvm/nvm.sh" ]; then
        ensure_line_in_file "$profile" "# Managed by macOS Updates — Bun only (nvm owns Node/npm)" || return 1
        ensure_line_in_file "$profile" "export BUN_INSTALL=\"$BUN_HOME\"" || return 1
        ensure_line_in_file "$profile" "export PATH=\"$LOCAL_BIN:$BUN_BIN:\$PATH\"" || return 1
        if [ -n "$NVM_BIN" ]; then
            ensure_line_in_file "$profile" "[ -n \"\$NVM_BIN\" ] && export PATH=\"\$NVM_BIN:\$PATH\"" || return 1
        fi
        return 0
    fi
    ensure_line_in_file "$profile" "# Managed by macOS Updates — native CLI toolchain" || return 1
    ensure_line_in_file "$profile" "export N_PREFIX=\"$N_PREFIX\"" || return 1
    ensure_line_in_file "$profile" "export BUN_INSTALL=\"$BUN_HOME\"" || return 1
    ensure_line_in_file "$profile" "export PATH=\"$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:\$PATH\"" || return 1
}

normalize_semver() {
    printf '%s' "$1" | sed 's/^v//; s/ .*//'
}

semver_is_newer() {
    awk -v lhs="$(normalize_semver "$1")" -v rhs="$(normalize_semver "$2")" '
        BEGIN {
            sub(/[-+].*$/, "", lhs)
            sub(/[-+].*$/, "", rhs)
            lhs_n = split(lhs, lhs_parts, ".")
            rhs_n = split(rhs, rhs_parts, ".")
            max_n = lhs_n > rhs_n ? lhs_n : rhs_n
            for (i = 1; i <= max_n; i++) {
                left = lhs_parts[i] + 0
                right = rhs_parts[i] + 0
                if (left > right) exit 0
                if (left < right) exit 1
            }
            exit 1
        }
    '
}

detect_command_version() {
    local display_name="$1"
    local command_path="$2"
    local version=""

    case "$display_name" in
        node)
            version="$("$command_path" -v </dev/null 2>/dev/null | head -1)"
            ;;
        npm|pnpm|opencode-cli|bun)
            version="$("$command_path" --version </dev/null 2>/dev/null | head -1)"
            ;;
        claude-code)
            version="$("$command_path" -v </dev/null 2>/dev/null | head -1)"
            version="$(printf '%s' "$version" | sed 's/ .*//')"
            ;;
        codex-cli)
            version="$("$command_path" --version </dev/null 2>/dev/null | head -1 | awk '{print $NF}')"
            ;;
        *)
            version="$("$command_path" --version </dev/null 2>/dev/null | head -1 | awk '{print $NF}')"
            ;;
    esac

    normalize_semver "${version:-?}"
}

resolve_command_path() {
    local command_name="$1"

    case "$command_name" in
        node|npx)
            if [ -x "$N_PREFIX/bin/$command_name" ]; then
                echo "$N_PREFIX/bin/$command_name"
                return 0
            fi
            ;;
        npm|pnpm|claude|codex|opencode)
            if [ -x "$NPM_GLOBAL_BIN/$command_name" ]; then
                echo "$NPM_GLOBAL_BIN/$command_name"
                return 0
            fi
            ;;
        bun)
            if [ -x "$BUN_BIN/bun" ]; then
                echo "$BUN_BIN/bun"
                return 0
            fi
            ;;
        agy)
            if [ -x "$LOCAL_BIN/agy" ]; then
                echo "$LOCAL_BIN/agy"
                return 0
            fi
            ;;
    esac

    if command -v "$command_name" >/dev/null 2>&1; then
        command -v "$command_name"
        return 0
    fi

    return 1
}

run_with_timeout() {
    local seconds="$1"
    local command_pid command_exit elapsed grace
    shift
    if command -v timeout >/dev/null 2>&1; then
        timeout "$seconds" "$@"
    elif command -v gtimeout >/dev/null 2>&1; then
        gtimeout "$seconds" "$@"
    else
        # Stock macOS has neither GNU timeout nor gtimeout. Run the command in
        # the background and supervise it with a Bash 3.2 polling watchdog.
        "$@" &
        command_pid=$!
        elapsed=0
        while kill -0 "$command_pid" 2>/dev/null; do
            if [ "$elapsed" -ge "$seconds" ]; then
                kill -TERM "$command_pid" 2>/dev/null || true
                grace=0
                while kill -0 "$command_pid" 2>/dev/null && [ "$grace" -lt 5 ]; do
                    sleep 1
                    grace=$((grace + 1))
                done
                kill -KILL "$command_pid" 2>/dev/null || true
                wait "$command_pid" 2>/dev/null || true
                return 124
            fi
            sleep 1
            elapsed=$((elapsed + 1))
        done
        wait "$command_pid"
        command_exit=$?
        return "$command_exit"
    fi
}

write_cli_snapshot() {
    local outfile="$1"
    : > "$outfile" || return 1

    while IFS='|' read -r display_name package_name method _brew_formula command_name; do
        local command_path
        local version

        case "$display_name" in
            ""|\#*) continue ;;
        esac

        if command_path="$(resolve_command_path "$command_name")"; then
            version="$(detect_command_version "$display_name" "$command_path")"
            if ! printf '%s|%s|%s|%s|%s\n' \
                "$display_name" \
                "$package_name" \
                "${version:-?}" \
                "$command_name" \
                "$command_path" >> "$outfile"; then
                return 1
            fi
        fi
    done < "$MANIFEST_PATH"
    return 0
}

detect_latest_node_version() {
    local json_body ver
    json_body="$(curl -fsSL --max-time 60 --retry 3 --retry-delay 2 https://nodejs.org/dist/index.json 2>/dev/null)"
    if [ -n "$json_body" ]; then
        ver="$(echo "$json_body" | python3 -c 'import json,sys; arr=json.load(sys.stdin); print(arr[0]["version"])' 2>/dev/null)"
        if [ -z "$ver" ]; then
            ver="$(echo "$json_body" | awk -F'"' '/"version":/ {print $4; exit}')"
        fi
        if [ -n "$ver" ]; then
            echo "$ver"
            return 0
        fi
    fi
    SOFT_FAIL=1
    return 1
}

install_node_tarball() {
    local latest_node="$1"
    local archive_arch
    local archive_name
    local archive_url
    local shasums_url
    local tmpdir
    local extracted_dir
    local staging_dir
    local backup_dir

    if [ -z "$latest_node" ]; then
        print_error "Nie udało się ustalić najnowszej wersji Node.js"
        return 1
    fi

    case "$(uname -m)" in
        arm64)  archive_arch="arm64" ;;
        x86_64) archive_arch="x64" ;;
        *)
            print_error "Nieobsługiwana architektura dla bootstrapu Node.js: $(uname -m)"
            return 1
            ;;
    esac

    archive_name="node-${latest_node}-darwin-${archive_arch}.tar.gz"
    archive_url="https://nodejs.org/dist/${latest_node}/${archive_name}"
    shasums_url="https://nodejs.org/dist/${latest_node}/SHASUMS256.txt"
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_node.XXXXXX")" || return 1

    print_info "Bootstrapuję Node.js bez npm z oficjalnego archiwum..."
    if ! curl -fsSL --max-time 180 --retry 3 --retry-delay 2 -o "$tmpdir/$archive_name" "$archive_url"; then
        rm -rf "$tmpdir"
        return 1
    fi

    if ! curl -fsSL --max-time 60 --retry 3 --retry-delay 2 -o "$tmpdir/SHASUMS256.txt" "$shasums_url"; then
        rm -rf "$tmpdir"
        return 1
    fi
    if ! grep "  ${archive_name}\$" "$tmpdir/SHASUMS256.txt" > "$tmpdir/node.sha256"; then
        rm -rf "$tmpdir"
        return 1
    fi
    if ! (cd "$tmpdir" && shasum -a 256 -c node.sha256 >/dev/null 2>&1); then
        print_error "Checksum Node.js nie zgadza się dla $archive_name"
        rm -rf "$tmpdir"
        return 1
    fi

    if ! tar -xzf "$tmpdir/$archive_name" -C "$tmpdir"; then
        rm -rf "$tmpdir"
        return 1
    fi

    extracted_dir="$tmpdir/node-${latest_node}-darwin-${archive_arch}"
    mkdir -p "$N_PREFIX"
    staging_dir="$(mktemp -d "$TOOLCHAIN_HOME/node.staging.XXXXXX")" || {
        rm -rf "$tmpdir"
        return 1
    }
    if ! cp -R "$extracted_dir"/. "$staging_dir"/; then
        rm -rf "$tmpdir" "$staging_dir"
        return 1
    fi
    backup_dir="$TOOLCHAIN_HOME/node.backup.$(date +%Y%m%d%H%M%S).$$"
    if [ -d "$N_PREFIX" ]; then
        if ! mv "$N_PREFIX" "$backup_dir"; then
            rm -rf "$tmpdir" "$staging_dir"
            return 1
        fi
    fi
    if ! mv "$staging_dir" "$N_PREFIX"; then
        [ -d "$backup_dir" ] && mv "$backup_dir" "$N_PREFIX" 2>/dev/null || true
        rm -rf "$tmpdir" "$staging_dir"
        return 1
    fi
    rm -rf "$backup_dir" 2>/dev/null || true
    rm -rf "$tmpdir"
    export PATH="$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true
}

bootstrap_npm() {
    if [ -x "$N_PREFIX/bin/npm" ]; then
        echo "$N_PREFIX/bin/npm"
    elif [ -x "$NPM_GLOBAL_BIN/npm" ]; then
        echo "$NPM_GLOBAL_BIN/npm"
    elif command -v npm >/dev/null 2>&1; then
        command -v npm
    else
        echo ""
    fi
}

ensure_n_helper() {
    local npm_bin
    npm_bin="$(bootstrap_npm)"
    if [ -z "$npm_bin" ]; then
        print_error "Brak bootstrap npm — nie mogę zainstalować narzędzia n"
        return 1
    fi

    run_quiet_with_error_log \
        "npm install n@latest" \
        "$npm_bin" install -g --prefix "$NPM_GLOBAL_PREFIX" n@latest
}

ensure_latest_node() {
    local latest_node
    local current_node=""
    local n_bin="$NPM_GLOBAL_BIN/n"

    latest_node="$(detect_latest_node_version)"
    if [ -z "$latest_node" ]; then
        SOFT_FAIL=1
    fi
    current_node="$([ -x "$N_PREFIX/bin/node" ] && "$N_PREFIX/bin/node" -v 2>/dev/null || true)"
    if [ -z "$current_node" ] && command -v node >/dev/null 2>&1; then
        current_node="$(node -v 2>/dev/null || true)"
    fi

    if ! ensure_n_helper; then
        if ! install_node_tarball "$latest_node"; then
            print_error "Nie udało się zbootstrapować Node.js"
            return 1
        fi
        if ! ensure_n_helper; then
            return 1
        fi
    fi

    if [ ! -x "$N_PREFIX/bin/node" ] || [ "$(normalize_semver "$current_node")" != "$(normalize_semver "$latest_node")" ]; then
        print_info "Aktualizuję Node.js do ${latest_node:-latest} przez n (bez Homebrew)..."
        if N_PREFIX="$N_PREFIX" "$n_bin" latest; then
            export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
            hash -r 2>/dev/null || true
            print_ok "Node.js aktywny: $("$N_PREFIX/bin/node" -v 2>/dev/null)"
        else
            print_error "Aktualizacja Node.js przez n nie powiodła się"
            return 1
        fi
    else
        print_ok "Node.js już jest aktualny: $(normalize_semver "$current_node")"
    fi
}

read_bun_version() {
    local ver
    if [ -f "$BUN_VERSION_PATH" ]; then
        ver="$(sed -e 's/#.*//' -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//' "$BUN_VERSION_PATH" | head -1)"
        if [ -n "$ver" ]; then
            echo "$ver"
            return 0
        fi
    fi
    return 1
}

install_bun_tarball() {
    local bun_version="$1"
    local archive_arch archive_name tag archive_url shasums_url tmpdir
    local bun_binary staging_bin backup_bin installed_version

    case "$(uname -m)" in
        arm64)  archive_arch="aarch64" ;;
        x86_64) archive_arch="x64" ;;
        *)
            print_error "Nieobsługiwana architektura dla Bun: $(uname -m)"
            return 1
            ;;
    esac

    tag="bun-v${bun_version}"
    archive_name="bun-darwin-${archive_arch}.zip"
    archive_url="https://github.com/oven-sh/bun/releases/download/${tag}/${archive_name}"
    shasums_url="https://github.com/oven-sh/bun/releases/download/${tag}/SHASUMS256.txt"
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_bun.XXXXXX")" || return 1

    print_info "Instaluję Bun ${bun_version} z oficjalnego archiwum GitHub..."
    if ! curl -fsSL --max-time 180 --retry 3 --retry-delay 2 -o "$tmpdir/$archive_name" "$archive_url"; then
        rm -rf "$tmpdir"
        return 1
    fi
    if ! curl -fsSL --max-time 60 --retry 3 --retry-delay 2 -o "$tmpdir/SHASUMS256.txt" "$shasums_url"; then
        rm -rf "$tmpdir"
        return 1
    fi
    if ! grep "  ${archive_name}$" "$tmpdir/SHASUMS256.txt" > "$tmpdir/bun.sha256"; then
        rm -rf "$tmpdir"
        return 1
    fi
    if ! (cd "$tmpdir" && shasum -a 256 -c bun.sha256 >/dev/null 2>&1); then
        print_error "Checksum Bun nie zgadza się dla $archive_name"
        rm -rf "$tmpdir"
        return 1
    fi
    if ! unzip -q -o "$tmpdir/$archive_name" -d "$tmpdir"; then
        rm -rf "$tmpdir"
        return 1
    fi
    bun_binary="$tmpdir/bun-darwin-${archive_arch}/bun"
    if [ ! -f "$bun_binary" ]; then
        rm -rf "$tmpdir"
        return 1
    fi
    chmod +x "$bun_binary" 2>/dev/null || true

    mkdir -p "$BUN_BIN"
    staging_bin="$(mktemp "${TMPDIR:-/tmp}/mac_update_bun_bin.XXXXXX")" || {
        rm -rf "$tmpdir"
        return 1
    }
    if ! cp "$bun_binary" "$staging_bin"; then
        rm -rf "$tmpdir" "$staging_bin"
        return 1
    fi
    chmod +x "$staging_bin"
    backup_bin="$BUN_BIN/bun.backup.$(date +%Y%m%d%H%M%S).$$"
    if [ -f "$BUN_BIN/bun" ]; then
        if ! mv "$BUN_BIN/bun" "$backup_bin" 2>/dev/null; then
            rm -rf "$tmpdir"
            rm -f "$staging_bin" 2>/dev/null || true
            return 1
        fi
    fi
    if ! mv "$staging_bin" "$BUN_BIN/bun"; then
        [ -f "$backup_bin" ] && mv "$backup_bin" "$BUN_BIN/bun" 2>/dev/null || true
        rm -rf "$tmpdir"
        return 1
    fi
    installed_version="$(normalize_semver "$("$BUN_BIN/bun" --version 2>/dev/null || echo '?')")"
    if [ "$installed_version" != "$(normalize_semver "$bun_version")" ]; then
        print_error "Weryfikacja wersji Bun nie powiodła się: oczekiwano $bun_version, wykryto $installed_version"
        rm -f "$BUN_BIN/bun" 2>/dev/null || true
        [ -f "$backup_bin" ] && mv "$backup_bin" "$BUN_BIN/bun" 2>/dev/null || true
        rm -rf "$tmpdir"
        return 1
    fi
    rm -f "$backup_bin" 2>/dev/null || true
    rm -rf "$tmpdir"
    return 0
}

ensure_latest_bun() {
    local pinned
    local current

    export BUN_INSTALL="$BUN_HOME"
    mkdir -p "$BUN_HOME" "$BUN_BIN" || return 1

    if [ -x "$BUN_BIN/bun" ]; then
        current="$(normalize_semver "$("$BUN_BIN/bun" --version 2>/dev/null || echo '?')")"
        print_info "Aktualizuję Bun natywnie przez bun upgrade..."
        if run_quiet_with_error_log "bun upgrade" "$BUN_BIN/bun" upgrade; then
            print_ok "Bun aktywny: $("$BUN_BIN/bun" --version 2>/dev/null)"
        else
            print_warn "bun upgrade zakończony ostrzeżeniem — próbuję instalacji z archiwum..."
            if pinned="$(read_bun_version)"; then
                if semver_is_newer "$pinned" "$current"; then
                    install_bun_tarball "$pinned" || return 1
                    print_ok "Bun aktywny: $("$BUN_BIN/bun" --version 2>/dev/null)"
                else
                    print_ok "Bun $current nie jest starszy niż zweryfikowany fallback $pinned — bez downgrade"
                fi
            else
                print_error "Brak config/bun_version.txt — nie mogę zweryfikować fallbacku Bun"
                return 1
            fi
        fi
    else
        pinned="$(read_bun_version)" || pinned=""
        if [ -z "$pinned" ]; then
            print_error "Brak config/bun_version.txt — nie mogę zainstalować Bun bez weryfikacji SHA256"
            return 1
        fi
        if install_bun_tarball "$pinned"; then
            print_ok "Bun aktywny: $("$BUN_BIN/bun" --version 2>/dev/null)"
        else
            print_error "Instalacja Bun nie powiodła się"
            return 1
        fi
    fi

    export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true
}

install_latest_npm_packages() {
    local active_npm="$N_PREFIX/bin/npm"
    local display_name
    local package_name
    local method
    local _brew_formula
    local command_name
    local command_path
    local package_spec
    local failures=0

    if [ ! -x "$active_npm" ]; then
        active_npm="$(bootstrap_npm)"
    fi

    if [ -z "$active_npm" ]; then
        print_error "Brak działającego npm po instalacji Node.js"
        return 1
    fi

    while IFS='|' read -r display_name package_name method _brew_formula command_name; do
        case "$display_name" in
            ""|\#*) continue ;;
        esac

        if [ "$method" = "npm" ]; then
            package_spec="${package_name}@latest"
            print_info "Aktualizuję ${display_name} przez npm (${package_spec})..."
            if run_quiet_with_error_log \
                "npm install ${package_spec}" \
                "$active_npm" install -g --prefix "$NPM_GLOBAL_PREFIX" "$package_spec"; then
                print_ok "${display_name}: $(detect_command_version "$display_name" "$NPM_GLOBAL_BIN/$command_name")"
            else
                print_warn "Aktualizacja ${display_name} nie powiodła się"
                failures=$((failures + 1))
            fi
        elif [ "$method" = "self-update" ]; then
            if command_path="$(resolve_command_path "$command_name")"; then
                print_info "Aktualizuję ${display_name} przez własny updater (${command_name} update)..."
                if run_quiet_with_error_log \
                    "${command_name} update" \
                    run_with_timeout 300 "$command_path" update; then
                    command_path="$(resolve_command_path "$command_name" 2>/dev/null || printf '%s' "$command_path")"
                    print_ok "${display_name}: $(detect_command_version "$display_name" "$command_path")"
                else
                    print_warn "Aktualizacja ${display_name} nie powiodła się"
                    failures=$((failures + 1))
                fi
            else
                print_info "${display_name} nie jest zainstalowany — pomijam"
            fi
        fi
    done < "$MANIFEST_PATH"

    export PATH="$LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN:$PATH"
    hash -r 2>/dev/null || true

    if [ "$failures" -ne 0 ]; then
        print_warn "$failures aktualizacji npm/self-update zakończyło się błędem"
        if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -f "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log" ]; then
            print_info "Diagnostyka: $MAC_UPDATE_SESSION_DIR/npm_cli_errors.log"
        fi
        SOFT_FAIL=1
        return 1
    fi
    return 0
}

remove_legacy_brew_formulas() {
    if ! command -v brew >/dev/null 2>&1; then
        return 0
    fi

    print_info "Usuwam legacy formulae CLI z Homebrew, jeśli zostały pomyślnie zmigrowane..."

    local formula
    local command_name
    local command_path
    local brew_prefix

    brew_prefix="$(brew --prefix 2>/dev/null || echo "/opt/homebrew")"
    for formula in opencode bun node; do
        if ! brew list --formula "$formula" >/dev/null 2>&1; then
            continue
        fi

        case "$formula" in
            opencode)   command_name="opencode" ;;
            bun)        command_name="bun" ;;
            node)       command_name="node" ;;
        esac

        command_path="$(command -v "$command_name" 2>/dev/null || true)"
        if [ -n "$command_path" ] && ! echo "$command_path" | grep -q "^${brew_prefix}/"; then
            if brew uninstall --formula "$formula" >/dev/null 2>&1; then
                print_ok "Usunięto z Homebrew: $formula"
            else
                print_warn "Nie udało się usunąć z Homebrew: $formula"
            fi
        else
            print_warn "Pomijam uninstall $formula — aktywna komenda nadal wskazuje Homebrew"
        fi
    done
}

print_header "🧰 Native CLI & npm"

if [ ! -f "$MANIFEST_PATH" ]; then
    print_error "Brak manifestu CLI: $MANIFEST_PATH"
    exit 1
fi

if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ]; then
    print_warn "DRY-RUN mode — no npm/CLI files or shell profiles will be modified"
    print_info "[DRY-RUN] Would run: Node bootstrap, npm global upgrades, Bun install/upgrade"
    print_header "✅ Native CLI & npm — dry-run complete"
    exit 0
fi

trap cleanup_npm_cli EXIT
trap 'cleanup_npm_cli; exit 130' INT TERM
if ! ensure_toolchain_paths; then
    print_error "Nie udało się bezpiecznie skonfigurować ścieżek natywnego toolchainu"
    exit 1
fi

NPM_CLI_EXIT=0
if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ]; then
    if ! : > "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log"; then
        print_warn "Nie udało się utworzyć logu diagnostycznego npm"
        SOFT_FAIL=1
    fi
fi

if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "Zapisuję snapshot CLI przed aktualizacją..."
    if ! write_cli_snapshot "$MAC_UPDATE_SESSION_DIR/npm_cli_before.txt"; then
        print_warn "Nie udało się zapisać snapshotu CLI przed aktualizacją"
        SOFT_FAIL=1
    fi
fi

NODE_READY=1
if ! ensure_latest_node; then
    NODE_READY=0
fi
if [ "$NODE_READY" -eq 1 ]; then
    install_latest_npm_packages || SOFT_FAIL=1
else
    print_error "Pomijam pakiety npm, ponieważ aktualizacja Node.js nie powiodła się"
fi
ensure_latest_bun || true
remove_legacy_brew_formulas

if [ -n "$MAC_UPDATE_SESSION_DIR" ]; then
    print_info "Zapisuję snapshot CLI po aktualizacji..."
    if ! write_cli_snapshot "$MAC_UPDATE_SESSION_DIR/npm_cli_after.txt"; then
        print_warn "Nie udało się zapisać snapshotu CLI po aktualizacji"
        SOFT_FAIL=1
    fi
fi

NPM_CLI_EXIT="$(mac_update_severity_exit_code)"
if [ "$NPM_CLI_EXIT" -ne 0 ]; then
    if [ -n "${MAC_UPDATE_SESSION_DIR:-}" ] && [ -s "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log" ]; then
        print_warn "Ostatnia diagnostyka npm/self-update (sanityzowana):"
        tail -n 20 "$MAC_UPDATE_SESSION_DIR/npm_cli_errors.log" | sed 's/^/    /'
    fi
    print_header "⚠️  Native CLI & npm — zakończono z błędami/ostrzeżeniami"
    exit "$NPM_CLI_EXIT"
fi

print_header "✅ Native CLI & npm — gotowe"
print_ok "PATH: $LOCAL_BIN:$NPM_GLOBAL_BIN:$N_PREFIX/bin:$BUN_BIN"
