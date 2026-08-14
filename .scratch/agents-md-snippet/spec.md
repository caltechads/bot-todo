# AGENTS.md / CLAUDE.md task-system snippet

Ship a copy-paste Task Management section that consuming repositories can
add to `AGENTS.md` or `CLAUDE.md`. Distinct from T006, which is about this
repository's own `AGENTS.md`.

## Draft

```markdown
## Task Management

- Use `TODO.md` as the repository backlog.
- ANY request to add, change, claim, close, or look up a task — however it is phrased ("add an ops task", "put this on the list", "what's next") — MUST start by invoking the `todo` skill. Do not inspect `TODO.md` or search the filesystem first.
- Use the `bot-todo` CLI with `--json` for all agent mutations; never hand-edit `TODO.md`.
- Run `bot-todo --json validate` before and after task-file changes.
- Keep detailed task specs and implementation issues in `.scratch/<feature>/` and link them from the corresponding TODO task.
- When specs, ADRs, or plans are written to the filesystem, add a link to the files in the corresponding TODO task.
```

## Notes

- `init`, README, `install-skill`, or a dedicated command may be how the
  snippet is delivered; the contract is that the text is easy for a human or
  agent to copy into `AGENTS.md` or `CLAUDE.md`.
- Keep `--json` on `validate` so the snippet matches the todo skill.
