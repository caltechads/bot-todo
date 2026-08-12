# Phase 2 — Complete the public single-repository CLI

## Context

Phase 1 (T002, closed 2026-08-11) extracted the embedded script into an
installable `bot-todo` package: `repository.py` owns Task Data Format 1 with
locking, snapshots, transactions and unsafe-file rejection, and `cli.py` carries
a deliberately *provisional* human CLI that kept the old command spellings so the
tests would not be rewritten twice.

That provisional surface is the problem Phase 2 solves. Today there is no
`--json`, no configuration, no `--repo`, the query commands are still the old
`next` rather than the settled `critical`/`actionable`, `init` still spells its
option `--project`, and `TodoError.code` — which is already populated correctly
at all 10 raise sites — is read in exactly one place, only to tell `usage` from
everything else.

Phase 2 turns that into the released public contract: the full flat command
grammar, Configuration Schema Version 1, `--repo`, JSON Schema Version 1 for both
success and error documents, the complete error-code mapping, and settled exit
statuses 0/1/2. `--all`, exit 3 and aggregate queries stay in Phase 3; the skill
installer stays in Phase 4.

Sources: `.scratch/installable-bot-todo/spec.md` §"CLI contract", §"Configuration
Schema Version 1", §"JSON and process contract", §"Phase 2"; tickets `04`
(grammar, JSON, exits), `06` (argparse), `07` (configuration), `08` (query
semantics), `11`, `12` (error mapping), `16` (config version policy).

## Decisions this plan makes

### Confirmed with the user

1. **The JSON projection lives on `Task` plus assembly in `cli.py`.** `Task`
   gains typed read-only properties; `cli.py` assembles the documents. No new
   serialization module — the spec's "do not split rendering into more modules
   until pressure requires it" still holds.
2. **`init --repo NAME` creates a missing configured path**, per ticket 07.
   Directory creation is scoped to `--repo`; `--root` at a missing path keeps
   reporting `repository_not_found`.
3. **Renamed commands get their call sites fixed now.** `skills/todo/SKILL.md`
   and `AGENTS.md:96` are mechanically updated to the new spellings so this
   repository's own tooling keeps working. Phase 4 still owns the real skill
   reduction. No `next` alias is retained.

### Filling gaps the tickets leave open

The tickets never specify four JSON shapes. This plan settles them, and since
JSON Schema 1 is frozen at release they are worth a look during review:

| Command | `data` |
| --- | --- |
| `add` `edit` `claim` `release` `complete` `cancel` | `{"task": {…}}` — same key as `show`, rather than a per-command key |
| `init` | `{"repository": {"name": …, "path": …}}` |
| `validate` | `{"repository": {"name": …, "path": …}}` — success *is* the validity signal, so no redundant `"valid": true` |
| `archive` | `{"archived": 3}` |

Two smaller readings, both consistent with the tickets but not stated outright:

- **A file named by `BOT_TODO_CONFIG` is treated as explicit**, so a missing one
  is `config_not_found`, exactly like a missing `--config`. Only the *platform
  default* may be absent, and that means an empty Repository Collection.
- **`TodoError` gains an optional `details: dict[str, object]`**, merged into the
  `error` object. This is how `unsupported_config_version` and
  `unsupported_format_version` carry their encountered/supported versions, and
  it is the hook Phase 3 uses for `aggregate_partial_failure`.

## Target layout

```text
src/bot_todo/
├── __init__.py
├── cli.py           # grammar, selection, dispatch, both renderers, exit mapping
├── config.py        # new — Configuration Schema 1
└── repository.py    # + Task accessors, Claim, snapshot queries, error details

tests/
├── support.py       # updated harness (init --name, JSON helpers)
├── test_cli.py      # + grammar, JSON, exit-code coverage
├── test_config.py   # new
├── test_repository.py
└── test_distribution.py
```

## Implementation

### 1. `config.py` — Configuration Schema Version 1

Cohesive classes per AGENTS.md, not a pile of loaders:

```python
#: Configuration schema versions this release understands.
SUPPORTED_CONFIG_VERSIONS = (1,)
#: Environment variable naming an explicit configuration file.
CONFIG_ENV_VAR = "BOT_TODO_CONFIG"
#: Valid Repository Name grammar.
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True)
class RepositoryEntry:
    name: str
    path: Path          # resolved, may not exist


class RepositoryCollection:
    @classmethod
    def load(cls, explicit: Path | None) -> RepositoryCollection: ...
    @classmethod
    def default_path(cls) -> Path: ...
    def entry(self, name: str) -> RepositoryEntry: ...   # raises repository_not_found
    def __iter__(self) -> Iterator[RepositoryEntry]: ...  # configuration order
```

`default_path()` returns `${XDG_CONFIG_HOME:-~/.config}/bot-todo/config.toml`,
or `%APPDATA%\bot-todo\config.toml` when `os.name == "nt"`.

`load()` resolution order — `explicit` (already merged from `--config` then
`BOT_TODO_CONFIG` by the caller) then the platform default:

1. Explicit path missing → `config_not_found`. Default path missing → an **empty
   collection**, not an error.
2. `tomllib.load` failure → `invalid_config`. An existing but empty file has no
   `schema_version`, so it lands in step 3 as `invalid_config`.
3. `schema_version` absent or not an `int` → `invalid_config`. Present but not in
   `SUPPORTED_CONFIG_VERSIONS` → `unsupported_config_version` with
   `details={"encountered": n, "supported": [1]}`. **This check runs before any
   structural validation, repository access, or filesystem mutation** (ticket 16).
4. Structure: top-level keys ⊆ `{schema_version, repositories}`; `repositories`
   a list of tables each with exactly `name` and `path`; `name` matches
   `NAME_RE`; names unique. Any violation invalidates the **whole** file →
   `invalid_config`.
5. Paths: `expanduser()`, then resolve relative paths **against the config
   file's directory**, then `Path.resolve()` (non-strict — the path need not
   exist). No environment-variable expansion. Duplicate resolved paths →
   `invalid_config`.

Configuration is loaded **only** for `--repo`. `--root` and local discovery never
touch it and report a `null` Repository Name.

### 2. `repository.py` — accessors, not a second model

`TodoError.__init__` gains `details: dict[str, object] | None = None`, stored as
`self.details`. The existing `unsupported_format_version` raise site populates it.

A `Claim` frozen dataclass (`actor`, `claimed_on`, `branch`) plus read-only
properties on `Task` that project the raw `fields` dict into contract terms:

| Property | Derived from |
| --- | --- |
| `state` | `"open"` when not `checked`, else `fields["Outcome"]` → `completed`/`cancelled` |
| `task_type` | the single tag in `TYPE_TAGS` |
| `user_tags` | `tags` minus the type tag |
| `simple` | `"Acceptance" not in fields` |
| `acceptance` `context` `related` `closed_on` `reason` | the matching field, else `None` |
| `blocked_by` | `fields["Blocked by"]` split into a list, else `[]` |
| `claim` | `fields["Claimed"]` split on `|` into `Claim`, else `None` |

`actionable` is *not* a `Task` property — it needs the whole document to resolve
blockers. Extract the predicate already buried in `_find_next` into
`_is_actionable(document, task) -> bool`, have `_find_next` call it, and expose:

```python
class RepositorySnapshot:
    def critical(self) -> Task | None:        # first open task, P0→P1→P2, file order
    def actionable(self) -> Task | None:      # rename of next_actionable()
    def is_actionable(self, task: Task) -> bool
```

`critical` deliberately ignores claims and blockers (CONTEXT.md: "whether or not
it can currently be acted upon").

`RepositoryTransaction.edit` gains explicit `clear_acceptance`,
`clear_context`, `clear_related` booleans. `blocked_by=[]` already means clear, so
no sentinel type is introduced and mypy stays clean under `strict`.

### 3. `cli.py` — grammar, selection, two renderers

**Grammar changes.** `next` → `critical` and `actionable`; `init --project` →
`init --name`; `edit` gains `--simple`, `--clear-context`, `--clear-related`
(each mutually exclusive with its value-setting option); an `edit` that requests
no change at all raises `usage`. Globals gain `--json` and `--config PATH`, and
`--root`/`--repo` become a mutually exclusive group.

`--config` is accepted only with `--repo`; anywhere else it is a usage error.

**Usage errors under `--json`.** Ticket 06 requires this and Phase 1 skipped it:
override `_Parser.error()` to raise `TodoError(code="usage")` instead of
printing and exiting, and — because parse failures happen before a namespace
exists — detect an **exact** `--json` token in raw `argv` before any `--`
terminator to choose the renderer. `--js` must not count. `-h`/`--help` and
`--version` keep exiting 0 with human text even under `--json`, so `SystemExit`
is still caught for those.

**Classes** (the AGENTS.md class preference, at the boundaries that are real —
two output formats and three selection modes are the actual pressure):

- `RepositorySelector` — turns the parsed selector options into a
  `SelectedRepository(store: TodoStore, name: str | None)`. Owns the three modes:
  `--root` exact, `--repo` via `RepositoryCollection` (creating the directory
  when the command is `init`), and no-selector discovery (`init` → exact cwd,
  everything else → `TodoStore.discover`).
- `TaskPresenter` — constructed with the repository name and resolved path;
  `as_json(task, actionable)` builds the 16-key Task object, `summary_line(task)`
  builds the human line.
- `CommandRunner` — one method per command, each returning
  `CommandOutcome(data: dict, human: str)`. Explicit dict dispatch, replacing the
  12-branch `if/elif`.
- `OutputWriter(json_mode: bool)` — `success(command, outcome)` writes either the
  human text to stdout or `{"schema_version": 1, "command": …, "data": …}` plus a
  newline; `failure(error)` writes either `bot-todo: error: …` to stderr or the
  error document (with `details` merged into `error`) to stderr, **emitting
  nothing on stdout**.

**Exit mapping** in `main()`: `0` success; `TodoError` with code `usage` → `2`;
every other `TodoError` → `1`; `OSError` → wrapped as
`TodoError(code="io_error")` → `1` (Phase 1 caught `OSError` but never gave it a
code, so JSON mode has nothing to report without this).

**Human output** per ticket 04: `list` prints one summary line per task and
prints *nothing* when empty; `critical`/`actionable` print an explanatory line
and still exit 0 when empty; `show` prints canonical Markdown; mutations print a
short confirmation naming the task ID; `init`/`validate`/`archive` print a short
status or count.

### 4. Call sites and repository bookkeeping

- `tests/support.py`: `init --project` → `init --name`; add a small
  `run_json(*args)` helper that parses the stdout document.
- `skills/todo/SKILL.md`: `next` → `actionable`, `--project` → `--name`.
  Mechanical only — Phase 4 does the reduction.
- `AGENTS.md:96` already reads `bot-todo --root . validate`; verify no stale
  spellings remain.
- Copy this plan to `.scratch/installable-bot-todo/phase-2-plan.md`, matching the
  `phase-1-plan.md` convention, so the decisions above live beside the spec.
- Add the Phase 2 task to this repo's `TODO.md` **through the CLI** and complete
  it, per the AGENTS.md task-management contract (it will be T003).
- Write `docs/adr/0003-…` only if implementation forces a departure from this
  plan; the four JSON shapes above are gap-filling, not spec departures, so they
  belong in the Phase 2 plan document rather than an ADR.

### 5. Out of scope

`--all`, exit 3, aggregate queries, `skill_installation.py`, `skill_assets/`,
removing `skills/todo/`, and CI. Do not scaffold for them.

Two pre-existing issues found during exploration are **flagged, not fixed**:
`README.md` is 0 bytes but declared as `readme` in `pyproject.toml`, and
`[tool.ruff.lint]` declares no `select` even though `repository.py:3` carries
`# ruff: noqa: DTZ011` (a rule outside ruff's default set), so the lint gate is
not reproducible from the repo alone. Say the word and either becomes a one-line
addition to this phase.

## Verification

Standard gate (AGENTS.md), all of which must pass:

```bash
uv sync
make pytest
ruff check src tests && ruff format --check src tests
mypy src tests
make napoleon-gate            # baseline is 0 violations — any new one fails
```

New coverage, phrased as the Phase 2 gate from ticket 14:

**`tests/test_config.py`** — precedence (`--config` > `BOT_TODO_CONFIG` >
default); missing default is an empty collection; missing explicit file is
`config_not_found`; empty and malformed files are `invalid_config`; unsupported
`schema_version` is `unsupported_config_version` carrying encountered/supported
**and touching no repository**; unknown top-level key, unknown entry key,
duplicate name, and duplicate resolved path each invalidate the whole file;
entry paths resolve absolute/`~`/config-relative and do **not** expand `$VARS`;
a missing entry path is valid configuration.

**`tests/test_cli.py`** — every command in both human and JSON mode; the Task
object carries all 16 keys with correct nullability for simple/completed/
cancelled/claimed tasks; `critical` returns a blocked or claimed task while
`actionable` skips it, and a cancelled blocker still blocks; empty `list` prints
nothing but exits 0; empty singular queries print a line and exit 0; JSON failure
writes **no stdout**; abbreviation rejected at root *and* subcommand level;
`--json` usage errors emit a JSON error document (the pre-namespace path) while
`--js` does not; `--help`/`--version` succeed under `--json`; `--config` without
`--repo` is exit 2; a no-op `edit` is exit 2; `--repo` against a configured
repository works and `init --repo` creates a missing path.

End-to-end against a wheel installed outside the checkout, extending the existing
`test_distribution.py` path:

```bash
uv build && cd $(mktemp -d) && uv venv
uv pip install /path/to/bot_todo/dist/bot_todo-0.1.0-*.whl
mkdir demo && ./.venv/bin/bot-todo --root demo init --name Demo
./.venv/bin/bot-todo --json --root demo add "Try it" --type chore --simple
./.venv/bin/bot-todo --json --root demo critical
printf 'schema_version = 1\n\n[[repositories]]\nname = "demo"\npath = "%s/demo"\n' "$PWD" > cfg.toml
./.venv/bin/bot-todo --json --config cfg.toml --repo demo list
```

Compatibility against this repository's own live files, which must still pass
unchanged and must not rewrite anything on a read:

```bash
bot-todo --root . validate && bot-todo --root . list
git diff --stat TODO.md TODO.archive.md    # must be empty
```

Phase 2 is done when every public command and selector accepts and rejects the
documented shapes, single-repository human and JSON workflows pass end to end,
configuration precedence and validation match the settled contract, and both
unsupported Task Data Format and unsupported Configuration Schema versions fail
before repository access or writes.
