# TODO — Bot Todo
<!-- todo-format: 1; next-id: 4 -->

## P0 — Critical / Blocking

## P1 — High Priority

## P2 — Backlog

## Done (recent)

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
