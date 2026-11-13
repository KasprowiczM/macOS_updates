"""Action results extend summary v4 without turning policy choices into failures."""

import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
from run_summary import build_run_summary, collect_run_items
from chronic_warnings import is_skipped


class PlanReportingTests(unittest.TestCase):
    def test_action_status_is_additive_and_only_observed_change_is_updated(self):
        with tempfile.TemporaryDirectory() as folder:
            rows = [
                dict(
                    target={"kind": "app", "id": "a"},
                    action_id="1",
                    status="current_verified",
                    verified=True,
                    before="1",
                    after="2",
                    reason_code="updated_verified",
                ),
                dict(
                    target={"kind": "app", "id": "b"},
                    action_id="2",
                    status="ignored_by_policy",
                    verified=False,
                    before="1",
                    after=None,
                    reason_code="ignored_by_policy",
                ),
            ]
            (Path(folder) / "action-results.jsonl").write_text(
                "".join(json.dumps(r) + "\n" for r in rows)
            )
            items = collect_run_items(folder)
            self.assertEqual([i["status"] for i in items], ["updated", "skipped"])
            self.assertEqual(items[1]["action_status"], "ignored_by_policy")
            result = build_run_summary(
                0, 1, 0, 0, 0, {}, session_dir=folder, items=items
            )
            self.assertEqual(result["format_version"], 4)
            self.assertEqual(len(result["action_results"]), 2)

    def test_policy_choices_are_neutral_but_conflict_is_not(self):
        self.assertTrue(is_skipped({"code": "manual_by_policy"}))
        self.assertTrue(is_skipped({"code": "ignored_by_policy"}))
        self.assertFalse(is_skipped({"code": "source_conflict"}))

    def test_unverified_change_never_becomes_updated(self):
        with tempfile.TemporaryDirectory() as folder:
            row = dict(
                target={"kind": "app", "id": "a"},
                action_id="1",
                status="update_unverified",
                verified=False,
                before="1",
                after="2",
                reason_code="post_update_unverified",
            )
            (Path(folder) / "action-results.jsonl").write_text(json.dumps(row) + "\n")
            items = collect_run_items(folder)
            self.assertEqual(items[0]["status"], "unconfirmed")
