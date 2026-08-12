# 2. Decouple the archive from the repository transaction

Status: accepted (2026-08-11)

## Context

Task Data Format 1 stores tasks in a pair of files. `TODO.md` holds active
tasks plus the newest twenty closed ones; `TODO.archive.md` holds older closed
tasks. The two were mutually dependent: task identifiers had to be unique
across both, and the archive heading had to name the same project.

[Ticket 12](../../.scratch/installable-bot-todo/issues/12-define-concurrency-and-failure-policy.md)
therefore specified a Repository Transaction that stages the complete pair,
publishes a durable commit marker, and replays the staged pair on the next
command after a crash. That machinery exists only because two files must move
in step; a single file is already crash-safe under `os.replace`.

It was the largest and riskiest part of Phase 1 — staging, marker encoding,
recovery, fail-closed handling of malformed transaction state — and every bit
of it protected an invariant that serves no user-visible purpose. Nothing reads
the archive to decide whether a mutation is legal.

The constraint freezing Task Data Format 1 was then lifted.

## Decision

Make `TODO.md` the only transactional file, and make `TODO.archive.md`
append-only history.

- A mutation is one atomic `os.replace` of `TODO.md`, preceded by a durable
  append of any retired tasks to the archive. No staged pair, no commit marker,
  no recovery pass.
- Task identifiers are unique within `TODO.md`. Cross-file uniqueness is no
  longer validated, and the archive heading no longer has to match the project.
- The archive is never rewritten, never validated, and read only so `show` can
  display an archived task.
- A closed task still named by an open task's `Blocked by` is retained in Done
  past the twenty-entry limit. This keeps every blocker reference resolvable
  from `TODO.md` alone, so blocker validation is unchanged and a cancelled
  blocker still blocks.

The format marker stays `todo-format: 1`. `TODO.md`'s bytes are unchanged, so
existing repositories keep working with no migration and files written by this
release remain readable by the previous embedded script.

## Consequences

- Phase 1 loses its staged pair, commit marker, and recovery layer, along with
  the tests that would have covered them. Ticket 12's transaction-durability
  section is superseded; its locking, filesystem-boundary, and aggregate-failure
  sections still stand.
- One new failure mode, deliberately accepted: a crash between the archive
  append and the `TODO.md` replace leaves a task in both Done and the archive,
  and the next overflow appends it to the archive a second time. `TODO.md`
  remains authoritative throughout, so this is cosmetic duplication in a history
  file. It is marked with a `ponytail:` comment at the commit site.
- Three behaviors are removed. Duplicate identifiers across `TODO.md` and the
  archive no longer fail validation; the archive heading no longer has to match
  the project; and Done may exceed twenty entries when a closed task is still
  referenced as a blocker.
- `init` now creates only `TODO.md`. The archive appears on first overflow.
