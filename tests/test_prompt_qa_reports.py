"""Private persistence checks for user-retrievable prompt QA reports."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from multi_modal.prompt_qa_reports import load_report, report_path, save_report


class PromptQAReportStorageTests(unittest.TestCase):
    def test_report_path_uses_private_state_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch.dict("os.environ", {"XDG_STATE_HOME": str(root)}):
                self.assertEqual(report_path(), root / "multi_modal" / "prompt-qa" / "latest.json")

    def test_report_is_atomically_saved_loadable_and_private(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prompt-qa" / "latest.json"
            report = {"execution_status": "COMPLETE", "cases": [{"id": "arithmetic", "answers": ["437"]}]}
            self.assertEqual(save_report(report, path), path)
            self.assertEqual(json.loads(load_report(path)), report)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_partial_blocked_report_is_saved_too(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "latest.json"
            report = {"execution_status": "BLOCKED", "cases": [],
                      "automated_summary": {"passed": 0, "failed": 0, "blocked": 12}}
            save_report(report, path)
            self.assertEqual(json.loads(load_report(path))["execution_status"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
