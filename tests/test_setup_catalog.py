"""The optional public catalog never implies installation or prior consent."""

import copy
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
import setup_catalog

RECIPE = dict(
    id="fixture",
    product_id="fixture-gui",
    name="Fixture",
    edition="gui",
    sources=[
        dict(
            source_id="vendor",
            official_url="https://example.org/download",
            architectures=["arm64"],
        )
    ],
    architectures=["arm64"],
    minimum_os="13",
    channel="stable",
    license_review="unknown",
    install_adapter=None,
    first_install_acceptance=None,
    requirements_known=False,
)


class CatalogTests(unittest.TestCase):
    def test_public_catalog_does_not_require_any_private_inventory(self):
        catalog = setup_catalog.load_setup_catalog()
        view = setup_catalog.build_catalog_view({}, catalog, [], {})
        self.assertEqual(len(view["rows"]), 48)
        self.assertEqual(view["registry_rows"], 47)
        self.assertTrue(all(row["selected"] is False for row in view["rows"]))
        self.assertTrue(
            all(row["installation_status"] == ("manager_delegated" if row["product_id"] == "keepassxc-gui" else "manual") for row in view["rows"])
        )

    def test_installed_products_offer_review_or_manual_migration(self):
        view = setup_catalog.build_catalog_view(
            {
                "instances": [
                    dict(
                        product_id="fixture-gui",
                        edition="gui",
                        presence="present",
                        source="homebrew",
                    )
                ]
            },
            {"recipes": [RECIPE]},
            [],
            {},
        )
        row = view["rows"][0]
        self.assertTrue(row["installed"])
        self.assertFalse(row["selected"])
        self.assertEqual(row["installation_status"], "already_installed")

    def test_selection_is_plain_data_and_invalid_source_or_edition_rejected(self):
        view = setup_catalog.build_catalog_view({}, {"recipes": [RECIPE]}, [], {})
        self.assertEqual(
            setup_catalog.parse_selections("1", view),
            [dict(product_id="fixture-gui", source_id="vendor", edition="gui")],
        )
        for text in ["1:npm", "0", "99", "1; touch x", "1:vendor:cli"]:
            with self.assertRaises(ValueError):
                setup_catalog.parse_selections(text, view)
        for text in ["", "cancel", "back", "q"]:
            self.assertEqual(setup_catalog.parse_selections(text, view), [])

    def test_installed_selection_is_manual_and_no_automatic_migration(self):
        view = setup_catalog.build_catalog_view(
            {
                "instances": [
                    dict(product_id="fixture-gui", edition="gui", presence="present")
                ]
            },
            {"recipes": [RECIPE]},
            [],
            {},
        )
        self.assertEqual(
            setup_catalog.parse_selections("1", view)[0]["product_id"], "fixture-gui"
        )
        self.assertEqual(view["rows"][0]["installation_status"], "already_installed")


class CatalogShellTests(unittest.TestCase):
    def test_pythonless_preview_never_installs_python_or_mas(self):
        from tests._policy_fixtures import PolicyFixture

        with PolicyFixture() as fixture:
            (fixture.bin / "python3").unlink()
            fixture.shell("python3", "exit 1")
            marker = fixture.root / "bootstrap"
            for tool in ("brew", "mas", "curl", "open"):
                fixture.shell(tool, 'echo called > "' + str(marker) + '"; exit 1')
            import subprocess

            root = Path(__file__).resolve().parents[1]
            result = subprocess.run(
                ["/bin/bash", str(root / "setup.sh"), "--catalog"],
                capture_output=True,
                text=True,
                env=dict(os.environ),
                timeout=10,
            )
            self.assertEqual(result.returncode, 10, result.stdout + result.stderr)
            self.assertIn("Python", result.stdout)
            self.assertIn("preview", result.stdout.lower())
            self.assertFalse(marker.exists())

    def test_fresh_terminal_selection_requires_digest_then_opens_only_one_manual_url(
        self,
    ):
        import os, pty, re, select, subprocess, time
        from tests._policy_fixtures import PolicyFixture

        with PolicyFixture() as fixture:
            marker = fixture.root / "opened"
            fixture.shell("open", 'printf "%s\\n" "$*" >> "' + str(marker) + '"')
            env = dict(os.environ, MAC_UPDATE_YES="0", MAC_UPDATE_NONINTERACTIVE="0")
            root = Path(__file__).resolve().parents[1]
            master, slave = pty.openpty()
            process = subprocess.Popen(
                ["/bin/bash", str(root / "setup.sh"), "--catalog"],
                env=env,
                stdin=slave,
                stdout=slave,
                stderr=slave,
            )
            os.close(slave)
            captured = bytearray()

            def until(pattern):
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    match = re.search(pattern, captured.decode(errors="replace"))
                    if match:
                        return match
                    if process.poll() is not None:
                        break
                    ready, _, _ = select.select([master], [], [], 0.1)
                    if ready:
                        try:
                            captured.extend(os.read(master, 65536))
                        except OSError:
                            break
                self.fail(
                    "catalog prompt not observed: "
                    + captured.decode(errors="replace")[-1500:]
                )

            try:
                until(r"Choose numbers")
                self.assertFalse(marker.exists())
                os.write(master, b"1\n")
                token = until(r"approve ([0-9a-f]{12})").group(1)
                self.assertFalse(marker.exists(), "selection/preview is never consent")
                os.write(master, ("approve " + token + "\n").encode())
                until(r"Press Enter after manual acquisition")
                os.write(master, b"back\n")
                process.wait(timeout=10)
                self.assertEqual(
                    process.returncode, 0, captured.decode(errors="replace")
                )
                self.assertEqual(
                    marker.read_text().splitlines(), ["https://www.google.com/chrome/"]
                )
                self.assertEqual(
                    list((fixture.root / "Applications").glob("*.app")), [fixture.app]
                )
                journals = list(
                    (fixture.state / "installation-transactions").glob("*.json")
                )
                import json

                result = json.loads(journals[0].read_text())
                self.assertEqual(result["status"], "manual_acquisition_opened")
                self.assertFalse(result["verified"])
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                os.close(master)


class CatalogManualFlowTests(unittest.TestCase):
    def test_each_manual_action_gets_fresh_identity_and_late_conflict_blocks_open(self):
        import io
        import tempfile
        from unittest.mock import patch
        import install_execution
        from install_plan import build_install_plan
        from policy_runtime import utc_now

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            state = root / "state"
            state.mkdir(mode=0o700)
            second = dict(
                copy.deepcopy(RECIPE), id="other", product_id="other-gui", name="Other"
            )
            second["sources"][0]["official_url"] = "https://example.org/other"
            recipes = {"recipes": [copy.deepcopy(RECIPE), second]}
            baseline = {"instances": [], "packages": []}
            plan = build_install_plan(
                [
                    dict(product_id=p, source_id="vendor", edition="gui")
                    for p in ("fixture-gui", "other-gui")
                ],
                baseline,
                recipes,
                utc_now(),
            )
            late = {
                "instances": [
                    dict(product_id="other-gui", edition="gui", presence="present")
                ],
                "packages": [],
            }
            opened = []
            results = []
            execute = install_execution.execute_install_action

            def checked(*args, **kwargs):
                result = execute(*args, **kwargs, opener=lambda url: opened.append(url))
                results.append(result)
                return result

            with (
                patch.dict(
                    os.environ, {"HOME": str(root), "MAC_UPDATE_STATE_DIR": str(state)}
                ),
                patch.object(setup_catalog, "_interactive", return_value=True),
                patch.object(
                    setup_catalog,
                    "_answer",
                    return_value="approve " + plan["plan_digest"][:12],
                ),
                patch.object(
                    setup_catalog, "_rescan_requested", return_value=False, create=True
                ),
                patch(
                    "inventory_migration.collect_current_snapshot",
                    side_effect=[baseline, late],
                ) as collect,
                patch.object(install_execution, "_roots", return_value=[]),
                patch.object(
                    install_execution, "execute_install_action", side_effect=checked
                ),
            ):
                code = setup_catalog.approve_install_preview(
                    plan, recipes, baseline, io.StringIO(), io.StringIO()
                )
            self.assertEqual(collect.call_count, 2)
            self.assertEqual(opened, ["https://example.org/download"])
            self.assertEqual(results[1]["reason_code"], "source_conflict")
            self.assertEqual(code, 10)

    def test_optional_rescan_reports_observed_install_without_changing_acquisition_result(
        self,
    ):
        import io, json, tempfile
        from unittest.mock import patch
        import install_execution
        from install_plan import build_install_plan
        from policy_runtime import utc_now

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            state = root / "state"
            state.mkdir(mode=0o700)
            app = root / "Fixture.app"
            recipes = {"recipes": [RECIPE]}
            baseline = {"instances": [], "packages": []}
            plan = build_install_plan(
                [dict(product_id="fixture-gui", source_id="vendor", edition="gui")],
                baseline,
                recipes,
                utc_now(),
            )

            def observe(*args, **kwargs):
                present = app.is_dir()
                return {
                    "instances": [
                        dict(
                            instance_id="observed",
                            product_id="fixture-gui",
                            edition="gui",
                            name="Fixture",
                            presence="present",
                            freshness="fresh",
                            short_version=(app / "version").read_text(),
                            source_id="app_store",
                            path=str(app),
                        )
                    ]
                    if present
                    else [],
                    "packages": [],
                }

            def opened(url):
                self.assertEqual(url, "https://example.org/download")
                app.mkdir()
                (app / "version").write_text("2.0.0")

            execute = install_execution.execute_install_action

            def checked(*args, **kwargs):
                return execute(*args, **kwargs, opener=opened)

            output = io.StringIO()
            with (
                patch.dict(
                    os.environ, {"HOME": str(root), "MAC_UPDATE_STATE_DIR": str(state)}
                ),
                patch.object(setup_catalog, "_interactive", return_value=True),
                patch.object(
                    setup_catalog,
                    "_answer",
                    return_value="approve " + plan["plan_digest"][:12],
                ),
                patch.object(
                    setup_catalog, "_rescan_requested", return_value=True, create=True
                ),
                patch(
                    "inventory_migration.collect_current_snapshot", side_effect=observe
                ) as collect,
                patch.object(install_execution, "_roots", return_value=[]),
                patch.object(
                    install_execution, "execute_install_action", side_effect=checked
                ),
            ):
                code = setup_catalog.approve_install_preview(
                    plan, recipes, baseline, io.StringIO(), output
                )
            self.assertEqual(code, 0)
            self.assertEqual(collect.call_count, 2)
            self.assertIn("App Store", output.getvalue())
            self.assertIn("2.0.0", output.getvalue())
            self.assertNotIn("installed_verified", output.getvalue())
            journal = json.loads(
                next((state / "installation-transactions").glob("*.json")).read_text()
            )
            self.assertEqual(journal["status"], "manual_acquisition_opened")
            self.assertFalse(journal["verified"])

    def test_optional_rescan_eof_back_and_timeout_do_not_scan(self):
        import io
        from unittest.mock import patch

        for reply in ("", "back\n", "cancel\n"):
            with (
                self.subTest(reply=reply),
                patch("select.select", return_value=([object()], [], [])),
            ):
                self.assertFalse(
                    setup_catalog._rescan_requested(io.StringIO(reply), timeout=1)
                )
        with patch("select.select", return_value=([], [], [])):
            self.assertFalse(
                setup_catalog._rescan_requested(io.StringIO("\n"), timeout=1)
            )
        with patch("select.select", return_value=([object()], [], [])):
            self.assertTrue(
                setup_catalog._rescan_requested(io.StringIO("\n"), timeout=1)
            )
