"""Checks for the live Qwen prompt-evaluation rubric."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prompt_qa import CASES, check_answer


class PromptEvalRubricTests(unittest.TestCase):
    def test_arithmetic_rubric_detects_wrong_result(self) -> None:
        result = check_answer("19 × 23 = 437.", {"contains": ["437"]})
        self.assertTrue(result["contains"]["437"])
        self.assertFalse(check_answer("The answer is 438.", {"contains": ["437"]})["contains"]["437"])

    def test_summary_rubric_counts_bullets(self) -> None:
        result = check_answer("- one\n- two\n- three", {"bullet_count": 3})
        self.assertTrue(result["bullet_count"]["passed"])
        self.assertFalse(check_answer("- one\n- two", {"bullet_count": 3})["bullet_count"]["passed"])

    def test_live_matrix_covers_common_prompt_patterns(self) -> None:
        self.assertEqual({case["id"] for case in CASES}, {
            "arithmetic", "plain-language-explanation", "constrained-summary",
            "coding-and-edge-cases", "multi-turn-follow-up", "untrusted-web-content",
        })
        self.assertTrue(all(case["review"] for case in CASES))


if __name__ == "__main__":
    unittest.main()
