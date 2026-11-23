# Local operator guide

## Launch

- Run `scripts/launch.sh`, or install `scripts/install-user.sh` and open **Multi Modal Task Router** from the desktop menu.
- The router must be available at `http://127.0.0.1:9931`. The UI shows model IDs advertised by its `/v1/models` or `/models` endpoint.
- If it is offline, press **Start local router** in the GUI. This starts the configured `llama-router.service` through the active desktop user's systemd session, then waits for its model catalog. If startup fails, inspect `journalctl --user -u llama-router.service`; no root access is required.
- Optional environment overrides adapt the deployment without code edits: `MULTI_MODAL_ROUTER_URL` (must remain loopback HTTP), `MULTI_MODAL_QWEN_MODEL`, and `MULTI_MODAL_GLM_MODEL`.
- App data lives under `$XDG_DATA_HOME/multi_modal` or `~/.local/share/multi_modal`, with a private SQLite task journal.

## GPU optimization launcher

- Run `make install-gpu-optimizer` to install `multi-modal-gpu-optimize`, an application-menu entry, and a desktop icon. The icon opens a terminal so benchmark progress and GPU access blockers remain visible.
- Set `MULTI_MODAL_GPU_MODEL` to a local Qwen `.gguf` file, or launch `multi-modal-gpu-optimize --model /path/to/model.gguf`. Set `MULTI_MODAL_LLAMA_BENCH` if `llama-bench` is not on `PATH` or under `~/.local/lib/llama.cpp`.
- The optimizer requires llama.cpp to enumerate a hardware GPU and passes that exact device with 99 GPU layers and host offload disabled. It rejects CPU and software-renderer devices. It saves per-run measurements and a best tested configuration under `$XDG_STATE_HOME/multi_modal/gpu-optimizer`; no task prompts, outputs, or repo context are read or uploaded.
- It benchmarks prompt and generation throughput for context/batch combinations and saves a recommendation only. Apply settings to the model server manually after reviewing the report. No weights are fine-tuned and no server configuration is changed automatically.

## Task flow

Run `make test` for the scripted prompt, worker-state, llama.cpp HTTP-contract, report-storage, and GTK-binding regression checks. Those tests do not claim model answer quality. Run `make prompt-qa` from a shell that can reach the local router, or click **Run prompt QA** in the GUI to execute the suite from the desktop session. The 12-case live suite includes production triage with its single schema repair, 10 direct-answer prompts (arithmetic, explanation, constrained summary, coding edge cases, genuine multi-turn follow-up, untrusted web content, JSON-only output, ambiguity, context grounding, and translation), and a persisted app conversation that tests review approval and follow-up. It caps QA generations at 768 tokens, records per-case latency, emits progress, and continues after per-case model errors so the report retains the full matrix. Empty final answers are blocked with safe diagnostic metadata (finish reason, token count, and reasoning text length; reasoning text itself is never saved). The report includes deterministic format checks and manual criteria for semantic quality; it does not establish parity with a hosted assistant. The GUI automatically saves complete and partial reports at `$XDG_STATE_HOME/multi_modal/prompt-qa/latest.json` (default `~/.local/state/multi_modal/prompt-qa/latest.json`) with user-only permissions. Use **Open latest QA report** to retrieve it; the generated report window also offers a copy action.

1. Enter a task in the bottom composer and press Enter to submit (Shift+Enter inserts a line break). Use the left task list to revisit earlier conversations; persisted user and model turns appear in the main pane. Qwen returns complexity (1–5), priority (0–100), risk, confidence, rationale, and a suggested model. Triage requests schema-constrained JSON when supported by the local llama.cpp server, validates the response, and makes one repair attempt if needed. If both responses fail validation before routing, use **Run blocked prompt on Qwen · skip triage** on that task to preserve and answer its original prompt; risk and complexity remain unassessed. For future prompts, **Ask Qwen directly · skip triage** is also available.
2. GLM recommendations are honored only at complexity 3 or higher and confidence 0.70 or higher; other recommendations stay on Qwen. High-risk work or confidence below 0.55 requires a human choice. Task details show why a model was assigned and whether its configured ID is advertised by the local router. For queued, blocked, or attention-required tasks, the assignment dropdown can change the model before work starts; the manual override is recorded in the task history and routing reason.
3. The worker processes one request at a time. Qwen is the default; GLM can be much slower and should be chosen for work that warrants the wait.
4. Completion or a detected blocker creates a review packet. Copy it to Codex manually, paste the response, and record approval or return changes. Revisions retain the original assigned local model and include prior conversation turns plus review notes in the next prompt. After recording `APPROVE`, use **Continue conversation** to ask a follow-up; it is added as another user turn and routed to the same model without repeating triage.

The task status line describes the next action for the selected state (triage, user decision, queue, inference, review, blocker recovery, or completion). Read that line alongside the event history when resuming older tasks.

## Model readiness and web research

- Use **Refresh models** in the header to check the configured Qwen and GLM IDs against the local router. A unique quantized model variant can satisfy a base configured ID; ambiguous or missing IDs are reported. Models shown as unloaded are configured for lazy loading.
- For research, enter the task draft and choose **Research prompt on web**. Confirm the exact query preview to search DuckDuckGo's [non-JavaScript HTML results](https://duckduckgo.com/duckduckgo-help-pages/features/non-javascript) and scrape up to three public HTTPS pages. The app displays the extracted text with title and domain attribution and omits clickable URLs.
- Select **Include scraped text in next local task** to pass the displayed material to the configured loopback model. If the draft changes after the search, results are marked stale and cannot be attached until a fresh search. Treat all scraped content as untrusted.
- Only the confirmed query and requested public pages leave the app. Model outputs, Git context, task history, and settings remain local. The scraper enforces response size limits, timeouts, HTTPS, and public-address checks; sites may block automated requests, in which case available search snippets are shown.

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
