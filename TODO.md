# TODO — Bot Todo
<!-- todo-format: 2; next-id: 15 -->

## P0 — Critical / Blocking

## P1 — High Priority

- [ ] **T013** Prepare bot-todo for public deployment and deploy it #ops
  - Acceptance: Done when the package has the public-release metadata, license, and install docs required to ship, the distribution is published to PyPI, and a stranger can install and run bot-todo with uv tool install bot-todo (or the documented equivalent) without a checkout.
  - Context: README currently says the distribution is not on PyPI and documents checkout-only install. The wheel already installs and runs outside the checkout (T002, T003, T005). This task covers remaining release hygiene plus the actual publish.
  - Related: T003

## P2 — Backlog

- [ ] **T010** Add a NiceGUI Kanban web frontend #feature
  - Acceptance: Done when a NiceGUI Kanban board can browse and mutate tasks in a Task Repository through bot-todo's existing core rather than by hand-editing TODO.md, covering at least list, show, add, and complete, with columns that reflect task state.
  - Context: The CLI remains the programmatic interface. The UI is a human-facing Kanban frontend over the same Task Repository model.

## Done (recent)

- [x] **T011** Add a review state for work that needs validation #feature
  - Acceptance: Done when a task can move into a review state that means the work is finished but still needs validation, then be completed or returned to open from that state, with CLI, JSON, and the todo skill documenting the new state.
  - Context: Today a task is open, completed, or cancelled. Review sits between opened and completed so validation can happen before Outcome completed. Related Kanban work: T010. Plan: .scratch/review-state/plan.md ADR: docs/adr/0006-review-is-an-in-section-lifecycle-state.md Glossary: CONTEXT.md
  - Related: T010
  - Outcome: completed
  - Closed: 2026-08-17

- [x] **T012** Require claiming a task before planning or implementing #docs
  - Acceptance: Done when the AGENTS.md Task Management text tells agents to claim a task before planning or implementing it, and the T009 snippet draft matches that rule if it is still the canonical copy-paste text.
  - Context: .scratch/agents-md-snippet/spec.md, .scratch/agents-md-snippet/plan.md, and docs/adr/0005-emit-task-management-snippet-do-not-write-instruction-files.md. This repo AGENTS.md gains claim-first while keeping local skill-path and .scratch bullets.
  - Related: T009
  - Outcome: completed
  - Closed: 2026-08-17

- [x] **T009** Ship an AGENTS.md/CLAUDE.md snippet for the task system #docs
  - Acceptance: Done when the package provides a copy-paste Task Management section for AGENTS.md or CLAUDE.md that requires invoking the todo skill before any task lookup or mutation, forbids hand-editing TODO.md, requires bot-todo --json including validate before and after writes, and tells agents to link filesystem specs/ADRs/plans from the corresponding task.
  - Context: .scratch/agents-md-snippet/spec.md, .scratch/agents-md-snippet/plan.md, and docs/adr/0005-emit-task-management-snippet-do-not-write-instruction-files.md
  - Related: T006
  - Outcome: completed
  - Closed: 2026-08-17

- [x] **T006** Verify AGENTS.md documents current behavior (ledger, etc.) #docs
  - Acceptance: Done when AGENTS.md is checked against the implementation and every stale or missing detail — including the ledger — is corrected.
  - Outcome: completed
  - Closed: 2026-08-17

- [x] **T014** Group human --all list by Repository Name and show Tags #feature
  - Acceptance: Human --all list groups open tasks under Repository Name headers without repeating the name on each line; every human list line shows ordinary Tags as #tag; JSON, critical, and actionable keep priority-first Aggregate Query order.
  - Context: .scratch/grouped-human-list/plan.md and docs/adr/0004-group-human-all-list-by-repository-name.md
  - Outcome: completed
  - Closed: 2026-08-14

- [x] **T008** Default init --name to the cwd basename #feature
  - Acceptance: Done when bot-todo init accepts a missing --name and writes the basename of the repository path (--root if given, otherwise cwd) into the TODO.md heading; --name remains an optional override; help, README, and the todo skill document --name as optional.
  - Context: .scratch/init-default-name/plan.md
  - Outcome: completed
  - Closed: 2026-08-14

- [x] **T007** Manage the global Repository Collection config from the CLI #feature
  - Acceptance: Done when bot-todo can show the active config path, list configured repositories, and add/remove entries without hand-editing the TOML, each subcommand emitting --json output and validating the file before and after the write.
  - Context: config.py only loads and validates the collection today; every change means editing the TOML by hand. Spec: .scratch/repos-cli/spec.md. Plan: .scratch/repos-cli/plan.md
  - Outcome: completed
  - Closed: 2026-08-14

- [x] **T005** Bundle and install the todo skill (Phase 4) #feature
  - Acceptance: install-skill installs the packaged todo skill for codex/claude/cursor/grok with manifests, conflict detection, dry-run, and forced replacement; skill assets ship in wheel and sdist; root skills/ tree removed
  - Context: .scratch/installable-bot-todo/phase-4-plan.md
  - Outcome: completed
  - Closed: 2026-08-12

- [x] **T004** Add aggregate read queries to the bot-todo CLI #feature
  - Acceptance: --all answers list, critical, and actionable across the configured Repository Collection in priority, configuration, and file order with repository provenance, rejects every other command, and fails entirely with exit 3 when any repository fails
  - Context: .scratch/installable-bot-todo/phase-3-plan.md
  - Related: T003
  - Outcome: completed
  - Closed: 2026-08-12

- [x] **T003** Complete the public single-repository bot-todo CLI #feature
  - Acceptance: Every public command and selector accepts and rejects the documented shapes, single-repository human and JSON workflows pass end to end, configuration precedence and validation match the settled contract, and unsupported task-data and configuration schema versions fail before repository access or writes.
  - Context: .scratch/installable-bot-todo/spec.md phase 2; .scratch/installable-bot-todo/phase-2-plan.md
  - Outcome: completed
  - Closed: 2026-08-12

- [x] **T002** Extract the single-repository core into an installable bot-todo package #feature
  - Acceptance: The wheel installs and runs outside the checkout, format-1 data works without migration, and locking, durability, archive decoupling, discovery, and unsafe-file rejection have runnable coverage.
  - Context: .scratch/installable-bot-todo/spec.md phase 1; docs/adr/0001, docs/adr/0002
  - Outcome: completed
  - Closed: 2026-08-11

- [x] **T001** Plan the installable bot-todo architecture #docs
  - Acceptance: Wayfinder decisions produce a build-ready architecture specification and phased implementation plan.
  - Context: .scratch/installable-bot-todo/map.md
  - Outcome: completed
  - Closed: 2026-08-11
