# multi_modal
multi-modal is a model selector based on tasking

## Local desktop task router

This repository contains an open-source GTK4 desktop app for triaging tasks with local models, assigning them to model queues, and preparing a manual Codex review packet when a local model completes or blocks. Task records, source snapshots, and outputs are stored in the user's XDG data directory. Model inference stays on the loopback llama.cpp router. Qwen can request one bounded web search for current public facts; only the query goes to DuckDuckGo and retrieved pages return to the local conversation as untrusted evidence. The GUI also supports a user-confirmed manual search. Generated commands are never executed.

Model-requested and user-confirmed searches scrape up to three public HTTPS result pages with redirect, private-host, size, and timeout checks. The GUI shows each query and extracted source text; model-requested results are sent only to the local model and remain labeled as untrusted evidence.

## Requirements

- Linux with GTK4 and its PyGObject bindings available to the system Python.
- Python 3.11 or newer.
- A local llama.cpp router exposing an OpenAI-compatible chat endpoint on loopback.

The default endpoint is `http://127.0.0.1:9931`, with Qwen3.5-9B and GLM-5.2 model IDs. Adapt these defaults with `MULTI_MODAL_ROUTER_URL`, `MULTI_MODAL_QWEN_MODEL`, and `MULTI_MODAL_GLM_MODEL`; the router URL must remain loopback HTTP.

Run from a checkout with GTK4/PyGObject available:

```sh
sh scripts/launch.sh
```

## Build and validate

No Python packages are installed by the project. GTK4/PyGObject come from the Linux distribution, and the launcher runs the system Python so those bindings remain available.

```sh
make build        # Compile the application modules
make check        # Compile, check shell syntax, and validate the installed desktop entry when available
make test         # Run prompt lifecycle, local API contract, QA storage, and GTK compatibility checks
make prompt-qa    # Run the full local Qwen system QA suite and print its JSON report
make run          # Start the desktop application
make install-user # Install a per-user desktop launcher
make install-gpu-optimizer # Install the GPU optimizer executable and desktop icon
```

`make check` writes its temporary launcher under a fresh temporary directory and removes it when validation finishes. It does not touch the user's application data.

The **Multi Modal GPU Optimizer** desktop icon runs GPU-only llama.cpp benchmarks across context and batch settings, then saves a private report under `$XDG_STATE_HOME/multi_modal/gpu-optimizer` (default `~/.local/state/multi_modal/gpu-optimizer`). Set `MULTI_MODAL_GPU_MODEL` to a local GGUF file, or provide `--model` when running `multi-modal-gpu-optimize`. The optimizer requires a hardware GPU device exposed by llama.cpp, rejects software Vulkan/CPU devices, and does not download models or fall back to CPU. It recommends benchmark settings; it does not fine-tune model weights or rewrite router configuration.

Install a per-user Linux desktop launcher:

```sh
sh scripts/install-user.sh
```

New prompts go directly to Qwen without triage. **Triage then route** is optional and requests schema-constrained JSON from llama.cpp, with validated repair and direct-Qwen recovery if the router returns an invalid schema. GLM is available for user-confirmed escalation and may take much longer. Inference is serialized. Ask follow-up questions in the same conversation without a review step. Optional Codex review and Git patch approval are tucked into a collapsed section; the app does not launch Codex CLI.

The desktop uses a conversation workspace with task history in a left sidebar, persisted user/model turns in the main pane, and a bottom composer. Press Enter to submit and Shift+Enter for a new line. Ask follow-ups directly from a completed response; prior turns are retained and the same model continues. Optional Codex review and Git patch approval are in the collapsed review section. Tool options for web research and Git context are grouped under the composer. If llama.cpp is offline, use **Start local router** in the GUI to start the configured `llama-router.service` from the active desktop user's systemd session. **Run prompt QA** executes the live Qwen evaluation from that same desktop session and opens the generated report in the app. Reports auto-save privately to `~/.local/state/multi_modal/prompt-qa/latest.json` (or `$XDG_STATE_HOME`), and every run is archived under `prompt-qa/runs/`; use **Open latest QA report** or **Browse QA reports** to retrieve them.

See [prompt QA status](docs/PROMPT_QA_STATUS.md) for the current regression evidence and the live-model checks that still need an active local Qwen/GPU session.
See the [token optimization evidence review](docs/TOKEN_OPTIMIZATION_REVIEW.md) for the prompt budgets, context-size tradeoffs, and literature reviewed before adding compression mechanisms.

For repository tasks, users can attach a Git checkout and selected text files as local model context. A proposed unified diff can be applied to clean working-tree files only after Codex approval, validation, and a separate confirmation. The app never stages, commits, or pushes. See [the operator guide](docs/OPERATIONS.md) and [architecture notes](docs/ARCHITECTURE.md).

## Repository sweep and change control

Documentation and maintenance passes follow the generalized [repository sweep decision-routing policy](https://github.com/pskeffington/agent_skills/blob/main/docs/REPO_SWEEP_DECISION_ROUTING.md). The policy keeps proposed changes reviewable, records blockers as evidence-backed handoffs, and does not imply that local model output or a clean working tree is production approval.

The project is MIT-licensed. See [LICENSE](LICENSE).
