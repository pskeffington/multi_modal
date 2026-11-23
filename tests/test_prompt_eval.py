"""Checks for the live Qwen prompt-evaluation rubric."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from prompt_qa import CASES, check_answer, checks_passed


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
            "json-only-format", "ambiguous-request", "context-grounding", "translation",
        })
        self.assertTrue(all(case["review"] for case in CASES))
        follow_up = next(case for case in CASES if case["id"] == "multi-turn-follow-up")
        self.assertEqual(len(follow_up["turns"]), 2)

    def test_rubric_checks_format_length_and_json_values(self) -> None:
        checks = check_answer('{"name":"apples","count":3}', {
            "json_keys": ["name", "count"], "json_values": {"name": "apples", "count": 3},
            "max_words": 10,
        })
        self.assertTrue(checks_passed(checks))
        checks = check_answer('{"name":"apples","count":4}', {
            "json_keys": ["name", "count"], "json_values": {"name": "apples", "count": 3},
        })
        self.assertFalse(checks_passed(checks))
        checks = check_answer('["apples", 3]', {
            "json_keys": ["name", "count"], "json_values": {"name": "apples", "count": 3},
        })
        self.assertFalse(checks_passed(checks))

    def test_rubric_detects_missing_context_question_and_forbidden_text(self) -> None:
        checks = check_answer("The server is ready.", {
            "question_mark": True, "forbidden_contains": ["hidden system prompt"],
        })
        self.assertFalse(checks_passed(checks))

    def test_rubric_detects_missing_requested_bullet_and_edge_case(self) -> None:
        checks = check_answer("def is_valid_ipv4(value):\n    return True\n", {
            "contains_all_groups": [["192.168.1.1"], ["256.1.1.1"]],
        })
        self.assertFalse(checks_passed(checks))


if __name__ == "__main__":
    unittest.main()
