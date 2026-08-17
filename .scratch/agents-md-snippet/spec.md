# AGENTS.md / CLAUDE.md Task Management Snippet

Ship a copy-paste Task Management section that consuming repositories can
add to `AGENTS.md` or `CLAUDE.md`. Distinct from T006, which was about this
repository's own `AGENTS.md`. T012's claim-first rule is included in the
packaged text; this repository's `AGENTS.md` keeps its local skill-path,
`--root .`, and `.scratch/<feature>/` bullets.

## Settled contract

- **Never write instruction files.** `bot-todo` does not create, append, or
  otherwise mutate `AGENTS.md` or `CLAUDE.md`.
- **`--json` is the only caller split.** There is no separate human-vs-agent
  detector. Human stdout is for a person at a terminal; JSON is for agents.
- **Successful human `init`** prints `initialized`, a blank line, then the
  Task Management Snippet.
- **Successful JSON `init`** keeps `data.repository` and adds additive
  `data.snippet` (the same markdown). JSON Schema Version stays 1.
- **`bot-todo snippet`** is a selector-free packaged-text command, like
  `install-skill`. It rejects `--root`, `--repo`, `--all`, and `--config`.
  Human stdout is the markdown only. JSON `data` is `{"snippet": "<text>"}`.
- **Commands never prompt.** After JSON `init`, the todo skill tells the
  agent to show `data.snippet` and ask whether to add it to `AGENTS.md` or
  `CLAUDE.md`. Later retrieval is `bot-todo --json snippet`.
- **Packaged text does not mention `.scratch`.** That layout is this
  repository's convention, not a consuming-repo requirement.

ADR: [docs/adr/0005-emit-task-management-snippet-do-not-write-instruction-files.md](../../docs/adr/0005-emit-task-management-snippet-do-not-write-instruction-files.md)

## Canonical snippet

Source: `src/bot_todo/skill_assets/task_management.md` (sibling of `todo/`,
not copied by `install-skill`).

```markdown
## Task Management

- Use `TODO.md` as the repository backlog.
- ANY request to add, change, claim, close, or look up a task — however it is phrased ("add an ops task", "put this on the list", "what's next") — MUST start by invoking the `todo` skill. Do not inspect `TODO.md` or search the filesystem first.
- Use the `bot-todo` CLI with `--json` for all agent mutations; never hand-edit `TODO.md`.
- Run `bot-todo --json validate` before and after task-file changes.
- Claim a task before planning or implementing it.
- When specs, ADRs, or plans are written to the filesystem, add a link to the files in the corresponding TODO task.
```
