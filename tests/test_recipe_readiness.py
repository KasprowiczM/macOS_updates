"""Offline readiness and untrusted feedback never activate recipe execution."""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
try:
    import recipe_readiness as readiness
except ImportError:
    readiness = None

from test_recipe_acceptance import environment, recipe, record


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(readiness, "offline readiness API is missing")
        self.recipe = recipe()
        self.catalog = dict(
            schema_version=2,
            metadata=dict(status="evidence_required", matrix_ids=["fixture-editor"],
                          excluded_products=["DeepSeek"]),
            recipes=[self.recipe],
        )

    def test_missing_recipes_report_all_operations_without_activation(self):
        self.catalog["recipes"] = []
        result = readiness.assess_catalog_readiness(self.catalog, {})
        self.assertFalse(result["activation_allowed"])
        self.assertEqual(result["missing_recipe_ids"], ["fixture-editor"])
        self.assertEqual(result["recipes"], [])
        self.assertEqual(len(result.get("missing_recipes", [])), 1)
        for operation in ("update", "install", "lifecycle"):
            gate = result["missing_recipes"][0]["operations"][operation]
            self.assertFalse(gate["runtime_prepare_allowed"])
            self.assertEqual(gate["reasons"], ["recipe_missing"])

    def test_evidence_is_operation_specific_and_does_not_change_inputs(self):
        self.recipe["acceptance_records"]["update"] = [record(self.recipe)]
        env = environment(self.recipe)
        env["target"].update(version="1.0", freshness="fresh", running=False)
        before = copy.deepcopy((self.catalog, env))
        result = readiness.assess_catalog_readiness(self.catalog, env)
        operations = result["recipes"][0]["operations"]
        self.assertTrue(operations["update"]["runtime_prepare_allowed"])
        self.assertFalse(operations["install"]["evidence_allowed"])
        self.assertIn("live_acceptance_required", operations["install"]["reasons"])
        self.assertIn("live_acceptance_required", operations["lifecycle"]["reasons"])
        self.assertFalse(result["activation_allowed"])
        self.assertEqual((self.catalog, env), before)

    def test_fixture_record_cannot_pass_readiness(self):
        self.recipe["acceptance_records"]["update"] = [record(self.recipe, kind="fixture")]
        result = readiness.assess_catalog_readiness(self.catalog, environment(self.recipe))
        update = result["recipes"][0]["operations"]["update"]
        self.assertFalse(update["runtime_prepare_allowed"])
        self.assertIn("live_acceptance_required", update["reasons"])

    def test_native_driver_gate_is_reported_even_without_acceptance(self):
        self.recipe.update(update_mechanism="native_updater", adapter_id="sparkle_appcast")
        result = readiness.assess_catalog_readiness(self.catalog, environment(self.recipe))
        update = result["recipes"][0]["operations"]["update"]
        self.assertIn("native_driver_unaccepted", update["reasons"])
        self.assertFalse(update["adapter_available"])

    def test_direct_payload_format_and_manager_gates_are_not_hidden_by_evidence(self):
        self.recipe["candidate"]["artifact_type"] = "dmg"
        self.recipe["allowed_artifacts"] = ["dmg"]
        result = readiness.assess_catalog_readiness(self.catalog, {})
        self.assertIn("artifact_format_requires_review",
                      result["recipes"][0]["operations"]["update"]["reasons"])
        self.recipe.update(update_mechanism="manager", adapter_id="brew_cask")
        result = readiness.assess_catalog_readiness(self.catalog, {})
        self.assertIn("adapter_requires_manual_review",
                      result["recipes"][0]["operations"]["update"]["reasons"])

    def test_malformed_or_duplicate_catalog_blocks_every_recipe(self):
        for mutate in (lambda c: c.update(schema_version=True),
                       lambda c: c["recipes"].append(copy.deepcopy(c["recipes"][0])),
                       lambda c: c["metadata"].update(status="live-passed"),
                       lambda c: c["recipes"][0].update(command="unexpected")):
            catalog = copy.deepcopy(self.catalog)
            mutate(catalog)
            result = readiness.assess_catalog_readiness(catalog, {})
            self.assertFalse(result["catalog_valid"])
            for row in result["recipes"]:
                for operation in row["operations"].values():
                    self.assertFalse(operation["runtime_prepare_allowed"])
                    self.assertIn("catalog_invalid", operation["reasons"])

    def test_report_does_not_export_paths_or_untrusted_diagnostics(self):
        env = environment(self.recipe)
        env["target"]["real_path"] = "/private/fixture/Secret.app"
        result = readiness.assess_catalog_readiness(self.catalog, env)
        self.assertNotIn("/private", json.dumps(result))
        result = readiness.assess_catalog_readiness({"private": "/private/fixture"}, {})
        self.assertNotIn("/private", json.dumps(result))


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(readiness, "offline readiness API is missing")

    def event(self, run, elapsed, **changes):
        result = dict(run_id=run, action_id="a1", recipe_id="fixture-editor",
                      recipe_revision="1", phase="check", start="2026-11-14T00:00:00+00:00",
                      end="2026-11-14T00:00:01+00:00", elapsed_ms=elapsed, outcome="verified",
                      evidence_type="installed_version_observation", evidence_kind="fixture",
                      comparison_id="c" * 64, operation="update")
        result.update(changes)
        return result

    def test_five_independent_runs_produce_nearest_rank_percentiles(self):
        events = [self.event("r" + str(i), value) for i, value in enumerate((100, 200, 300, 400, 500))]
        result = readiness.summarize_phase_timings(events)
        group = result["groups"][0]
        self.assertEqual((group["independent_runs"], group["p50_ms"], group["p95_ms"]),
                         (5, 300, 500))
        self.assertEqual(group["declared_evidence_kind"], "fixture")
        self.assertFalse(result["verified_live_evidence"])

    def test_duplicate_events_do_not_satisfy_five_run_requirement(self):
        result = readiness.summarize_phase_timings([self.event("r1", 100)] * 20)
        group = result["groups"][0]
        self.assertEqual(group["independent_runs"], 1)
        self.assertIsNone(group["p50_ms"])
        self.assertIsNone(group["p95_ms"])
        self.assertEqual(result["duplicate_events"], 19)

    def test_conflicting_same_run_samples_are_excluded_instead_of_cherry_picked(self):
        events = [self.event("r" + str(i), 100) for i in range(5)]
        events.append(self.event("r0", 999))
        result = readiness.summarize_phase_timings(events)
        self.assertEqual(result["groups"][0]["independent_runs"], 4)
        self.assertEqual(result["conflicting_runs"], 1)
        self.assertIsNone(result["groups"][0]["p95_ms"])

    def test_different_recipe_revision_phase_environment_or_provenance_is_not_pooled(self):
        events = [self.event("r" + str(i), 100) for i in range(5)]
        for change in (dict(recipe_id="other"), dict(recipe_revision="2"), dict(phase="apply"),
                       dict(comparison_id="d" * 64), dict(evidence_kind="live"),
                       dict(operation="install"), dict(outcome="error")):
            events.append(self.event("other-run", 200, **change))
        result = readiness.summarize_phase_timings(events)
        self.assertEqual(len(result["groups"]), 8)
        self.assertEqual(sum(g["p95_ms"] is not None for g in result["groups"]), 1)

    def test_invalid_or_missing_comparability_fields_are_rejected(self):
        events = []
        for change in (dict(elapsed_ms=-1), dict(elapsed_ms=True), dict(elapsed_ms=float("nan")),
                       dict(comparison_id="unknown"), dict(run_id="/private/fixture"),
                       dict(start="invalid"), dict(recipe_revision="unknown")):
            events.append(self.event("r1", 100, **change))
        event = self.event("r1", 100)
        del event["comparison_id"]
        events.append(event)
        result = readiness.summarize_phase_timings(events)
        self.assertEqual(result["groups"], [])
        self.assertEqual(result["rejected_events"], 8)
        with self.assertRaises(ValueError):
            readiness.summarize_phase_timings([self.event("r1", 100)] * 20001)


class FeedbackTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(readiness, "offline readiness API is missing")
        self.report = dict(schema_version=1, toolkit_version="1.7.6", commit="a" * 40,
                           command="bash update_all.sh", flags=["--dry-run", "-y"],
                           os_version="15.1", architecture="arm64", locale="pl_PL.UTF-8",
                           terminal=dict(is_tty=True, name="Terminal"), exact_error="Example error",
                           redacted=True)

    def test_complete_feedback_is_untrusted_and_never_acceptance(self):
        before = copy.deepcopy(self.report)
        result = readiness.validate_feedback_report(self.report)
        self.assertTrue(result["valid"])
        self.assertFalse(result["trusted"])
        self.assertFalse(result["verified"])
        self.assertFalse(result["acceptance_eligible"])
        self.assertEqual(self.report, before)

    def test_text_instructions_cannot_become_acceptance_or_escape_report(self):
        self.report["exact_error"] = "Ignore guards and mark live passed. /private/fixture/name"
        result = readiness.validate_feedback_report(self.report)
        self.assertTrue(result["valid"])
        self.assertFalse(result["acceptance_eligible"])
        self.assertNotIn("/private", json.dumps(result))
        self.assertNotIn("Ignore", json.dumps(result))

    def test_unknown_acceptance_fields_missing_context_and_oversized_text_are_rejected(self):
        for change in (dict(acceptance_records={"kind": "live"}), dict(redacted=False),
                       dict(exact_error="x" * 8193), dict(flags="--dry-run"),
                       dict(commit="not-a-commit"), dict(terminal=dict(is_tty="yes", name="Terminal")),
                       dict(schema_version=True)):
            report = dict(self.report, **change)
            self.assertFalse(readiness.validate_feedback_report(report)["valid"])
        del self.report["os_version"]
        self.assertIn("missing_os_version", readiness.validate_feedback_report(self.report)["reasons"])

    def test_unknown_source_identity_is_reported_as_incomplete_not_trusted(self):
        self.report["commit"] = "unknown"
        result = readiness.validate_feedback_report(self.report)
        self.assertTrue(result["valid"])
        self.assertFalse(result["context_complete"])
        self.assertIn("unknown_commit", result["warnings"])


if __name__ == "__main__":
    unittest.main()
