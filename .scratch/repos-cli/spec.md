# Repository Collection CLI

Settled contract for T007. Implementation plan: [plan.md](./plan.md).

This amends the flat command list in
[issue 04](../installable-bot-todo/issues/04-define-public-cli-contract.md).
JSON Schema Version stays 1. Configuration Schema Version stays 1.

Do not call this “global”. The object is the **Repository Collection** of
**Repository Entries**.

## Command surface

```text
bot-todo [--json] [--config PATH] repos path
bot-todo [--json] [--config PATH] repos list
bot-todo [--json] [--config PATH] repos add [PATH] [--name NAME]
bot-todo [--json] [--config PATH] repos remove TARGET
```

Typical new Task Repository flow (PATH defaults to `.`):

```bash
cd ~/Programming/new-repo
bot-todo repos add
bot-todo repos add --name ledger
```

## Selectors

`--config` is valid with `repos`. `--root`, `--repo`, and `--all` are usage
errors. Precedence is unchanged: `--config` > `BOT_TODO_CONFIG` > platform
default.

## Missing file

Honor the load contract:

- Missing **default**: empty collection. `list` succeeds with no entries.
  `add` creates the default file and parent directories. `remove` fails with
  `repository_not_found`.
- Missing **explicit** `--config` or `BOT_TODO_CONFIG`: `config_not_found` for
  list, add, and remove.
- `repos path` always prints the resolved path, even if the file does not exist.
- An existing invalid or unsupported file is never rewritten.

## Add

- PATH is optional and defaults to `.`.
- Exact path, resolved from the current directory. No walk-up. `TODO.md` is
  not required. The directory need not exist (prospective Repository Entry).
- A positional PATH must be `.`, start with `~`, be absolute, or contain `/`
  or `\`. A bare slug is `usage`.
- Name: lowercase the resolved directory’s basename; use it if it matches
  `NAME_RE`; otherwise require `--name`. `--name` always wins.
- Store `~/...` when the resolved path is under home; otherwise store an
  absolute path. Never store `.`.
- Append, preserving configuration order.
- Duplicate name or resolved path fails with `duplicate_repository`.
- Not idempotent. Does not run `init`.

## Remove

- If TARGET equals a Repository Name, remove that entry (name wins).
- Otherwise resolve TARGET as a path (`.` allowed) and remove the matching
  entry.
- Unknown target: `repository_not_found`.

## Writes

Validate (load or empty default) → mutate in memory → validate with the
existing parser → exclusive lock → canonical TOML replace → reload and
validate.

Canonical file only: `schema_version = 1` plus ordered `[[repositories]]`
tables. Comments are not preserved. Emit this closed schema by hand; stdlib
`tomllib` remains the reader.

Atomic replace, same durability pattern as task-file writes. Exclusive
`portalocker` lock beside the config file.

## JSON

`command` is the single token `repos`. `data.operation` is `path`, `list`,
`add`, or `remove`. Every success includes `data.config_path` (resolved
absolute). List includes `data.repositories` in configuration order. Add and
remove include `data.entry`. Entry `path` in JSON is the resolved absolute
path. Human wording is not contractual.

## Out of scope

Rename, reorder, init-on-add, comment-preserving round-trip.
