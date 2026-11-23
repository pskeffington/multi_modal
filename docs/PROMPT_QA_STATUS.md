# Prompt QA status

## Baseline and scope

- Repository: `multi_modal`
- Source commit: `956514a830f94cdfd8975406add7b21cd43ad0b3` (published to `main`)
- Observed: `2026-11-23 05:46 UTC`
- QA scope: prompt routing and validation, persisted multi-turn conversation, response lifecycle, revision context, llama.cpp client contract, Qwen live prompt quality, and GTK prompt workflow.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Prompt/workflow contract suite | PASS | `make test`: 42 tests passed using scripted model replies. Covers strict triage schema validation and single repair, unsupported structured-output fallback, blocked-prompt recovery, response lifecycle, revisions, approved follow-ups, desktop-router control, untrusted research/repository context, QA rubrics, and the full tester's persisted review/follow-up lifecycle. |
| Build and package checks | PASS | `make check`, `python3 -m py_compile scripts/prompt_qa.py`, and `git diff --check` completed with exit 0. |
| Live Qwen prompt matrix from this shell | BLOCKED | `make prompt-qa` exited 2: local Qwen endpoint could not be reached (`Operation not permitted` from this execution environment). A separate probe to `127.0.0.1:9931` found no listening service. No model answers were generated or scored. |
| Live Qwen full-system QA from desktop GUI | BLOCKED pending report | The user reports the GUI displays the router online and engaged the earlier runner. Server journal entries show multiple Qwen generations between 00:33 and 00:39 local, but the report and answers have not been received, so quality cannot be scored. The updated in-app **Run prompt QA** action launches a 12-case suite: production triage/repair, 10 prompt types, and a persisted app conversation. The updated app must be reopened and the suite run for full-system evidence. |
| Start the local llama router | BLOCKED | `systemctl --user restart llama-router.service` could not connect to the user service bus (`Operation not permitted`). Prior host logs show the Qwen model had served requests, but that does not prove it is running now. |
| Desktop router recovery control | PASS (mocked) | The GUI's **Start local router** action uses only the fixed command `systemctl --user start llama-router.service`, then polls the local model catalog. Four unit checks cover already-running, successful start, service error, and unavailable desktop bus. Actual desktop-session startup remains unverified here. |
| Rendered GUI inspection | BLOCKED | `scripts/launch.sh` reports no active display. GTK initializes, but `Gdk.Display.get_default()` is `None`; visual layout and keyboard interaction were not observed. |
| GPU-backed inference | BLOCKED | This execution environment exposes neither `/dev/dri` nor `/dev/kfd`, and llama.cpp lists no available devices here. No CPU fallback was used. |

The prompt-recovery change, GUI layout refinement, and in-GUI QA runner are committed and pushed to `main` at `956514a830f94cdfd8975406add7b21cd43ad0b3`; installer executable permission is preserved. The latest direct probe to `http://127.0.0.1:9931/v1/models` failed with curl exit 7 (`Could not connect to server`), and GTK returned no default display when probed against the discovered Wayland socket, so no live Qwen answer or GUI rendering was observed in this shell. The user reports that the desktop GUI shows the router online; the in-app runner executes QA through that session.

## Interpretation

The passing scripted checks establish application behavior when the backend returns the supplied test replies, including persistent follow-up history after approval. They do not establish that Qwen answers accurately, follows instructions, handles follow-ups well, or matches a hosted assistant's quality. The Codex-style GUI structure and GTK API compatibility are implemented, but rendering remains unverified.

## Next verification

Reopen the updated desktop app from its desktop entry, confirm the router is online, and select **Run prompt QA**. Review the generated 12-case report and each answer against its rubric. Inspect request display, response readability, Enter/Shift+Enter behavior, web-research attachment, follow-up turns, and review handoff. Record GPU offload from the llama server's startup log before calling GPU deployment verified. For each subsequent change, run the scripted contract checks locally and the in-app live suite when the desktop router is available; attach the report to the change record.
