# 6. Review is an in-section lifecycle state

Status: accepted (2026-08-17)

## Context

T011 needs a Task State between open and completed so finished work can wait
for validation. Today open means unchecked in P0/P1/P2, and completed or
cancelled means checked in Done with Outcome. Claim is metadata on an open
task, not a state. A new lifecycle state plus a closed JSON `state`
enumeration cannot stay on Task Data Format 1 or JSON Schema Version 1
([compatibility policy](../../.scratch/installable-bot-todo/issues/11-define-compatibility-and-migration-policy.md)).

## Decision

Review is a fourth Task State. The task stays unchecked in its P0/P1/P2
section with `Review: YYYY-MM-DD`. JSON `state` is `review` and
`reviewed_on` carries that date. `list` includes Review tasks; `critical` and
`actionable` do not. Review does not satisfy blockers. Claim is cleared on
entry and cannot be taken again until `reopen` returns the task to open.
`complete` from open remains legal. `reopen` is legal only from Review.
Cancel is legal from Review.

Task Data Format 2 and JSON Schema Version 2 carry this contract. The CLI
reads formats 1 and 2. `init` and every mutation require format 2. Opt-in
`migrate` rewrites the format marker; a format-2 repository is a successful
no-op. Mutating format 1 fails with `migration_required`. Unknown versions
still use `unsupported_format_version`. Format 1 documents must not carry a
`Review` field. Writes must not auto-upgrade format 1.

## Considered Options

- Overlay on open (a Claim-like field with `state` still `open`) — acceptance
  asks for a state and a return to open, and T010's Kanban columns reflect
  Task State.
- A `## Review` section — looks like a Kanban column, but `list` is
  priority-ordered from P0/P1/P2, and reopen would have to persist priority
  as a separate field.
- `Outcome: review` in Done — unfinished work would look closed and could be
  archived (ADR 0002).

## Consequences

- JSON Schema Version 2 applies to every `--json` envelope, including
  `snippet` and `init`. ADR 0005's additive `data.snippet` still stands; its
  "schema stays 1" note does not.
- Human `--all list` (ADR 0004) groups unfinished work, including Review,
  under Repository Name headers. JSON aggregate order is unchanged.
- T010 can grow a Review column from `state` without a new Markdown section.
