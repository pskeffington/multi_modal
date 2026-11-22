# Product roadmap

## Current capabilities

- Linux GTK4 desktop task composer with Qwen and GLM queues.
- Local Qwen triage for complexity, priority, risk, confidence, and model assignment.
- Serialized llama.cpp inference over loopback HTTP.
- Private task journal under the user's XDG data directory.
- Manual Codex review packets and revision routing back to the assigned local model.
- Optional user-selected Git checkout and source context, with a Codex-approved, validated unified-diff path into the working tree.

## Follow-up work

- Add automated unit and integration coverage for routing, journal recovery, patch parsing, and Git safety boundaries.
- Add a reproducible packaging path for common Linux distributions.
- Improve model health and long-running inference progress reporting across llama.cpp router variants.
- Consider optional staging as a separate, explicit user action after working-tree review.

## Release gates

- Keep task data, model output, source snapshots, and local settings outside the repository and excluded from version control.
- Keep all model API traffic on the configured loopback endpoint.
- Never execute model-generated shell commands.
- Require Codex approval and explicit user confirmation before applying a model-proposed patch.
- Review the resulting Git diff before any user-managed stage, commit, or publication action.
