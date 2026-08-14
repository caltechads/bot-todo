# Grouped human list by Repository Name

**Task:** T014.

**ADR:** [docs/adr/0004-group-human-all-list-by-repository-name.md](../../docs/adr/0004-group-human-all-list-by-repository-name.md)

**Goal:** Human `--all list` groups open tasks under Repository Name headers, and every human `list` line shows ordinary Tags as `#tag`, without changing JSON Aggregate Query order or `critical` / `actionable`.

## Settled contract

- **`--all list` (human only)** groups open tasks under a header per populated repository. JSON `--all list` is unchanged: an Aggregate Query ordered by priority, then configuration order, then task-file order.
- **Header** is the configured Repository Name (slug), bare, on its own line. Always printed for `--all list`, even when only one repository has open tasks. `--repo` / `--root` / discovery `list` stay flat (no header).
- **Group order** is Repository Collection (TOML) order. Repositories with no open tasks are omitted. Inside a group: P0, then P1, then P2, then file order.
- **Blank line between groups**, not between header and first task. Task lines are unindented and do not repeat the name.
- **Tags** on every human `list` line (single-repo and `--all`): ordinary user tags (`Task.user_tags` / JSON `tags`), space-separated `#tag` after the title, first-seen order. Type (`chore`, …) and `simple` stay off the line. No tags → no extra suffix.
- **`critical` / `actionable`** human lines stay `{name} {id} {priority} {title}` (aggregate) or `{id} {priority} {title}` (single-repo). No headers, no tags.
- **Glossary:** add **Tag** only. Do not add Task Type. Do not add a term for the grouped view.

Mockup (`--all list`):

```
alpha
T002 P0 urgent #auth
T001 P2 later

beta
T001 P0 beta work
T003 P1 beta next #api
```

Single-repo `list`: `T002 P0 urgent #auth`

## Why `summary_line` cannot grow tags

[`TaskPresenter.summary_line`](../../src/bot_todo/cli.py) is `{id} {priority} {title}` and is shared by `list`, `critical`, and `actionable` (via [`aggregate_line`](../../src/bot_todo/cli.py) for `--all`). Tags belong only on `list`.

## Architecture

Keep ownership on `TaskPresenter` and `AggregateRunner`:

1. **`TaskPresenter.list_line(task)`** — `summary_line` plus a Tag suffix. `CommandRunner._list` uses it. `summary_line` and `aggregate_line` stay unchanged.
2. **`AggregateRunner._human_list(rows)`** — group the existing priority-first row stream by Repository Name in `self.collection` order. JSON still uses `[row.as_json() for row in rows]` from `_rows()`.

Do not change `_rows()`, JSON Schema Version, or the todo skill (agents use `--json`).

## Implementation order

### 1. Persist this plan and ADR (this directory)

This plan and
[ADR 0004](../../docs/adr/0004-group-human-all-list-by-repository-name.md)
are linked from T014.

### 2. Failing tests (TDD)

Modify and add cases on [`tests/test_cli.py`](../../tests/test_cli.py) `AggregateQueryTests` / `QueryTests`, matching existing `AggregateTestCase` helpers. Update the packaged smoke in [`tests/test_distribution.py`](../../tests/test_distribution.py).

Replace `test_human_rows_name_their_repository`:

```python
def test_human_rows_name_their_repository(self) -> None:
    self.add("alpha", "alpha work", "P0")
    self.add("beta", "beta work", "P1")

    result = self.aggregate("list")

    self.assertEqual(
        result.stdout.splitlines(),
        ["alpha", "T001 P0 alpha work", "", "beta", "T001 P1 beta work"],
    )
```

Human vs JSON order (alpha only P2, beta P0):

```python
def test_human_list_groups_by_repository_while_json_stays_priority_first(
    self,
) -> None:
    self.add("alpha", "alpha late", "P2")
    self.add("beta", "beta first", "P0")

    result = self.aggregate("list")
    tasks = self.aggregate_json("list")["tasks"]

    self.assertEqual(self.provenance(tasks), [("beta", "T001"), ("alpha", "T001")])
    self.assertEqual(
        result.stdout.splitlines(),
        ["alpha", "T001 P2 alpha late", "", "beta", "T001 P0 beta first"],
    )
```

One populated repository still prints the header:

```python
def test_all_list_prints_a_header_for_a_single_populated_repository(self) -> None:
    self.add("alpha", "alpha work", "P0")

    result = self.aggregate("list")

    self.assertEqual(result.stdout.splitlines(), ["alpha", "T001 P0 alpha work"])
```

Empty repositories omitted (gamma configured, no open tasks — extend `write_config` / `setUp` as needed, or configure alpha+beta and leave beta empty):

```python
def test_all_list_omits_repositories_with_no_open_tasks(self) -> None:
    self.add("alpha", "alpha work", "P0")

    result = self.aggregate("list")

    self.assertEqual(result.stdout.splitlines(), ["alpha", "T001 P0 alpha work"])
    self.assertNotIn("beta", result.stdout.splitlines())
```

Tags on single-repo and `--all` list; type and `simple` absent. `AggregateTestCase.add` already passes `--type chore --simple`; pass `--tag auth` via `*extra`:

```python
def test_human_list_appends_user_tags(self) -> None:
    self.add("alpha", "alpha work", "P0", "--tag", "auth")

    listed = invoke("--config", str(self.config), "--repo", "alpha", "list")
    aggregated = self.aggregate("list")

    self.assertEqual(listed.stdout.splitlines(), ["T001 P0 alpha work #auth"])
    self.assertEqual(
        aggregated.stdout.splitlines(),
        ["alpha", "T001 P0 alpha work #auth"],
    )
    self.assertNotIn("#chore", listed.stdout)
    self.assertNotIn("#simple", listed.stdout)
```

Singular aggregate queries keep the name prefix and omit tags:

```python
def test_all_critical_keeps_a_prefixed_line_without_tags(self) -> None:
    self.add("alpha", "alpha work", "P0", "--tag", "auth")

    result = self.aggregate("critical")

    self.assertEqual(result.stdout.strip(), "alpha T001 P0 alpha work")
    self.assertNotIn("#auth", result.stdout)
```

Packaged `--all list` in `test_distribution.py`:

```python
self.assertEqual(aggregated.strip(), "demo\nT001 P2 Installed task")
```

Single-repo empty list and `--repo` without a header stay as they are (`test_a_single_repository_row_keeps_no_provenance_prefix`, `test_an_empty_list_prints_nothing_and_succeeds`). JSON provenance tests stay as they are.

Run: `make pytest ARGS="tests/test_cli.py::AggregateQueryTests --no-cov"` — expect the human-line assertions to fail until the presenter and runner change.

### 3. Glossary

In [`CONTEXT.md`](../../CONTEXT.md), after **Aggregate Query**, add:

```md
**Tag**:
An ordinary label on a Task. It is not the classifying type and not the
`simple` marker.
_Avoid_: Type, hashtag, label, keyword
```

### 4. `TaskPresenter.list_line`

In [`src/bot_todo/cli.py`](../../src/bot_todo/cli.py) on `TaskPresenter`, next to `summary_line`:

```python
def list_line(self, task: Task) -> str:
    """
    Build one human list row, including Tags.

    Args:
        task: Task to summarize.

    Returns:
        Single-line list row.

    """
    suffix = "".join(f" #{tag}" for tag in task.user_tags)
    return f"{self.summary_line(task)}{suffix}"
```

`CommandRunner._list` joins `self.presenter.list_line(task)` instead of `summary_line`. Leave `_singular` and `mutation_line` on `summary_line` / `aggregate_line`.

### 5. `AggregateRunner._human_list`

Replace the human string in `AggregateRunner._list`. Filtering the existing `_rows()` stream per Repository Name preserves P0→P1→P2 then file order inside each group.

```python
def _list(self, rows: Sequence[AggregateRow]) -> CommandOutcome:
    """
    List every open task across the collection.

    Args:
        rows: Every open task in aggregate order.

    Returns:
        Every open task, empty when no backlog has open work.

    """
    return CommandOutcome(
        {"tasks": [row.as_json() for row in rows]},
        self._human_list(rows),
    )

def _human_list(self, rows: Sequence[AggregateRow]) -> str:
    """
    Group open tasks under Repository Name headers.

    Args:
        rows: Every open task in aggregate order.

    Returns:
        Human list text, empty when no group has open work.

    """
    groups: dict[str, list[AggregateRow]] = {
        entry.name: [] for entry in self.collection
    }
    for row in rows:
        name = row.presenter.name
        if name is not None:
            groups[name].append(row)
    chunks: list[str] = []
    for entry in self.collection:
        group = groups[entry.name]
        if not group:
            continue
        presenter = group[0].presenter
        lines = [entry.name, *(presenter.list_line(row.task) for row in group)]
        chunks.append("\n".join(lines))
    return "\n\n".join(chunks)
```

Empty collection / no open tasks: `chunks` is empty, `_human_list` returns `""`, `OutputWriter.success` prints nothing.

### 6. README

In [`README.md`](../../README.md), keep “`--all` orders results by priority, then configuration order, then file order” for JSON / `critical` / `actionable`. Add that human `--all list` groups by Repository Name in collection order, omits empty repositories, and omits the name from task lines. Do not change [`src/bot_todo/skill_assets/todo/SKILL.md`](../../src/bot_todo/skill_assets/todo/SKILL.md).

### 7. Quality gate

- `uv run ruff check` on touched files
- `uv run mypy` on touched files
- `make napoleon-gate`
- `make pytest ARGS="tests/test_cli.py tests/test_distribution.py --no-cov"` then `make pytest` if that slice is green
