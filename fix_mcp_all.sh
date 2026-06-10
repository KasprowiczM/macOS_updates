#!/usr/bin/env bash
# ============================================================
# fix_mcp_all.sh — Global MCP Configuration Patcher
# ============================================================
# Finds all mcp_config.json files and applies absolute paths and PATH env.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FIXER_PY="$SCRIPT_DIR/scripts/fix_mcp_configs.py"

# Colors
GREEN='\033[0;32m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${CYAN}Searching for MCP configuration files...${NC}"

# Find mcp_config.json files in common locations (~/.gemini, ~/.codeium, etc.)
# We limit depth to avoid scanning everything.
# Use NUL-terminated records + bash 3.2-compatible array loop to handle paths
# containing spaces or shell-special characters safely.
CONFIG_FILES=()
while IFS= read -r -d '' f; do
    CONFIG_FILES+=("$f")
done < <(find "$HOME" -maxdepth 4 -name "mcp_config.json" -print0 2>/dev/null)

if [ ${#CONFIG_FILES[@]} -eq 0 ]; then
    echo -e "${RED}No mcp_config.json files found.${NC}"
    exit 0
fi

echo -e "${CYAN}Found files:${NC}"
printf '%s\n' "${CONFIG_FILES[@]}"
echo ""

# Run the Python fixer
python3 "$FIXER_PY" "${CONFIG_FILES[@]}"

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ All MCP configurations have been sanitized.${NC}"
else
    echo ""
    echo -e "${RED}❌ Some errors occurred during patching.${NC}"
    exit 1
fi
