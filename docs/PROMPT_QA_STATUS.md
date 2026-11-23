# Prompt QA status

## Baseline and scope

- Repository: `multi_modal`
- Source commit: `5fcf8134b60ea6aec11cb6f3399e929a1c5b6c95` (published to `main`)
- Observed: `2026-11-23 05:51 UTC`
- QA scope: prompt routing and validation, persisted multi-turn conversation, response lifecycle, revision context, llama.cpp client contract, Qwen live prompt quality, and GTK prompt workflow.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Prompt/workflow contract suite | PASS | `make test`: 47 tests passed using scripted model replies. Covers strict triage schema validation and single repair, unsupported structured-output fallback, blocked-prompt recovery, response lifecycle, revisions, approved follow-ups, desktop-router control, untrusted research/repository context, QA rubrics, continued suite after empty completions, private report persistence, and the full tester's persisted review/follow-up lifecycle. |
| Build and package checks | PASS | `make check`, `python3 -m py_compile scripts/prompt_qa.py`, and `git diff --check` completed with exit 0. |
| Live Qwen prompt matrix from this shell | BLOCKED | `make prompt-qa` exited 2: local Qwen endpoint could not be reached (`Operation not permitted` from this execution environment). A separate probe to `127.0.0.1:9931` found no listening service. No model answers were generated or scored. |
| Live Qwen prompt matrix from desktop GUI | FAIL | User-provided report from `2026-11-23T05:33:10Z`: 4/10 automated cases passed, 6 failed. Four of ten answers were empty; the other failures were coding edge-case example mismatch and an ambiguity answer exceeding its 100-word limit. Arithmetic, multi-turn follow-up, context grounding, and translation passed their automated checks. This report came from the earlier 10-case runner and lacks finish reason/token metadata; semantic review was not recorded. |
| Live Qwen full-system QA from desktop GUI | BLOCKED pending updated report | The updated in-app **Run prompt QA** action launches a 12-case suite: production triage/repair, 10 prompt types, and a persisted app conversation. It now saves complete/partial JSON reports privately and diagnoses empty completions without recording reasoning text. The updated app must be reopened and the suite run for full-system evidence. |
| Start the local llama router | BLOCKED | `systemctl --user restart llama-router.service` could not connect to the user service bus (`Operation not permitted`). Prior host logs show the Qwen model had served requests, but that does not prove it is running now. |
| Desktop router recovery control | PASS (mocked) | The GUI's **Start local router** action uses only the fixed command `systemctl --user start llama-router.service`, then polls the local model catalog. Four unit checks cover already-running, successful start, service error, and unavailable desktop bus. Actual desktop-session startup remains unverified here. |
| Rendered GUI inspection | BLOCKED | `scripts/launch.sh` reports no active display. GTK initializes, but `Gdk.Display.get_default()` is `None`; visual layout and keyboard interaction were not observed. |
| GPU-backed inference | BLOCKED | This execution environment exposes neither `/dev/dri` nor `/dev/kfd`, and llama.cpp lists no available devices here. No CPU fallback was used. |

The prompt-recovery change, GUI layout refinement, and in-GUI QA runner are committed and pushed to `main` at `956514a830f94cdfd8975406add7b21cd43ad0b3`; report auto-save and empty-generation diagnostics are committed and pushed at `5fcf8134b60ea6aec11cb6f3399e929a1c5b6c95`; installer executable permission is preserved. The user-provided earlier-run report is direct live-answer evidence and shows material Qwen failures, but its old schema omits server completion metadata. The latest direct probe to `http://127.0.0.1:9931/v1/models` failed with curl exit 7 (`Could not connect to server`), and GTK returned no default display when probed against the discovered Wayland socket, so the updated suite and rendered GUI remain unverified in this shell. The user reports that the desktop GUI shows the router online.

## Interpretation

The passing scripted checks establish application behavior when the backend returns the supplied test replies, including persistent follow-up history after approval. They do not establish that Qwen answers accurately, follows instructions, handles follow-ups well, or matches a hosted assistant's quality. The Codex-style GUI structure and GTK API compatibility are implemented, but rendering remains unverified.

## Next verification

Reopen the updated desktop app from its desktop entry, confirm the router is online, and select **Run prompt QA**. Review the saved 12-case report and each answer against its rubric. The report location is shown in the app status and can be reopened with **Open latest QA report**. Inspect request display, response readability, Enter/Shift+Enter behavior, web-research attachment, follow-up turns, and review handoff. Record GPU offload from the llama server's startup log before calling GPU deployment verified. For each subsequent change, run the scripted contract checks locally and the in-app live suite when the desktop router is available; retain the report in the user's local state directory.
