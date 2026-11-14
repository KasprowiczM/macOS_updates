#!/usr/bin/env bash
# Shared routing for the optional terminal interface (Bash 3.2 compatible).
mac_update_tui_message() {
    local reason="$1" lang="${MAC_UPDATE_LANG:-${MAC_LANG:-}}" key value
    if [ -z "$lang" ] && [ -f "$SCRIPT_DIR/.mac_update_prefs" ]; then
        while IFS='=' read -r key value; do
            key="${key#"${key%%[![:space:]]*}"}"
            key="${key%"${key##*[![:space:]]}"}"
            value="${value#"${value%%[![:space:]]*}"}"
            value="${value%"${value##*[![:space:]]}"}"
            if [ "$key" = MAC_LANG ]; then lang="$value"; break; fi
        done < "$SCRIPT_DIR/.mac_update_prefs"
    fi
    case "${lang:-en}:$reason" in
        pl:terminal) echo 'Interfejs terminalowy wymaga terminala.' ;;
        pl:options) echo 'Opcji --tui nie można łączyć z innymi opcjami CLI.' ;;
        pl:unavailable) echo 'Interfejs terminalowy jest niedostępny.' ;;
        pl:fallback) echo 'Interfejs terminalowy jest niedostępny. Uruchamianie trybu CLI.' ;;
        de:terminal) echo 'Die Terminaloberfläche benötigt ein Terminal.' ;;
        de:options) echo '--tui kann nicht mit anderen CLI-Optionen kombiniert werden.' ;;
        de:unavailable) echo 'Terminaloberfläche nicht verfügbar.' ;;
        de:fallback) echo 'Terminaloberfläche nicht verfügbar. CLI wird gestartet.' ;;
        fr:terminal) echo 'Un terminal est nécessaire pour cette interface.' ;;
        fr:options) echo '--tui ne peut pas être associé aux autres options CLI.' ;;
        fr:unavailable) echo 'Interface terminal indisponible.' ;;
        fr:fallback) echo 'Interface terminal indisponible. Démarrage du CLI.' ;;
        es:terminal) echo 'Esta interfaz necesita un terminal.' ;;
        es:options) echo '--tui no se puede combinar con otras opciones CLI.' ;;
        es:unavailable) echo 'Interfaz de terminal no disponible.' ;;
        es:fallback) echo 'Interfaz de terminal no disponible. Se inicia el CLI.' ;;
        it:terminal) echo 'Questa interfaccia richiede un terminale.' ;;
        it:options) echo '--tui non può essere combinato con altre opzioni CLI.' ;;
        it:unavailable) echo 'Interfaccia terminale non disponibile.' ;;
        it:fallback) echo 'Interfaccia terminale non disponibile. Avvio della CLI.' ;;
        pt:terminal) echo 'Esta interface requer um terminal.' ;;
        pt:options) echo '--tui não pode ser combinado com outras opções CLI.' ;;
        pt:unavailable) echo 'Interface de terminal indisponível.' ;;
        pt:fallback) echo 'Interface de terminal indisponível. Iniciando CLI.' ;;
        *:terminal) echo 'A terminal is required for the terminal interface.' ;;
        *:options) echo '--tui cannot be combined with other CLI options.' ;;
        *:unavailable) echo 'Terminal interface unavailable.' ;;
        *) echo 'Terminal interface unavailable. Starting CLI.' ;;
    esac >&2
}

# This guard resolves Apple developer shims without starting an installer.
if ! type mac_update_tool_usable >/dev/null 2>&1; then
    . "$SCRIPT_DIR/lib/platform.sh"
fi

mac_update_tui_route() {
    local view="$1" arg explicit=0 force_cli=0
    shift
    MAC_UPDATE_TUI_ARGS=()
    MAC_UPDATE_TUI_STARTED=0
    for arg in "$@"; do
        case "$arg" in
            --tui) explicit=1 ;;
            --cli) force_cli=1 ;;
            *) MAC_UPDATE_TUI_ARGS[${#MAC_UPDATE_TUI_ARGS[@]}]="$arg" ;;
        esac
    done
    [ "$force_cli" = 1 ] && return 0
    [ "${MAC_UPDATE_TUI_CHILD:-0}" = 1 ] && return 0
    if [ "$explicit" = 1 ] && [ ${#MAC_UPDATE_TUI_ARGS[@]} -gt 0 ]; then
        mac_update_tui_message options
        MAC_UPDATE_TUI_STARTED=1
        return 2
    fi
    if [ "$explicit" = 0 ]; then
        [ ${#MAC_UPDATE_TUI_ARGS[@]} -eq 0 ] || return 0
        [ "${MAC_UPDATE_NONINTERACTIVE:-0}" != 1 ] || return 0
        [ -t 0 ] && [ -t 1 ] || return 0
    elif [ ! -t 0 ] || [ ! -t 1 ] || [ "${MAC_UPDATE_NONINTERACTIVE:-0}" = 1 ]; then
        mac_update_tui_message terminal
        MAC_UPDATE_TUI_STARTED=1
        return 2
    fi
    if [ "${TERM:-dumb}" = dumb ] || ! mac_update_tool_usable python3 ||
       ! PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c 'import curses, terminal_app' >/dev/null 2>&1; then
        if [ "$explicit" = 1 ]; then
            mac_update_tui_message unavailable
            MAC_UPDATE_TUI_STARTED=1
            return 2
        fi
        mac_update_tui_message fallback
        return 0
    fi
    MAC_UPDATE_TUI_STARTED=1
    PYTHONPATH="$SCRIPT_DIR/lib/python${PYTHONPATH:+:$PYTHONPATH}" python3 -c 'import sys; from terminal_app import run; sys.exit(run(sys.argv[1], sys.argv[2]))' "$SCRIPT_DIR" "$view"
}
