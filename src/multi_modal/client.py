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


def resolve_model_id(configured: str, available: list[str]) -> str | None:
    """Resolve a configured ID or a unique quantized variant advertised by the router."""
    if configured in available:
        return configured
    folded = configured.casefold()
    exact = [model for model in available if model.casefold() == folded]
    if len(exact) == 1:
        return exact[0]
    variants = [model for model in available if model.casefold().startswith(folded + ":")]
    return variants[0] if len(variants) == 1 else None


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

    def model_catalog(self) -> list[dict[str, str]]:
        try:
            data = self.request("/v1/models")
        except LocalModelError:
            data = self.request("/models")
        entries = data if isinstance(data, list) else data.get("data") if isinstance(data, dict) else None
        if not isinstance(entries, list):
            raise LocalModelError("The local router returned an invalid model catalog")
        catalog = []
        for item in entries:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            status = item.get("status", "")
            if isinstance(status, dict):
                status = status.get("value", "")
            catalog.append({"id": str(item["id"]), "status": str(status or "available")})
        return catalog

    def models(self) -> list[str]:
        return [item["id"] for item in self.model_catalog()]

    def chat(self, model: str, messages: list[dict], timeout: float,
             response_format: dict | None = None) -> str:
        available = self.models()
        resolved = resolve_model_id(model, available)
        if not resolved:
            raise LocalModelError(
                f"Configured model {model!r} is not uniquely advertised by the local router; "
                "check the model ID or its environment override"
            )
        payload = {
            "model": resolved, "messages": messages, "temperature": 0.1,
            "stream": False, "max_tokens": 2048,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        data = self.request("/v1/chat/completions", payload, timeout=timeout)
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalModelError("The local server returned an unexpected chat response") from exc
