# Review State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Task:** T011.

**ADR:** [docs/adr/0006-review-is-an-in-section-lifecycle-state.md](../../docs/adr/0006-review-is-an-in-section-lifecycle-state.md)

**Glossary:** [CONTEXT.md](../../CONTEXT.md) (**Task State**, **Review**).

**Goal:** A task can move into Review (work finished, not yet accepted), then be completed, cancelled, or returned to open, with CLI, JSON, and the todo skill documenting the new state.

**Architecture:** Keep Review in P0/P1/P2 as an unchecked task with `Review: YYYY-MM-DD`. `Task.state` derives `review` from that field. `TodoDocument` stores `format_version` so writes never auto-upgrade format 1. `RepositoryTransaction.review` / `reopen` / `migrate` own the new transitions; `claim`/`release`/`_find_critical`/`_is_actionable` skip or reject Review. JSON Schema Version becomes 2.

**Tech Stack:** Existing `bot-todo` CLI (`argparse`), Markdown Task Repository, pytest via `make pytest`.

---

## Settled contract

- **Task State:** `open | review | completed | cancelled`. JSON `state` is that value. Review is not an Outcome.
- **Markdown:** Unchecked, still in P0/P1/P2, field `Review: YYYY-MM-DD`. FIELD_ORDER inserts `Review` after `Claimed`, before `Outcome`. No `## Review` section. Not in Done.
- **JSON task object:** existing keys plus `reviewed_on: YYYY-MM-DD | null`. Envelope `schema_version` is **2**.
- **Human `list`:** `T001 P1 review Title` then the existing type/tag suffix. `critical` / `actionable` stay `{id} {priority} {title}` (no `review` word) because they never select Review.
- **Transitions:**
  - `open → review` via `review` (claim optional; Claim is cleared).
  - `review → open` via `reopen` only (not from completed/cancelled).
  - `open → completed` and `review → completed` via `complete`.
  - `open → cancelled` and `review → cancelled` via `cancel --reason`.
- **While in Review:** `edit` legal; `claim`/`release`/`review` → `invalid_transition`.
- **Selectors:** `list` includes Review. `critical` and `actionable` are open-only. Review does not satisfy blockers.
- **Formats:** Read Task Data Format 1 and 2. `init` and all mutations require 2. `migrate` rewrites the marker (1→2); already-2 is a successful no-op reporting `from: 2, to: 2`. Mutating format 1 → `migration_required` with `encountered` and `required`. Format 3+ → `unsupported_format_version` with `encountered` and `supported: [1, 2]`. Format 1 documents must not carry `Review`.
- **Out of scope:** T010 Kanban, package major bump (still 0.1.0), Configuration Schema Version, skill-manifest schema.

## Files

- Modify: `src/bot_todo/repository.py`
- Modify: `src/bot_todo/cli.py`
- Modify: `src/bot_todo/skill_assets/todo/SKILL.md`
- Modify: `README.md`
- Modify: `tests/test_repository.py`, `tests/test_cli.py`, `tests/test_skill_guidance.py`, `tests/test_task_management_snippet.py` (CLI envelope only)
- Optional one-line: `src/bot_todo/skill_assets/task_management.md` if the skill mentions Review as a workflow step agents copy into AGENTS.md
- Do not change: config TOML schema tests, skill-manifest `schema_version`, `CONTEXT.md` / ADR (already written)

## Footguns (read before coding)

1. `_list` already emits every P0/P1/P2 task. Review appears in `list` once the field exists. `_find_critical` and aggregate `_critical` (`next(iter(rows))`) take the **first active** task today and **must skip Review**. `_is_actionable` treats unchecked+unclaimed as startable and **must require `state == "open"`**.
2. `TodoDocument.render` writes `SUPPORTED_FORMAT_VERSION`. The document must store `format_version` so a format-1 read that later saves does not auto-upgrade.
3. `close()` / current `_require_open` accept any unchecked priority-section task. Complete/cancel from Review work if `close` pops `Review`. `claim`/`release` must reject Review explicitly (`state == "open"`).
4. `TodoCliTestCase.setUp` runs `init`. After this work, fixtures are format 2. Format-1 tests must rewrite the marker (or use `CompatibilityTests.LEGACY_TODO`). The current “replace format 1 with 2” unsupported-version tests become a no-op unless they replace **2 with 3**.
5. Bump **CLI JSON** `schema_version` assertions from 1 to 2 (`tests/test_cli.py`, `tests/test_task_management_snippet.py`, README JSON examples). Leave configuration and skill-manifest schema_version 1 alone.
6. ADR 0005’s additive `data.snippet` stays; the envelope version does not.

---

## Implementation order

### 1. Persist this plan (done in the T011 recording session)

This plan and [ADR 0006](../../docs/adr/0006-review-is-an-in-section-lifecycle-state.md) are linked from T011.

### 2. Format 2 read/write + migrate (TDD)

Existing tests treat format 2 as unsupported. Invert that first so later Review tests can `init` (format 2) and still load format 1.

- [ ] **Step 2a: Rewrite the unsupported-version tests**

In [`tests/test_repository.py`](../../tests/test_repository.py) `FormatVersionTests` and [`tests/test_cli.py`](../../tests/test_cli.py) `test_an_unsupported_format_version_reports_its_versions`:

After `init`, the marker is `todo-format: 2`. Replace **2 with 3** (not 1 with 2). Expect `unsupported_format_version`, `encountered: 3`, `supported: [1, 2]`. Mutation of format 3 still must not write.

Add dual-read and migrate cases to `FormatVersionTests` / a new `MigrationTests(TodoCliTestCase)`:

```python
def test_format_1_remains_readable(self) -> None:
    path = self.root / "TODO.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("todo-format: 2", "todo-format: 1"),
        encoding="utf-8",
    )
    result = self.run_cli("validate")
    self.assertEqual(result.stdout.strip(), "valid")


def test_mutating_format_1_requires_migrate(self) -> None:
    path = self.root / "TODO.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("todo-format: 2", "todo-format: 1"),
        encoding="utf-8",
    )
    error = self.run_json_error("add", "Work", "--type", "chore", "--simple")
    self.assertEqual(error["code"], "migration_required")
    self.assertEqual(error["encountered"], 1)
    self.assertEqual(error["required"], 2)
    self.assertIn("todo-format: 1", path.read_text(encoding="utf-8"))


def test_migrate_rewrites_format_1_to_2(self) -> None:
    path = self.root / "TODO.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("todo-format: 2", "todo-format: 1"),
        encoding="utf-8",
    )
    document = self.run_json("migrate")
    self.assertEqual(document["command"], "migrate")
    self.assertEqual(document["data"]["from"], 1)
    self.assertEqual(document["data"]["to"], 2)
    self.assertIn("todo-format: 2", path.read_text(encoding="utf-8"))
    self.run_cli("add", "Work", "--type", "chore", "--simple")


def test_migrate_on_format_2_is_a_successful_noop(self) -> None:
    document = self.run_json("migrate")
    self.assertEqual(document["data"]["from"], 2)
    self.assertEqual(document["data"]["to"], 2)


def test_format_1_rejects_a_review_field(self) -> None:
    path = self.root / "TODO.md"
    body = path.read_text(encoding="utf-8").replace("todo-format: 2", "todo-format: 1")
    body = body.replace(
        "## P2 — Normal\n",
        "## P2 — Normal\n\n"
        "- [ ] **T001** Hand edited #chore #simple\n"
        "  - Review: 2026-08-17\n",
    )
    path.write_text(body, encoding="utf-8")
    error = self.run_json_error("validate")
    self.assertEqual(error["code"], "invalid_document")
```

Update [`tests/test_cli.py`](../../tests/test_cli.py) `test_add_round_trips_through_the_canonical_file` (and any other `todo-format: 1` assertion after `init`) to expect `todo-format: 2`.

Keep `CompatibilityTests.LEGACY_TODO` loading as a format-1 read.

JSON envelope tests: `self.assertEqual(document["schema_version"], 2)` in `test_the_success_envelope_names_its_command_and_version` and `tests/test_task_management_snippet.py`. Add `"reviewed_on"` to `JsonContractTests.TASK_KEYS` (null for open tasks).

Run: `make pytest ARGS="tests/test_cli.py::JsonContractTests tests/test_repository.py::FormatVersionTests --no-cov"`

Expected: FAIL — format 2 still unsupported; `migrate` unknown; schema still 1.

- [ ] **Step 2b: Format constants and `TodoDocument.format_version`**

In [`src/bot_todo/repository.py`](../../src/bot_todo/repository.py) replace the single supported-version constant:

```python
#: Task Data Format versions this release can read.
READABLE_FORMAT_VERSIONS = frozenset({1, 2})
#: Task Data Format version this release writes.
WRITE_FORMAT_VERSION = 2
```

Add `format_version: int` to `TodoDocument` (constructor `Args:`). `initialize` builds `TodoDocument(..., format_version=WRITE_FORMAT_VERSION)`. `render` uses `self.format_version`, not a module constant:

```python
f"<!-- todo-format: {self.format_version}; next-id: {self.next_id} -->"
```

`_parse_document` stores the parsed version. Reject versions not in `READABLE_FORMAT_VERSIONS` with `unsupported_format_version` and `supported: sorted(READABLE_FORMAT_VERSIONS)`. Soften the metadata error from “todo-format 1” to “todo-format and next-id”.

- [ ] **Step 2c: `migration_required` on mutations; `migrate`**

On `RepositoryTransaction`, call `_require_writable_format()` at the start of `add`, `edit`, `claim`, `release`, `close`, and `retire_overflow` (covers `archive`). Do **not** call it from `migrate`.

```python
def _require_writable_format(self) -> None:
    """
    Require Task Data Format 2 before mutating.

    Raises:
        TodoError: If the loaded document is not the write format.
    """
    if self.document.format_version != WRITE_FORMAT_VERSION:
        raise TodoError(
            (
                f"task data format {self.document.format_version} cannot "
                "be mutated; run bot-todo migrate"
            ),
            "migration_required",
            {
                "encountered": self.document.format_version,
                "required": WRITE_FORMAT_VERSION,
            },
        )


def migrate(self) -> tuple[int, int]:
    """
    Set the document's Task Data Format to the write version.

    Returns:
        Encountered version and write version (equal when already current).
    """
    encountered = self.document.format_version
    self.document.format_version = WRITE_FORMAT_VERSION
    return encountered, WRITE_FORMAT_VERSION
```

CLI: `JSON_SCHEMA_VERSION = 2`. Parser `commands.add_parser("migrate", help="upgrade the task data format")`. Handler:

```python
def _migrate(self, _arguments: argparse.Namespace) -> CommandOutcome:
    with self.store.transaction() as transaction:
        encountered, required = transaction.migrate()
    return CommandOutcome(
        {
            "repository": self.presenter.repository(),
            "from": encountered,
            "to": required,
        },
        (
            f"already format {required}"
            if encountered == required
            else f"migrated {encountered} -> {required}"
        ),
    )
```

Wire `migrate` in `CommandRunner.run` handlers. `migrate` is a task command (`--root` / `--repo`); not `--all`; not selector-free.

Run the Step 2a tests. Expected: PASS.

### 3. Review field, state, and selectors (TDD)

- [ ] **Step 3a: Failing lifecycle tests**

Add `ReviewStateTests(TodoCliTestCase)` in [`tests/test_cli.py`](../../tests/test_cli.py). Fixtures are already format 2 after `init`.

```python
class ReviewStateTests(TodoCliTestCase):
    """Cover Review transitions, selectors, and JSON."""

    def test_review_clears_claim_and_stays_in_priority_section(self) -> None:
        task_id = self.add_simple("Needs a look", "P1")
        self.run_cli(
            "claim", task_id, "--actor", "codex", "--branch", "feature/review"
        )
        result = self.run_cli("review", task_id)
        self.assertEqual(result.stdout.strip(), f"reviewed {task_id} Needs a look")

        shown = self.run_cli("show", task_id).stdout
        self.assertIn("Review:", shown)
        self.assertNotIn("Claimed:", shown)
        self.assertNotIn("Outcome:", shown)
        todo = (self.root / "TODO.md").read_text(encoding="utf-8")
        p1 = todo.index("## P1")
        done = todo.index("## Done")
        self.assertLess(p1, todo.index(task_id))
        self.assertLess(todo.index(task_id), done)

        task = self.run_json("show", task_id)["data"]["task"]
        self.assertEqual(task["state"], "review")
        self.assertEqual(task["priority"], "P1")
        self.assertIsNone(task["claim"])
        self.assertFalse(task["actionable"])
        self.assertRegex(task["reviewed_on"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIsNone(task["closed_on"])

    def test_unclaimed_open_task_can_enter_review(self) -> None:
        task_id = self.add_simple("Unclaimed work", "P2")
        self.run_cli("review", task_id)
        self.assertEqual(
            self.run_json("show", task_id)["data"]["task"]["state"], "review"
        )

    def test_list_includes_review_with_state_word(self) -> None:
        open_id = self.add_simple("Still open", "P1")
        review_id = self.add_simple("Waiting", "P1")
        self.run_cli("review", review_id)
        lines = self.run_cli("list").stdout.splitlines()
        self.assertIn(f"{open_id} P1 Still open #chore", lines)
        self.assertIn(f"{review_id} P1 review Waiting #chore", lines)

    def test_critical_and_actionable_skip_review(self) -> None:
        first = self.add_simple("In review", "P0")
        second = self.add_simple("Still open", "P1")
        self.run_cli("review", first)
        self.assertEqual(self.run_cli("critical").stdout.split()[0], second)
        self.assertEqual(self.run_cli("actionable").stdout.split()[0], second)

    def test_review_does_not_satisfy_blockers(self) -> None:
        blocker = self.add_simple("Blocker", "P1")
        dependent = self.added_id(
            "Dependent",
            "--priority",
            "P1",
            "--type",
            "feature",
            "--simple",
            "--blocked-by",
            blocker,
        )
        self.run_cli("review", blocker)
        self.assertEqual(
            self.run_cli("actionable").stdout.strip(), "no actionable task"
        )
        self.assertIn(dependent, self.run_cli("list").stdout)

    def test_complete_from_review_and_from_open(self) -> None:
        reviewed = self.add_simple("Reviewed work", "P2")
        opened = self.add_simple("Direct complete", "P2")
        self.run_cli("review", reviewed)
        self.run_cli("complete", reviewed)
        self.run_cli("complete", opened)
        self.assertEqual(
            self.run_json("show", reviewed)["data"]["task"]["state"], "completed"
        )
        self.assertIsNone(
            self.run_json("show", reviewed)["data"]["task"]["reviewed_on"]
        )
        self.assertEqual(
            self.run_json("show", opened)["data"]["task"]["state"], "completed"
        )

    def test_cancel_from_review(self) -> None:
        task_id = self.add_simple("Abandoned in review", "P2")
        self.run_cli("review", task_id)
        self.run_cli("cancel", task_id, "--reason", "Not shipping")
        task = self.run_json("show", task_id)["data"]["task"]
        self.assertEqual(task["state"], "cancelled")
        self.assertEqual(task["reason"], "Not shipping")
        self.assertIsNone(task["reviewed_on"])

    def test_reopen_returns_to_open_and_is_actionable(self) -> None:
        task_id = self.add_simple("Send back", "P1")
        self.run_cli("review", task_id)
        result = self.run_cli("reopen", task_id)
        self.assertEqual(result.stdout.strip(), f"reopened {task_id} Send back")
        task = self.run_json("show", task_id)["data"]["task"]
        self.assertEqual(task["state"], "open")
        self.assertIsNone(task["reviewed_on"])
        self.assertTrue(task["actionable"])
        self.assertIn(f"{task_id} P1 Send back #chore", self.run_cli("list").stdout)

    def test_reopen_rejects_open_and_completed(self) -> None:
        opened = self.add_simple("Never reviewed", "P2")
        closed = self.add_simple("Already done", "P2")
        self.run_cli("complete", closed)
        self.assertEqual(
            self.run_json_error("reopen", opened)["code"], "invalid_transition"
        )
        self.assertEqual(
            self.run_json_error("reopen", closed)["code"], "invalid_transition"
        )

    def test_claim_and_second_review_are_invalid_in_review(self) -> None:
        task_id = self.add_simple("Locked", "P2")
        self.run_cli("review", task_id)
        self.assertEqual(
            self.run_json_error(
                "claim", task_id, "--actor", "codex", "--branch", "x"
            )["code"],
            "invalid_transition",
        )
        self.assertEqual(
            self.run_json_error("review", task_id)["code"], "invalid_transition"
        )

    def test_edit_is_legal_in_review(self) -> None:
        task_id = self.add_simple("Editable", "P2")
        self.run_cli("review", task_id)
        self.run_cli("edit", task_id, "--title", "Still editable")
        self.assertEqual(
            self.run_json("show", task_id)["data"]["task"]["title"],
            "Still editable",
        )
        self.assertEqual(
            self.run_json("show", task_id)["data"]["task"]["state"], "review"
        )
```

Add one aggregate case on `AggregateQueryTests`: a P0 Review task in `alpha` must not become `--all critical` when `beta` has a P1 open task. Filter `row.task.state == "open"` in `_critical`; `_list` still includes Review rows; human list line uses `list_line` (already grouped).

Run: `make pytest ARGS="tests/test_cli.py::ReviewStateTests --no-cov"`

Expected: FAIL — `review` / `reopen` unknown.

- [ ] **Step 3b: Model — FIELD_ORDER, `state`, `reviewed_on`, validation**

```python
FIELD_ORDER = (
    "Acceptance",
    "Context",
    "Related",
    "Blocked by",
    "Claimed",
    "Review",
    "Outcome",
    "Closed",
    "Reason",
)
```

`Task.state`:

```python
if self.checked:
    return self.fields.get("Outcome", "completed")
if "Review" in self.fields:
    return "review"
return "open"
```

Add `reviewed_on` mirroring `closed_on` (`self.fields.get("Review")`).

`_validate_document` active branch (has `priority`): still unchecked; no Outcome/Closed; if `Review` present: format_version must be 2, no Claimed, valid date; if format_version == 1, any `Review` field is invalid. Closed branch: must not carry `Review`.

- [ ] **Step 3c: Transitions**

Tighten helpers:

```python
def _require_not_closed(task: Task) -> None:
    if task.checked or task.priority is None:
        raise TodoError(f"{task.task_id} is closed", "invalid_transition")


def _require_state(task: Task, expected: str) -> None:
    if task.state != expected:
        raise TodoError(
            f"{task.task_id} is {task.state}", "invalid_transition"
        )
```

- `claim` / `release`: `_require_writable_format`, `_require_state(task, "open")`, then existing logic.
- `review(task_id)`: writable, `_require_state(..., "open")`, `fields.pop("Claimed", None)`, `fields["Review"] = date.today().isoformat()`.
- `reopen(task_id)`: writable, `_require_state(..., "review")`, `fields.pop("Review")`.
- `close`: writable, `_require_not_closed`, then existing move to Done; also `fields.pop("Review", None)` (and existing Claimed pop).
- `edit`: writable, `_require_not_closed` (open **or** review). Do not let edit plant Outcome/Review via flags (no new edit flags).

`_is_actionable`: return False unless `task.state == "open"` (then existing claim/blocker rules). `_find_critical`: skip `task.state != "open"`. `_find_next` already uses `_is_actionable`.

- [ ] **Step 3d: CLI presenters and commands**

`TaskPresenter._project`: add `"reviewed_on": task.reviewed_on`.

`list_line`:

```python
def list_line(self, task: Task) -> str:
    suffix = "".join(f" #{tag}" for tag in task.tags if tag != SIMPLE_TAG)
    if task.state == "review":
        return f"{task.task_id} {task.priority} review {task.title}{suffix}"
    return f"{self.summary_line(task)}{suffix}"
```

Leave `summary_line` as `{id} {priority or state} {title}` so critical/actionable stay unchanged.

`MUTATION_VERBS`: `"review": "reviewed"`, `"reopen": "reopened"`.

Handlers `_review` / `_reopen` like `_complete`, calling `transaction.review` / `transaction.reopen` then `_mutated`.

Parser: `review` and `reopen` each take `task_id`. Help text: `list` “list open and review tasks”; `complete`/`cancel`/`edit` mention open or review; `claim` stays “open”.

`AggregateRunner._critical`:

```python
return self._singular(
    next((row for row in rows if row.task.state == "open"), None),
    "no open task",
)
```

`_list` / `_rows` stay every active (P0/P1/P2) task so Review is included. `_actionable` already filters `is_actionable`.

Napoleon: update `Task.state` Returns, `_list` docstrings, `_require_open` if renamed, new methods’ Args/Raises/Returns/Side Effects.

Run ReviewStateTests + FormatVersionTests + JsonContractTests. Expected: PASS.

### 4. Docs: skill, snippet, README

- [ ] **Step 4a: Skill**

In [`src/bot_todo/skill_assets/todo/SKILL.md`](../../src/bot_todo/skill_assets/todo/SKILL.md):

- Vocabulary: **Review** — Task State for finished work awaiting validation; not a Claim. **Closed task** stays completed/cancelled only.
- Workflow: `review T001` when validation is wanted; `reopen T001` to return to open; `complete`/`cancel` from open or review. Format 1 repositories must `migrate` before any mutation.
- Examples (all `--json`):

```bash
bot-todo --json --root <repo> migrate
bot-todo --json --root <repo> review T001
bot-todo --json --root <repo> reopen T001
```

- `list` includes Review; `critical` / `actionable` do not. Review does not satisfy blockers.
- Add `review`, `reopen`, and `migrate` to the “mutations follow the same shape” set.

[`tests/test_skill_guidance.py`](../../tests/test_skill_guidance.py) already requires `--json` on every fenced `bot-todo` line. Keep that. Add an assertion that the skill mentions ``review`` and ``migrate``.

- [ ] **Step 4b: Snippet (optional one sentence)**

If you mention Review in the skill’s agent-facing workflow, add one sentence to [`src/bot_todo/skill_assets/task_management.md`](../../src/bot_todo/skill_assets/task_management.md) such as: “When work is finished but still needs validation, move the task to review before completing it.” Update `EXPECTED` in [`tests/test_task_management_snippet.py`](../../tests/test_task_management_snippet.py). Do not write consuming `AGENTS.md` files (ADR 0005).

- [ ] **Step 4c: README**

Command table: `list` open and review; add `review TASK_ID`, `reopen TASK_ID`, `migrate`. `complete`/`cancel` from open or review. `edit` open or review. `claim` open only.

JSON examples: `"schema_version": 2`. Mention `reviewed_on` on the task object. Note format 2 / `migrate`.

### 5. Quality gate

- [ ] `uv run ruff check` on touched Python files
- [ ] `uv run mypy` on touched Python files
- [ ] `make napoleon-gate`
- [ ] `make pytest ARGS="tests/test_cli.py tests/test_repository.py tests/test_skill_guidance.py tests/test_task_management_snippet.py --no-cov"` then `make pytest`

Fix everything those runs report before claiming T011 complete.
