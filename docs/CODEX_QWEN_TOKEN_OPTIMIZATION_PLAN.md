# Codex implementation plan: Qwen token economy with correctness gates

**Owner:** Codex engineering agent / human reviewer  
**Scope:** `multi_modal` on Linux, Qwen3.5-9B GGUF through local loopback llama.cpp.  
**Research basis:** [literature matrix](QWEN_TOKEN_OPTIMIZATION_LITERATURE_MATRIX.md).  
**Delivery policy:** This document is a handoff. Do not assume any live GPU, Qwen or GTK test ran here. Create separate reviewable PRs per phase, and never apply unsafe automatic changes.

## Unchanged product invariants

- All inference stays at the configured **HTTP loopback** llama.cpp endpoint. No new hosted providers or outward telemetry.
- No third-party Python dependencies. Python standard library + distribution GTK4/PyGObject only.
- One serialized worker; GLM escalation rules, human routing decisions, and 512-token structured triage repair remain safe.
- No generated shell execution or Codex CLI launch. Preserve manual review packets and approved-unified-diff + second-confirmation boundary.
- Raw user request, selected Git file snapshot, web research, model answer, and reviewer instruction persist privately and remain retrievable. Never silently rewrite historical records.
- No Qwen change may turn an empty content response into a successful task or claim that a truncated answer is complete. Preserve existing user-selected evidence/attribution and prompt-injection boundary.
- Operator-adjustable model and server parameters must not be silently rewritten.

## Phase 0 — Baseline and capability discovery (**first PR**)

### Deliverables

1. Add a **backward-compatible** response-metadata path to `src/multi_modal/client.py` (e.g. an optional `chat_with_metrics()` returning `ChatResult` while `chat()` continues returning `str`). Capture bounded, non-content-bearing: resolved model ID, `finish_reason`, `usage.prompt_tokens`, `usage.completion_tokens`, `usage.prompt_tokens_details.cached_tokens` if available, timing from server where provided and client elapsed milliseconds, and optional `reasoning_content` **length** only (never its text). Validate fields and tolerate missing/malformed optional values. Do not persist the prompt or response in a telemetry artifact; existing authorized task store behavior stays intact.
2. Include an **explicit, opt-in** private per-run benchmark artifact under `$XDG_STATE_HOME/multi_modal/token-qa/` with owner-only directory/file permissions, stable run/config identifiers, overall and per-case metrics, and no raw prompts, responses, scraped context, or system prompts. Do not send anything to external analytics.
3. Extend `scripts/prompt_qa.py` to measure original QA cases, production triage + single repair, persisted follow-up, correct final-answer text, and empty-answer failure. Compare like-for-like model, backend, quantization, context, temperature, max token budget and runtime. Do not break the old scripted-client contract; add a metrics adapter or update fakes explicitly.
4. Add a safe **read-only** capability diagnostic: installed `llama-server` binary/version (if exposed), selected GGUF/model ID, reasoning controls available in the actual version, GPU/backend/offload evidence, effective context size, and cache usage availability. No automatic service file edits, shell interpolation, server restarts or CPU fallback.
5. Add unit tests: missing usage, malformed usage, no reasoning content, reasoning-only exhaustion, truncated JSON, transport timeout, unavailable model, no external host, privacy/permissions, multiple QA cases, and baseline export.
6. Update `docs/OPERATIONS.md` and `docs/PROMPT_QA_STATUS.md` without presenting unavailable live tests as successful.

### Baseline metrics

- `prompt_tokens`, `completion_tokens`, `cached_tokens` (optional), `reasoning_chars` (optional), `finish_reason`, client end-to-end latency and (when exposed) prompt/decode times.
- QA **PASS / FAIL / BLOCKED** by case, triage schema validity, retry/repair count, routing/risk decisions, and empty final-answer count.
- Prompt token counts should come from server usage with the **actual Qwen tokenizer/template**. If unavailable, label the metric **unavailable**; do not substitute naive word counts as factual token totals.
- Compare at least three controlled repeats where hardware is available, reporting p50 and p95 only if enough samples exist. Cold vs warm traces must be labeled.

### Exit gate

`make check && make test` pass; `make prompt-qa` is run in a host session with actual Qwen/GPU and archived privately, or marked **BLOCKED** with the underlying reason. Baseline 12-case results, failures and nonempty-answer counts are available for review. Do not continue if instrumentation changes behavior.

## Phase 1 — Qwen reasoning controls (**second PR, behind opt-in flag**)

Implement a single, explicit `QwenReasoningPolicy` with initially disabled values `inherit`, `probe_only`, `prefer_non_thinking_simple` (or equivalent). Determine behavior from the **installed server build** and exact loaded Qwen3.5 GGUF/chat-template path. Inspect the server's documented request-level `reasoning_effort: "none"` and `chat_template_kwargs: {"enable_thinking": false}` support: Qwen model documentation describes the latter, but llama.cpp version/template issues mean **neither may be assumed working**. `--reasoning off` and `--reasoning-budget` are server/operator settings, **not** silently injected into user requests.

Use a testable adapter that sends **only settings confirmed supported**, and defaults to the existing behavior on unexpected responses or unsupported settings. Never hide a server failure by continuing with a different model. Keep controls Qwen-specific; GLM remains unchanged. On untrusted or risk-sensitive tasks, coding with edge cases, long-context grounding, patch generation, or uncertain routing, preserve thinking mode unless approved per case.

**Strict tests:** compare triage fields, risk policy, schema repair rate, 10 QA answers, multi-turn conversation and grounded source use with baseline. Log token counts and reasoning-only exhaustion without reasoning text. Do **not** implement `/no_think` prompt hacks (official Qwen3.5 card says these soft switches are not supported), shorten `max_tokens` blindly or silently change the production QA budget to make numbers look smaller.

**Exit gate:** zero newly empty answers or triage validation failures; equivalent or better correctness on all previously passing cases, no suppressed high-risk/low-confidence review; measurable reduction in generated tokens **on the eligible prompt classes**. If a mode fails, ship disabled and document failure.

## Phase 2 — Explicit context budgeting and compaction (**third PR**)

1. Build a **read-only** estimator/preview for next inference request showing per-segment approximate or actual token costs (system, user task, approved historical turns, selected Git snapshot, user-confirmed web research, reviewer instruction). Reuse server tokenization only if safely supported by the local version; otherwise indicate estimates clearly and do not promise exact token counts.
2. Preserve strict hard categories: **no automatic pruning** of system safety boundary, original user task, review decisions/instructions, Git source files, code blocks, unified diffs, quoted exact requirements, filenames/paths, error messages and integrity checks. Avoid lossy condensation of untrusted research directives. All chronological original turns remain in the private store.
3. Provide a separate **explicitly previewed/approved** context-selection proposal for *eligible* web research or redundant, previously approved conversational explanation. Display exact before/after text and source/title/domain attributions. If user does not approve, send original context; no mutation of original stored message.
4. For deterministic first pass, do **not** add a separate compression model. Start with deduplicating identical, opt-in research excerpts and relevance-preserving extractive inclusion boundaries. Never drop sources necessary to substantiate an answer. If the tool has insufficient evidence, refuse compaction or require re-research.
5. Add tests for retained middle-position facts, adversarial web-instruction injection, quoted file paths, multi-turn dependencies, review notes and code-fence integrity. Use F1/F2/F3 (decision, compression loss, later retrieval) as failure classifications.

**Exit gate:** measured input-token reduction for genuinely compressible, selected contexts without loss of relevant facts on an evaluation set; no changes to non-opted-in contexts; raw originals still accessible; safeguards unchanged.

## Phase 3 — Cache/GPU tuning as a **separate** operator experiment

Measure native llama.cpp prompt-cache reuse already enabled by default, stable prefixes, cold/warm p50/p95 request time, cached vs processed prompt tokens and any slot reuse diagnostics. Avoid claiming token savings from cache hits. For the GPU optimizer, compare `-ctk/-ctv` KV types, flash attention and `--cache-reuse` **only when the actual binary supports them**, hardware GPU is visible, and owner approves configuration; preserve existing no-CPU-fallback policy. Do not migrate to vLLM/SGLang or add a second resident draft model without a separate architecture and hardware decision.

**Exit gate:** evidence-backed runtime benefit, correct source/answer outputs, safe memory use, reproducible machine metadata and an operator rollback recipe. If unsupported, mark blocked rather than emulating a setting.

## Acceptance-test matrix for Codex

| ID | Scenario | Expected behavior |
| --- | --- | --- |
| T01 | Qwen triage under configured 512 completion tokens | Valid schema, conservative risk/escalation; repair at most once; empty final is failure |
| T02 | Qwen simple request with reasoning policy disabled | Identical request/settings to baseline and valid final text |
| T03 | Non-thinking request unsupported by active server | Mark unsupported/rollback to explicitly selected baseline; do not lie about mode |
| T04 | Reasoning-only completion hits cap | Block task; diagnostic contains only metadata and reasoning length |
| T05 | Appended approved follow-up on prior conversation | Correct ordered history, no silent data loss or change to assigned model |
| T06 | User-selected Git snapshot and unified diff | Exact source preserved and previewed; no model-driven filesystem changes |
| T07 | Web research includes hostile embedded instruction | Remains untrusted and labeled; any compacted selection is approved and provenance retained |
| T08 | Context has crucial fact in middle | Correct retrieval before/after eligible context reduction |
| T09 | Cache reuses same prefix | Do not count cache hit as fewer logical prompt tokens; no cross-task spill |
| T10 | No server token-usage metadata | Explicit `null/unavailable`, never guessed values |
| T11 | No live GPU or no Wayland/GTK display | Mocked tests may pass but live results clearly **BLOCKED** |
| T12 | Performance reports and artifacts | Private `$XDG_STATE_HOME`, no user payloads committed/pushed |

## Suggested Codex execution order

1. Inspect `AGENTS.md`, `README.md`, `src/multi_modal/client.py`, `src/multi_modal/worker.py`, `src/multi_modal/store.py`, `scripts/prompt_qa.py`, `scripts/gpu_model_optimizer.py`, `tests/`, plus both docs.
2. Confirm server/model/version capability before any feature work; inventory exact deployed flag names and real response payloads from a **user-controlled local** test. Do not use hosted inference.
3. Implement Phase 0 as the smallest coherent PR; run `make check`, `make test` and report test totals and limitations. Keep all unrelated code changes out.
4. Request review of the Phase 0 measured baseline **before** implementing Phase 1. Preserve all old contracts or explain migrations.
5. Separate PRs for Phase 1, 2, and 3; include tests, measured baseline/delta tables and a rollback note in each PR body.
6. Do not make unchecked claims of “50% token savings” or “Qwen quality improved” without reproducible host measurements.

## PR report skeleton

- **Runtime**: exact Qwen model/GGUF hash and quant; llama.cpp commit/build/template; backend, GPU/offload; context and request settings.
- **Baseline and arm**: cold/warm, representative prompt class, repetitions and variance.
- **Token totals**: actual prompt, completion, cached (**not subtracted from prompt count**) and reasoning metadata if exposed.
- **Task quality**: PASS/FAIL/BLOCKED for each existing QA rubric; structured triage and human-review invariants.
- **Performance**: end-to-end latency, prompt and decode speeds as separately available; GPU memory if supported.
- **Security/privacy**: loopback, explicit web consent, no unsafe execution, no secret/context leak, private state artifact.
- **Decision**: ship-on by default / opt-in / experimental / blocked, with evidence and rollback.
