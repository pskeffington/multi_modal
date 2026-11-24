# Architecture

## Desktop UI

Use GTK4/PyGObject to provide a native Linux desktop window. The launch script uses the system Python so it can load the distribution's GTK bindings. No embedded web server or hosted UI is required.

## Task pipeline

`draft → queued (direct Qwen by default) → running → review_pending → done`

**Triage then route** is optional: `draft → triage_pending → queued → running → review_pending → done`.

Exceptional paths include `needs_attention` for unsafe or low-confidence triage, `blocked` for model or runtime failures, `revision_queued` after Codex requests changes, and `cancelled` for work not yet submitted to inference. The assigned-model field persists through review and revision cycles.

Each task also owns an ordered conversation log of user, model, web-research, and review-instruction turns. New tasks go directly to Qwen unless the user explicitly chooses **Triage then route**. After a response is approved, the user may append a follow-up to the same task. The worker sends the saved turns to the task's original assigned model without rerunning triage. Legacy task records are seeded into the conversation log when first opened or resumed.

The app uses one background worker and a process lock. Queue ordering uses advisory priority followed by age. Claiming queued work is atomic with reading the assigned model, so a user model override either commits before execution and is honored or is rejected after the worker has claimed the task. User review and retry actions also check the task's current state before changing it.

## Model boundary

The worker calls an OpenAI-compatible llama.cpp API on loopback only. Qwen is the default task model; GLM is an optional escalation when the user chooses triage and routing. Triage requests llama.cpp schema-constrained JSON and validates bounded numeric scores and a risk category. If the server rejects structured output, the client retries with a validated JSON-only prompt; malformed output gets one repair attempt. A still-unrouted triage failure can be explicitly sent to Qwen directly from the blocked task, with risk and complexity left unassessed. The router accepts a GLM recommendation only at complexity 3 or higher and confidence 0.70 or higher; otherwise it keeps Qwen. High risk or confidence below 0.55 pauses for user input regardless of model recommendation. The reason for each assignment is stored and shown in task details. Model IDs and the router URL can be changed through documented environment variables. Generated responses are untrusted text. The worker has no arbitrary filesystem or command interface.

The GUI refreshes the local model catalog at startup, on request, and periodically. If the endpoint is offline, the GUI can start the existing `llama-router.service` through `systemctl --user` in the active desktop session, then poll the loopback catalog for readiness. This uses the desktop user's D-Bus session and does not require root or shell interpolation. It resolves an exact configured model ID or a unique quantized variant advertised by llama.cpp; ambiguous or absent IDs are reported and cannot be submitted for triage/assignment. Unloaded but configured models remain selectable because the router may load them on demand.

## Web research boundary

Web research has two bounded paths: the user can confirm a visible draft query, or the local model can request one `web_search` action when current public facts are needed. The app sends only the search query to DuckDuckGo, then fetches at most three public HTTPS pages with response-size and timeout limits and private-host/redirect checks. Model-requested queries exclude private context by system instruction; retrieved text is shown in the conversation as untrusted evidence and sent only to the configured loopback model. Model answers, task history, Git context, and settings are never sent to web search.

## Review boundary

Every completion or blocker produces a local review packet with the request, score, assignment, and model response. The user copies it to Codex and pastes the result back. Requested changes return to the same assigned model and are appended as a user turn, preserving earlier context. Approved tasks can continue as a conversation; each subsequent model response also waits for Codex review. The application does not start Codex CLI.

## Git workspace boundary

The user can attach a checkout and explicitly select bounded UTF-8 source files. The UI previews the exact snapshot sent to the local model. A proposed unified diff is applied only after a pasted Codex `APPROVE`, patch preview, per-path safety checks, a successful `git apply --check`, and a second user confirmation. Symlinks, paths outside the checkout, sensitive-looking paths, binary/mode/rename patches, and dirty targets are rejected. The app changes the working tree only; it does not stage, commit, or push.

## Persistence and privacy

Store tasks, conversation turns, scores, model output, source snapshots, review packets, and events in SQLite under `$XDG_DATA_HOME/multi_modal` (default `~/.local/share/multi_modal`). Do not store user records in the checkout. `.gitignore` excludes local databases, environment files, and Python build artifacts.
