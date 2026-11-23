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
DEFAULT_MAX_TOKENS = int(os.environ.get("MULTI_MODAL_MAX_TOKENS", "4096"))
DEFAULT_THINKING_BUDGET_TOKENS = int(os.environ.get("MULTI_MODAL_THINKING_BUDGET_TOKENS", "1024"))
DEFAULT_CONTEXT_TOKENS = int(os.environ.get("MULTI_MODAL_CONTEXT_TOKENS", "8192"))
CONTEXT_RESERVE_TOKENS = 128


class LocalModelError(RuntimeError):
    pass


def fit_messages_to_budget(messages: list[dict], max_prompt_tokens: int, count_tokens) -> tuple[list[dict], dict]:
    """Drop only old complete turns until the exact tokenizer count fits.

    The first user turn and the newest turn are preserved. If those alone do not
    fit, fail visibly instead of silently truncating the current request/context.
    """
    fitted = [dict(message) for message in messages]
    original_tokens = count_tokens(fitted)
    current_tokens = original_tokens
    omitted_turns = 0
    omission_note = " Earlier conversation turns were omitted to fit the local context; use only the retained turns."
    while current_tokens > max_prompt_tokens:
        user_indexes = [index for index, message in enumerate(fitted)
                        if message.get("role") == "user"]
        if len(user_indexes) < 3:
            raise LocalModelError(
                f"Prompt needs {current_tokens} tokens, exceeding the {max_prompt_tokens}-token input budget "
                "after reserving space for the answer. Shorten the current request or reduce attached context."
            )
        first_user, newest_user = user_indexes[0], user_indexes[-1]
        pair_index = None
        for index in range(first_user + 1, newest_user):
            if fitted[index].get("role") != "user":
                continue
            next_user = next((candidate for candidate in range(index + 1, newest_user)
                              if fitted[candidate].get("role") == "user"), newest_user)
            assistant_index = next((candidate for candidate in range(index + 1, next_user)
                                    if fitted[candidate].get("role") == "assistant"), None)
            if assistant_index is not None:
                pair_index = (index, assistant_index)
                break
        if pair_index is None:
            raise LocalModelError(
                f"Prompt needs {current_tokens} tokens, exceeding the {max_prompt_tokens}-token input budget "
                "and no complete older turn can be removed. Shorten the current request or reduce attached context."
            )
        user_index, assistant_index = pair_index
        del fitted[assistant_index]
        del fitted[user_index]
        omitted_turns += 1
        if omitted_turns == 1:
            system_index = next((index for index, message in enumerate(fitted)
                                 if message.get("role") == "system"), None)
            if system_index is None:
                fitted.insert(0, {"role": "system", "content": omission_note.strip()})
            else:
                fitted[system_index]["content"] = str(fitted[system_index].get("content", "")) + omission_note
        current_tokens = count_tokens(fitted)
    return fitted, {"input_tokens_before": original_tokens, "input_tokens_after": current_tokens,
                    "input_token_budget": max_prompt_tokens, "omitted_history_turns": omitted_turns}


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
    def __init__(self, base_url: str = DEFAULT_URL, context_tokens: int = DEFAULT_CONTEXT_TOKENS):
        parsed = urlsplit(base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise ValueError("Only an HTTP llama.cpp endpoint on loopback is allowed")
        if not isinstance(context_tokens, int) or isinstance(context_tokens, bool) or context_tokens < 1:
            raise ValueError("context_tokens must be a positive integer")
        self.base_url = base_url.rstrip("/")
        self.context_tokens = context_tokens
        self.last_prompt_stats: dict = {}

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

    def count_chat_tokens(self, model: str, messages: list[dict], timeout: float = 30) -> int:
        """Count a model-formatted chat prompt without generating a response."""
        data = self.request("/v1/chat/completions/input_tokens",
                            {"model": model, "messages": messages}, timeout=timeout)
        try:
            count = data["input_tokens"]
        except (KeyError, TypeError) as exc:
            raise LocalModelError("The local tokenizer returned an invalid prompt token count") from exc
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise LocalModelError("The local tokenizer returned an invalid prompt token count")
        return count

    def chat(self, model: str, messages: list[dict], timeout: float,
             response_format: dict | None = None, max_tokens: int = DEFAULT_MAX_TOKENS,
             thinking_budget_tokens: int = DEFAULT_THINKING_BUDGET_TOKENS) -> str:
        if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
            raise ValueError("max_tokens must be a positive integer")
        if (not isinstance(thinking_budget_tokens, int) or isinstance(thinking_budget_tokens, bool)
                or thinking_budget_tokens < 0):
            raise ValueError("thinking_budget_tokens must be a nonnegative integer")
        prompt_budget = self.context_tokens - max_tokens - CONTEXT_RESERVE_TOKENS
        if prompt_budget < 1:
            raise ValueError("max_tokens leaves no room for a prompt in the configured context")
        available = self.models()
        resolved = resolve_model_id(model, available)
        if not resolved:
            raise LocalModelError(
                f"Configured model {model!r} is not uniquely advertised by the local router; "
                "check the model ID or its environment override"
            )
        fitted_messages, token_stats = fit_messages_to_budget(
            messages, prompt_budget, lambda candidate: self.count_chat_tokens(resolved, candidate)
        )
        self.last_prompt_stats = {**token_stats, "context_tokens": self.context_tokens,
                                  "max_tokens": max_tokens,
                                  "thinking_budget_tokens": thinking_budget_tokens,
                                  "counter": "llama.cpp exact chat-token endpoint"}
        payload = {
            "model": resolved, "messages": fitted_messages, "temperature": 0.1,
            "stream": False, "max_tokens": max_tokens,
            "thinking_budget_tokens": thinking_budget_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format
        data = self.request("/v1/chat/completions", payload, timeout=timeout)
        try:
            choice = data["choices"][0]
            if not isinstance(choice, dict):
                raise TypeError("choice must be an object")
            message = choice["message"]
            if not isinstance(message, dict):
                raise TypeError("message must be an object")
            content = message.get("content")
        except (KeyError, IndexError, TypeError) as exc:
            raise LocalModelError("The local server returned an unexpected chat response") from exc
        if not isinstance(content, str) or not content.strip():
            finish_reason = choice.get("finish_reason", "unknown")
            usage = data.get("usage", {})
            completion_tokens = usage.get("completion_tokens", "unknown") if isinstance(usage, dict) else "unknown"
            reasoning = message.get("reasoning_content", "")
            reasoning_chars = len(reasoning) if isinstance(reasoning, str) else 0
            raise LocalModelError(
                "The local server returned no final answer text "
                f"(finish_reason={finish_reason}, completion_tokens={completion_tokens}, "
                f"reasoning_chars={reasoning_chars}). The model may have used its completion budget "
                "without producing a user-facing answer."
            )
        return content
