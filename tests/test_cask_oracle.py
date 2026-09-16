#!/usr/bin/env python3
"""Tests for Homebrew cask oracle for silent_launch / unverified internet apps (P1-7)."""

import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class CaskOracleBrewHelperTests(unittest.TestCase):
    """Tests for brew_cask_latest_versions in lib/brew.sh."""

    def test_brew_cask_latest_versions_with_mock_brew(self) -> None:
        """Mock brew info --json=v2 --cask returns 3 tokens: current, behind, missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_brew = bin_dir / "brew"

            # Mock brew script
            mock_brew.write_text(
                "#!/usr/bin/env bash\n"
                "if [ \"$1\" = \"info\" ] && [ \"$2\" = \"--json=v2\" ] && [ \"$3\" = \"--cask\" ]; then\n"
                "    shift 3\n"
                "    for arg in \"$@\"; do\n"
                "        if [ \"$arg\" = \"missing-cask\" ]; then\n"
                "            echo \"Error: Cask missing-cask not found\" >&2\n"
                "            exit 1\n"
                "        fi\n"
                "    done\n"
                "    cat <<'EOF'\n"
                "{\n"
                '  "casks": [\n'
                '    {"token": "chatgpt", "version": "26.908.70816", "old_tokens": []},\n'
                '    {"token": "warp", "version": "0.2026.09.09.08.26.stable_02", "old_tokens": []}\n'
                "  ]\n"
                "}\n"
                "EOF\n"
                "    exit 0\n"
                "fi\n"
                "exit 1\n",
                encoding="utf-8",
            )
            mock_brew.chmod(mock_brew.stat().st_mode | stat.S_IEXEC)

            # Test calling brew_cask_latest_versions
            cmd = (
                f'export PATH="{bin_dir}:$PATH"; '
                f'source "{REPO_ROOT}/lib/brew.sh"; '
                'brew_cask_latest_versions chatgpt warp'
            )
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            output = res.stdout.strip().splitlines()
            self.assertEqual(len(output), 2)
            self.assertIn("chatgpt\t26.908.70816", output)
            self.assertIn("warp\t0.2026.09.09.08.26.stable_02", output)

    def test_brew_cask_latest_versions_handles_missing_token(self) -> None:
        """When one token in batch fails, fallback recovers valid tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_brew = bin_dir / "brew"

            mock_brew.write_text(
                "#!/usr/bin/env bash\n"
                "if [ \"$1\" = \"info\" ] && [ \"$2\" = \"--json=v2\" ] && [ \"$3\" = \"--cask\" ]; then\n"
                "    shift 3\n"
                "    # If missing-cask is among args, fail entire call\n"
                "    for arg in \"$@\"; do\n"
                "        if [ \"$arg\" = \"missing-cask\" ]; then\n"
                "            echo \"Error: Cask missing-cask not found\" >&2\n"
                "            exit 1\n"
                "        fi\n"
                "    done\n"
                "    # Otherwise return requested casks\n"
                '    echo "{\\"casks\\": ["\n'
                "    first=1\n"
                "    for arg in \"$@\"; do\n"
                "        [ $first -eq 1 ] || echo \",\"\n"
                "        first=0\n"
                '        echo "{\\"token\\": \\"$arg\\", \\"version\\": \\"1.0.0\\", \\"old_tokens\\": []}"\n'
                "    done\n"
                '    echo "]}"\n'
                "    exit 0\n"
                "fi\n"
                "exit 1\n",
                encoding="utf-8",
            )
            mock_brew.chmod(mock_brew.stat().st_mode | stat.S_IEXEC)

            cmd = (
                f'export PATH="{bin_dir}:$PATH"; '
                f'source "{REPO_ROOT}/lib/brew.sh"; '
                'brew_cask_latest_versions chatgpt missing-cask'
            )
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("chatgpt\t1.0.0", res.stdout)
            self.assertNotIn("missing-cask", res.stdout)


class CaskOracleIntegrationTests(unittest.TestCase):
    """Test oracle version comparison and session artifacts."""

    def test_cask_oracle_evaluation_and_counts(self) -> None:
        """Verify that ChatGPT is verified, Warp is behind, Claude is unverified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            (session_dir / "internet_after.txt").write_text(
                "ChatGPT / Codex|26.908.70816\n"
                "Warp|0.2026.01.01.00.00\n"
                "Claude|2.100.0\n",
                encoding="utf-8",
            )

            # Mock brew returning chatgpt (current) and warp (newer)
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_brew = bin_dir / "brew"
            mock_brew.write_text(
                "#!/usr/bin/env bash\n"
                "cat <<'EOF'\n"
                "{\n"
                '  "casks": [\n'
                '    {"token": "chatgpt", "version": "26.908.70816", "old_tokens": []},\n'
                '    {"token": "warp", "version": "0.2026.09.09.08.26.stable_02", "old_tokens": []}\n'
                "  ]\n"
                "}\n"
                "EOF\n",
                encoding="utf-8",
            )
            mock_brew.chmod(mock_brew.stat().st_mode | stat.S_IEXEC)

            # Run snippet replicating update_internet_apps.sh oracle section
            test_script = fr"""
export PATH="{bin_dir}:$PATH"
export MAC_UPDATE_SESSION_DIR="{session_dir}"
SCRIPT_DIR="{REPO_ROOT}"
source "$SCRIPT_DIR/lib/brew.sh"
source "$SCRIPT_DIR/lib/version.sh"
source "$SCRIPT_DIR/i18n/lang_pl.sh"

STATUS_CHATGPT="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
STATUS_WARP="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
STATUS_CLAUDE_APP="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"

internet_msg() {{
    local fmt="$1"; shift
    printf "$fmt" "$@"
}}

# Run oracle logic
if [ -f "$SCRIPT_DIR/config/cask_oracles.txt" ] && command -v brew >/dev/null 2>&1; then
    _oracle_tokens="chatgpt warp claude"
    _oracle_data="$(brew_cask_latest_versions $_oracle_tokens 2>/dev/null || true)"

    while IFS='|' read -r _o_app _o_token; do
        case "$_o_app" in '#'*|'') continue ;; esac
        _o_app="$(echo "$_o_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _o_token="$(echo "$_o_token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$_o_token" ] || continue

        _o_var=""
        while IFS='|' read -r _m_app _m_meth _m_var; do
            case "$_m_app" in '#'*|'') continue ;; esac
            _m_app="$(echo "$_m_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            if [ "$_m_app" = "$_o_app" ]; then
                _o_var="$(echo "$_m_var" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
                break
            fi
        done < "$SCRIPT_DIR/config/internet_app_methods.txt"

        [ -n "$_o_var" ] || continue
        eval "_cur_st=\$$_o_var"
        case "$_cur_st" in
            *"⏳"*) ;;
            *) continue ;;
        esac

        _cask_ver="$(echo "$_oracle_data" | awk -F'\t' -v tok="$_o_token" '$1 == tok {{print $2; exit}}')"
        [ -n "$_cask_ver" ] || continue

        _bundle_ver=""
        if [ -n "{session_dir}" ] && [ -f "{session_dir}/internet_after.txt" ]; then
            _bundle_ver="$(awk -F'|' -v app="$_o_app" '$1 == app {{print $2; exit}}' "{session_dir}/internet_after.txt")"
        fi

        case "$_bundle_ver" in
            ''|'unknown'|'nieznana'|'null') continue ;;
        esac

        _cask_rel="$(app_vs_package_version_relation "$_cask_ver" "$_bundle_ver" 2>/dev/null || echo "unknown")"

        if [ "$_cask_rel" = "newer" ]; then
            eval "${{_o_var}}=\"\$(internet_msg \"\$L_INTERNET_STATUS_CASK_BEHIND_FMT\" \"\$_bundle_ver\" \"\$_cask_ver\")\""
            printf "%s|%s|%s\n" "$_o_app" "$_bundle_ver" "$_cask_ver" >> "{session_dir}/internet_behind_apps.txt"
        elif [ "$_cask_rel" = "current" ]; then
            eval "${{_o_var}}=\"\$L_INTERNET_STATUS_CASK_CURRENT\""
            printf "%s|%s\n" "$_o_app" "$_bundle_ver" >> "{session_dir}/internet_verified_apps.txt"
        fi
    done < "$SCRIPT_DIR/config/cask_oracles.txt"
fi

echo "STATUS_CHATGPT=$STATUS_CHATGPT"
echo "STATUS_WARP=$STATUS_WARP"
echo "STATUS_CLAUDE_APP=$STATUS_CLAUDE_APP"
"""
            res = subprocess.run(["bash", "-c", test_script], capture_output=True, text=True, check=True)
            self.assertIn("STATUS_CHATGPT=✅ aktualna (cask)", res.stdout)
            self.assertIn("STATUS_WARP=⚠️  w tyle: 0.2026.01.01.00.00 < 0.2026.09.09.08.26.stable_02", res.stdout)
            self.assertIn("STATUS_CLAUDE_APP=⏳ Uruchomiony (niezweryfikowany)", res.stdout)

            # Check recorded files
            behind_content = (session_dir / "internet_behind_apps.txt").read_text(encoding="utf-8")
            self.assertIn("Warp|0.2026.01.01.00.00|0.2026.09.09.08.26.stable_02", behind_content)

            verified_content = (session_dir / "internet_verified_apps.txt").read_text(encoding="utf-8")
            self.assertIn("ChatGPT / Codex|26.908.70816", verified_content)

            # Test run_summary collect_run_items
            import sys
            sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))
            from run_summary import collect_run_items
            items = collect_run_items(str(session_dir))
            warp_item = next((it for it in items if it.get("name") == "Warp"), None)
            self.assertIsNotNone(warp_item)
            self.assertEqual(warp_item.get("status"), "pending")
            self.assertEqual(warp_item.get("category"), "internet")
            self.assertEqual(warp_item.get("old_version"), "0.2026.01.01.00.00")
            self.assertEqual(warp_item.get("new_version"), "0.2026.09.09.08.26.stable_02")


if __name__ == "__main__":
    unittest.main()
