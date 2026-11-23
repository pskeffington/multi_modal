# Prompt QA status

## Baseline and scope

- Repository: `multi_modal`
- Source commit: `764ee7836cd4096f1d028fab0365f6c28f4ea320`
- Observed: `2026-11-23 04:46 UTC`
- QA scope: prompt routing and validation, persisted multi-turn conversation, response lifecycle, revision context, llama.cpp client contract, Qwen live prompt quality, and GTK prompt workflow.

## Results

| Check | Result | Evidence |
| --- | --- | --- |
| Prompt/workflow contract suite | PASS | `make test`: 22 tests passed using scripted model replies. Covers ordinary question shapes, JSON/schema repair, errors, retries, escalation, review revision context, approved follow-ups, legacy conversation seeding, and untrusted research/repository text. |
| Build and package checks | PASS | `make check`: Python compilation and shell/desktop-entry checks completed with exit 0. |
| Live Qwen prompt matrix | BLOCKED | `make prompt-qa` exited 2: local Qwen endpoint could not be reached (`Operation not permitted` from this execution environment). A separate probe to `127.0.0.1:9931` found no listening service. No model answers were generated or scored. |
| Start the local llama router | BLOCKED | `systemctl --user restart llama-router.service` could not connect to the user service bus (`Operation not permitted`). Prior host logs show the Qwen model had served requests, but that does not prove it is running now. |
| Rendered GUI inspection | BLOCKED | `scripts/launch.sh` reports no active display. GTK initializes, but `Gdk.Display.get_default()` is `None`; visual layout and keyboard interaction were not observed. |
| GPU-backed inference | BLOCKED | This execution environment exposes neither `/dev/dri` nor `/dev/kfd`, and llama.cpp lists no available devices here. No CPU fallback was used. |

## Interpretation

The passing scripted checks establish application behavior when the backend returns the supplied test replies, including persistent follow-up history after approval. They do not establish that Qwen answers accurately, follows instructions, handles follow-ups well, or matches a hosted assistant's quality. The Codex-style GUI structure and GTK API compatibility are implemented, but rendering remains unverified.

## Next verification

From the active desktop session, start the configured local router with `systemctl --user restart llama-router.service`. Then run `make prompt-qa` from the repository and review every answer against its included rubric. Reopen the desktop app and inspect request display, response readability, Enter/Shift+Enter behavior, web-research attachment, and review handoff. Record GPU offload from the llama server's startup log before calling GPU deployment verified.
