#!/usr/bin/env bash
# lib/overrides.sh — per-item user overrides (the only parser for them).
#
# File: <config>/overrides.tsv (lib/paths.sh; MAC_UPDATE_OVERRIDES_FILE wins).
#       While that file does not exist, the old <state>/user_overrides.tsv is
#       read instead (never moved; `mac-update migrate` copies it).
# Line: group<TAB>id<TAB>mode[<TAB>source]
#   group  appstore | cli | brew | cask | internet | system
#   id     item identifier (formula/cask token, App Store id or app name, CLI
#          name, internet app name as in config/internet_app_methods.txt,
#          macOS label or title; "*" matches every item of the group)
#   mode   auto | manual | skip
#            auto   — update normally (the default for anything not listed)
#            manual — check and report "update available", never install
#            skip   — ignore the item entirely
#   source optional: brew | appstore | vendor | native
# Blank lines and lines starting with # are ignored; malformed lines are
# ignored (mu_overrides_check reports them). A missing file means everything
# is automatic. Identifiers compare case-insensitively; an exact entry wins
# over "*". Bash 3.2 compatible; no associative arrays.

_MU_OVERRIDES_LOADED=""
_MU_OVERRIDES_DATA=""

_MU_OVERRIDES_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The file the engine reads (new location, or the old one while the new is missing).
mu_overrides_file() {
    if [ -n "${MAC_UPDATE_OVERRIDES_FILE:-}" ]; then
        printf '%s\n' "$MAC_UPDATE_OVERRIDES_FILE"
        return 0
    fi
    type mu_data_resolve >/dev/null 2>&1 || . "$_MU_OVERRIDES_LIB_DIR/paths.sh"
    if mu_data_resolve 2>/dev/null; then
        printf '%s\n' "$MU_OVERRIDES_READ"
    else
        printf '%s\n' "${MAC_UPDATE_STATE_DIR:-$HOME/.local/state/mac-update}/user_overrides.tsv"
    fi
}

# Normalised, validated rows: "group<TAB>lower(id)<TAB>mode<TAB>source".
_mu_overrides_load() {
    local file
    file="$(mu_overrides_file)"
    [ "$_MU_OVERRIDES_LOADED" = "$file" ] && return 0
    _MU_OVERRIDES_LOADED="$file"
    _MU_OVERRIDES_DATA=""
    [ -f "$file" ] && [ -r "$file" ] || return 0
    _MU_OVERRIDES_DATA="$(awk -F '\t' '
        function trim(s) { gsub(/^[ \r]+|[ \r]+$/, "", s); return s }
        /^[[:space:]]*(#|$)/ { next }
        {
            g = tolower(trim($1)); id = trim($2); m = tolower(trim($3)); s = tolower(trim($4))
            if (NF < 3 || id == "") next
            if (g !~ /^(appstore|cli|brew|cask|internet|system)$/) next
            if (m !~ /^(auto|manual|skip)$/) next
            if (s != "" && s !~ /^(brew|appstore|vendor|native)$/) s = ""
            printf "%s\t%s\t%s\t%s\n", g, tolower(id), m, s
        }' "$file" 2>/dev/null)"
    return 0
}

# Print the matching row's field N (3 = mode, 4 = source); exact id before "*".
_mu_override_field() {
    local group="$1" id="$2" field="$3" lid
    _mu_overrides_load
    [ -n "$_MU_OVERRIDES_DATA" ] || return 1
    lid="$(printf '%s' "$id" | tr '[:upper:]' '[:lower:]')"
    printf '%s\n' "$_MU_OVERRIDES_DATA" | awk -F '\t' -v g="$group" -v id="$lid" -v f="$field" '
        $1 == g && $2 == id { exact = $f; found_exact = 1 }
        $1 == g && $2 == "*" && !found_star { star = $f; found_star = 1 }
        END {
            if (found_exact) { print exact; exit 0 }
            if (found_star) { print star; exit 0 }
            exit 1
        }'
}

# mu_override_mode <group> <id> [alt-id ...] -> auto | manual | skip
# The first identifier with an exact entry wins; otherwise a "*" entry; else auto.
mu_override_mode() {
    local group="$1" mode="" id
    shift
    _mu_overrides_load
    if [ -n "$_MU_OVERRIDES_DATA" ]; then
        for id in "$@"; do
            [ -n "$id" ] || continue
            mode="$(printf '%s\n' "$_MU_OVERRIDES_DATA" | awk -F '\t' -v g="$group" \
                -v id="$(printf '%s' "$id" | tr '[:upper:]' '[:lower:]')" '$1 == g && $2 == id { print $3; exit }')"
            [ -n "$mode" ] && break
        done
        [ -n "$mode" ] || mode="$(printf '%s\n' "$_MU_OVERRIDES_DATA" | awk -F '\t' -v g="$group" '$1 == g && $2 == "*" { print $3; exit }')"
    fi
    printf '%s\n' "${mode:-auto}"
}

# mu_override_source <group> <id> -> source or empty
mu_override_source() {
    _mu_override_field "$1" "$2" 4 2>/dev/null || true
}

# mu_override_is <group> <id> <mode> — convenience predicate.
mu_override_is() {
    [ "$(mu_override_mode "$1" "$2")" = "$3" ]
}

# mu_overrides_check — print one note per ignored (malformed) line.
mu_overrides_check() {
    local file
    file="$(mu_overrides_file)"
    [ -f "$file" ] || return 0
    awk -F '\t' '
        function trim(s) { gsub(/^[ \r]+|[ \r]+$/, "", s); return s }
        /^[[:space:]]*(#|$)/ { next }
        {
            g = tolower(trim($1)); id = trim($2); m = tolower(trim($3)); s = tolower(trim($4))
            bad = ""
            if (NF < 3 || id == "") bad = "expected group<TAB>id<TAB>mode"
            else if (g !~ /^(appstore|cli|brew|cask|internet|system)$/) bad = "unknown group " g
            else if (m !~ /^(auto|manual|skip)$/) bad = "unknown mode " m
            else if (s != "" && s !~ /^(brew|appstore|vendor|native)$/) bad = "unknown source " s " (ignored)"
            if (bad != "") printf "user_overrides.tsv line %d ignored: %s\n", NR, bad
        }' "$file" 2>/dev/null
}

# Forget the cached file (tests, or after the file changed).
mu_overrides_reset() {
    _MU_OVERRIDES_LOADED=""
    _MU_OVERRIDES_DATA=""
}
