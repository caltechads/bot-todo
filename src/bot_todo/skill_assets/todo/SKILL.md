---
name: todo
description: Use when a repository tracks work in canonical TODO.md files and an agent needs to inspect, select, add, edit, claim, complete, cancel, archive, or validate tasks.
---

# Todo

Use the `bot-todo` CLI for every agent mutation. Treat `TODO.md` as the
human-readable source of truth; never rewrite it by hand except while resolving
a sequential-ID merge collision.

## Vocabulary

- **Task ID**: Repository-unique `T` plus at least three digits. Never reuse it.
- **High-water mark**: `next-id` in the `TODO.md` metadata comment. Never lower it.
- **Claim**: Advisory actor, date, and branch metadata on an open task.
- **Closed task**: Checked task with a completed or cancelled outcome.
- **Archive**: Append-only `TODO.archive.md` history of older closed tasks. It
  is written by the CLI, never read to decide whether a mutation is legal, and
  never edited by hand.

## Workflow

Replace `<repo>` with the repository root, or omit `--root` to use the nearest
Task Repository at or above the working directory:

```bash
bot-todo --root <repo> init --name "Project name"
bot-todo --root <repo> validate
bot-todo --root <repo> list
bot-todo --root <repo> critical
bot-todo --root <repo> actionable
bot-todo --root <repo> show T001
```

Before changing tasks, run `validate`. Stop and repair reported errors rather
than editing around them. Use `--help` on the CLI or a subcommand for its exact
arguments.

Mutations follow the same shape; `edit`, `release`, and `archive` complete the
set:

```bash
bot-todo --root <repo> add "Title" --type bug --priority P1 --acceptance "Done when..."
bot-todo --root <repo> claim T001 --actor codex
bot-todo --root <repo> complete T001
bot-todo --root <repo> cancel T001 --reason "Superseded"
```

Require exactly one type: `bug`, `chore`, `docs`, `feature`, or `ops`. Require
acceptance criteria unless `--simple` deliberately marks a trivial task. Keep
active tasks in P0/P1/P2; claims do not move tasks between sections. `critical`
selects the highest-priority open task even when it is blocked or claimed;
`actionable` selects the first unclaimed task whose blockers completed, in
priority and file order.

Read results as human text when reporting to a person. Add `--json` whenever the
workflow parses a result or branches on it: it emits one machine-readable
document on stdout, and an expected failure writes one error document to stderr
instead.

Replace the selector with `--all` to run `list`, `critical`, or `actionable`
across every configured repository at once. Aggregate results name the
repository each task came from, order priority first and configuration order
second, and refuse to answer at all — exiting 3 — when any configured repository
cannot be read. No mutation accepts `--all`.

Completion and cancellation retain the ID and move the task to Done. The CLI
keeps the newest 20 closed tasks there and retires older entries to the archive,
except a closed task still named by an open task's blockers, which stays in Done
until nothing depends on it. Cancellation does not satisfy dependents
automatically.

After a mutation, run `validate` again. The CLI validates before and after each
write, serializes concurrent access per repository, and replaces `TODO.md`
atomically.

## Merge Collisions

Sequential IDs are stable after default-branch merge. If two branches allocate
the same ID, manually renumber the unmerged task and its references, set
`next-id` above every observed ID, then run `validate`. This is the only agent
manual-edit exception.
