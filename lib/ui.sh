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
        echo -e "\033[1;34m║\033[0m  Run summary"
        echo -e "\033[1;34m╠══════════════════════════════════════════════════════════════╣\033[0m"
        echo "$rows" | while IFS= read -r line; do
            [ -n "$line" ] && printf "\033[1;34m║\033[0m  %-58s \033[1;34m║\033[0m\n" "$line"
        done
        echo -e "\033[1;34m╚══════════════════════════════════════════════════════════════╝\033[0m"
        echo ""
    else
        echo ""; echo "Run summary"; echo "$rows"; echo ""
    fi
}
