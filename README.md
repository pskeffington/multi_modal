# multi_modal
multi-modal is a model selector based on tasking

## Local desktop task router

This repository contains an open-source GTK4 desktop app for triaging tasks with local models, assigning them to model queues, and preparing a manual Codex review packet when a local model completes or blocks. Task data, source snapshots, and outputs stay in the user's XDG data directory. Model calls are loopback-only; generated commands are never executed.

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
make run          # Start the desktop application
make install-user # Install a per-user desktop launcher
```

`make check` writes its temporary launcher under a fresh temporary directory and removes it when validation finishes. It does not touch the user's application data.

Install a per-user Linux desktop launcher:

```sh
sh scripts/install-user.sh
```

Qwen handles triage and is the default task model. GLM is available for user-confirmed escalation and may take much longer. Inference is serialized. Codex review is a copy/paste handoff; the app does not launch Codex CLI.

For repository tasks, users can attach a Git checkout and selected text files as local model context. A proposed unified diff can be applied to clean working-tree files only after Codex approval, validation, and a separate confirmation. The app never stages, commits, or pushes. See [the operator guide](docs/OPERATIONS.md) and [architecture notes](docs/ARCHITECTURE.md).

## Repository sweep and change control

Documentation and maintenance passes follow the generalized [repository sweep decision-routing policy](https://github.com/pskeffington/agent_skills/blob/main/docs/REPO_SWEEP_DECISION_ROUTING.md). The policy keeps proposed changes reviewable, records blockers as evidence-backed handoffs, and does not imply that local model output or a clean working tree is production approval.

The project is MIT-licensed. See [LICENSE](LICENSE).
