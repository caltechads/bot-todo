# bot-todo

`bot-todo` is a command-line tool for a canonical, Git-friendly task backlog.
Humans and coding agents share one `TODO.md` per repository and mutate it only
through this CLI.

The package also ships a thin `todo` skill that teaches Codex, Claude, Cursor,
and Grok to call `bot-todo` instead of editing the task files by hand.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/) for installation (recommended)

The only runtime dependency is `portalocker`, used for per-repository locking.

## Installation

```bash
uv tool install bot-todo
```

Confirm the install:

```bash
bot-todo --version
```

## Quick start

From a project directory:

```bash
bot-todo init
bot-todo add "Write the README" --type docs --priority P1 --acceptance "README covers install and usage"
bot-todo list
bot-todo claim T001 --actor glenn
bot-todo complete T001
bot-todo validate
```

`init` always targets the current directory (or `--root`). Omit `--name` to use
the repository directory basename as the project heading. Successful human
`init` prints a copy-paste Task Management section for `AGENTS.md` or
`CLAUDE.md`; JSON `init` includes that text as `data.snippet`. `bot-todo`
never writes those instruction files. Other commands without a selector walk
from the current directory toward the filesystem root and use the nearest
`TODO.md`.

## Usage

Global options precede the command:

```text
bot-todo [--json] [--config PATH] [--root PATH | --repo NAME | --all] COMMAND ...
```

`--help` and `--version` always print human text and succeed, including when
`--json` is present. Commands never prompt, page, or colorize output.

### Commands

| Command | Purpose |
| --- | --- |
| `init [--name NAME]` | Create `TODO.md` and `TODO.archive.md` |
| `validate` | Check the canonical files |
| `list` | List open and review tasks |
| `show TASK_ID` | Print one task |
| `critical` | Highest-priority open task (even if blocked or claimed) |
| `actionable` | First unclaimed open task whose blockers are completed |
| `add TITLE --type TYPE` | Create an open task |
| `edit TASK_ID ...` | Change an open or review task |
| `claim TASK_ID --actor NAME` | Take an advisory claim on an open task |
| `release TASK_ID` | Drop a claim |
| `review TASK_ID` | Move an open task into review |
| `reopen TASK_ID` | Return a review task to open |
| `complete TASK_ID` | Mark an open or review task completed |
| `cancel TASK_ID --reason TEXT` | Mark an open or review task cancelled |
| `archive` | Move older Done tasks into the archive |
| `migrate` | Upgrade the task data format to 2 |
| `web [--port PORT] [--no-open]` | Serve one repository as a local Kanban Board |
| `repos path` | Show the active configuration path |
| `repos list` | List configured repositories |
| `repos add [PATH]` | Add a repository entry; PATH defaults to `.` |
| `repos remove TARGET` | Remove a repository entry by name or path |
| `install-skill --target TARGET` | Install the bundled `todo` skill |
| `snippet` | Print the Task Management section for `AGENTS.md` or `CLAUDE.md` |

Task IDs look like `T001` and are never reused. Types are `bug`, `chore`,
`docs`, `feature`, and `ops`. Priorities are `P0`, `P1`, and `P2` (default
`P2`).

`add` requires either `--acceptance` or `--simple`. Repeatable options are
`--tag` and `--blocked-by`. `claim` records the actor, today's date, and the
current Git branch unless `--branch` is given. `review` clears that claim and
records today's date; `reopen` returns the task to open. `complete` and
`cancel` accept open or review tasks.

`init` writes Task Data Format 2. Format 1 files still load for queries;
mutations require `bot-todo migrate` first.

```bash
bot-todo add "Fix the lock timeout" --type bug --priority P0 \
  --acceptance "Conflict errors after five seconds, no partial writes" \
  --tag locking --blocked-by T002

bot-todo edit T003 --title "Clarify lock timeout" --priority P1 --clear-blockers
bot-todo cancel T004 --reason "Superseded by T003"
```

`edit` is a usage error if it requests no change. It also accepts `--simple`,
`--clear-context`, `--clear-related`, and `--clear-blockers`.

### Local Kanban Board

Serve the selected Task Repository in a browser:

```bash
bot-todo web
bot-todo --root ~/Programming/bot_todo web --port 8765 --no-open
bot-todo --repo bot-todo web
```

The server binds only to `127.0.0.1`, prints its URL, and opens the default
browser unless `--no-open` is supplied. Port `8765` is the default; port `0`
asks the operating system to choose an available port. `web` manages one Task
Repository and rejects `--all` and `--json`.

The Kanban Board groups recent tasks into Open, Review, Completed, and
Cancelled columns. Card titles open that task's details in a modal. It can
add tasks, edit Open and Review tasks in the detail modal, move Open work to
Review, reopen Review work, and complete or cancel Open or Review work.
Claims, full-archive browsing, and multi-repository boards remain CLI-only.
A Task Data Format 1 repository is displayed read-only with instructions to
run `bot-todo migrate`.

This is a local human interface, not a remotely deployable service. It has no
authentication and deliberately provides no option to bind beyond loopback.

### Selecting a repository

| Selector | Meaning | Allowed commands |
| --- | --- | --- |
| *(none)* | Nearest ancestor `TODO.md`; `init` uses the current directory | Task commands |
| `--root PATH` | Exact directory | Task commands |
| `--repo NAME` | One named entry from configuration | Task commands |
| `--all` | Every configured repository | `list`, `critical`, `actionable` only |

`--root`, `--repo`, and `--all` are mutually exclusive. `install-skill` and
`snippet` accept none of them. `repos` accepts `--config` and rejects the other
selectors.

```bash
bot-todo --root ~/Programming/bot_todo list
bot-todo --repo bot-todo show T001
bot-todo --all critical
```

### Configuration

`--repo`, `--all`, and `repos` read a TOML file. `--config PATH` overrides
`BOT_TODO_CONFIG`, which overrides the platform default:

- Unix: `${XDG_CONFIG_HOME:-~/.config}/bot-todo/config.toml`
- Windows: `%APPDATA%\bot-todo\config.toml`

```toml
schema_version = 1

[[repositories]]
name = "bot-todo"
path = "~/Programming/bot_todo"

[[repositories]]
name = "ledger"
path = "~/Programming/ledger"
```

Names are unique lowercase slugs matching `[a-z0-9][a-z0-9._-]*`. Paths may be
absolute, start with `~`, or be relative to the configuration file. A missing
path is valid so `init --repo NAME` can create it.

`--all` orders JSON results, `critical`, and `actionable` by priority, then
configuration order, then file order. Human `--all list` groups tasks by
Repository Name in collection order, omits repositories with no open tasks,
and omits the name from task lines.

If any configured repository cannot be read, the command prints no task data
and exits `3`.

A missing default config is an empty collection. Local discovery and `--root`
never load configuration.

Manage the collection without editing the file by hand:

```bash
bot-todo repos path
bot-todo repos list
cd ~/Programming/new-repo
bot-todo repos add
bot-todo repos add --name ledger
bot-todo repos remove ledger
```

`repos add` stores `~/...` when the path is under home, otherwise an absolute
path. A missing default file is created on the first add. A missing `--config`
path is an error. Duplicate names and resolved paths are rejected.

## JSON output

`--json` is the stable automation interface. Agents should pass it on every
command that returns data. Humans typing in a terminal can omit it.

Success writes one JSON document to stdout:

```json
{
  "schema_version": 2,
  "command": "list",
  "data": {
    "tasks": []
  }
}
```

JSON task objects include `state` (`open`, `review`, `completed`, or
`cancelled`), `reviewed_on` (an ISO date while in Review, otherwise `null`),
and `closed_on`.

Expected failure writes nothing to stdout and one error document to stderr:

```json
{
  "schema_version": 2,
  "error": {
    "code": "unknown_task",
    "message": "unknown task ID T999"
  }
}
```

Exit statuses: `0` success (including empty queries), `1` operational or data
failure, `2` usage error, `3` aggregate partial failure.

## Agent skill

Install the bundled `todo` skill for one agent at a time:

```bash
bot-todo install-skill --target cursor
bot-todo install-skill --target claude
bot-todo install-skill --target grok
bot-todo install-skill --target codex
```

Default skill roots:

| Target | Skill root | Installed path |
| --- | --- | --- |
| `cursor` | `~/.cursor/skills` | `~/.cursor/skills/todo` |
| `claude` | `~/.claude/skills` | `~/.claude/skills/todo` |
| `grok` | `~/.grok/skills` | `~/.grok/skills/todo` |
| `codex` | `~/.agents/skills` | `~/.agents/skills/todo` |

`--destination PATH` replaces the skill root, not the final `todo` directory.
`--dry-run` classifies the action without writing. `--force` replaces a
conflicting tree after moving it to a `todo.backup-*` sibling.

Codex receives `SKILL.md` plus `agents/openai.yaml`. The other targets receive
`SKILL.md` only. A managed install is marked with `.bot-todo-install.json`.
Unknown or modified files are a conflict unless `--force` is given.

The installer only writes files. It does not reload the agent.

## Task files

Each Task Repository is a directory with `TODO.md` and `TODO.archive.md`. Treat
`TODO.md` as the human-readable source of truth, but do not rewrite it by hand
except to resolve a sequential-ID merge collision.

Open tasks live under `P0`, `P1`, and `P2`. Completed and cancelled tasks move
to Done; the newest 20 stay there, and older closed tasks are appended to the
archive. A closed task that still blocks an open task stays in Done until
nothing depends on it. Cancellation does not satisfy dependents.

Every mutation takes an exclusive lock (`.bot-todo.lock`), validates before and
after the write, and replaces the canonical files atomically. Reads take a
shared lock. Lock acquisition waits up to five seconds, then fails with
`conflict`.

## Development

```bash
uv sync
source .venv/bin/activate
make pytest
```

Quality gates used in this repository:

```bash
uv run ruff check src tests
uv run mypy src
make napoleon-gate
```

Pass extra pytest arguments with `make pytest ARGS="tests/test_cli.py -q"`.

## Further reading

- [`CONTEXT.md`](CONTEXT.md) — domain vocabulary
- [`.scratch/installable-bot-todo/spec.md`](.scratch/installable-bot-todo/spec.md) — architecture and public contract
- [`docs/adr/`](docs/adr/) — architecture decisions
