"""Private, bounded operation evidence; fixtures never invoke host updaters."""

import json
import os
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib/python"))
import operation_receipts as receipts


class ReceiptTests(unittest.TestCase):
    def event(self, **changes):
        return dict(
            run_id="r1",
            action_id="a1",
            recipe_revision="v1",
            phase="quit",
            start="2026-11-14T00:00:00+00:00",
            end="2026-11-14T00:00:01+00:00",
            elapsed_ms=1000,
            outcome="unknown",
            evidence_type="quit_request",
            **changes,
        )

    def test_append_private_and_read_without_asserting_quit_success(self):
        with tempfile.TemporaryDirectory() as root:
            receipts.append_phase_event(root, self.event())
            path = Path(root, "operation-receipts.jsonl")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            event = receipts.read_phase_events(root)[0]
            self.assertEqual(event["outcome"], "unknown")
            self.assertEqual(event["evidence_freshness"], "unconfirmed")

    def test_history_and_fresh_comparison_have_different_freshness(self):
        self.assertEqual(receipts.evidence_freshness("updater_history"), "historical")
        self.assertEqual(
            receipts.evidence_freshness("live_version_comparison"), "fresh"
        )
        self.assertEqual(receipts.evidence_freshness("made_up"), "unknown")

    def test_monotonic_phase_timer_even_when_wall_clock_moves(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(receipts.time, "monotonic", side_effect=[20.0, 20.25]):
                with receipts.phase_receipt(
                    root, run_id="r", action_id="a", recipe_revision="v", phase="check"
                ) as event:
                    event["outcome"] = "current"
            self.assertEqual(receipts.read_phase_events(root)[0]["elapsed_ms"], 250)

    def test_redacted_export_drops_private_paths_and_untrusted_extra_fields(self):
        event = self.event()
        event.update(
            path="/private/fixture/App.app", command="secret", error="/private/fixture"
        )
        public = receipts.public_receipt(event)
        self.assertNotIn("/private", json.dumps(public))
        self.assertNotIn("command", public)
        event["action_id"] = "/private/fixture"
        self.assertEqual(receipts.public_receipt(event)["action_id"], "unknown")

    def test_missing_sha_is_unknown_not_a_release_claim(self):
        with tempfile.TemporaryDirectory() as root:
            Path(root, "VERSION").write_text("1.7.0\n")
            with patch.object(
                receipts.subprocess, "run", side_effect=OSError("unavailable")
            ):
                provenance = receipts.capture_provenance(root, {})
            self.assertEqual(provenance["toolkit_version"], "1.7.0")
            self.assertEqual(provenance["git_sha"], "unknown")
            self.assertIsNone(provenance["dirty"])

    def test_symlink_receipt_cannot_write_outside_session(self):
        with tempfile.TemporaryDirectory() as root:
            outside = Path(root, "outside")
            outside.write_text("unchanged")
            Path(root, "operation-receipts.jsonl").symlink_to(outside)
            with self.assertRaises((OSError, ValueError)):
                receipts.append_phase_event(root, self.event())
            self.assertEqual(outside.read_text(), "unchanged")

    def test_negative_or_missing_elapsed_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            event = self.event()
            event["elapsed_ms"] = -1
            with self.assertRaises(ValueError):
                receipts.append_phase_event(root, event)
            event.pop("elapsed_ms")
            with self.assertRaises(ValueError):
                receipts.append_phase_event(root, event)

    def test_concurrent_receipts_are_complete_and_hardlinks_rejected(self):
        from concurrent.futures import ThreadPoolExecutor

        with tempfile.TemporaryDirectory() as root:
            with ThreadPoolExecutor(max_workers=2) as pool:
                list(
                    pool.map(
                        lambda n: receipts.append_phase_event(
                            root, dict(self.event(), action_id=str(n))
                        ),
                        range(40),
                    )
                )
            events = receipts.read_phase_events(root)
            self.assertEqual(
                {e["action_id"] for e in events}, {str(n) for n in range(40)}
            )
            path = Path(root, "operation-receipts.jsonl")
            original = path.read_bytes()
            os.link(path, Path(root, "hardlink"))
            with self.assertRaises(ValueError):
                receipts.append_phase_event(root, self.event())
            self.assertEqual(path.read_bytes(), original)

    def test_orchestrator_step_timer_records_monotonic_phase_evidence(self):
        root = Path(__file__).resolve().parents[1]
        text = (root / "update_all.sh").read_text()
        timer = text[text.index("_STEP_T0=0") : text.index("_fmt_duration()")]
        with tempfile.TemporaryDirectory() as session:
            result = subprocess.run(
                [
                    "/bin/bash",
                    "-c",
                    timer + "\nstep_timer_start\nstep_timer_stop internet",
                ],
                env=dict(
                    os.environ,
                    SCRIPT_DIR=str(root),
                    SESSION_DIR=session,
                    MAC_UPDATE_RUN_ID="fixture-run",
                    MAC_UPDATE_DRY_RUN="0",
                ),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            events = receipts.read_phase_events(session)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["phase"], "internet")
            self.assertEqual(events[0]["evidence_type"], "phase_timing")
            self.assertGreaterEqual(events[0]["elapsed_ms"], 0)

    def test_source_diagnostics_preserve_partial_counts_without_paths(self):
        snapshot = {
            "sources": {
                "brew:/private/prefix": {
                    "status": "partial",
                    "complete": False,
                    "reason_code": "manager_metadata_incomplete",
                    "items": [{}, {}],
                    "issues": [{"reason_code": "cask_metadata_invalid", "count": 12}],
                }
            }
        }
        with tempfile.TemporaryDirectory() as root:
            receipts.write_source_diagnostics(root, snapshot)
            issues = receipts.read_source_diagnostics(root)
        self.assertNotIn("/private", json.dumps(issues))
        self.assertEqual(issues[0]["observed_items"], 2)
        self.assertEqual(issues[0]["issues"][0]["count"], 12)
