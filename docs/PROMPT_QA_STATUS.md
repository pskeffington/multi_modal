# Prompt QA status

## Baseline and scope

- Repository: `multi_modal`
- Source commit: `2740a0decb212516100a2f6bcff17c80b01255af` (published to `main`; current rubric refinements are pending commit)
- Observed: `2026-11-23 05:54 UTC`
- QA scope: prompt routing and validation, persisted multi-turn conversation, response lifecycle, revision context, llama.cpp client contract, Qwen live prompt quality, and GTK prompt workflow.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Prompt/workflow contract suite | PASS | `make test`: 49 tests passed. This includes explicit prompt-aligned coding/ambiguity constraints, universal empty-answer rejection, syntax-only parsing for Python code fences (never execution), report persistence, and prior worker/router state coverage. |
| Build and package checks | PASS | `make check`, `python3 -m py_compile scripts/prompt_qa.py`, and `git diff --check` completed with exit 0. |
| Live Qwen prompt matrix from this shell | BLOCKED | `make prompt-qa` exited 2: local Qwen endpoint could not be reached (`Operation not permitted` from this execution environment). A separate probe to `127.0.0.1:9931` found no listening service. No model answers were generated or scored. |
| Live Qwen prompt matrix from desktop GUI | FAIL | User-provided report from `2026-11-23T05:33:10Z`: 4/10 automated cases passed, 6 failed. Four answers were empty. Two other automated failures exposed rubric mismatch: requested IPv4 examples were not specified exactly, and the ambiguity answer had an unrequested 100-word cap. Manual inspection found one generated Python test had an unquoted dotted address and was invalid syntax. Arithmetic, multi-turn follow-up, context grounding, and translation passed automated checks. This earlier 10-case report lacks finish-reason/token metadata; broader semantic review was not recorded. |
| Live Qwen full-system QA from desktop GUI | BLOCKED pending updated report | The updated in-app **Run prompt QA** action launches a 12-case suite: production triage/repair, 10 prompt types, and a persisted app conversation. It now saves complete/partial JSON reports privately, diagnoses empty completions without recording reasoning text, aligns coding/ambiguity constraints with their rubrics, and parses generated Python syntax without execution. The updated app must be reopened and the suite run for full-system evidence. |
| Start the local llama router | BLOCKED | `systemctl --user restart llama-router.service` could not connect to the user service bus (`Operation not permitted`). Prior host logs show the Qwen model had served requests, but that does not prove it is running now. |
| Desktop router recovery control | PASS (mocked) | The GUI's **Start local router** action uses only the fixed command `systemctl --user start llama-router.service`, then polls the local model catalog. Four unit checks cover already-running, successful start, service error, and unavailable desktop bus. Actual desktop-session startup remains unverified here. |
| Rendered GUI inspection | BLOCKED | `scripts/launch.sh` reports no active display. GTK initializes, but `Gdk.Display.get_default()` is `None`; visual layout and keyboard interaction were not observed. |
| GPU-backed inference | BLOCKED | This execution environment exposes neither `/dev/dri` nor `/dev/kfd`, and llama.cpp lists no available devices here. No CPU fallback was used. |

The prompt-recovery change, GUI layout refinement, and in-GUI QA runner are committed and pushed to `main` at `956514a830f94cdfd8975406add7b21cd43ad0b3`; report auto-save and empty-generation diagnostics are committed and pushed at `5fcf8134b60ea6aec11cb6f3399e929a1c5b6c95`; current rubric refinements are pending commit; installer executable permission is preserved. The user-provided earlier-run report is direct live-answer evidence and shows material Qwen failures, but its old schema omits server completion metadata. No saved report from the updated runner is present in the default state directory or elsewhere under the home directory. The latest direct probe to `http://127.0.0.1:9931/v1/models` failed with curl exit 7 (`Could not connect to server`), and GTK returned no default display when probed against the discovered Wayland socket, so the updated suite and rendered GUI remain unverified in this shell. The user reports that the desktop GUI shows the router online.

## Interpretation

The passing scripted checks establish application behavior when the backend returns the supplied test replies, including persistent follow-up history after approval. They do not establish that Qwen answers accurately, follows instructions, handles follow-ups well, or matches a hosted assistant's quality. The Codex-style GUI structure and GTK API compatibility are implemented, but rendering remains unverified.

## Next verification

Reopen the updated desktop app from its desktop entry, confirm the router is online, and select **Run prompt QA**. Review the saved 12-case report and each answer against its rubric. The report location is shown in the app status and can be reopened with **Open latest QA report**. Inspect request display, response readability, Enter/Shift+Enter behavior, web-research attachment, follow-up turns, and review handoff. Record GPU offload from the llama server's startup log before calling GPU deployment verified. For each subsequent change, run the scripted contract checks locally and the in-app live suite when the desktop router is available; retain the report in the user's local state directory.
