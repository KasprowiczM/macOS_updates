#!/usr/bin/env bash
# Optional catalog display never bootstraps a dependency just to draw a menu.
_SETUP_CATALOG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
setup_catalog_python_ready() {
    if command -v mac_update_tool_usable >/dev/null 2>&1; then
        mac_update_tool_usable python3 || return 1
    else
        command -v python3 >/dev/null 2>&1 || return 1
    fi
    python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' >/dev/null 2>&1
}
setup_catalog_bootstrap_preview() {
    printf '%s\n' "${L_CATALOG_PYTHON_REQUIRED:-Python 3.9 or newer is required for the full catalog and install plan.}"
    printf '%s\n' "${L_CATALOG_PYTHON_PREVIEW:-Limited requirements preview: Python is missing. Install it manually from https://www.python.org/downloads/macos/ and return. Homebrew is optional for a selected Homebrew channel. No dependency was installed.}"
    return 10
}
setup_catalog_menu() {
    setup_catalog_python_ready || { setup_catalog_bootstrap_preview; return 10; }
    PYTHONPATH="$_SETUP_CATALOG_DIR/python${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -c 'import sys; from setup_catalog import catalog_main; sys.exit(catalog_main(sys.argv[1]))' "${SCRIPT_DIR:-$(dirname "$_SETUP_CATALOG_DIR")}"
}
setup_catalog_install_plan() {
    [ "$#" -eq 1 ] || return 1
    setup_catalog_python_ready || { setup_catalog_bootstrap_preview; return 10; }
    PYTHONPATH="$_SETUP_CATALOG_DIR/python${PYTHONPATH:+:$PYTHONPATH}" \
        python3 -c 'import sys; from setup_catalog import catalog_main; sys.exit(catalog_main(sys.argv[1], "install-plan", sys.argv[2]))' "${SCRIPT_DIR:-$(dirname "$_SETUP_CATALOG_DIR")}" "$1"
}
