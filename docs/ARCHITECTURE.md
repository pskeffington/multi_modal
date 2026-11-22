# Architecture

## Desktop UI

Use GTK4/PyGObject to provide a native Linux desktop window. The launch script uses the system Python so it can load the distribution's GTK bindings. No embedded web server or hosted UI is required.

## Task pipeline

`draft → triage_pending → queued → running → review_pending → done`

Exceptional paths include `needs_attention` for unsafe or low-confidence triage, `blocked` for model or runtime failures, `revision_queued` after Codex requests changes, and `cancelled` for work not yet submitted to inference. The assigned-model field persists through review and revision cycles.

The app uses one background worker and a process lock. Queue ordering uses advisory priority followed by age; users can override model assignment before execution.

## Model boundary

The worker calls an OpenAI-compatible llama.cpp API on loopback only. Qwen is the default triage and task model; GLM is an optional escalation. Model IDs and the router URL can be changed through documented environment variables. Generated responses are untrusted text. The worker has no arbitrary filesystem or command interface.

## Review boundary

Every completion or blocker produces a local review packet with the request, score, assignment, and model response. The user copies it to Codex and pastes the result back. Requested changes return to the same assigned model. The application does not start Codex CLI.

## Git workspace boundary

The user can attach a checkout and explicitly select bounded UTF-8 source files. The UI previews the exact snapshot sent to the local model. A proposed unified diff is applied only after a pasted Codex `APPROVE`, patch preview, per-path safety checks, a successful `git apply --check`, and a second user confirmation. Symlinks, paths outside the checkout, sensitive-looking paths, binary/mode/rename patches, and dirty targets are rejected. The app changes the working tree only; it does not stage, commit, or push.

## Persistence and privacy

Store tasks, scores, model output, source snapshots, review packets, and events in SQLite under `$XDG_DATA_HOME/multi_modal` (default `~/.local/share/multi_modal`). Do not store user records in the checkout. `.gitignore` excludes local databases, environment files, and Python build artifacts.
