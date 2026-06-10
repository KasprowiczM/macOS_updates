#!/usr/bin/env bash
# lib/internet_registry.sh — load config/internet_app_methods.txt (Bash 3.2+)

_internet_methods_config_path() {
    echo "${SCRIPT_DIR}/config/internet_app_methods.txt"
}

# Populates INTERNET_METHOD_APPS[], INTERNET_METHOD_TYPES[], INTERNET_METHOD_STATUS[]
internet_registry_load() {
    local cfg line app method status
    INTERNET_METHOD_APPS=()
    INTERNET_METHOD_TYPES=()
    INTERNET_METHOD_STATUS=()
    cfg="$(_internet_methods_config_path)"
    [ -f "$cfg" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$line" ] || continue
        # Validate: exactly 3 pipe-delimited fields (AppName|method|STATUS_VAR)
        case "$line" in
            *"|"*"|"*) ;;
            *)
                echo "internet_registry_load: malformed row (need 3 fields): $line" >&2
                continue
                ;;
        esac
        app="${line%%|*}"
        line="${line#*|}"
        method="${line%%|*}"
        status="${line#*|}"
        INTERNET_METHOD_APPS+=("$app")
        INTERNET_METHOD_TYPES+=("$method")
        INTERNET_METHOD_STATUS+=("$status")
    done < "$cfg"
    return 0
}

internet_registry_method_for() {
    local name="$1"
    local i
    internet_registry_load || return 1
    i=0
    while [ "$i" -lt "${#INTERNET_METHOD_APPS[@]}" ]; do
        if [ "${INTERNET_METHOD_APPS[$i]}" = "$name" ]; then
            echo "${INTERNET_METHOD_TYPES[$i]}"
            return 0
        fi
        i=$((i + 1))
    done
    return 1
}

_internet_dispatch_config_path() {
    echo "${SCRIPT_DIR}/config/internet_dispatch_order.txt"
}

# Run ordered handler functions from config/internet_dispatch_order.txt
internet_dispatch_run_all() {
    local cfg line fn
    cfg="$(_internet_dispatch_config_path)"
    [ -f "$cfg" ] || return 1
    while IFS= read -r line || [ -n "$line" ]; do
        line="${line%%#*}"
        line="$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$line" ] || continue
        fn="$line"
        if type "$fn" >/dev/null 2>&1; then
            "$fn"
        else
            print_warn "Missing internet handler: $fn"
            INTERNET_EXIT=1
        fi
    done < "$cfg"
    return 0
}
