"""Loopback API contract checks for the llama.cpp client."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from multi_modal.client import (QWEN, LocalClient, LocalModelError,
                                fit_messages_to_budget, resolve_sampling)


class LocalClientHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.requests: list[tuple[str, dict | None]] = []
        self.client = LocalClient("http://127.0.0.1:9931")

    def mock_transport(self):
        requests = self.requests

        class Response:
            def __init__(self, payload: dict):
                self.body = json.dumps(payload).encode()

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return self.body

        class Opener:
            def open(self, request, timeout):
                from urllib.parse import urlsplit
                path = urlsplit(request.full_url).path
                payload = json.loads(request.data) if request.data else None
                requests.append((path, payload))
                if path == "/v1/models":
                    body = {"data": [{"id": QWEN + ":Q4_K_M", "status": {"value": "available"}}]}
                elif path == "/v1/chat/completions/input_tokens":
                    body = {"input_tokens": 12}
                elif path == "/v1/chat/completions":
                    body = {"choices": [{"message": {"content": "Loopback answer."}, "finish_reason": "stop"}]}
                else:
                    raise AssertionError(f"Unexpected endpoint {path}")
                return Response(body)

        return patch("multi_modal.client.urllib.request.build_opener", return_value=Opener())

    def test_model_catalog_and_quantized_chat_alias(self) -> None:
        with self.mock_transport():
            catalog = self.client.model_catalog()
            self.assertEqual(catalog, [{"id": QWEN + ":Q4_K_M", "status": "available"}])
            response_format = {"type": "json_object", "schema": {"type": "object"}}
            answer = self.client.chat(QWEN, [{"role": "user", "content": "Hi"}], timeout=2,
                                     response_format=response_format, max_tokens=512)
        self.assertEqual(answer, "Loopback answer.")
        post = next(payload for path, payload in self.requests if path == "/v1/chat/completions")
        self.assertEqual(post["model"], QWEN + ":Q4_K_M")
        self.assertEqual(post["messages"][-1]["content"], "Hi")
        self.assertFalse(post["stream"])
        self.assertEqual(post["response_format"], response_format)
        self.assertEqual(post["max_tokens"], 512)
        self.assertEqual(post["thinking_budget_tokens"], 1024)
        self.assertEqual(self.client.last_prompt_stats["input_tokens_after"], 12)

    def test_invalid_max_tokens_is_rejected(self) -> None:
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.client.chat(QWEN, [{"role": "user", "content": "Hi"}], timeout=2,
                                 max_tokens=value)

    def test_failed_request_clears_previous_prompt_statistics(self) -> None:
        self.client.last_prompt_stats = {"input_tokens_before": 123}
        with patch.object(LocalClient, "request", side_effect=LocalModelError("router offline")):
            with self.assertRaises(LocalModelError):
                self.client.chat(QWEN, [{"role": "user", "content": "Hi"}], timeout=2)
        self.assertEqual(self.client.last_prompt_stats, {})

    def test_history_fitting_preserves_original_and_newest_turns(self) -> None:
        messages = [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "original"},
            {"role": "assistant", "content": "first answer"},
            {"role": "user", "content": "old middle question"},
            {"role": "assistant", "content": "old middle answer"},
            {"role": "user", "content": "newest request"},
        ]
        def fake_count(candidate: list[dict]) -> int:
            return 100 if any(message.get("content") == "old middle question" for message in candidate) else 40

        fitted, stats = fit_messages_to_budget(messages, 55, fake_count)
        user_content = [message["content"] for message in fitted if message["role"] == "user"]
        self.assertEqual(user_content, ["original", "newest request"])
        self.assertEqual(stats["omitted_history_turns"], 1)
        self.assertLessEqual(stats["input_tokens_after"], 55)
        self.assertIn("omitted", fitted[0]["content"])

    def test_history_fitting_blocks_if_current_prompt_cannot_fit(self) -> None:
        with self.assertRaisesRegex(LocalModelError, "Shorten the current request"):
            fit_messages_to_budget([{"role": "user", "content": "too large"}], 1,
                                   lambda _messages: 2)

    def test_empty_final_answer_is_reported_with_safe_generation_metadata(self) -> None:
        with self.mock_transport():
            with patch("multi_modal.client.LocalClient.request", side_effect=[
                {"data": [{"id": QWEN}]},
                {"input_tokens": 12},
                {"choices": [{"message": {"content": "", "reasoning_content": "private reasoning"},
                              "finish_reason": "length"}],
                 "usage": {"completion_tokens": 768}},
            ]):
                with self.assertRaisesRegex(LocalModelError, "finish_reason=length") as raised:
                    self.client.chat(QWEN, [{"role": "user", "content": "Hi"}], timeout=2)
        self.assertIn("completion_tokens=768", str(raised.exception))
        self.assertIn("reasoning_chars=17", str(raised.exception))
        self.assertNotIn("private reasoning", str(raised.exception))

    def test_wrong_host_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LocalClient("http://0.0.0.0:9931")
        with self.assertRaises(ValueError):
            LocalClient("https://127.0.0.1:9931")

    def test_sampling_profiles_follow_configured_qwen_and_preserve_glm_default(self) -> None:
        profile, sampling = resolve_sampling(QWEN, QWEN)
        self.assertEqual(profile, "qwen-general")
        self.assertEqual(sampling, {"temperature": 1.0, "top_p": 0.95,
                                    "top_k": 20, "presence_penalty": 1.5})
        profile, sampling = resolve_sampling(QWEN + ":Q4_K_M", QWEN)
        self.assertEqual(profile, "qwen-general")
        self.assertEqual(sampling["top_k"], 20)
        profile, sampling = resolve_sampling("local/GLM", QWEN)
        self.assertEqual(profile, "server-default")
        self.assertEqual(sampling, {"temperature": 0.1})

    def test_explicit_qwen_coding_sampling_profile(self) -> None:
        profile, sampling = resolve_sampling(QWEN, QWEN, "qwen-coding")
        self.assertEqual(profile, "qwen-coding")
        self.assertEqual(sampling, {"temperature": 0.6, "top_p": 0.95,
                                    "top_k": 20, "presence_penalty": 0.0})


if __name__ == "__main__":
    unittest.main()
