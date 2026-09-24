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
        """Verify that Teams is behind when cask is newer, and unchanged when no cask."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            (session_dir / "internet_after.txt").write_text(
                "Microsoft Teams|24.0.0\n"
                "Claude|2.100.0\n",
                encoding="utf-8",
            )

            # Mock brew returning microsoft-teams (newer)
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_brew = bin_dir / "brew"
            mock_brew.write_text(
                "#!/usr/bin/env bash\n"
                "cat <<'EOF'\n"
                "{\n"
                '  "casks": [\n'
                '    {"token": "microsoft-teams", "version": "24.100.0", "old_tokens": []}\n'
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
source "$SCRIPT_DIR/lib/vendor_feeds.sh"
source "$SCRIPT_DIR/i18n/lang_pl.sh"

STATUS_TEAMS="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"
STATUS_CLAUDE_APP="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"

internet_msg() {{
    local fmt="$1"; shift
    printf "$fmt" "$@"
}}

# Run oracle logic
if [ -f "$SCRIPT_DIR/config/cask_oracles.txt" ] && command -v brew >/dev/null 2>&1; then
    _oracle_tokens="microsoft-teams claude"
    _oracle_data="$(brew_cask_latest_versions $_oracle_tokens 2>/dev/null || true)"

    while IFS='|' read -r _o_app _o_token; do
        case "$_o_app" in '#'*|'') continue ;; esac
        _o_app="$(echo "$_o_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _o_token="$(echo "$_o_token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$_o_token" ] || continue

        # v1.5.0 (T3): Skip apps that have a vendor feed in config/vendor_feeds.txt
        if vendor_feed_row "$_o_app" >/dev/null 2>&1; then
            continue
        fi

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

        _cask_rel="$(version_cmp "$_cask_ver" "$_bundle_ver")"

        if [ "$_cask_rel" = "newer" ]; then
            eval "${{_o_var}}=\"\$(internet_msg \"\$L_INTERNET_STATUS_CASK_BEHIND_FMT\" \"\$_bundle_ver\" \"\$_cask_ver\")\""
            printf "%s|%s|%s\n" "$_o_app" "$_bundle_ver" "$_cask_ver" >> "{session_dir}/internet_behind_apps.txt"
        elif [ "$_cask_rel" = "equal" ]; then
            eval "${{_o_var}}=\"\$L_INTERNET_STATUS_CASK_CURRENT\""
            printf "%s|%s\n" "$_o_app" "$_bundle_ver" >> "{session_dir}/internet_verified_apps.txt"
        fi
        # older / unknown -> no change of status (remains ⏳)
    done < "$SCRIPT_DIR/config/cask_oracles.txt"
fi

echo "STATUS_TEAMS=$STATUS_TEAMS"
echo "STATUS_CLAUDE_APP=$STATUS_CLAUDE_APP"
"""
            res = subprocess.run(["bash", "-c", test_script], capture_output=True, text=True, check=True)
            self.assertIn("STATUS_TEAMS=⚠️  w tyle: 24.0.0 < 24.100.0", res.stdout)
            self.assertIn("STATUS_CLAUDE_APP=⏳ Uruchomiony (niezweryfikowany)", res.stdout)

            # Check recorded files
            behind_content = (session_dir / "internet_behind_apps.txt").read_text(encoding="utf-8")
            self.assertIn("Microsoft Teams|24.0.0|24.100.0", behind_content)

            # Test run_summary collect_run_items
            import sys
            sys.path.insert(0, str(REPO_ROOT / "lib" / "python"))
            from run_summary import collect_run_items
            items = collect_run_items(str(session_dir))
            teams_item = next((it for it in items if it.get("name") == "Microsoft Teams"), None)
            self.assertIsNotNone(teams_item)
            self.assertEqual(teams_item.get("status"), "pending")
            self.assertEqual(teams_item.get("category"), "internet")
            self.assertEqual(teams_item.get("old_version"), "24.0.0")
            self.assertEqual(teams_item.get("new_version"), "24.100.0")

    def test_cask_oracle_equal_verifies(self) -> None:
        """Verify that Teams is marked current when cask version equals bundle version."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            (session_dir / "internet_after.txt").write_text(
                "Microsoft Teams|24.100.0\n",
                encoding="utf-8",
            )

            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_brew = bin_dir / "brew"
            mock_brew.write_text(
                "#!/usr/bin/env bash\n"
                "cat <<'EOF'\n"
                "{\n"
                '  "casks": [\n'
                '    {"token": "microsoft-teams", "version": "24.100.0", "old_tokens": []}\n'
                "  ]\n"
                "}\n"
                "EOF\n",
                encoding="utf-8",
            )
            mock_brew.chmod(mock_brew.stat().st_mode | stat.S_IEXEC)

            test_script = fr"""
export PATH="{bin_dir}:$PATH"
export MAC_UPDATE_SESSION_DIR="{session_dir}"
SCRIPT_DIR="{REPO_ROOT}"
source "$SCRIPT_DIR/lib/brew.sh"
source "$SCRIPT_DIR/lib/version.sh"
source "$SCRIPT_DIR/lib/vendor_feeds.sh"
source "$SCRIPT_DIR/i18n/lang_pl.sh"

STATUS_TEAMS="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"

if [ -f "$SCRIPT_DIR/config/cask_oracles.txt" ] && command -v brew >/dev/null 2>&1; then
    _oracle_tokens="microsoft-teams"
    _oracle_data="$(brew_cask_latest_versions $_oracle_tokens 2>/dev/null || true)"

    while IFS='|' read -r _o_app _o_token; do
        case "$_o_app" in '#'*|'') continue ;; esac
        _o_app="$(echo "$_o_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _o_token="$(echo "$_o_token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$_o_token" ] || continue
        if vendor_feed_row "$_o_app" >/dev/null 2>&1; then continue; fi

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
        _cask_ver="$(echo "$_oracle_data" | awk -F'\t' -v tok="$_o_token" '$1 == tok {{print $2; exit}}')"
        [ -n "$_cask_ver" ] || continue
        _bundle_ver="24.100.0"
        _cask_rel="$(version_cmp "$_cask_ver" "$_bundle_ver")"
        if [ "$_cask_rel" = "equal" ]; then
            eval "${{_o_var}}=\"\$L_INTERNET_STATUS_CASK_CURRENT\""
            printf "%s|%s\n" "$_o_app" "$_bundle_ver" >> "{session_dir}/internet_verified_apps.txt"
        fi
    done < "$SCRIPT_DIR/config/cask_oracles.txt"
fi

echo "STATUS_TEAMS=$STATUS_TEAMS"
"""
            res = subprocess.run(["bash", "-c", test_script], capture_output=True, text=True, check=True)
            self.assertIn("STATUS_TEAMS=✅ aktualna (cask)", res.stdout)
            verified_content = (session_dir / "internet_verified_apps.txt").read_text(encoding="utf-8")
            self.assertIn("Microsoft Teams|24.100.0", verified_content)


    def test_cask_older_than_bundle_does_not_verify(self) -> None:
        """# Changed in v1.5.0: cask older than bundle is NOT marked current (status remains unverified / ⏳)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            (session_dir / "internet_after.txt").write_text(
                "Microsoft Teams|25.0.0\n",
                encoding="utf-8",
            )

            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_brew = bin_dir / "brew"
            # Cask version 24.0.0 is OLDER than installed bundle 25.0.0
            mock_brew.write_text(
                "#!/usr/bin/env bash\n"
                "cat <<'EOF'\n"
                "{\n"
                '  "casks": [\n'
                '    {"token": "microsoft-teams", "version": "24.0.0", "old_tokens": []}\n'
                "  ]\n"
                "}\n"
                "EOF\n",
                encoding="utf-8",
            )
            mock_brew.chmod(mock_brew.stat().st_mode | stat.S_IEXEC)

            test_script = fr"""
export PATH="{bin_dir}:$PATH"
export MAC_UPDATE_SESSION_DIR="{session_dir}"
SCRIPT_DIR="{REPO_ROOT}"
source "$SCRIPT_DIR/lib/brew.sh"
source "$SCRIPT_DIR/lib/version.sh"
source "$SCRIPT_DIR/lib/vendor_feeds.sh"
source "$SCRIPT_DIR/i18n/lang_pl.sh"

STATUS_TEAMS="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"

internet_msg() {{
    local fmt="$1"; shift
    printf "$fmt" "$@"
}}

if [ -f "$SCRIPT_DIR/config/cask_oracles.txt" ] && command -v brew >/dev/null 2>&1; then
    _oracle_tokens="microsoft-teams"
    _oracle_data="$(brew_cask_latest_versions $_oracle_tokens 2>/dev/null || true)"

    while IFS='|' read -r _o_app _o_token; do
        case "$_o_app" in '#'*|'') continue ;; esac
        _o_app="$(echo "$_o_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _o_token="$(echo "$_o_token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$_o_token" ] || continue
        if vendor_feed_row "$_o_app" >/dev/null 2>&1; then continue; fi

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

        # Changed in v1.5.0: version_cmp is used instead of app_vs_package_version_relation
        _cask_rel="$(version_cmp "$_cask_ver" "$_bundle_ver")"

        if [ "$_cask_rel" = "newer" ]; then
            eval "${{_o_var}}=\"\$(internet_msg \"\$L_INTERNET_STATUS_CASK_BEHIND_FMT\" \"\$_bundle_ver\" \"\$_cask_ver\")\""
        elif [ "$_cask_rel" = "equal" ]; then
            eval "${{_o_var}}=\"\$L_INTERNET_STATUS_CASK_CURRENT\""
        fi
        # older / unknown -> no change of status (remains ⏳)
    done < "$SCRIPT_DIR/config/cask_oracles.txt"
fi

echo "STATUS_TEAMS=$STATUS_TEAMS"
"""
            res = subprocess.run(["bash", "-c", test_script], capture_output=True, text=True, check=True)
            # Must remain unverified! Not current!
            self.assertIn("STATUS_TEAMS=⏳ Uruchomiony (niezweryfikowany)", res.stdout)
            self.assertFalse((session_dir / "internet_verified_apps.txt").exists())

    def test_cask_oracle_skips_apps_with_vendor_feeds(self) -> None:
        """Apps that have a vendor feed in config/vendor_feeds.txt are skipped by the cask oracle."""
        with tempfile.TemporaryDirectory() as tmpdir:
            session_dir = Path(tmpdir) / "session"
            session_dir.mkdir()
            (session_dir / "internet_after.txt").write_text(
                "ChatGPT / Codex|26.908.70816\n",
                encoding="utf-8",
            )

            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_brew = bin_dir / "brew"
            mock_brew.write_text(
                "#!/usr/bin/env bash\n"
                "cat <<'EOF'\n"
                "{\n"
                '  "casks": [\n'
                '    {"token": "chatgpt", "version": "26.908.70816", "old_tokens": []}\n'
                "  ]\n"
                "}\n"
                "EOF\n",
                encoding="utf-8",
            )
            mock_brew.chmod(mock_brew.stat().st_mode | stat.S_IEXEC)

            test_script = fr"""
export PATH="{bin_dir}:$PATH"
export MAC_UPDATE_SESSION_DIR="{session_dir}"
SCRIPT_DIR="{REPO_ROOT}"
source "$SCRIPT_DIR/lib/brew.sh"
source "$SCRIPT_DIR/lib/version.sh"
source "$SCRIPT_DIR/lib/vendor_feeds.sh"
source "$SCRIPT_DIR/i18n/lang_pl.sh"

STATUS_CHATGPT="$L_INTERNET_STATUS_LAUNCHED_UNVERIFIED"

if [ -f "$SCRIPT_DIR/config/cask_oracles.txt" ] && command -v brew >/dev/null 2>&1; then
    _oracle_tokens="chatgpt"
    _oracle_data="$(brew_cask_latest_versions $_oracle_tokens 2>/dev/null || true)"

    while IFS='|' read -r _o_app _o_token; do
        case "$_o_app" in '#'*|'') continue ;; esac
        _o_app="$(echo "$_o_app" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        _o_token="$(echo "$_o_token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        [ -n "$_o_token" ] || continue

        # v1.5.0: Skip apps in vendor_feeds.txt
        if vendor_feed_row "$_o_app" >/dev/null 2>&1; then
            continue
        fi

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
        _cask_ver="$(echo "$_oracle_data" | awk -F'\t' -v tok="$_o_token" '$1 == tok {{print $2; exit}}')"
        _bundle_ver="26.908.70816"
        _cask_rel="$(version_cmp "$_cask_ver" "$_bundle_ver")"
        if [ "$_cask_rel" = "equal" ]; then
            eval "${{_o_var}}=\"\$L_INTERNET_STATUS_CASK_CURRENT\""
        fi
    done < "$SCRIPT_DIR/config/cask_oracles.txt"
fi

echo "STATUS_CHATGPT=$STATUS_CHATGPT"
"""
            res = subprocess.run(["bash", "-c", test_script], capture_output=True, text=True, check=True)
            # Since ChatGPT / Codex is in vendor_feeds.txt, it is skipped by oracle and remains ⏳
            self.assertIn("STATUS_CHATGPT=⏳ Uruchomiony (niezweryfikowany)", res.stdout)


if __name__ == "__main__":
    unittest.main()

