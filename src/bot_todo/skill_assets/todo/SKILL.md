---
name: todo
description: Use when a repository tracks work in canonical TODO.md files and an agent needs to inspect, select, add, edit, claim, complete, cancel, review, reopen, archive, migrate, or validate tasks.
---

# Todo

Use the `bot-todo` CLI for every agent mutation. Treat `TODO.md` as the
human-readable source of truth; never rewrite it by hand except while resolving
a sequential-ID merge collision.

## Agent invocation rules

Pass `--json` on every command that returns data: `list`, `critical`,
`actionable`, `show`, `validate`, `init`, `repos`, `snippet`, and every
mutation. Parse the JSON document, then summarize it for a person in ordinary
language. The only commands that stay human-only are `--help` and `--version`.

Do not omit `--json` because a person will read your reply. Human CLI output
is for humans typing in a terminal, not for agents.

Use `--all` only when the person explicitly asks for tasks across all
projects or repositories. Default to the current repository (`--root` or cwd
discovery). Do not pass `--all` to be thorough, to search, or because the
current list looks empty. Mutations never accept `--all`.

## Vocabulary

- **Task ID**: Repository-unique `T` plus at least three digits. Never reuse it.
- **High-water mark**: `next-id` in the `TODO.md` metadata comment. Never lower it.
- **Claim**: Advisory actor, date, and branch metadata on an open task.
- **Review**: Task State for finished work awaiting validation. It is not a Claim.
- **Closed task**: Checked task with a completed or cancelled outcome.
- **Archive**: Append-only `TODO.archive.md` history of older closed tasks. It
  is written by the CLI, never read to decide whether a mutation is legal, and
  never edited by hand.

## Workflow

Replace `<repo>` with the repository root, or omit `--root` to use the nearest
Task Repository at or above the working directory:

```bash
bot-todo --json --root <repo> init
bot-todo --json --root <repo> init --name "Project name"
bot-todo --json snippet
bot-todo --json --root <repo> validate
bot-todo --json --root <repo> list
bot-todo --json --root <repo> critical
bot-todo --json --root <repo> actionable
bot-todo --json --root <repo> show T001
bot-todo --json --root <repo> migrate
```

After a successful `init`, parse `data.snippet`. Show that Task Management
section and ask whether to add it to `AGENTS.md` or `CLAUDE.md`. Do not write
those files unless asked. `snippet` accepts no repository selector or
configuration; use it later to retrieve the same text.

Before changing tasks, run `validate`. Stop and repair reported errors rather
than editing around them. Use `--help` on the CLI or a subcommand for its exact
arguments.

Mutations follow the same shape; `edit`, `release`, `review`, `reopen`,
`migrate`, and `archive` complete the set:

```bash
bot-todo --json --root <repo> add "Title" --type bug --priority P1 --acceptance "Done when..."
bot-todo --json --root <repo> claim T001 --actor codex
bot-todo --json --root <repo> review T001
bot-todo --json --root <repo> reopen T001
bot-todo --json --root <repo> complete T001
bot-todo --json --root <repo> cancel T001 --reason "Superseded"
```

Manage the Repository Collection with `repos`. `--config` is valid with these
commands; `--root`, `--repo`, and `--all` are not. `repos add` defaults to the
current directory. Pass `--name` when the directory basename is not a valid
Repository Name.

```bash
bot-todo --json repos path
bot-todo --json repos list
bot-todo --json repos add
bot-todo --json repos add --name ledger
bot-todo --json repos remove bot-todo
```

Require exactly one type: `bug`, `chore`, `docs`, `feature`, or `ops`. Require
acceptance criteria unless `--simple` deliberately marks a trivial task. Keep
active tasks in P0/P1/P2; claims do not move tasks between sections. `list`
includes Review tasks. `critical` selects the highest-priority open task even
when it is blocked or claimed; `actionable` selects the first unclaimed open
task whose blockers completed, in priority and file order. Review does not
satisfy blockers. Format 1 repositories must `migrate` before any mutation.
When work is finished but still needs validation, `review` it; `reopen` returns
it to open. `complete` and `cancel` are legal from open or Review.

`--json` emits one machine-readable document on stdout; an expected failure
writes one error document to stderr instead.

Only when the person explicitly asks for every project:

```bash
bot-todo --json --all list
```

`list`, `critical`, and `actionable` accept `--all`. Aggregate results name
the repository each task came from, order priority first and configuration
order second, and refuse to answer at all — exiting 3 — when any configured
repository cannot be read. No mutation accepts `--all`.

Completion and cancellation retain the ID and move the task to Done. The CLI
keeps the newest 20 closed tasks there and retires older entries to the archive,
except a closed task still named by an open task's blockers, which stays in Done
until nothing depends on it. Cancellation does not satisfy dependents
automatically.

After a mutation, run `validate` again. The CLI validates before and after each
write, serializes concurrent access per repository, and replaces `TODO.md`
atomically.

## Common mistakes

| Excuse | Reality |
|--------|---------|
| "I am reporting to a person, so skip `--json`." | Parse JSON, then summarize. Human CLI output is not for agents. |
| "Use `--all` to be thorough / find work." | `--all` only when the person explicitly asks for all projects. |
| "The current repo looks empty, so try `--all`." | Stay on the current repository unless asked for every project. |

## Merge Collisions

Sequential IDs are stable after default-branch merge. If two branches allocate
the same ID, manually renumber the unmerged task and its references, set
`next-id` above every observed ID, then run `validate`. This is the only agent
manual-edit exception.
