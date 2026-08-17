# Task Management Snippet implementation plan

**Tasks:** T009, T012.

**ADR:** [docs/adr/0005-emit-task-management-snippet-do-not-write-instruction-files.md](../../docs/adr/0005-emit-task-management-snippet-do-not-write-instruction-files.md)

**Goal:** The package emits a copy-paste Task Management Snippet from `init`
and from selector-free `snippet`, never writing `AGENTS.md` or `CLAUDE.md`.
This repository's `AGENTS.md` also requires claiming a task before planning
or implementing.

## Settled contract

See [spec.md](spec.md). JSON Schema Version stays 1. `install-skill` still
copies only the `todo/` skill allowlist.

## Architecture

A cohesive `TaskManagementSnippet` class loads
`src/bot_todo/skill_assets/task_management.md` through `importlib.resources`
and builds `CommandOutcome` values for `snippet` and `init`. The CLI treats
`snippet` like `install-skill`: no Task Repository, no selectors, no
`--config`.

## Implementation order

### 1. Persist spec, ADR, glossary, and this plan

Already linked from T009 and T012.

### 2. Failing tests, then loader

- Packaged markdown plus `TaskManagementSnippet.text()` / `outcome()` /
  `initialized()`.
- `snippet` human and JSON output; selector rejection.
- Human `init` is no longer exactly `initialized`; JSON `init` includes
  `data.snippet`.

### 3. Wire the CLI

[`src/bot_todo/cli.py`](../../src/bot_todo/cli.py): parser, selector
validation, `main` dispatch, `_init`.

### 4. This-repo docs and the todo skill

[`AGENTS.md`](../../AGENTS.md),
[`src/bot_todo/skill_assets/todo/SKILL.md`](../../src/bot_todo/skill_assets/todo/SKILL.md),
[`README.md`](../../README.md).

### 5. Quality gate

`ruff`, `mypy`, `make napoleon-gate`, `make pytest` on the affected tests.
