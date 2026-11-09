#!/usr/bin/env bash
# lib/ui.sh — terminal UX helpers (TTY-aware, Bash 3.2+)

UI_START_EPOCH="${UI_START_EPOCH:-$(date +%s)}"

ui_is_tty() {
    [ -t 1 ]
}

GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
MAGENTA='\033[0;35m'
NC='\033[0m'

print_ok()    { echo -e "  ${GREEN}✅ $1${NC}"; }
print_info()  { echo -e "  ${CYAN}ℹ️  $1${NC}"; }
print_warn()  { echo -e "  ${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "  ${RED}❌ $1${NC}"; }
print_step()  { echo -e "  ${MAGENTA}▶  $1${NC}"; }

# Repeat a single character (Bash 3.2 — no seq/printf %*s).
_ui_repeat_char() {
    local char="$1" count="$2" out="" i=0
    while [ "$i" -lt "$count" ]; do out="${out}${char}"; i=$((i + 1)); done
    printf '%s' "$out"
}

# Single-line boxed header; width grows with title (min 48 cols).
ui_print_header() {
    local title="$1"
    local prefix="  "
    local title_len=${#title}
    local inner_width=$((title_len + 2))
    local min_width=48
    local right_pad border rp="" i=0

    [ "$inner_width" -lt "$min_width" ] && inner_width=$min_width
    right_pad=$((inner_width - title_len - 2))
    border=$(_ui_repeat_char "═" "$inner_width")
    while [ "$i" -lt "$right_pad" ]; do rp="${rp} "; i=$((i + 1)); done

    echo ""
    echo -e "\033[0;34m╔${border}╗\033[0m"
    echo -e "\033[0;34m║${prefix}${title}${rp}║\033[0m"
    echo -e "\033[0;34m╚${border}╝\033[0m"
    echo ""
}

print_header() { ui_print_header "$1"; }

# ── Bounded yes/no prompt (Bash 3.2) ─────────────────────────
# A prompt that waits forever turns one unattended-looking run into an hour of
# silence (2026-11-04: 51 minutes on a brew question). Every mid-run question
# goes through here so it has a lifetime and a safe default.
#
#   mac_update_prompt_timeout     -> effective seconds (0 = wait forever)
#   mac_update_prompt_yn <prompt> <timeout-default y|n> [<enter-default y|n>]
#       returns 0 for yes, 1 for no. Typed n*/y*/t* wins; an empty answer (or
#       end of input) uses the enter-default; other text means no (defaults to the
#       timeout default). No answer within MAC_UPDATE_PROMPT_TIMEOUT seconds
#       (default 120, clamped 10-900, 0 = no limit) uses the timeout-default,
#       prints a notice and sets MAC_UPDATE_PROMPT_TIMED_OUT=1.
mac_update_prompt_timeout() {
    local v="${MAC_UPDATE_PROMPT_TIMEOUT:-120}"
    case "$v" in
        ''|*[!0-9]*) v=120 ;;
    esac
    if [ "$v" -ne 0 ]; then
        [ "$v" -lt 10 ] && v=10
        [ "$v" -gt 900 ] && v=900
    fi
    printf '%s\n' "$v"
}

mac_update_prompt_yn() {
    local prompt="$1" tdef="${2:-n}" edef="${3:-}" ans="" rc=0 t started
    [ -n "$edef" ] || edef="$tdef"
    MAC_UPDATE_PROMPT_TIMED_OUT=0
    t="$(mac_update_prompt_timeout)"
    printf '  %s' "$prompt"
    started=$SECONDS
    if [ "$t" -gt 0 ]; then
        read -r -t "$t" ans
        rc=$?
    else
        read -r ans
        rc=$?
    fi
    # Bash 3.2 returns 1 (not >128) when `read -t` expires, so a failed read that
    # used the whole window is a timeout; an earlier failure is end of input.
    if [ "$rc" -gt 128 ] || { [ "$rc" -ne 0 ] && [ "$t" -gt 0 ] && [ $((SECONDS - started)) -ge "$t" ]; }; then
        MAC_UPDATE_PROMPT_TIMED_OUT=1
        echo ""
        # shellcheck disable=SC2059
        print_info "$(printf "${L_PROMPT_TIMEOUT_FMT:-No answer within %ss — assuming \"%s\"}" "$t" "$tdef")"
        [ "$tdef" = "y" ] && return 0
        return 1
    fi
    case "$ans" in
        [Nn]*) return 1 ;;
        [YyTt]*) return 0 ;;
        '') ;;
        *) return 1 ;;  # unrecognised text is never a yes
    esac
    [ "$edef" = "y" ] && return 0
    return 1
}

# Centered single-line boxed message (summary banners).
ui_print_box() {
    local text="$1"
    local min_width="${2:-48}"
    local text_len=${#text}
    local inner_width=$text_len
    local pad_total pad_left pad_right border lp="" rp="" i=0

    [ "$inner_width" -lt "$min_width" ] && inner_width=$min_width
    pad_total=$((inner_width - text_len))
    pad_left=$((pad_total / 2))
    pad_right=$((pad_total - pad_left))
    border=$(_ui_repeat_char "═" "$inner_width")
    while [ "$i" -lt "$pad_left" ]; do lp="${lp} "; i=$((i + 1)); done
    i=0
    while [ "$i" -lt "$pad_right" ]; do rp="${rp} "; i=$((i + 1)); done

    echo -e "\033[0;34m\033[1m╔${border}╗\033[0m"
    echo -e "\033[0;34m\033[1m║${lp}${text}${rp}║\033[0m"
    echo -e "\033[0;34m\033[1m╚${border}╝\033[0m"
}

ui_elapsed() {
    local now=$(( $(date +%s) - UI_START_EPOCH ))
    local m=$((now / 60))
    local s=$((now % 60))
    if [ "$m" -gt 0 ]; then
        printf '%dm %02ds' "$m" "$s"
    else
        printf '%ds' "$s"
    fi
}

ui_step_header() {
    local step_num="$1"
    local step_total="$2"
    local title="$3"
    if ui_is_tty; then
        echo ""
        echo -e "\033[0;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
        echo -e "\033[0;36m  Step ${step_num}/${step_total}: ${title}\033[0m  \033[0;90m($(ui_elapsed))\033[0m"
        echo -e "\033[0;36m━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\033[0m"
        echo ""
    else
        echo ""
        echo "=== Step ${step_num}/${step_total}: ${title} ($(ui_elapsed)) ==="
        echo ""
    fi
}

ui_progress_bar() {
    local current="$1"
    local total="$2"
    local label="${3:-}"
    local width=30 filled=0 empty=0 bar="" i=0 pct=0

    [ "$total" -gt 0 ] 2>/dev/null || total=1
    pct=$(( current * 100 / total ))
    filled=$(( current * width / total ))
    empty=$(( width - filled ))
    while [ "$i" -lt "$filled" ]; do bar="${bar}█"; i=$((i + 1)); done
    i=0
    while [ "$i" -lt "$empty" ]; do bar="${bar}░"; i=$((i + 1)); done
    if ui_is_tty; then
        printf '\r  \033[0;36m[%s]\033[0m %3d%% %s' "$bar" "$pct" "$label"
        echo ""
    else
        printf '  [%s] %3d%% %s\n' "$bar" "$pct" "$label"
    fi
}

ui_master_progress() {
    ui_progress_bar "$1" "$2" "overall"
}

ui_status_line() {
    if ui_is_tty; then
        echo -e "  \033[0;36mℹ️  $1\033[0m"
    else
        echo "  INFO: $1"
    fi
}

ui_summary_table() {
    local rows="$1"
    if ui_is_tty; then
        echo ""
        echo -e "\033[1;34m╔══════════════════════════════════════════════════════════════╗\033[0m"
        echo -e "\033[1;34m║\033[0m  ${L_ALL_RUN_SUMMARY_TITLE:-Run summary}"
        echo -e "\033[1;34m╠══════════════════════════════════════════════════════════════╣\033[0m"
        echo "$rows" | while IFS= read -r line; do
            [ -n "$line" ] && printf "\033[1;34m║\033[0m  %-58s \033[1;34m║\033[0m\n" "$line"
        done
        echo -e "\033[1;34m╚══════════════════════════════════════════════════════════════╝\033[0m"
        echo ""
    else
        echo ""; echo "${L_ALL_RUN_SUMMARY_TITLE:-Run summary}"; echo "$rows"; echo ""
    fi
}
