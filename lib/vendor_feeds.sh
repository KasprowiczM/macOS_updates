#!/usr/bin/env bash
# lib/vendor_feeds.sh — vendor feeds lookup and config (Bash 3.2+)

_VENDOR_FEEDS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # = lib/

vendor_feed_config_path() {
    echo "$_VENDOR_FEEDS_DIR/../config/vendor_feeds.txt"
}

vendor_feed_row() {
    local app="$1" cfg row
    cfg="$(vendor_feed_config_path)"
    [ -f "$cfg" ] || return 1
    row=$(awk -F'|' -v a="$app" '
        /^[[:space:]]*#/ { next }
        { n = $1; gsub(/^[[:space:]]+|[[:space:]]+$/, "", n); if (n == a) { print; exit } }
    ' "$cfg" 2>/dev/null)
    [ -n "$row" ] || return 1
    printf "%s\n" "$row"
}

_vf_diag() {
    command -v internet_diag_log >/dev/null 2>&1 && internet_diag_log "$@"
    return 0
}

# vendor_feed_fetch <app> <url> <out_file>
# HTTPS-only fetch of a vendor feed into <out_file>. Every attempt records the curl
# exit code, the HTTP status and the elapsed time in the session diagnostics
# (internet_diag.txt) — on 2026-11-08 two GitHub-hosted feeds failed in the same
# run and nothing said why. Transient failures are retried (--retry-all-errors).
# Returns 0 when a body arrived with a 2xx status (or no status at all, e.g. a
# test double), 2 otherwise.
vendor_feed_fetch() {
    local app="$1" url="$2" out="$3"
    local err_file="$out.err" rc http t bytes host start msg
    host="${url#https://}"
    host="${host%%/*}"
    start=$(date +%s 2>/dev/null || echo 0)
    curl -sSL --proto '=https' --proto-redir '=https' --max-time 15 \
        --retry 2 --retry-all-errors --max-filesize 5242880 \
        -w '%{stderr}VFMETA %{http_code} %{time_total}\n' \
        "$url" >"$out" 2>"$err_file"
    rc=$?
    http="$(awk '$1 == "VFMETA" { print $2 }' "$err_file" 2>/dev/null | tail -n 1)"
    t="$(awk '$1 == "VFMETA" { print $3 }' "$err_file" 2>/dev/null | tail -n 1)"
    if [ -z "$t" ]; then
        t="$(( $(date +%s 2>/dev/null || echo 0) - start ))"
    fi
    bytes="$(wc -c < "$out" 2>/dev/null | tr -d ' ')"
    msg="$(grep -v '^VFMETA ' "$err_file" 2>/dev/null | head -n 1)"
    rm -f "$err_file"
    case "$http" in
        ''|2??) ;;
        *) rc="${rc:-0}"; [ "$rc" -eq 0 ] && rc=22 ;;
    esac
    if [ "$rc" -eq 0 ] && [ "${bytes:-0}" -gt 0 ]; then
        _vf_diag "Vendor feed $app: fetch ok (curl=0 http=${http:--} time=${t}s bytes=$bytes host=$host)"
        return 0
    fi
    [ "$rc" -eq 0 ] && msg="${msg:-empty response body}"
    _vf_diag "Vendor feed $app: fetch FAILED (curl=$rc http=${http:-000} time=${t}s bytes=${bytes:-0} host=$host)${msg:+: $msg}"
    return 2
}

# vendor_feed_lookup <app>
# Prints version|url|checksum_kind|checksum|artifact|host|policy on success.
# Return codes (subshell-safe, callers use $?): 0 ok, 1 no config row,
# 2 fetch failed (network/HTTP), 3 fetched but no usable version (parse).
vendor_feed_lookup() {
    local app="$1" row
    row=$(vendor_feed_row "$app") || return 1
    local _app kind url arg artifact host
    IFS='|' read -r _app kind url arg artifact host <<EOF
$row
EOF
    [ -n "$url" ] || return 1
    case "$url" in
        https://*) ;;
        *) _vf_diag "Vendor feed $app: refused non-https feed URL"; return 2 ;;
    esac

    local tmp_dir body
    tmp_dir="$(mktemp -d "${MAC_UPDATE_SESSION_DIR:-${TMPDIR:-/tmp}}/mac_update_feed.XXXXXX" 2>/dev/null)" || \
        tmp_dir="$(mktemp -d "${TMPDIR:-/tmp}/mac_update_feed.XXXXXX")" || return 2
    body="$tmp_dir/body"
    if ! vendor_feed_fetch "$app" "$url" "$body"; then
        rm -rf "$tmp_dir"
        return 2
    fi

    local py_res
    py_res=$(head -c 5242880 "$body" | \
        PYTHONPATH="$_VENDOR_FEEDS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from vendor_feeds import evaluate_feed

kind = sys.argv[1]
arg = sys.argv[2]
os_ver = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
base_url = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
body = sys.stdin.read()

res = evaluate_feed(kind, body, arg, os_version=os_ver, base_url=base_url)
if not res or not res.get("version"):
    sys.exit(1)

v = res.get("version") or "-"
u = res.get("url") or "-"
ck = res.get("checksum_kind") or "-"
cs = res.get("checksum") or "-"
policy = "rollout_hold" if res.get("rollout_hold") else "eligible"
print(f"{v}|{u}|{ck}|{cs}|{policy}")
' "$kind" "$arg" "$(sw_vers -productVersion 2>/dev/null)" "$url"
    )
    local rc=$?
    local bytes
    bytes="$(wc -c < "$body" 2>/dev/null | tr -d ' ')"
    rm -rf "$tmp_dir"
    if [ $rc -ne 0 ] || [ -z "$py_res" ]; then
        _vf_diag "Vendor feed $app: parse FAILED (kind=$kind bytes=${bytes:-0}): no usable version in the response"
        return 3
    fi

    local v u ck cs policy
    IFS='|' read -r v u ck cs policy <<EOF_RESULT
$py_res
EOF_RESULT
    printf "%s|%s|%s|%s|%s|%s|%s\n" "$v" "$u" "$ck" "$cs" "${artifact:--}" "${host:--}" "$policy"
}

# ── Persistent feed state (lib/python/feed_state.py) ─────────────────────────
# Per-app last successful vendor version + high-water mark, used ONLY to avoid
# blind launches on a transient fetch failure (cached proof, bounded TTL) and to
# recognise a vendor-side feed regression. Never an install target.
vendor_feed_state_file() {
    printf '%s' "${MAC_UPDATE_FEED_STATE_FILE:-$HOME/.local/state/mac-update/feed_state.json}"
}

# TTL in hours for a cached proof (MAC_UPDATE_FEED_CACHE_TTL_H, default 24,
# clamped 0-168; 0 disables cached proofs).
vendor_feed_cache_ttl_h() {
    printf '%s' "${MAC_UPDATE_FEED_CACHE_TTL_H:-24}"
}

# vendor_feed_state_record <app> ok <version> | <app> fail <fetch|parse>
# Dry runs never write. Failures to write are logged, never fatal.
vendor_feed_state_record() {
    local app="$1" what="$2" value="$3"
    [ "${MAC_UPDATE_DRY_RUN:-0}" = "1" ] && return 0
    [ -n "$app" ] && [ -n "$value" ] || return 0
    PYTHONPATH="$_VENDOR_FEEDS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys, time
import feed_state as fs
path, app, what, value = sys.argv[1:5]
st = fs.load_state(path)
if what == "ok":
    fs.record_success(st, app, value, time.time())
else:
    fs.record_failure(st, app, value, time.time())
fs.save_state(path, st)
' "$(vendor_feed_state_file)" "$app" "$what" "$value" 2>/dev/null || \
        _vf_diag "Vendor feed $app: could not write feed state ($(vendor_feed_state_file))"
    return 0
}

# vendor_feed_state_cached_proof <app> <installed>
# Prints "<version>|<age>" (age in whole hours or "<1") and returns 0 when a
# successful feed check younger than the TTL listed exactly the installed version.
vendor_feed_state_cached_proof() {
    local app="$1" installed="$2"
    PYTHONPATH="$_VENDOR_FEEDS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys, time
import feed_state as fs
path, app, installed, ttl = sys.argv[1:5]
p = fs.cached_proof(fs.load_state(path), app, installed, fs.clamp_ttl(ttl), time.time())
if not p:
    sys.exit(1)
print("%s|%s" % (p["version"], fs.format_age_h(p["age_h"])))
' "$(vendor_feed_state_file)" "$app" "$installed" "$(vendor_feed_cache_ttl_h)" 2>/dev/null
}

# vendor_feed_state_high_water <app> <installed>
# Prints the highest vendor version ever seen and returns 0 when it is >= installed.
vendor_feed_state_high_water() {
    local app="$1" installed="$2"
    PYTHONPATH="$_VENDOR_FEEDS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
import feed_state as fs
path, app, installed = sys.argv[1:4]
h = fs.high_water_covers(fs.load_state(path), app, installed)
if not h:
    sys.exit(1)
print(h["version"])
' "$(vendor_feed_state_file)" "$app" "$installed" 2>/dev/null
}

# Explicit appcast URL for an app (config/vendor_appcasts.txt); empty when none.
vendor_appcast_url() {
    local app="$1" cfg
    cfg="$_VENDOR_FEEDS_DIR/../config/vendor_appcasts.txt"
    [ -f "$cfg" ] || return 1
    awk -F'|' -v a="$app" '
        /^[[:space:]]*#/ { next }
        { n = $1; gsub(/^[[:space:]]+|[[:space:]]+$/, "", n);
          if (n == a) { u = $2; gsub(/^[[:space:]]+|[[:space:]]+$/, "", u); print u; exit } }
    ' "$cfg" 2>/dev/null
}

# Cross-check used when the primary vendor feed is OLDER than the installed app.
# Prints the channel in which the app's own Sparkle appcast publishes the installed
# version ("stable", "gradual-rollout", ... or "default") and returns 0; returns 1
# when it is not published there, the appcast is missing/unreachable, or its host is
# not the app's allowed host. Proof of "current" only: never an install target.
vendor_appcast_published_channel() {
    local app="$1" app_path="$2" row url host
    url="$(vendor_appcast_url "$app")" || return 1
    [ -n "$url" ] || return 1
    row="$(vendor_feed_row "$app")" || return 1
    host="$(printf '%s' "$row" | awk -F'|' '{ h = $6; gsub(/^[[:space:]]+|[[:space:]]+$/, "", h); print h }')"

    local short build
    short="$(defaults read "$app_path/Contents/Info" CFBundleShortVersionString 2>/dev/null || true)"
    build="$(defaults read "$app_path/Contents/Info" CFBundleVersion 2>/dev/null || true)"
    [ -n "$short" ] || return 1

    PYTHONPATH="$_VENDOR_FEEDS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from vendor_feeds import appcast_url_allowed
sys.exit(0 if appcast_url_allowed(sys.argv[1], sys.argv[2]) else 1)
' "$url" "$host" || return 1

    local out
    out="$(curl -fsSL --proto '=https' --proto-redir '=https' --max-time 15 --retry 2 "$url" 2>/dev/null | head -c 5242880 | \
        PYTHONPATH="$_VENDOR_FEEDS_DIR/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c '
import sys
from vendor_feeds import appcast_publishes_installed
ch = appcast_publishes_installed(sys.stdin.read(), sys.argv[1], sys.argv[2] or None)
if ch is None:
    sys.exit(1)
print(ch or "default")
' "$short" "$build")" || return 1
    [ -n "$out" ] || return 1
    printf '%s\n' "$out"
}
