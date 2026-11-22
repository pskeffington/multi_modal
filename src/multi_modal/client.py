"""Minimal loopback-only client for the local llama.cpp router."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlsplit

DEFAULT_URL = os.environ.get("MULTI_MODAL_ROUTER_URL", "http://127.0.0.1:9931")
QWEN = os.environ.get("MULTI_MODAL_QWEN_MODEL", "lmstudio-community/Qwen3.5-9B-GGUF")
GLM = os.environ.get("MULTI_MODAL_GLM_MODEL", "glm5.2-ud-iq1_s")


class LocalModelError(RuntimeError):
    pass


class LocalClient:
    def __init__(self, base_url: str = DEFAULT_URL):
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Only an HTTP llama.cpp endpoint on loopback is allowed")
        self.base_url = base_url.rstrip("/")

    def request(self, path: str, payload: dict | None = None, timeout: float = 8) -> dict:
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.base_url + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            raise LocalModelError(str(exc)) from exc

    def models(self) -> list[str]:
        try:
            data = self.request("/v1/models")
        except LocalModelError:
            data = self.request("/models")
        entries = data if isinstance(data, list) else data.get("data", [])
        return [str(item.get("id", "")) for item in entries if isinstance(item, dict) and item.get("id")]

    def chat(self, model: str, messages: list[dict], timeout: float) -> str:
        data = self.request("/v1/chat/completions", {
            "model": model, "messages": messages, "temperature": 0.1,
            "stream": False, "max_tokens": 2048,
        }, timeout=timeout)
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalModelError("The local server returned an unexpected chat response") from exc
