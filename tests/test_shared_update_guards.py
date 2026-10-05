"""Behavioral checks for shared application and orchestrator guards."""

from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SharedUpdateGuardsTests(unittest.TestCase):
    def test_running_or_unknown_app_is_never_copied_or_quit(self):
        source = (ROOT / "update_internet_apps.sh").read_text()
        helper = source[source.index("replacement_app_is_idle() {"):source.index('. "$SCRIPT_DIR/lib/proc.sh"')]
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "Applications" / "Example.app"
            app.mkdir(parents=True)
            helper = helper.replace("/" + "Applications/", f"{tmp}/Applications/")
            for answer, code in [("true", 0), ("", 1), ("garbled", 0)]:
                script = f'''
print_warn() {{ :; }}
app_bundle_identifier() {{ echo com.example.app; }}
run_with_timeout() {{ echo '{answer}'; return {code}; }}
verify_app_signature() {{ echo BAD_SIGNATURE_CALL; return 0; }}
osascript() {{ echo BAD_QUIT_CALL; }}
{helper}
copy_verified_app /irrelevant/Example.app Example.app
rc=$?
echo "rc=$rc deferred=$INTERNET_COPY_DEFERRED"
'''
                result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("rc=2 deferred=1", result.stdout)
                self.assertNotIn("BAD_", result.stdout)
                self.assertTrue(app.is_dir())

    def test_user_launch_during_staging_preserves_existing_bundle(self):
        source = (ROOT / "update_internet_apps.sh").read_text()
        helper = source[source.index("replacement_app_is_idle() {"):source.index('. "$SCRIPT_DIR/lib/proc.sh"')]
        with tempfile.TemporaryDirectory() as tmp:
            app = Path(tmp) / "Applications" / "Example.app"
            app.mkdir(parents=True)
            (app / "original").write_text("keep")
            helper = helper.replace("/" + "Applications/", f"{tmp}/Applications/")
            script = f'''
print_warn() {{ :; }}
verify_app_signature() {{ return 0; }}
verify_replacement_identity() {{ return 0; }}
ditto() {{ mkdir -p "$2"; }}
{helper}
checks=0
replacement_app_is_idle() {{ checks=$((checks+1)); [ "$checks" -eq 1 ]; }}
copy_verified_app /irrelevant/Example.app Example.app
echo "rc=$? deferred=$INTERNET_COPY_DEFERRED"
'''
            result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
            self.assertIn("rc=2 deferred=1", result.stdout, result.stderr)
            self.assertEqual((app / "original").read_text(), "keep")
            self.assertEqual(list(app.parent.glob(".macupd_*")), [])

    def test_system_soft_warning_propagates_but_user_skip_does_not(self):
        source = (ROOT / "update_all.sh").read_text()
        start = source.index('        SYS_EXIT=$?')
        end = source.index('\n    fi', start)
        branch = source[start:end]
        for user_skip in [False, True]:
            with tempfile.TemporaryDirectory() as tmp:
                if user_skip:
                    (Path(tmp) / "system_skipped_by_user").touch()
                script = f'''SESSION_DIR='{tmp}'
DEGRADED=0
false_status() {{ return 10; }}
false_status
{branch}
echo "$DEGRADED|$STATUS_CODE_SYSTEM"
'''
                result = subprocess.run(["bash", "-c", script], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("0|skipped_by_user" if user_skip else "1|warn", result.stdout)
