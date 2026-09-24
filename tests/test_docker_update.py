#!/usr/bin/env python3
"""Tests for Docker Desktop vendor feed and CLI update flow (T6)."""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent


class DockerUpdateTests(unittest.TestCase):
    """Verify Docker Desktop feed-first behavior and safe engine startup/shutdown."""

    def setUp(self) -> None:
        self.fixtures_dir = REPO_ROOT / "tests" / "fixtures" / "vendor_feeds"

    def test_docker_current_does_not_start_engine(self) -> None:
        """When installed version matches feed, Docker engine is never started."""
        docker_xml = (self.fixtures_dir / "docker_attr.xml").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_curl = bin_dir / "curl"
            mock_curl.write_text(f"""#!/usr/bin/env bash\ncat <<'EOF'\n{docker_xml}\nEOF\n""", encoding="utf-8")
            mock_curl.chmod(mock_curl.stat().st_mode | stat.S_IEXEC)

            log_file = Path(tmpdir) / "docker_calls.log"
            mock_docker = bin_dir / "docker"
            mock_docker.write_text(f"""#!/usr/bin/env bash\necho "$*" >> "{log_file}"\n""", encoding="utf-8")
            mock_docker.chmod(mock_docker.stat().st_mode | stat.S_IEXEC)

            app_dir = Path(tmpdir) / "Applications"
            app_dir.mkdir()
            docker_app = app_dir / "Docker.app"
            docker_app.mkdir()

            cmd = f"""
                export PATH="{bin_dir}:$PATH"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                print_header() {{ :; }}
                print_info() {{ :; }}
                print_ok() {{ :; }}
                print_warn() {{ :; }}
                print_step() {{ :; }}
                internet_msg() {{ printf "$@"; }}
                app_version() {{ echo "4.92.0"; }}
                # Redirect /Applications/Docker.app check
                sed_iu_docker="$(declare -f iu_docker_desktop | sed 's|/Applications/Docker.app|{docker_app}|g')"
                eval "$sed_iu_docker"
                iu_docker_desktop
                echo "STATUS=$STATUS_DOCKER"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("Up to date (4.92.0, vendor feed)", res.stdout)
            # docker CLI must not have been invoked
            if log_file.exists():
                calls = log_file.read_text(encoding="utf-8").strip()
                self.assertEqual(calls, "", f"Expected no docker calls, got: {calls}")

    def test_docker_behind_running_runs_update_quiet(self) -> None:
        """When behind and Docker is already running, run update -q without starting/stopping engine."""
        docker_xml = (self.fixtures_dir / "docker_attr.xml").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_curl = bin_dir / "curl"
            mock_curl.write_text(f"""#!/usr/bin/env bash\ncat <<'EOF'\n{docker_xml}\nEOF\n""", encoding="utf-8")
            mock_curl.chmod(mock_curl.stat().st_mode | stat.S_IEXEC)

            log_file = Path(tmpdir) / "docker_calls.log"
            mock_docker = bin_dir / "docker"
            mock_docker.write_text(f"""#!/usr/bin/env bash
echo "$*" >> "{log_file}"
if [ "$1" = "desktop" ] && [ "$2" = "status" ]; then
    exit 0
fi
exit 0
""", encoding="utf-8")
            mock_docker.chmod(mock_docker.stat().st_mode | stat.S_IEXEC)

            docker_app = Path(tmpdir) / "Applications" / "Docker.app"
            docker_app.mkdir(parents=True)

            cmd = f"""
                export PATH="{bin_dir}:$PATH"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                print_header() {{ :; }}
                print_info() {{ :; }}
                print_ok() {{ :; }}
                print_warn() {{ :; }}
                print_step() {{ :; }}
                internet_msg() {{ printf "$@"; }}
                sleep() {{ :; }}
                current_ver="4.91.0"
                app_version() {{
                    echo "$current_ver"
                }}
                run_with_timeout() {{
                    shift
                    if [ "$1" = "docker" ] && [ "$2" = "desktop" ] && [ "$3" = "update" ]; then
                        current_ver="4.92.0"
                    fi
                    "$@"
                }}
                sed_iu_docker="$(declare -f iu_docker_desktop | sed 's|/Applications/Docker.app|{docker_app}|g')"
                eval "$sed_iu_docker"
                iu_docker_desktop
                echo "STATUS=$STATUS_DOCKER"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("Updated to 4.92.0", res.stdout)
            self.assertTrue(log_file.exists())
            calls = log_file.read_text(encoding="utf-8")
            self.assertIn("desktop update -q", calls)
            self.assertNotIn("desktop start", calls)
            self.assertNotIn("desktop stop", calls)

    def test_docker_behind_not_running_starts_then_stops(self) -> None:
        """When behind and Docker is not running, start engine, run update -q, then stop engine."""
        docker_xml = (self.fixtures_dir / "docker_attr.xml").read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_curl = bin_dir / "curl"
            mock_curl.write_text(f"""#!/usr/bin/env bash\ncat <<'EOF'\n{docker_xml}\nEOF\n""", encoding="utf-8")
            mock_curl.chmod(mock_curl.stat().st_mode | stat.S_IEXEC)

            log_file = Path(tmpdir) / "docker_calls.log"
            status_file = Path(tmpdir) / "running.state"
            mock_docker = bin_dir / "docker"
            mock_docker.write_text(f"""#!/usr/bin/env bash
echo "$*" >> "{log_file}"
if [ "$1" = "desktop" ] && [ "$2" = "status" ]; then
    if [ -f "{status_file}" ]; then
        exit 0
    else
        exit 1
    fi
elif [ "$1" = "desktop" ] && [ "$2" = "start" ]; then
    touch "{status_file}"
    exit 0
elif [ "$1" = "desktop" ] && [ "$2" = "stop" ]; then
    rm -f "{status_file}"
    exit 0
fi
exit 0
""", encoding="utf-8")
            mock_docker.chmod(mock_docker.stat().st_mode | stat.S_IEXEC)

            docker_app = Path(tmpdir) / "Applications" / "Docker.app"
            docker_app.mkdir(parents=True)

            cmd = f"""
                export PATH="{bin_dir}:$PATH"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                print_header() {{ :; }}
                print_info() {{ :; }}
                print_ok() {{ :; }}
                print_warn() {{ :; }}
                print_step() {{ :; }}
                internet_msg() {{ printf "$@"; }}
                sleep() {{ :; }}
                current_ver="4.91.0"
                app_version() {{
                    echo "$current_ver"
                }}
                run_with_timeout() {{
                    shift
                    if [ "$1" = "docker" ] && [ "$2" = "desktop" ] && [ "$3" = "update" ]; then
                        current_ver="4.92.0"
                    fi
                    "$@"
                }}
                sed_iu_docker="$(declare -f iu_docker_desktop | sed 's|/Applications/Docker.app|{docker_app}|g')"
                eval "$sed_iu_docker"
                iu_docker_desktop
                echo "STATUS=$STATUS_DOCKER"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("Updated to 4.92.0", res.stdout)
            self.assertTrue(log_file.exists())
            calls = log_file.read_text(encoding="utf-8")
            self.assertIn("desktop start", calls)
            self.assertIn("desktop update -q", calls)
            self.assertIn("desktop stop", calls)

    def test_docker_feed_unreachable_never_opens_app(self) -> None:
        """When feed is unreachable, Docker is never opened with open -a Docker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_dir = Path(tmpdir) / "bin"
            bin_dir.mkdir()
            mock_curl = bin_dir / "curl"
            mock_curl.write_text("#!/usr/bin/env bash\nexit 22\n", encoding="utf-8")
            mock_curl.chmod(mock_curl.stat().st_mode | stat.S_IEXEC)

            open_log = Path(tmpdir) / "open_calls.log"
            mock_open = bin_dir / "open"
            mock_open.write_text(f"""#!/usr/bin/env bash\necho "$*" >> "{open_log}"\n""", encoding="utf-8")
            mock_open.chmod(mock_open.stat().st_mode | stat.S_IEXEC)

            docker_app = Path(tmpdir) / "Applications" / "Docker.app"
            docker_app.mkdir(parents=True)

            cmd = f"""
                export PATH="{bin_dir}:$PATH"
                source "{REPO_ROOT}/i18n/lang_en.sh"
                source "{REPO_ROOT}/lib/version.sh"
                source "{REPO_ROOT}/lib/vendor_feeds.sh"
                source "{REPO_ROOT}/lib/proc.sh"
                source "{REPO_ROOT}/lib/internet_app_updates.sh"
                print_header() {{ :; }}
                print_info() {{ :; }}
                print_ok() {{ :; }}
                print_warn() {{ :; }}
                print_step() {{ :; }}
                internet_msg() {{ printf "$@"; }}
                app_version() {{ echo "4.91.0"; }}
                sed_iu_docker="$(declare -f iu_docker_desktop | sed 's|/Applications/Docker.app|{docker_app}|g')"
                eval "$sed_iu_docker"
                iu_docker_desktop
                echo "STATUS=$STATUS_DOCKER"
            """
            res = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, check=True)
            self.assertIn("Unknown version", res.stdout)
            if open_log.exists():
                calls = open_log.read_text(encoding="utf-8").strip()
                self.assertEqual(calls, "", f"Expected open not to be called, got: {calls}")


if __name__ == "__main__":
    unittest.main()
