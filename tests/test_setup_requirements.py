from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
from install_plan import resolve_requirements
from tests.test_setup_catalog import RECIPE


class RequirementsTests(unittest.TestCase):
    def selection(self):
        return [dict(product_id="fixture-gui", source_id="vendor", edition="gui")]

    def recipes(self, requirements):
        return {
            "recipes": [dict(RECIPE, requirements=["tool"])],
            "requirements": requirements,
        }

    def test_existing_newer_tool_is_satisfied_without_reinstall(self):
        result = resolve_requirements(
            self.selection(),
            {"tool": {"version": "3.12.0"}},
            self.recipes(
                {"tool": dict(kind="tool", minimum_version="3.9.0", dependencies=[])}
            ),
        )
        self.assertEqual(result["nodes"][0]["status"], "satisfied")
        self.assertEqual(result["missing_conditions"], [])

    def test_unknown_dependency_and_cycle_are_blocking(self):
        with self.assertRaises(ValueError):
            resolve_requirements(self.selection(), {}, self.recipes({}))
        with self.assertRaises(ValueError):
            resolve_requirements(
                self.selection(),
                {},
                self.recipes(
                    {
                        "tool": dict(kind="tool", dependencies=["other"]),
                        "other": dict(kind="tool", dependencies=["tool"]),
                    }
                ),
            )

    def test_permissions_and_licenses_are_manual_never_repaired(self):
        result = resolve_requirements(
            self.selection(),
            {},
            self.recipes({"tool": dict(kind="permission", dependencies=[])}),
        )
        self.assertEqual(result["nodes"][0]["status"], "manual")
        self.assertEqual(result["missing_conditions"], ["tool"])

    def test_homebrew_only_for_selected_manager_and_store_needs_no_mas(self):
        recipes = {
            "recipes": [
                dict(
                    RECIPE,
                    sources=RECIPE["sources"]
                    + [
                        dict(source_id="homebrew", official_url="https://brew.sh"),
                        dict(
                            source_id="app_store",
                            official_url="https://apps.apple.com/app/id123",
                        ),
                    ],
                )
            ],
            "requirements": {},
        }
        self.assertEqual(
            resolve_requirements(self.selection(), {}, recipes)["nodes"], []
        )
        store = [dict(self.selection()[0], source_id="app_store")]
        self.assertEqual(resolve_requirements(store, {}, recipes)["nodes"], [])
        brew = [dict(self.selection()[0], source_id="homebrew")]
        self.assertEqual(
            resolve_requirements(brew, {}, recipes)["missing_conditions"], ["homebrew"]
        )
