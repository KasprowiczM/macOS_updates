"""Static manager observations must not become invented ownership."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "lib/python"))


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def test_missing_brew_is_unavailable_not_empty(self):
        from inventory_providers import read_brew_receipts

        result = read_brew_receipts(str(self.root / "missing"))
        self.assertEqual(result["status"], "unavailable")
        self.assertFalse(result["complete"])

    def test_empty_existing_cellar_is_complete(self):
        from inventory_providers import read_brew_receipts

        (self.root / "Cellar").mkdir()
        result = read_brew_receipts(str(self.root))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["items"], [])

    def test_installed_cask_uses_actual_renamed_artifact_link(self):
        from inventory_providers import read_brew_receipts

        cask = self.root / "Caskroom/unrelated-token"
        self.write_json(
            cask / ".metadata/2/20261113/Casks/unrelated-token.json",
            {
                "token": "unrelated-token",
                "version": "2",
                "artifacts": [{"app": ["Source.app", {"target": "Renamed.app"}]}],
            },
        )
        target = self.root / "Custom Applications/Renamed.app"
        target.mkdir(parents=True)
        (cask / "2").mkdir()
        (cask / "2/Source.app").symlink_to(target)
        item = read_brew_receipts(str(self.root))["items"][0]
        self.assertEqual(item["version"], "2")
        self.assertEqual(item["evidence"][0]["artifact_path"], str(target))
        self.assertEqual(item["source_identity"], "cask:unrelated-token")

    def test_unresolved_cask_artifact_is_partial_not_default_appdir(self):
        from inventory_providers import read_brew_receipts

        self.write_json(
            self.root / "Caskroom/demo/.metadata/1/20261113/Casks/demo.json",
            {"token": "demo", "version": "1", "artifacts": [{"app": ["Demo.app"]}]},
        )
        result = read_brew_receipts(str(self.root))
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["complete"])
        self.assertFalse(
            any(e.get("artifact_path") for e in result["items"][0]["evidence"])
        )

    def test_cask_ruby_is_not_executed_and_remains_partial(self):
        from inventory_providers import read_brew_receipts

        path = self.root / "Caskroom/demo/.metadata/1/20261113/Casks/demo.rb"
        path.parent.mkdir(parents=True)
        path.write_text('raise "must not execute"')
        result = read_brew_receipts(str(self.root))
        self.assertEqual(result["status"], "partial")

    def test_cask_metadata_cannot_read_external_file_via_link(self):
        from inventory_providers import read_brew_receipts

        path = self.root / "Caskroom/demo/.metadata/1/20261113/Casks/demo.json"
        path.parent.mkdir(parents=True)
        secret = self.root / "external.json"
        secret.write_text('{"token":"must-not-read"}')
        path.symlink_to(secret)
        result = read_brew_receipts(str(self.root))
        self.assertEqual(result["status"], "partial")
        self.assertNotIn("must-not-read", json.dumps(result))

    def test_formula_receipt_is_inventory_not_command_execution(self):
        from inventory_providers import read_brew_receipts

        self.write_json(
            self.root / "Cellar/node/24.0/INSTALL_RECEIPT.json",
            {"installed_on_request": True, "source": {"tap": "homebrew/core"}},
        )
        item = read_brew_receipts(str(self.root))["items"][0]
        self.assertEqual(item["source_identity"], "formula:node")
        self.assertEqual(item["version"], "24.0")
        self.assertTrue(item["explicitly_installed"])

    def test_npm_scoped_manifest_does_not_execute_scripts(self):
        from inventory_providers import read_cli_manifests

        path = self.root / "lib/node_modules/@example/tool/package.json"
        self.write_json(
            path,
            {
                "name": "@example/tool",
                "version": "1.0",
                "scripts": {"postinstall": "must never execute"},
            },
        )
        item = read_cli_manifests(str(self.root))["items"][0]
        self.assertEqual(item["source_identity"], "@example/tool")
        self.assertEqual(item["installed_receipt"], str(path))
        self.assertNotIn("scripts", json.dumps(item))

    def test_external_node_has_unknown_provenance_without_execution(self):
        from inventory_providers import read_cli_manifests

        binary = self.root / "bin/node"
        binary.parent.mkdir()
        binary.write_text("#!/bin/sh\nexit 99\n")
        binary.chmod(0o755)
        item = read_cli_manifests(str(self.root))["items"][0]
        self.assertEqual(item["manager"], "unknown")
        self.assertIsNone(item["installed_receipt"])
        self.assertIsNone(item["version"])

    def test_invalid_or_oversized_manifest_is_partial(self):
        from inventory_providers import read_cli_manifests

        path = self.root / "lib/node_modules/demo/package.json"
        path.parent.mkdir(parents=True)
        path.write_text("x" * (1024 * 1024 + 1))
        result = read_cli_manifests(str(self.root))
        self.assertEqual(result["status"], "partial")
        self.assertFalse(result["complete"])

    def test_mas_empty_failure_and_invalid_json_are_distinct(self):
        from inventory_providers import read_mas

        for code, output, expected in [
            (0, "", "ok"),
            (1, "", "error"),
            (0, "{bad", "error"),
        ]:

            def runner(args, **kw):
                self.assertEqual(args, ["mas", "list", "--json"])
                self.assertLessEqual(kw["timeout"], 10)
                return subprocess.CompletedProcess(args, code, output, "")

            self.assertEqual(read_mas(run=runner)["status"], expected)

    def test_mas_ndjson_does_not_promote_names_to_bundle_identity(self):
        from inventory_providers import read_mas

        def runner(args, **kw):
            return subprocess.CompletedProcess(
                args, 0, '{"adamID":123,"name":"Demo","version":"1"}\n', ""
            )

        item = read_mas(run=runner)["items"][0]
        self.assertEqual(item["store_id"], "123")
        self.assertIsNone(item["bundle_id"])

    def test_mas_missing_and_timeout_never_become_empty_success(self):
        from inventory_providers import read_mas

        for error, status in [
            (FileNotFoundError(), "unavailable"),
            (subprocess.TimeoutExpired("mas", 10), "error"),
        ]:

            def runner(*args, **kw):
                raise error

            self.assertEqual(read_mas(run=runner)["status"], status)

    def test_prefix_discovery_never_uses_path_executables(self):
        from inventory_providers import discover_cli_prefixes

        version = self.root / ".nvm/versions/node/v24"
        version.mkdir(parents=True)
        roots = discover_cli_prefixes(str(self.root), {})
        self.assertIn(str(version), roots)
        self.assertIn(str(self.root / ".local/share/mac-update/npm-global"), roots)
        self.assertNotIn("/evil", roots)

    def test_manager_scan_has_total_entry_budget(self):
        from inventory_providers import read_brew_receipts, _regular_json
        from unittest.mock import patch

        for token in ("a", "b"):
            for version in ("1", "2"):
                self.write_json(
                    self.root / "Cellar" / token / version / "INSTALL_RECEIPT.json", {}
                )
        with (
            patch("inventory_providers.MAX_ENTRIES", 3),
            patch("inventory_providers._regular_json", wraps=_regular_json) as reads,
        ):
            result = read_brew_receipts(str(self.root))
        self.assertLessEqual(reads.call_count, 3)
        self.assertEqual(result["status"], "partial")
        self.assertLess(len(result["items"]), 4)

    def test_symlinked_modules_parent_does_not_supply_packages(self):
        from inventory_providers import read_cli_manifests

        other = self.root / "outside"
        self.write_json(
            other / "node_modules/demo/package.json", {"name": "demo", "version": "1"}
        )
        (self.root / "lib").symlink_to(other)
        result = read_cli_manifests(str(self.root))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["items"], [])
