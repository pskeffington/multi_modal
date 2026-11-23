# Prompt QA status

## Baseline and scope

- Repository: `multi_modal`
- Source commit: `0e69cabd0750a8345693ed9edaac163356939b27`
- Observed: `2026-11-23 05:17 UTC`
- QA scope: prompt routing and validation, persisted multi-turn conversation, response lifecycle, revision context, llama.cpp client contract, Qwen live prompt quality, and GTK prompt workflow.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Prompt/workflow contract suite | PASS | `make test`: 35 tests passed using scripted model replies. Includes constrained triage JSON, fallback when structured output is unsupported, direct Qwen recovery for an unrouted malformed-triage task, response lifecycle, revisions, approved follow-ups, desktop-router control, untrusted research/repository context, deterministic prompt-evaluation rubrics, a check that the live follow-up sends Qwen's generated first answer as conversation history, and a check that live QA uses the production assistant system prompt. |
| Build and package checks | PASS | `make check`, `python3 -m py_compile scripts/prompt_qa.py`, and `git diff --check` completed with exit 0. |
| Live Qwen prompt matrix | BLOCKED | `make prompt-qa` exited 2: local Qwen endpoint could not be reached (`Operation not permitted` from this execution environment). A separate probe to `127.0.0.1:9931` found no listening service. No model answers were generated or scored. The expanded 10-case matrix now includes a genuine two-turn exchange, per-case latency, and deterministic format checks; those live checks remain unrun. |
| Start the local llama router | BLOCKED | `systemctl --user restart llama-router.service` could not connect to the user service bus (`Operation not permitted`). Prior host logs show the Qwen model had served requests, but that does not prove it is running now. |
| Desktop router recovery control | PASS (mocked) | The GUI's **Start local router** action uses only the fixed command `systemctl --user start llama-router.service`, then polls the local model catalog. Four unit checks cover already-running, successful start, service error, and unavailable desktop bus. Actual desktop-session startup remains unverified here. |
| Rendered GUI inspection | BLOCKED | `scripts/launch.sh` reports no active display. GTK initializes, but `Gdk.Display.get_default()` is `None`; visual layout and keyboard interaction were not observed. |
| GPU-backed inference | BLOCKED | This execution environment exposes neither `/dev/dri` nor `/dev/kfd`, and llama.cpp lists no available devices here. No CPU fallback was used. |

The prompt-recovery change and GUI layout refinement are committed on `main`; installer executable permission is preserved. The latest direct probe to `http://127.0.0.1:9931/v1/models` failed with curl exit 7 (`Could not connect to server`), and GTK returned no default display when probed against the discovered Wayland socket, so no live Qwen answer or GUI rendering was observed in this shell.

## Interpretation

The passing scripted checks establish application behavior when the backend returns the supplied test replies, including persistent follow-up history after approval. They do not establish that Qwen answers accurately, follows instructions, handles follow-ups well, or matches a hosted assistant's quality. The Codex-style GUI structure and GTK API compatibility are implemented, but rendering remains unverified.

## Next verification

Launch or restart the desktop app from its desktop entry and use **Start local router**. Then run `make prompt-qa` from a shell in the same desktop session and review every answer against its included rubric. Inspect request display, response readability, Enter/Shift+Enter behavior, web-research attachment, follow-up turns, and review handoff. Record GPU offload from the llama server's startup log before calling GPU deployment verified.
