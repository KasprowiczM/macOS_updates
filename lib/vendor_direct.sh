#!/usr/bin/env bash
# lib/vendor_direct.sh — Direct vendor download and installation (Bash 3.2+)
#
# Implements "vendor truth" direct verification and installation path for
# apps where vendor feeds specify an installable artifact.
#
# Requires: lib/fetch.sh, lib/proc.sh, copy_verified_app (when installing)

_VENDOR_DIRECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/fetch.sh
[ -f "$_VENDOR_DIRECT_DIR/fetch.sh" ] && . "$_VENDOR_DIRECT_DIR/fetch.sh"
# shellcheck source=lib/proc.sh
[ -f "$_VENDOR_DIRECT_DIR/proc.sh" ] && . "$_VENDOR_DIRECT_DIR/proc.sh"

_vd_valid_bundle_id() {
    case "$1" in
        ''|*[!A-Za-z0-9._-]*) return 1 ;;
    esac
    return 0
}

internet_app_bundle_id() {
    local app_path="$1"
    [ -n "$app_path" ] && [ -e "$app_path" ] || return 1
    local bid=""
    bid="$(defaults read "$app_path/Contents/Info" CFBundleIdentifier 2>/dev/null || true)"
    if [ -z "$bid" ] && command -v codesign >/dev/null 2>&1; then
        bid="$(codesign -dv "$app_path" 2>&1 | sed -n 's/^Identifier=//p' | head -n 1)"
    fi
    printf '%s\n' "$bid"
}

internet_app_is_running() {
    local bid="$1"
    _vd_valid_bundle_id "$bid" || return 1
    local out=""
    out="$(run_with_timeout 10 osascript -e "application id \"$bid\" is running" 2>/dev/null || true)"
    [ "$out" = "true" ]
}

internet_app_quit_gracefully() {
    local bid="$1"
    _vd_valid_bundle_id "$bid" || return 1
    if ! internet_app_is_running "$bid"; then
        return 0
    fi
    run_with_timeout 20 osascript -e "tell application id \"$bid\" to quit" 2>/dev/null || true
    local elapsed=0
    while [ "$elapsed" -lt 60 ]; do
        if ! internet_app_is_running "$bid"; then
            return 0
        fi
        sleep 2
        elapsed=$((elapsed + 2))
    done
    return 1
}

vendor_direct_host_allowed() {
    local url="$1" host="$2"
    [ -n "$url" ] && [ -n "$host" ] || return 1
    case "$url" in
        https://*) ;;
        *) return 1 ;;
    esac
    local url_host
    url_host="${url#https://}"
    url_host="${url_host%%/*}"
    url_host="${url_host%%:*}"
    [ "$url_host" = "$host" ]
}

vendor_direct_verify_checksum() {
    local file="$1" kind="$2" val="$3"
    [ -f "$file" ] || return 1
    case "$kind" in
        ''|'-') return 0 ;;
    esac
    case "$val" in
        ''|'-') return 0 ;;
    esac

    case "$kind" in
        sha256hex)
            local actual
            actual="$(shasum -a 256 "$file" 2>/dev/null | awk '{print $1}')"
            python3 -c "import sys; sys.exit(0 if sys.argv[1].lower() == sys.argv[2].lower() else 1)" "$actual" "$val"
            ;;
        sha512hex)
            local actual
            actual="$(shasum -a 512 "$file" 2>/dev/null | awk '{print $1}')"
            python3 -c "import sys; sys.exit(0 if sys.argv[1].lower() == sys.argv[2].lower() else 1)" "$actual" "$val"
            ;;
        sha512b64)
            python3 -c "import hashlib, base64, sys; f=open(sys.argv[1],'rb').read(); h=base64.b64encode(hashlib.sha512(f).digest()).decode('ascii'); sys.exit(0 if h == sys.argv[2] else 1)" "$file" "$val"
            ;;
        *)
            return 1
            ;;
    esac
}

vendor_direct_install() {
    local installed_app_path="$1" url="$2" artifact="$3" checksum_kind="$4" checksum="$5" host="$6"

    # 1. DRY RUN / VERIFY ONLY
    if [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] || [ "${MAC_UPDATE_VERIFY_ONLY:-0}" = "1" ]; then
        print_info "[DRY-RUN] vendor_direct_install $installed_app_path from $url" 2>/dev/null || true
        return 2
    fi

    # 2. Installed path must start with /Applications/
    case "$installed_app_path" in
        /Applications/*) ;;
        *)
            [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: vendor_direct_install requires /Applications path: $installed_app_path" 2>/dev/null || true
            return 1
            ;;
    esac

    # 3. Host allowlist
    if ! vendor_direct_host_allowed "$url" "$host"; then
        print_warn "$(printf "${L_INTERNET_VENDOR_HOST_REJECTED_FMT:-Host %s rejected for URL %s}" "$host" "$url")" 2>/dev/null || true
        [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: vendor direct host $host not allowed for $url" 2>/dev/null || true
        return 1
    fi

    # 4. App must not be running
    local bid
    bid="$(internet_app_bundle_id "$installed_app_path")"
    if [ -n "$bid" ] && internet_app_is_running "$bid"; then
        [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: app $bid is currently running" 2>/dev/null || true
        return 1
    fi

    # 5. Fetch to file
    local ext="bin"
    case "$artifact" in
        zip) ext="zip" ;;
        dmg) ext="dmg" ;;
        tar.gz) ext="tar.gz" ;;
    esac
    local tmp_root="${INTERNET_TEMP_ROOT:-${TMPDIR:-/tmp}}"
    local dl_file
    dl_file="$(mktemp "$tmp_root/vd.XXXXXX.${ext}")" || return 1
    if ! fetch_to_file "$url" "$dl_file" 1800 4294967296; then
        [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: fetch_to_file failed for $url" 2>/dev/null || true
        rm -f "$dl_file"
        return 1
    fi

    # 6. Checksum
    if ! vendor_direct_verify_checksum "$dl_file" "$checksum_kind" "$checksum"; then
        print_warn "$(printf "${L_INTERNET_CHECKSUM_MISMATCH_FMT:-Checksum mismatch: expected %s, got %s}" "$checksum" "mismatch")" 2>/dev/null || true
        [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: checksum mismatch for $dl_file" 2>/dev/null || true
        rm -f "$dl_file"
        return 1
    fi

    # 7. Extract
    local extract_dir
    extract_dir="$(mktemp -d "$tmp_root/vd_x.XXXXXX")" || { rm -f "$dl_file"; return 1; }
    case "$artifact" in
        zip)
            if ! ditto -x -k "$dl_file" "$extract_dir" 2>/dev/null; then
                [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: ditto extract failed for $dl_file" 2>/dev/null || true
                rm -rf "$extract_dir" "$dl_file"
                return 1
            fi
            ;;
        tar.gz)
            if ! tar -xzf "$dl_file" -C "$extract_dir" 2>/dev/null; then
                [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: tar extract failed for $dl_file" 2>/dev/null || true
                rm -rf "$extract_dir" "$dl_file"
                return 1
            fi
            ;;
        dmg)
            local mnt
            mnt="$(mount_verified_dmg "$dl_file")" || {
                [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: mount_verified_dmg failed for $dl_file" 2>/dev/null || true
                rm -rf "$extract_dir" "$dl_file"
                return 1
            }
            find "$mnt" -maxdepth 3 -type d -name '*.app' -prune -exec cp -R {} "$extract_dir/" \; 2>/dev/null || true
            detach_verified_dmg "$mnt" 2>/dev/null || true
            ;;
        *)
            rm -rf "$extract_dir" "$dl_file"
            return 1
            ;;
    esac
    rm -f "$dl_file"

    # 8. Exactly one *.app matching bundle ID
    local target_bid="$bid"
    local found=""
    local match_count=0
    local candidate
    while IFS= read -r candidate; do
        [ -n "$candidate" ] || continue
        local c_bid
        c_bid="$(internet_app_bundle_id "$candidate")"
        if [ -n "$target_bid" ] && [ "$c_bid" = "$target_bid" ]; then
            match_count=$((match_count + 1))
            found="$candidate"
        fi
    done <<EOF
$(find "$extract_dir" -maxdepth 3 -type d -name '*.app' -prune 2>/dev/null)
EOF

    if [ "$match_count" -ne 1 ] || [ -z "$found" ]; then
        [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: expected 1 app bundle with id $target_bid, found $match_count" 2>/dev/null || true
        rm -rf "$extract_dir"
        return 1
    fi

    # 9. copy_verified_app
    local dest_label
    dest_label="$(basename "$installed_app_path")"
    if ! copy_verified_app "$found" "$dest_label"; then
        [ -n "${internet_diag_log:-}" ] && internet_diag_log "ERROR: copy_verified_app failed for $found -> $dest_label" 2>/dev/null || true
        rm -rf "$extract_dir"
        return 3
    fi

    rm -rf "$extract_dir"
    return 0
}
