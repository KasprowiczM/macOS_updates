"""Independent E acceptance: public catalog facts and deny-by-default shell flows."""

import json
import os
import shutil
import subprocess
import select
import time
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib/python"))
from setup_catalog import load_setup_catalog, build_catalog_view, parse_selections
from install_plan import (
    build_install_plan,
    install_recipe_eligible,
    resolve_requirements,
)
from channel_probes import load_channel_sources
from policy_runtime import load_plan

NOW = "2026-11-13T12:00:00Z"


class PublicCatalogAcceptanceTests(unittest.TestCase):
    def test_public_manifest_research_covers_each_registry_row_and_split_product(self):
        manifest = load_channel_sources()
        registry = [
            line.split("|")[0]
            for line in (ROOT / "config/internet_app_methods.txt")
            .read_text()
            .splitlines()
            if line.strip() and not line.startswith("#")
        ]
        self.assertEqual([row["name"] for row in manifest["registry_rows"]], registry)
        products = {row["product_id"]: row for row in manifest["products"]}
        self.assertEqual(len(products), 48)
        self.assertEqual(len(manifest["registry_rows"]), 47)
        for row in manifest["registry_rows"]:
            self.assertTrue(row["product_ids"])
            for product_id in row["product_ids"]:
                product = products[product_id]
                self.assertEqual(product["research_row"], row["row"])
                self.assertTrue(product["research_evidence"])
                self.assertTrue(product["research_summary"])
                self.assertFalse(product["installation_authority"])
        self.assertEqual(
            set(
                next(
                    row["product_ids"]
                    for row in manifest["registry_rows"]
                    if row["name"] == "ChatGPT / Codex"
                )
            ),
            {"chatgpt-gui", "codex-gui"},
        )

    def test_public_catalog_has_zero_verified_first_installs_and_no_machine_data(self):
        catalog = load_setup_catalog()
        with (
            patch(
                "socket.create_connection", side_effect=AssertionError("network denied")
            ),
            patch(
                "subprocess.run", side_effect=AssertionError("native commands denied")
            ),
        ):
            view = build_catalog_view({}, catalog, [], {})
        self.assertEqual(view["selected"], [])
        self.assertEqual(
            sum(install_recipe_eligible(row) for row in catalog["recipes"]), 0
        )
        self.assertTrue(
            all(row["installation_status"] == "manual" for row in view["rows"])
        )
        for row in view["rows"]:
            self.assertFalse(row["selected"])
            self.assertEqual(row["evidence_level"], "metadata_only")
            self.assertFalse(row["installed"])
            for source in row["sources"]:
                if source["official_url"]:
                    url = urlsplit(source["official_url"])
                    self.assertEqual(url.scheme, "https")
                    self.assertIsNone(url.username)
                    self.assertIsNone(url.password)
                    self.assertFalse(
                        set(parse_qs(url.query))
                        & {"token", "password", "secret", "api_key", "access_token"}
                    )
        serialized = json.dumps(view)
        for private in (
            "/Users/",
            "/private/var/",
            "kpxc://",
            "receipt_data",
            "account_email",
        ):
            self.assertNotIn(private, serialized)

    def test_public_selections_remain_manual_and_empty_selection_has_no_dependencies(
        self,
    ):
        catalog = load_setup_catalog()
        view = build_catalog_view({}, catalog, [], {})
        for text in ("", "cancel", "back", "q"):
            selections = parse_selections(text, view)
            plan = build_install_plan(selections, {}, catalog, NOW)
            self.assertEqual(plan["actions"], [])
            self.assertEqual(plan["requirements"]["nodes"], [])
        # Selecting public metadata explicitly still cannot create install authority.
        choices = []
        for row in view["rows"]:
            if row["sources"]:
                choices.append(
                    dict(
                        product_id=row["product_id"],
                        edition=row["edition"],
                        source_id=row["sources"][0]["source_id"],
                    )
                )
        plan = build_install_plan(choices, {}, catalog, NOW)
        self.assertTrue(plan["actions"])
        self.assertTrue(
            all(action["kind"] == "manual_acquisition" for action in plan["actions"])
        )
        self.assertTrue(
            all(action["artifact_effects"] == [] for action in plan["actions"])
        )

    def test_two_selected_products_share_only_their_one_required_dependency(self):
        recipe = dict(
            product_id="one-gui",
            id="one",
            name="One",
            edition="gui",
            sources=[dict(source_id="vendor", official_url="https://example.org/one")],
            requirements=["shared"],
        )
        unrelated = dict(
            recipe, product_id="unselected-gui", requirements=["unselected-tool"]
        )
        catalog = dict(
            recipes=[recipe, dict(recipe, product_id="two-gui", name="Two"), unrelated],
            requirements={
                "shared": dict(kind="tool", dependencies=[]),
                "unselected-tool": dict(kind="tool", dependencies=[]),
            },
        )
        selections = [
            dict(product_id=product, edition="gui", source_id="vendor")
            for product in ("one-gui", "two-gui")
        ]
        graph = resolve_requirements(selections, {}, catalog)
        self.assertEqual([node["id"] for node in graph["nodes"]], ["shared"])
        self.assertNotIn("unselected-tool", repr(graph))

    def test_update_plan_loader_refuses_even_valid_empty_or_stale_install_plan(self):
        catalog = load_setup_catalog()
        plan = build_install_plan([], {}, catalog, NOW)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "install-plan.json"
            path.write_text(json.dumps(plan))
            path.chmod(0o600)
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                load_plan(str(path))
            self.assertEqual(path.read_bytes(), before)


class CatalogShellAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        for folder in ("lib", "config", "i18n", "templates", "scripts"):
            shutil.copytree(
                ROOT / folder,
                self.repo / folder,
                ignore=shutil.ignore_patterns("__pycache__"),
            )
        (self.repo / "docs").mkdir()
        shutil.copytree(ROOT / "docs/catalog", self.repo / "docs/catalog")
        for file in ROOT.glob("*.sh"):
            shutil.copy2(file, self.repo / file.name)
        shutil.copy2(ROOT / "VERSION", self.repo / "VERSION")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.apps = self.root / "Applications"
        self.apps.mkdir()
        self.log = self.root / "commands"
        for command in (
            "brew",
            "mas",
            "curl",
            "wget",
            "open",
            "osascript",
            "sudo",
            "installer",
            "softwareupdate",
            "npm",
            "n",
        ):
            self.tool(
                command,
                'printf "%s\\n" "'
                + command
                + ' $*" >> "$FIXTURE_COMMAND_LOG"\nexit 97',
            )
        self.tool("uname", "echo arm64")
        self.tool("sw_vers", "echo 26.0")
        self.tool("ps", "exit 0")
        self.tool("pgrep", "exit 1")
        (self.bin / "python3").symlink_to(sys.executable)
        self.network_guard = self.root / "network-guard"
        self.network_guard.mkdir()
        (self.network_guard / "sitecustomize.py").write_text(
            "import os, socket\n"
            "def denied(*args, **kwargs):\n"
            '    with open(os.environ["FIXTURE_COMMAND_LOG"], "a") as stream: stream.write("NETWORK_DENIED\\n")\n'
            '    raise OSError("fixture network denied")\n'
            "socket.create_connection = denied\n"
            "socket.getaddrinfo = denied\n"
            "socket.socket.connect = denied\n"
            "socket.socket.connect_ex = denied\n"
        )
        self.env = dict(
            os.environ,
            HOME=str(self.root),
            PATH=str(self.bin) + ":/usr/bin:/bin",
            PYTHONPATH=str(self.network_guard),
            MAC_LANG="en",
            MAC_UPDATE_STATE_DIR=str(self.root / "state"),
            MAC_UPDATE_APP_DIRS=str(self.apps),
            MAC_UPDATE_BREW_PREFIXES="",
            MAC_UPDATE_CLI_PREFIXES="",
            MAC_UPDATE_HOMEBREW_PREFIX=str(self.root / "no-brew"),
            FIXTURE_COMMAND_LOG=str(self.log),
            MAC_UPDATE_NO_SUDO="1",
            MAC_UPDATE_NO_CAFFEINATE="1",
            MAC_UPDATE_NONINTERACTIVE="1",
        )
        for key in ("MAC_UPDATE_PLAN_PATH", "MAC_UPDATE_YES", "MAC_UPDATE_DRY_RUN"):
            self.env.pop(key, None)

    def tool(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)

    def run_script(self, script, *args, input_text=None):
        return subprocess.run(
            ["bash", str(self.repo / script), *args],
            cwd=self.repo,
            env=self.env,
            stdin=subprocess.DEVNULL if input_text is None else None,
            input=input_text,
            capture_output=True,
            text=True,
            timeout=20,
        )

    def assert_no_mutations(self):
        commands = self.log.read_text().splitlines() if self.log.exists() else []
        # The bounded signed-out observation is permitted; every other native call
        # is a test failure even if its double refused to perform the mutation.
        self.assertTrue(
            all(
                command == "mas list --json" or command == "mas list"
                for command in commands
            ),
            commands,
        )
        self.assertEqual(list(self.apps.iterdir()), [])
        self.assertFalse((self.root / ".mac_update_prefs").exists())

    def test_scan_and_catalog_noninteractive_or_yes_never_install(self):
        scan = self.run_script("scripts/scan_update_feeds.sh", "--json")
        self.assertEqual(scan.returncode, 0, scan.stdout + scan.stderr)
        self.assertEqual(json.loads(scan.stdout)["detected"], 0)
        for args in (
            ("--catalog",),
            ("--catalog", "-y"),
            ("--catalog", "--non-interactive"),
        ):
            with self.subTest(args=args):
                result = self.run_script("setup.sh", *args)
                self.assertIn(result.returncode, (0, 10), result.stdout + result.stderr)
                self.assertNotIn("installed_verified", result.stdout)
        plan = build_install_plan([], {}, load_setup_catalog(), NOW)
        plan_path = self.root / "no-consent-install-plan.json"
        plan_path.write_text(json.dumps(plan))
        plan_path.chmod(0o600)
        result = self.run_script("setup.sh", "--install-plan", str(plan_path), "-y")
        self.assertIn(result.returncode, (0, 10), result.stdout + result.stderr)
        self.assert_no_mutations()
        self.assertFalse((self.root / "state").exists())

    def test_catalog_empty_selection_and_eof_on_terminal_never_install(self):
        import pty

        for selection in (b"\n", b"\x04", b"1\n\x04"):
            with self.subTest(selection=selection):
                master, slave = pty.openpty()
                env = dict(self.env, MAC_UPDATE_NONINTERACTIVE="0")
                process = subprocess.Popen(
                    ["bash", str(self.repo / "setup.sh"), "--catalog"],
                    cwd=self.repo,
                    env=env,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                )
                os.close(slave)
                try:
                    os.write(master, selection)
                    output = bytearray()
                    deadline = time.monotonic() + 15
                    while process.poll() is None and time.monotonic() < deadline:
                        readable, _, _ = select.select([master], [], [], 0.1)
                        if readable:
                            try:
                                output.extend(os.read(master, 65536))
                            except OSError:
                                break
                    process.wait(timeout=max(0.1, deadline - time.monotonic()))
                    self.assertIn(
                        process.returncode, (0, 10), output.decode(errors="replace")
                    )
                finally:
                    if process.poll() is None:
                        process.kill()
                        process.wait()
                    os.close(master)
        self.assert_no_mutations()

    def test_update_all_refuses_install_plan_flag_and_ignores_install_plan_environment(
        self,
    ):
        plan = build_install_plan([], {}, load_setup_catalog(), NOW)
        path = self.root / "old-install-plan.json"
        path.write_text(json.dumps(plan))
        path.chmod(0o600)
        original = path.read_bytes()
        rejected = self.run_script("update_all.sh", "--install-plan", str(path))
        self.assertNotEqual(rejected.returncode, 0)
        self.env["MAC_UPDATE_PLAN_PATH"] = str(path)
        result = self.run_script(
            "update_all.sh",
            "--dry-run",
            "-y",
            "--skip-prescan",
            "--skip-appstore",
            "--skip-npm",
            "--skip-brew",
            "--skip-internet",
            "--skip-postupdate",
            "--skip-system",
            "--skip-doctor",
        )
        self.assertIn(result.returncode, (0, 10), result.stdout + result.stderr)
        self.assertEqual(path.read_bytes(), original)
        self.assertNotIn("installed_verified", result.stdout)
        self.assert_no_mutations()


class SelectedInstallAcceptanceTests(unittest.TestCase):
    def test_installer_changes_only_one_consented_fixture_and_records_observed_identity(
        self,
    ):
        import install_execution
        from policy_runtime import utc_now

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            apps = root / "Applications"
            apps.mkdir()
            state = root / "state"
            state.mkdir(mode=0o700)
            stage = root / "staged.app"
            stage.mkdir()
            (stage / "version").write_text("2.0.0")

            def recipe(product, name):
                destination = str(apps / (name + ".app"))
                return dict(
                    id=product,
                    product_id=product,
                    name=name,
                    edition="gui",
                    sources=[
                        dict(
                            source_id="vendor",
                            official_url="https://example.org/download",
                            architectures=["arm64"],
                        )
                    ],
                    installation_source="vendor",
                    revision="fixture-revision",
                    version="2.0.0",
                    channel="stable",
                    bundle_id="org.example." + name.lower(),
                    team_id="FIXTURETEAM",
                    architectures=["arm64"],
                    minimum_os="13",
                    download_hosts=["example.org"],
                    artifact_type="app",
                    requires_administrator=False,
                    destination=destination,
                    artifact_effects=[destination],
                    requirements_known=True,
                    requirements=["shared"],
                    install_adapter="vendor_bundle",
                    first_install_acceptance=dict(
                        status="passed",
                        recipe_revision="fixture-revision",
                        version="2.0.0",
                        source_id="vendor",
                    ),
                )

            recipes = dict(
                recipes=[
                    recipe("selected-one", "One"),
                    recipe("selected-two", "Two"),
                    recipe("unselected", "Unselected"),
                ],
                requirements={
                    "shared": dict(
                        kind="tool", dependencies=[], minimum_version="1.0.0"
                    )
                },
            )
            snapshot = dict(
                instances=[], packages=[], environment={"shared": {"version": "1.0.0"}}
            )
            selections = [
                dict(product_id=product, source_id="vendor", edition="gui")
                for product in ("selected-one", "selected-two")
            ]
            plan = build_install_plan(selections, snapshot, recipes, utc_now())
            action = plan["actions"][0]
            consent = install_execution.make_install_consent(
                plan, [action["action_id"]], utc_now()
            )
            observed_writes = []

            def observe(path):
                target = Path(path)
                return dict(
                    exists=target.is_dir(),
                    good=target.is_dir(),
                    receipt_present=False,
                    running=False,
                    bundle_id=action["recipe"]["bundle_id"],
                    team_id="FIXTURETEAM",
                    version=(target / "version").read_text()
                    if target.is_dir()
                    else None,
                    architectures=["arm64"],
                    minimum_os="13",
                    host_os="26",
                )

            def record(actual, observed):
                self.assertTrue(Path(actual["destination"]).is_dir())
                self.assertEqual(observed["bundle_id"], actual["recipe"]["bundle_id"])
                self.assertEqual(observed["version"], "2.0.0")
                observed_writes.append(actual["product_id"])
                return dict(
                    snapshot_id="observed-only-fixture-snapshot",
                    verified_path=actual["destination"],
                )

            with (
                patch.dict(
                    os.environ, {"HOME": str(root), "PATH": str(root / "no-tools")}
                ),
                patch(
                    "subprocess.run",
                    side_effect=AssertionError("native command denied"),
                ),
                patch(
                    "socket.create_connection",
                    side_effect=AssertionError("network denied"),
                ),
            ):
                result = install_execution.execute_install_action(
                    plan,
                    action["action_id"],
                    consent,
                    recipes,
                    snapshot["environment"],
                    staged_app=str(stage),
                    observe=observe,
                    snapshot=snapshot,
                    allowed_roots=[str(apps)],
                    state_dir=str(state),
                    snapshot_writer=record,
                )
                self.assertEqual(result["status"], "installed_verified")
                self.assertEqual(observed_writes, ["selected-one"])
                refused = install_execution.execute_install_action(
                    plan,
                    plan["actions"][1]["action_id"],
                    consent,
                    recipes,
                    snapshot["environment"],
                    staged_app=str(stage),
                    observe=observe,
                    snapshot=snapshot,
                    allowed_roots=[str(apps)],
                    state_dir=str(state),
                    snapshot_writer=record,
                )
                self.assertNotEqual(refused["status"], "installed_verified")
            self.assertEqual([path.name for path in apps.iterdir()], ["One.app"])
            self.assertFalse((apps / "Two.app").exists())
            self.assertFalse((apps / "Unselected.app").exists())
            self.assertEqual(observed_writes, ["selected-one"])
