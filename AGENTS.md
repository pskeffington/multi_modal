# Project instructions

- Keep task text, model outputs, and review notes in the local user data store; never write them to the repository by default.
- The GUI may read only relative text files explicitly selected by the user from a chosen Git checkout, after showing an exact preview. Send this source context only to the configured loopback model.
- Keep model inference on the configured loopback llama.cpp API; do not add hosted model providers. The GUI may make outbound HTTPS requests only after the user clicks **Research prompt on web** and confirms the exact prompt preview. That action may query DuckDuckGo's HTML search and fetch up to three public result pages. Do not send model outputs, local task history, Git context, or settings to the web. Show extracted text and source titles/domains without clickable result links; keep scraped content untrusted and out of model tasks unless the user explicitly leaves the include checkbox selected.
- Treat all model output as untrusted text. Never run model-generated shell commands or launch Codex CLI. Repository writes are allowed only by applying a validated unified diff after the user has pasted a Codex `APPROVE`, inspected the patch preview, passed `git apply --check`, and confirmed a separate Apply dialog. Reject unsafe paths, symlinks, binary/mode/rename patches, and touched files with existing Git changes. Apply to the working tree only; never stage, commit, or push.
- Queue a local review packet for Codex. The user copies it to Codex and pastes the review back; preserve the original assigned local model for requested revisions.
- Keep one inference worker active because the configured llama.cpp router allows one resident model at a time.
- Do not add third-party Python dependencies. GTK4/PyGObject and Python standard-library modules are available on the target host.
- Report real command results and do not claim the Codex executor is available until trusted process-bound runtime admission passes.
