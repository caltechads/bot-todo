# T023 — Retain closed blockers named by closed tasks in Done

Task: T023 (bug, P1). Decision: [ADR 0002](../../docs/adr/0002-decouple-the-archive-from-the-transaction.md)
(amended 2026-10-27).

## Problem

`_archive_overflow` (`src/bot_todo/repository.py`) retains an over-limit Done
task only when an *active* task (`priority is not None`) names it in
`Blocked by`. `_validate_document` requires every task's blockers — closed
tasks included — to resolve within `TODO.md`. So when Done holds closed T001
`Blocked by: T004` and T004 is the oldest entry, the next close retires T004
and `commit()` fails with `T001 references unknown blocker T004`.

`commit()` validates before appending to the archive or replacing `TODO.md`,
so the failed mutation writes nothing; affected repositories (ledger) need no
repair, only the upgraded `bot-todo`.

## Decision (settled)

Option A — retain transitively. A Done task past the limit stays in Done while
any task that remains in `TODO.md` (open, review, or closed) names it as a
blocker. Retention is a fixed point: a retained task's own blockers are
retained too. A chain retires together, in one pass, once its newest dependent
passes the limit.

Rejected:

- B — archive the dependent with its blocker: drops Done below twenty for no
  visible reason.
- C — validate blockers only on active tasks: smallest diff, but weakens
  validation of hand-edited closed tasks and breaks ADR 0002's
  "every blocker resolves from `TODO.md` alone" invariant.

## Change

One function: `_archive_overflow` in `src/bot_todo/repository.py`.

```python
kept = document.done[:DONE_LIMIT]
overflow = document.done[DONE_LIMIT:]
staying = [*(task for task in document.tasks if task.priority is not None), *kept]
retained: set[str] = set()
while True:
    referenced = {blocker for task in staying for blocker in _blockers(task)}
    newly = [
        task for task in overflow
        if task.task_id in referenced and task.task_id not in retained
    ]
    if not newly:
        break
    retained.update(task.task_id for task in newly)
    staying.extend(newly)
document.done = kept + [task for task in overflow if task.task_id in retained]
return [task for task in overflow if task.task_id not in retained]
```

- Retained tasks keep their Done order after the newest twenty (unchanged
  layout).
- Retired tasks keep Done order, so a chain lands in the archive contiguously.
- Update the docstring: retention applies to blockers named by any task that
  stays in the active file, transitively.
- No validator, CLI, web, or format change. `todo-format` stays 1.

## Tests (`tests/test_repository.py`, `ArchiveTests`)

1. `test_a_blocker_named_by_a_closed_task_is_retained_in_done` — the ledger
   scenario. Add blocker B and dependent D (`--blocked-by B`); complete B,
   then D, then fill Done to exactly twenty with simple tasks (B oldest).
   Complete one more: the command succeeds, `**B**` is still in `TODO.md`,
   `validate` is `valid`. Fails on current code.
2. `test_a_closed_blocker_chain_retires_together` — X ← Y ← Z (Y blocked by X,
   Z blocked by Y); complete X, Y, Z, then 19 fillers (X and Y past the limit;
   Y kept only via Z, X only via retained Y). Assert X and Y in `TODO.md` and
   `validate` is `valid`. Complete two more fillers so Z passes the limit:
   none of X, Y, Z in `TODO.md`, all three in `TODO.archive.md`, `validate`
   is `valid`.

Existing `test_a_referenced_blocker_is_retained_in_done` and
`test_a_cancelled_blocker_keeps_blocking_after_overflow` must keep passing.

## Docs

- ADR 0002: amended in this planning step (retention bullet + consequence).
- `src/bot_todo/skill_assets/todo/SKILL.md`: the sentence "except a closed task
  still named by an open task's blockers" becomes "except a closed task still
  named as a blocker by any task that stays in `TODO.md`". That is the only
  other copy of the wording (grep, 2026-10-27). Skill-guidance tests that pin
  SKILL.md text may need the same update; reinstall installed skills afterwards
  with `bot-todo install-skill`.
- `CONTEXT.md`: no new term.

## Quality gate

`ruff` and `mypy` on `src/bot_todo/repository.py` and
`tests/test_repository.py`; `make napoleon-gate`; `make pytest`.
