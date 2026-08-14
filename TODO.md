# TODO — Bot Todo
<!-- todo-format: 1; next-id: 8 -->

## P0 — Critical / Blocking

- [ ] **T006** Verify AGENTS.md documents current behavior (ledger, etc.) #docs
  - Acceptance: Done when AGENTS.md is checked against the implementation and every stale or missing detail — including the ledger — is corrected.

## P1 — High Priority

## P2 — Backlog

## Done (recent)

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
