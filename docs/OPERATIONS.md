# Local operator guide

## Launch

- Run `scripts/launch.sh`, or install `scripts/install-user.sh` and open **Multi Modal Task Router** from the desktop menu.
- The router must be available at `http://127.0.0.1:9931`. The UI shows model IDs advertised by its `/v1/models` or `/models` endpoint.
- Optional environment overrides adapt the deployment without code edits: `MULTI_MODAL_ROUTER_URL` (must remain loopback HTTP), `MULTI_MODAL_QWEN_MODEL`, and `MULTI_MODAL_GLM_MODEL`.
- App data lives under `$XDG_DATA_HOME/multi_modal` or `~/.local/share/multi_modal`, with a private SQLite task journal.

## Task flow

1. Enter a task and submit it. Qwen returns complexity (1–5), priority (0–100), risk, confidence, rationale, and a suggested model. JSON extraction tolerates surrounding prose or code fences, while scores and risk must pass schema checks.
2. GLM recommendations are honored only at complexity 3 or higher and confidence 0.70 or higher; other recommendations stay on Qwen. High-risk work or confidence below 0.55 requires a human choice. Task details show why a model was assigned. For queued tasks, the assignment dropdown can change the model before work starts.
3. The worker processes one request at a time. Qwen is the default; GLM can be much slower and should be chosen for work that warrants the wait.
4. Completion or a detected blocker creates a review packet. Copy it to Codex manually, paste the response, and record approval or return changes. Revisions retain the original assigned local model.

## Git checkout workflow

1. Before submitting a repository task, choose the Git checkout in the task composer. Optionally enter specific relative source paths and load them; the UI shows the exact UTF-8 snapshot that will be included in the local model request. Do not select secrets or files you do not want in the model context.
2. For repository tasks, ask the model to return a unified diff. The right-side Git patch panel extracts and displays the proposal.
3. Copy the completion packet to Codex and paste a response beginning with `APPROVE` to close the review. A patch cannot be applied without that approval.
4. Select **Validate patch**. The app checks patch syntax, target paths, symlinks, Git cleanliness for touched files, and `git apply --check`.
5. Inspect the patch and press **Apply approved patch to working tree**; confirm the dialog. Review the resulting changes in Git. The app does not stage, commit, or push.

## Boundaries

- Requests go only to a loopback HTTP endpoint. There is no hosted provider, arbitrary command runner, or model-driven file writer.
- Treat model scores and output as untrusted suggestions.
- A blocked task can be retried after fixing local server/model availability. Restarted in-flight work is marked blocked rather than silently replayed.
- Empty model responses are blockers, not successful review submissions; the assigned model can be retried.
- Automatic Codex CLI execution is not enabled; trusted host process admission remains a separate blocker.
