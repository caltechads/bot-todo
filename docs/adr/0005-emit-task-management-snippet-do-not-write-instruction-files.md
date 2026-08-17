# 5. Emit the Task Management Snippet; do not write instruction files

Status: accepted (2026-08-17)

## Context

Consuming repositories need a copy-paste Task Management section for
`AGENTS.md` or `CLAUDE.md`. `init` is a natural onboarding moment, but those
files often already exist with other policy, and choosing which file to
mutate is a human decision. `init` is also not idempotent, so a snippet that
appears only on first init is easy to miss.

`--json` is already the agent-versus-human split. A second caller detector
would duplicate that contract and invite interactive prompts, which the CLI
forbids.

## Decision

`bot-todo` never creates or edits `AGENTS.md` or `CLAUDE.md`.

Successful human `init` prints `initialized`, a blank line, then the Task
Management Snippet. JSON `init` keeps `data.repository` and adds additive
`data.snippet`. JSON Schema Version stays 1.

`snippet` is a selector-free packaged-text command, like `install-skill`: it
rejects `--root`, `--repo`, `--all`, and `--config`, needs no Task
Repository, and returns the same markdown. Agents retrieve it later with
`bot-todo --json snippet` and ask whether to add it; they do not write the
instruction files unless asked.

## Considered Options

- Auto-write or append `AGENTS.md` / `CLAUDE.md` on `init` — surprising and
  easy to duplicate or clobber existing policy.
- Detect “agent vs human” besides `--json` — a second, fragile channel.
- Emit on `init` only — lost after `already_initialized`.
