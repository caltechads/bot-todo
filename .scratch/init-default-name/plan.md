# Default init --name to the directory basename

**Task:** T008.

**Goal:** `bot-todo init` works without `--name` and writes `# TODO — <basename>` using the selected repository directory; `--name` remains an optional override.

## Settled contract

- Default name is `TodoStore.root.name` as-is (preserve case and punctuation). Do **not** reuse [`_choose_name`](../../src/bot_todo/config.py) — that lowercases and validates `NAME_RE` for Repository Collection slugs.
- The selected path already covers T008’s wording: [`RepositorySelector.select`](../../src/bot_todo/cli.py) uses `--root`, else cwd for `init`, else `--repo` entry path. `--repo init` therefore defaults to that path’s basename, not the configured slug.
- Empty/whitespace/newline names still fail through existing `_require_text(..., "project")`.
- No ADR. Historical phase specs under `.scratch/installable-bot-todo/` stay as written.

## Architecture

Keep ownership on `TodoStore`, which already knows `self.root`. CLI only stops requiring `--name` and passes `arguments.name` (possibly `None`).

In [`src/bot_todo/repository.py`](../../src/bot_todo/repository.py) `TodoStore.initialize`:

```python
def initialize(self, project: str | None = None) -> None:
    name = _require_text(
        project if project is not None else self.root.name,
        "project",
    )
```

In [`src/bot_todo/cli.py`](../../src/bot_todo/cli.py) parser (~line 1346) and `_init` (~line 497):

```python
initialize.add_argument(
    "--name",
    help="project name (default: repository directory basename)",
)
# ...
self.store.initialize(arguments.name)
```

Existing `--name` callers (tests, README examples that still want a display name) stay valid.

## Implementation order

### 1. Persist this plan and link T008

- Write the approved plan to `.scratch/init-default-name/plan.md`.
- `bot-todo --json --root . validate` then `edit T008 --context ".scratch/init-default-name/plan.md"` (keep acceptance; do not hand-edit `TODO.md`) then validate again.

### 2. Failing tests (TDD)

Add cases to [`tests/test_cli.py`](../../tests/test_cli.py) `InitializationAndIdentityTests` / `SelectionTests`, matching existing `tempfile` + `invoke` / `contextlib.chdir` style.

- `--root` without `--name` uses that directory’s basename, even when cwd differs:

```python
def test_init_defaults_name_to_root_basename(self) -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "My_App"
        root.mkdir()
        result = invoke("--root", str(root), "init")
        self.assertEqual(result.returncode, 0)
        self.assertIn("# TODO — My_App\n", (root / "TODO.md").read_text())
```

- `--name` still overrides the basename.
- No selector: `chdir` into a uniquely named empty directory and `invoke("init")`; heading is that cwd basename; `TODO.md` is created there (extends [`test_init_targets_the_exact_working_directory`](../../tests/test_cli.py)).
- Keep current tests that pass `--name` (multiline reject, already-initialized, support harness).

Optional tightening: [`tests/test_distribution.py`](../../tests/test_distribution.py) smoke `init` of a `demo` directory can drop `--name "Demo"` so the wheel path also exercises the default.

Run: `make pytest ARGS="tests/test_cli.py::InitializationAndIdentityTests::test_init_defaults_name_to_root_basename --no-cov"` — expect argparse “required” failure until the parser change.

### 3. Implementation

- `initialize.add_argument("--name", required=True)` → optional with help as above.
- `TodoStore.initialize(self, project: str | None = None)` as shown; update Napoleon `Args:` for the new default. Do not invent a helper class.

### 4. Docs

- [`README.md`](../../README.md): quick start can be `bot-todo init`; command table `init [--name NAME]`; one sentence that omitted `--name` uses the repository directory basename.
- [`src/bot_todo/skill_assets/todo/SKILL.md`](../../src/bot_todo/skill_assets/todo/SKILL.md): show `init` without `--name`, keep `--name` as the override example.

### 5. Quality gate

- `make pytest ARGS="tests/test_cli.py tests/test_distribution.py --no-cov"` (or full `make pytest` if time allows)
- `ruff` and `mypy` on `src/bot_todo/cli.py` `src/bot_todo/repository.py` and touched tests
- `make napoleon-gate`
