"""Loopback API contract checks for the llama.cpp client."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from multi_modal.client import QWEN, LocalClient, LocalModelError


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

    def test_invalid_max_tokens_is_rejected(self) -> None:
        for value in (0, -1, True, 1.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.client.chat(QWEN, [{"role": "user", "content": "Hi"}], timeout=2,
                                 max_tokens=value)

    def test_wrong_host_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            LocalClient("http://0.0.0.0:9931")
        with self.assertRaises(ValueError):
            LocalClient("https://127.0.0.1:9931")


if __name__ == "__main__":
    unittest.main()
