# Local token optimization: evidence review

Reviewed 2026-11-23 against the Qwen3.5-9B model card, llama.cpp server documentation/source, and prompt-compression papers. This review records what the evidence supports for this app; published compression results are not assumed to transfer to this Qwen GGUF, chat template, GPU, or task mix.

## Findings

| Mechanism | Evidence and fit | Decision |
| --- | --- | --- |
| Count the rendered chat prompt before generation | llama.cpp provides `POST /v1/chat/completions/input_tokens` for a model-formatted chat request. This is a better fit than character or generic tokenizer estimates and is supported by the installed server deployment probe recorded in the preceding implementation work. It adds one local HTTP round trip per request. | Implemented. Use the exact count to enforce the configured context budget. |
| Bound private reasoning separately from total output | llama.cpp supports a per-request `thinking_budget_tokens` value when no server-wide reasoning budget overrides it. Its server source applies the request value as the reasoning budget, and the server guide documents the corresponding reasoning-budget controls. The value bounds thinking; `max_tokens` still has to leave room for the final answer. A small budget can force early exit from reasoning, so quality must be checked live. | Implemented with defaults of 1,024 thinking / 4,096 total output tokens for direct tasks and 256 / 2,048 for triage. These are starting values for measurement, not proven optima. |
| Allocate reasoning budget by task difficulty | The ICLR 2026 PLAN-AND-BUDGET paper reports benefits from planning and assigning budgets to sub-questions, while warning that a single fixed cap can underthink harder problems. Its experiments cover math, instruction following, and agentic planning with 32B–70B models and o4-mini; the method adds a planning call. It does not test our 9B Qwen GGUF or routing complexity labels. | Follow-up experiment: compare a small/medium/large budget selected from triage complexity against the current fixed caps. Keep the fixed budgets until the local QA matrix shows better answer quality per token and acceptable latency. |
| Remove old complete conversation turns when context is tight | This is deterministic and does not paraphrase task content. The app preserves the initial and newest user turns, removes only complete intervening user/assistant turns, adds a notice, and blocks if the remaining current prompt cannot fit. It does not compress a long current request or attached research/repository snapshot. | Implemented as the safe automatic fallback. QA reports record token counts and how many turns were omitted. |
| Shorten fixed system prompts | Removes repeated instruction wording on every request without changing user-provided context. | Implemented. Keep safety boundaries, source attribution, and blocker reporting explicit. |
| Learned prompt compression (LLMLingua / LongLLMLingua) | LLMLingua reports up to 20x compression with little performance loss on its tested datasets; LongLLMLingua reports long-context gains on its tested benchmarks. These methods are model/data/task dependent and can remove important constraints, values, code, or source details. A compressor model can also add latency, GPU memory pressure, and another model dependency. The papers do not demonstrate quality for our Qwen3.5-9B GGUF deployment or app QA matrix. | Not added. Evaluate as an opt-in experiment only after a paired QA benchmark shows quality retention and end-to-end latency gains on this deployment. |

## Context-length tradeoff

The Qwen3.5-9B model card says the model's default context is 262,144 tokens and recommends maintaining at least 128K for complex tasks to preserve thinking capabilities; it also advises reducing context if the deployment runs out of memory. The application currently defaults to an 8,192-token server context, matching the deployment setting observed during implementation. That is a conservative GPU-memory choice, but it is substantially below the model-card recommendation and may constrain complex-task quality. The configured `MULTI_MODAL_CONTEXT_TOKENS` must match the actual loaded server context; increasing this value alone does not enlarge llama.cpp's context or provision KV-cache memory. Benchmark actual GPU memory, latency, and QA quality before raising the server setting.

## Validation still needed

The scripted suite verifies request shape, exact-count handling, and that compaction preserves required turns. It does not prove answer quality or that the router honors the request-level thinking budget. The desktop session must run the saved 12-case Qwen QA suite after this change. Compare blocked/empty outputs, semantic accuracy, latency, reported context/input tokens, and GPU memory. Then test any larger server context on the actual GPU. Do not accept token savings if important facts, code constraints, safety instructions, or answer quality regress.

## Sources

- llama.cpp server API: [`/v1/chat/completions/input_tokens`](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md#post-v1chatcompletionsinput_tokens-token-counting)
- llama.cpp reasoning controls: [server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md), [request-level budget handling in `server-common.cpp`](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/server-common.cpp)
- Qwen: [Qwen3.5-9B model card, context length and serving guidance](https://huggingface.co/Qwen/Qwen3.5-9B)
- Lin et al. (ICLR 2026), [Plan and Budget: Effective and Efficient Test-Time Scaling on Large Language Model Reasoning](https://openreview.net/forum?id=ctspw4CqbS)
- Jiang et al. (2023), [LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models](https://aclanthology.org/2023.emnlp-main.825/)
- Jiang et al. (2024), [LongLLMLingua: Accelerating and Enhancing LLMs in Long Context Scenarios via Prompt Compression](https://aclanthology.org/2024.acl-long.91/)
