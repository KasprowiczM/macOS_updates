"""First install uses a separate, immutable, explicit dependency preview."""

import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
import install_plan
from tests.test_setup_catalog import RECIPE

NOW = "2026-11-13T12:00:00Z"


class InstallPlanTests(unittest.TestCase):
    def test_unreviewed_catalog_is_manual_and_digest_binds_selection(self):
        recipes = {"recipes": [copy.deepcopy(RECIPE)]}
        plan = install_plan.build_install_plan(
            [dict(product_id="fixture-gui", source_id="vendor", edition="gui")],
            {},
            recipes,
            NOW,
        )
        self.assertEqual(plan["plan_type"], "install_plan")
        self.assertEqual(plan["actions"][0]["kind"], "manual_acquisition")
        self.assertEqual(
            plan["actions"][0]["official_url"], "https://example.org/download"
        )
        self.assertEqual(install_plan.validate_install_plan(plan), plan)
        changed = copy.deepcopy(plan)
        changed["actions"][0]["source_id"] = "homebrew"
        with self.assertRaises(ValueError):
            install_plan.validate_install_plan(changed)

    def test_empty_selection_is_empty_and_installed_never_adopted(self):
        recipes = {"recipes": [RECIPE]}
        self.assertEqual(
            install_plan.build_install_plan([], {}, recipes, NOW)["actions"], []
        )
        snapshot = {
            "instances": [
                dict(
                    product_id="fixture-gui",
                    edition="gui",
                    presence="present",
                    source="homebrew",
                )
            ]
        }
        plan = install_plan.build_install_plan(
            [dict(product_id="fixture-gui", source_id="vendor", edition="gui")],
            snapshot,
            recipes,
            NOW,
        )
        self.assertEqual(plan["actions"][0]["kind"], "manual_migration")

    def test_incompatible_edition_and_unknown_dependency_cannot_install(self):
        for change in [dict(edition="cli"), dict(source_id="npm")]:
            selection = dict(
                product_id="fixture-gui", source_id="vendor", edition="gui"
            )
            selection.update(change)
            with self.assertRaises(ValueError):
                install_plan.build_install_plan(
                    [selection], {}, {"recipes": [RECIPE]}, NOW
                )

    def test_plan_snapshot_and_recipe_are_copied(self):
        recipes = {"recipes": [copy.deepcopy(RECIPE)]}
        plan = install_plan.build_install_plan(
            [dict(product_id="fixture-gui", source_id="vendor", edition="gui")],
            {},
            recipes,
            NOW,
        )
        recipes["recipes"][0]["name"] = "Changed"
        self.assertEqual(plan["actions"][0]["name"], "Fixture")


class InstallPlanIndependentRequirementsTests(unittest.TestCase):
    def test_missing_requirement_does_not_hide_other_independent_ready_action(self):
        from tests.test_install_execution import InstallFixture

        with InstallFixture() as f:
            second = copy.deepcopy(f.recipe)
            second.update(
                id="other",
                product_id="other-gui",
                name="Other",
                requirements=["manual-tool"],
            )
            f.recipes["recipes"].append(second)
            f.recipes["requirements"] = {
                "manual-tool": dict(
                    kind="tool", dependencies=[], minimum_version="1.0.0"
                )
            }
            selections = [
                dict(product_id=p, source_id="vendor", edition="gui")
                for p in ("fixture-gui", "other-gui")
            ]
            plan = install_plan.build_install_plan(
                selections, f.snapshot, f.recipes, NOW
            )
            self.assertEqual(plan["actions"][0]["kind"], "install")
            self.assertEqual(plan["actions"][1]["kind"], "manual_acquisition")
            install_plan.validate_install_plan(plan)
