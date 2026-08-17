## Task Management

- Use `TODO.md` as the repository backlog.
- ANY request to add, change, claim, close, or look up a task — however it is phrased ("add an ops task", "put this on the list", "what's next") — MUST start by invoking the `todo` skill. Do not inspect `TODO.md` or search the filesystem first.
- Use the `bot-todo` CLI with `--json` for all agent mutations; never hand-edit `TODO.md`.
- Run `bot-todo --json validate` before and after task-file changes.
- Claim a task before planning or implementing it.
- When specs, ADRs, or plans are written to the filesystem, add a link to the files in the corresponding TODO task.
