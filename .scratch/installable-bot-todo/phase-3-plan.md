# Phase 3 — Add aggregate read queries

## Context

Phase 1 (T002) extracted the repository core; Phase 2 (T003) shipped the public
single-repository CLI — full command grammar, Configuration Schema 1, `--repo`,
JSON Schema 1, and exits 0/1/2. Everything Phase 3 needs already exists:
`RepositoryCollection` preserves configuration order, `TodoStore.snapshot()`
takes and releases one shared lock, every JSON Task already carries
`{"repository": {"name", "path"}}`, and `TodoError.details` already splats into
the JSON `error` object (proven by `unsupported_format_version`).

What is missing is the aggregate surface itself: there is no `--all` anywhere in
`src/` or `tests/`, no `aggregate_partial_failure` code, and no exit 3.
`--config` is currently a hard usage error unless `--repo` is given.

Phase 3 adds `--all` for `list`, `critical`, and `actionable` only, merges
per-repository snapshots in the settled deterministic order, and makes any
single repository failure abort the whole query with exit 3.

Sources: `spec.md` §"Phase 3", §"Repository selection", §"Queries"; tickets
[`08`](issues/08-define-aggregate-query-semantics.md) (ordering, provenance) and
[`12`](issues/12-define-concurrency-and-failure-policy.md) (aggregate failure).

## Decisions confirmed with the user

1. **The aggregate read path lives in `cli.py`**, as a new `AggregateRunner`
   class mirroring `CommandRunner`. `config.py` stays pure TOML discovery and
   validation and never imports `TodoStore`. The spec permits either; `cli.py`
   already owns stores, presenters, and rendering, which is all the merge needs.
2. **`CommandRunner` is not touched.** `AggregateRunner` re-implements the two
   ~3-line projection helpers over its own rows rather than refactoring both
   runners onto a shared row type. Phase 2's single-repository path cannot
   regress.

## Implementation — all in `src/bot_todo/cli.py`

### 1. Grammar (`_build_parser`, cli.py:797)

Add `--all` to the existing mutually exclusive `selector` group, so
`--all --root` / `--all --repo` are rejected by argparse itself, which routes
through the `_Parser.error` override to `usage` and exit 2 for free:

```python
selector.add_argument("--all", action="store_true", help="every configured repository")
```

New module constant beside `EXIT_USAGE`:

```python
#: Commands the aggregate selector supports.
AGGREGATE_COMMANDS = frozenset({"list", "critical", "actionable"})
#: Exit status for an aggregate query with any failed repository.
EXIT_AGGREGATE = 3
```

### 2. `RepositorySelector` (cli.py:124)

Gains an `aggregate: bool` constructor parameter (argparse's dest is `all`, a
builtin, so the attribute is named `aggregate`). Three changes:

- **New `validate(command)`** holding both selector-policy checks, called from
  `main()` before either runner is built:
  - `--config` without `--repo` and without `--all` → `usage`. This is the
    Phase 2 message `"--config requires --repo"` relaxed to
    `"--config requires --repo or --all"`.
  - `--all` with a command outside `AGGREGATE_COMMANDS` → `usage`. This is the
    prohibition on multi-repository mutation.
  Remove the `--config` check from `select()`.
- **New `_explicit()`** hoisting the `--config` → `BOT_TODO_CONFIG` →
  default precedence chain currently inlined in `_configured` (cli.py:206-210),
  so `--repo` and `--all` share one resolution path instead of duplicating it.
- **New `collection()`** returning `RepositoryCollection.load(self._explicit())`.
  `_configured` becomes `self.collection().entry(repo)`.

Configuration failures (`config_not_found`, `invalid_config`,
`unsupported_config_version`) therefore still raise before any repository is
read, which is exactly the all-or-nothing rule ticket 12 requires. A missing
platform default yields an empty collection, so `--all list` succeeds with
`{"tasks": []}` and exit 0.

### 3. `TaskPresenter` (cli.py:217)

One new method; `summary_line` is unchanged so single-repository output stays
unprefixed even under `--repo`:

```python
def aggregate_line(self, task: Task) -> str:
    """Prefix one summary with its Repository Name so IDs stay unambiguous."""
    return f"{self.name} {self.summary_line(task)}"
```

Punctuation is not contractual (ticket 08). `--all` entries always come from
configuration, so `self.name` is always a real name here.

### 4. `AggregateRunner` — new class in `cli.py`

```python
class AggregateRunner:
    """Run one aggregate read query across the configured Repository Collection."""

    def __init__(self, collection: RepositoryCollection) -> None: ...

    def run(self, command: str) -> CommandOutcome          # dict dispatch, 3 entries
    def _read(self) -> list[tuple[TaskPresenter, RepositorySnapshot]]
    def _rows(self, repositories) -> Iterator[tuple[TaskPresenter, RepositorySnapshot, Task]]
```

**`_read`** — inspect *every* entry in configuration order, building the
`TodoStore` inside the per-entry `try` so a bad path is a per-repository failure
rather than a global `io_error`. Catch `TodoError` and `OSError`; on any
failure, raise once at the end:

```python
raise TodoError(summary, "aggregate_partial_failure", {"failures": failures})
```

Each failure record is `{"name", "path", "code", "message"}` in configuration
order, per ticket 12. `OSError` is wrapped as code `io_error`. Successful
repositories' data is deliberately discarded — missing data could change global
ordering or the selected task. The summary message enumerates the failed
repository names so human mode is useful without touching `OutputWriter`.

**`_rows`** — the whole ordering contract, priority-major, repository-order
next, file-order last:

```python
for priority in PRIORITY_HEADINGS:
    for presenter, snapshot in repositories:
        for task in snapshot.document.active[priority]:
            yield presenter, snapshot, task
```

Note the loop nesting: a naive `for repo: extend(repo_tasks)` produces the wrong
order, because `CommandRunner._list` is already priority-major *within* one
repository. The repository loop must sit *between* the priority and file loops.

**The three queries** are then one line each over `_rows`:

- `list` → every row.
- `critical` → the first row (blocked and claimed tasks included).
- `actionable` → the first row where `snapshot.is_actionable(task)`; blockers
  stay repository-local, which `RepositorySnapshot.is_actionable` already
  guarantees.

Both singular queries return `{"task": null}` with an explanatory line and
exit 0 when empty, matching `CommandRunner._singular`.

### 5. `main()` (cli.py:864)

```python
selector = RepositorySelector(
    arguments.root, arguments.repo, arguments.all, arguments.config
)
selector.validate(arguments.command)
if arguments.all:
    outcome = AggregateRunner(selector.collection()).run(arguments.command)
else:
    outcome = CommandRunner(selector.select(arguments.command)).run(
        arguments.command, arguments
    )
```

Exit mapping becomes a small lookup instead of a second `if`:

```python
#: Exit status per error code, defaulting to EXIT_FAILURE.
EXIT_CODES = {"usage": EXIT_USAGE, "aggregate_partial_failure": EXIT_AGGREGATE}
...
except TodoError as error:
    writer.failure(error)
    return EXIT_CODES.get(error.code, EXIT_FAILURE)
```

`OutputWriter` needs no change: it already merges `error.details` into the JSON
`error` object and already writes nothing to stdout on failure.

### Not in this phase

`skill_installation.py`, `skill_assets/`, removing `skills/todo/`, CI, and any
aggregate mutation abstraction. Do not scaffold for them.

## Repository bookkeeping

- Copy this plan to `.scratch/installable-bot-todo/phase-3-plan.md`, matching the
  `phase-1-plan.md` / `phase-2-plan.md` convention.
- Add the Phase 3 task to `TODO.md` **through the CLI** (it will be T004) and
  complete it at the end, per the AGENTS.md task-management contract.
- Add one `--all` line to `skills/todo/SKILL.md` — mechanical only, Phase 4 still
  owns the reduction.
- Add an **Aggregate Query** entry to `CONTEXT.md` (Repository Collection,
  Critical Task, and Actionable Task are already defined there).
- No ADR: this plan makes no departure from the spec.

## Verification

Standard gate (AGENTS.md), all of which must pass:

```bash
uv sync
make pytest
ruff check src tests && ruff format --check src tests
mypy src tests            # strict for src — annotate everything new
make napoleon-gate        # baseline is 0 violations; any new one fails
```

New coverage in **`tests/test_cli.py`** (the spec's file layout adds no test
file in Phase 3). Follow the house style: `unittest.TestCase`, no docstrings on
`test_*` methods, arrange/act/assert separated by blank lines, one behavior per
test. `ConfiguredSelectionTests` is the closest existing template for building a
two-repository TOML fixture.

- **Ordering** — the load-bearing test. Two repositories, tasks at mixed
  priorities, e.g. `alpha` holding P2 then P0 and `beta` holding P0 then P1;
  assert the exact `--all list` sequence is `alpha-P0, beta-P0, beta-P1,
  alpha-P2`. This is what fails under naive per-repository concatenation.
- **Provenance** — each JSON Task's `repository.name` / `repository.path` matches
  its own source repository; human rows carry the Repository Name prefix; a
  single-repository `--repo` row does **not**.
- **Singular queries** — `--all critical` returns a blocked or claimed P0 from
  the first configured repository; `--all actionable` skips it and returns the
  next eligible task from a later repository; a cancelled blocker still blocks.
- **Empty collection** — no configuration at all → `--all list` exits 0 with
  `{"tasks": []}` and prints nothing; `--all critical` exits 0 with
  `{"task": null}`.
- **Partial failure** — one configured path missing → exit **3**, **no stdout**,
  error code `aggregate_partial_failure`, and `failures` carrying name, resolved
  path, `repository_not_found`, and a message. Assert the healthy repository's
  tasks are **not** returned. A second failing repository (e.g. an existing
  directory with no `TODO.md` → `not_initialized`) appears in configuration
  order.
- **Mutation prohibition** — `--all add`, `--all complete T001`, `--all init`,
  `--all validate`, and `--all show T001` each exit **2** with code `usage`.
- **Selector conflicts** — `--all --root`, `--all --repo` exit 2.
- **Config option** — `--config` with `--all` is now accepted; `--config` with
  neither `--repo` nor `--all` is still exit 2; `BOT_TODO_CONFIG` is honored for
  `--all`.

Extend **`tests/test_distribution.py`**'s existing wheel smoke test with one
`--all list` invocation against a two-entry config, so the aggregate path is
exercised from an installed console script outside the checkout:

```bash
uv build && cd $(mktemp -d) && uv venv
uv pip install /path/to/bot_todo/dist/bot_todo-0.1.0-*.whl
mkdir a b && for d in a b; do ./.venv/bin/bot-todo --root $d init --name $d; done
printf 'schema_version = 1\n\n[[repositories]]\nname = "a"\npath = "%s/a"\n\n[[repositories]]\nname = "b"\npath = "%s/b"\n' "$PWD" "$PWD" > cfg.toml
./.venv/bin/bot-todo --json --config cfg.toml --all list
```

Compatibility against this repository's own live files, which must still pass
unchanged and must not rewrite anything on a read:

```bash
bot-todo --root . validate && bot-todo --root . list
git diff --stat TODO.md TODO.archive.md    # must be empty
```

Phase 3 is done when aggregate ordering, provenance, strict all-or-nothing
partial failure with exit 3, and the prohibition on multi-repository mutation
all have runnable coverage, and the Phase 1/2 single-repository contracts pass
unchanged.
