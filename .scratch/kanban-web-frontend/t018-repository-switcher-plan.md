# Repository-switching Kanban Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let one running Kanban Board switch among `All`, every configured Repository Entry, and an unconfigured launch repository while keeping All read-only and single-repository mutations unchanged.

**Architecture:** Keep the standard-library loopback server from ADR 0007. `KanbanWebApp` owns an immutable Repository Collection and launch repository; each HTTP request resolves its `repo` query into an immutable `BoardSelection`, so the threaded server never changes shared selection state. The web layer performs its own strict four-state collection projection because the CLI `AggregateRunner` has a different active-only output contract.

**Tech Stack:** Python 3.11+, `argparse`, `dataclasses`, `http.server`, `urllib.parse`, existing `RepositoryCollection`, `TodoStore`, and Tabler 1.4.0 / Tabler Icons 3.46.0 assets.

**Spec:** `.scratch/kanban-web-frontend/spec.md`

**ADR:** `docs/adr/0011-keep-collection-kanban-selection-request-scoped-and-read-only.md`

## Global Constraints

- Keep the server bound only to `127.0.0.1`; do not add authentication, another bind address, a Python dependency, packaged static assets, or a client-side router.
- Load the Repository Collection once before the server binds. Task Repository snapshots remain fresh per request.
- Preserve `--json` rejection for `web`; permit `--all web` and permit `--config PATH` with every web launch form.
- Use `/?repo=all`, `/?repo=<Repository Name>`, and `/?repo=current`; bare `/` resolves to the launch selection.
- All shows Open, Review, recent Completed, and recent Cancelled tasks, but opens no Repository Transaction and renders no mutation control.
- All fails without partial cards when any configured repository cannot be read.
- Keep configured repository mutations on the existing `RepositoryTransaction` methods.
- Keep the existing pinned Tabler URLs, integrity values, Content Security Policy, Host check, Origin check, CSRF token, 32-field limit, and 64 KiB request limit unchanged. Resolve `repo` on POST only after those trust checks succeed.
- Follow the repository documentation contract for every non-test Python class, method, function, instance attribute, and module global.
- Do not generalize or relocate `AggregateRunner`; leave `src/bot_todo/config.py` and `src/bot_todo/repository.py` unchanged.
- Isolate `XDG_CONFIG_HOME` and pop `BOT_TODO_CONFIG` in every CLI test that actually runs `web`. After Task 1, `web` always loads a collection, so an unisolated default config makes occupied-port and dispatch tests machine-dependent.
- Treat All read-only, v1 migration read-only, and writable as three presentations. `writable=False` today is the migrate banner; do not reuse it for All.
- Catch `ValueError` from `parse_qs` (`strict_parsing=True`, `max_num_fields=1`) and treat it as a generic 404. Duplicate or malformed queries must not become 500s.

## File Map

- Modify `src/bot_todo/cli.py` — permit collection-aware web selectors, load the collection once, pass the launch store plus collection to `run_web`, and update `RepositorySelector` documentation.
- Modify `src/bot_todo/web.py` — accept the new `run_web` / `KanbanWebApp` constructor in Task 1; resolve request-local board selections, render the repository menu and strict All projection, qualify modal identity, and route mutations through the selected store in later tasks.
- Modify `tests/test_cli.py` — isolate web config, cover `--all web`, `--repo NAME web`, explicit configuration with local/root launches, missing default `--all web`, collection startup failures, and the new `run_web` contract.
- Modify `tests/test_web.py` — update the `KanbanWebApp` / `run_web` call sites in Task 1; cover menu/query behavior, All ordering/provenance/read-only behavior, collisions, strict failure, and selection-preserving mutations.
- Modify `README.md` — document the selector menu, All semantics, explicit configuration, and read-only boundary.
- Modify `src/bot_todo/skill_assets/todo/SKILL.md` — include human-only `web` in the supported `--all` command guidance without weakening the rule against aggregate mutations.
- Already updated by planning: `CONTEXT.md`, `.scratch/kanban-web-frontend/spec.md`, and ADR 0011. Do not rewrite those decisions during implementation.

`--all web` is dispatched by Task 1 but not served until Task 2. Do not smoke-test an unmocked All board until Task 2 lands. After Task 1, `bot-todo web` (one repository) and occupied-port failure must still work.

Human visual confirmation of the Tabler dropdown belongs to T018 Review after implementation. Automated loopback tests in this plan are the implementation gate.

---

### Task 1: Make CLI web dispatch collection-aware

**Files:**

- Modify: `tests/test_cli.py`
- Modify: `tests/test_web.py`
- Modify: `src/bot_todo/cli.py`
- Modify: `src/bot_todo/web.py`

**Interfaces:**

- Consumes: `RepositorySelector.collection() -> RepositoryCollection`, `RepositoryCollection.entry(name) -> RepositoryEntry`, `RepositorySelector.select(command) -> SelectedRepository`.
- Produces: `run_web(store: TodoStore | None, *, collection: RepositoryCollection, port: int, open_browser: bool) -> None`. `store is None` means the launch selection is All; a store means the application derives its configured name or `Current` identity by resolved path in Task 2.
- Produces: `KanbanWebApp(store: TodoStore | None, collection: RepositoryCollection, csrf_token: str | None = None)`. Task 1 stores both values and still renders from `self.store` when it is not `None`. Serving All is Task 2.

- [ ] **Step 1: Isolate web CLI config and replace the aggregate-rejection assertion**

`CONFIG_ENV_VAR` is already imported in `tests/test_cli.py`. Give `WebCommandTests` its own config isolation so `web` cannot read the developer's default file:

```python
class WebCommandTests(TodoCliTestCase):
    """Verify the human-only web command contract."""

    def setUp(self) -> None:
        """Create an isolated repository and an empty default configuration."""
        super().setUp()
        self._config_home = tempfile.TemporaryDirectory()
        self._config_patch = mock.patch.dict(
            os.environ,
            {"XDG_CONFIG_HOME": self._config_home.name},
            clear=False,
        )
        self._config_patch.start()
        os.environ.pop(CONFIG_ENV_VAR, None)

    def tearDown(self) -> None:
        """Restore configuration environment and remove the isolated root."""
        self._config_patch.stop()
        self._config_home.cleanup()
        super().tearDown()
```

Keep the existing JSON rejection. Replace the `--all web` rejection assertion, and add focused tests shaped as follows:

```python
    def test_web_rejects_json_mode(self) -> None:
        """Catch web accidentally entering the machine-output flow."""
        machine = invoke(
            "--json", "--root", str(self.root), "web", "--no-open"
        )

        self.assertEqual(machine.returncode, 2)
        self.assertEqual(json.loads(machine.stderr)["error"]["code"], "usage")
        self.assertIn("web does not support --json", machine.stderr)

    @mock.patch("bot_todo.cli.run_web")
    def test_all_web_passes_one_loaded_collection(self, run_web: mock.Mock) -> None:
        """Catch All being rejected or dispatched without its collection."""
        config = self.root / "config.toml"
        config.write_text(
            "schema_version = 1\n\n"
            f'[[repositories]]\nname = "demo"\npath = "{self.root}"\n',
            encoding="utf-8",
        )

        result = invoke(
            "--config", str(config), "--all", "web", "--port", "0", "--no-open"
        )

        self.assertEqual(result.returncode, 0)
        self.assertIsNone(run_web.call_args.args[0])
        collection = run_web.call_args.kwargs["collection"]
        self.assertEqual([entry.name for entry in collection], ["demo"])
        self.assertEqual(run_web.call_args.kwargs["port"], 0)
        self.assertFalse(run_web.call_args.kwargs["open_browser"])

    @mock.patch("bot_todo.cli.run_web")
    def test_all_web_with_missing_default_config_passes_an_empty_collection(
        self, run_web: mock.Mock
    ) -> None:
        """Catch --all web still requiring an explicit configuration file."""
        result = invoke("--all", "web", "--no-open")

        self.assertEqual(result.returncode, 0)
        self.assertIsNone(run_web.call_args.args[0])
        self.assertEqual(len(run_web.call_args.kwargs["collection"]), 0)

    @mock.patch("bot_todo.cli.run_web")
    def test_repo_web_passes_the_named_entry_and_collection(
        self, run_web: mock.Mock
    ) -> None:
        """Catch --repo web dropping the collection or resolving the wrong path."""
        config = self.root / "config.toml"
        config.write_text(
            "schema_version = 1\n\n"
            f'[[repositories]]\nname = "demo"\npath = "{self.root}"\n',
            encoding="utf-8",
        )

        result = invoke(
            "--config", str(config), "--repo", "demo", "web", "--no-open"
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(run_web.call_args.args[0].root, self.root)
        self.assertEqual(
            [entry.name for entry in run_web.call_args.kwargs["collection"]],
            ["demo"],
        )

    @mock.patch("bot_todo.cli.run_web")
    def test_root_web_accepts_an_explicit_menu_configuration(
        self, run_web: mock.Mock
    ) -> None:
        """Catch --config remaining coupled to --repo and --all for web."""
        config = self.root / "config.toml"
        config.write_text("schema_version = 1\n", encoding="utf-8")

        result = invoke(
            "--config", str(config), "--root", str(self.root), "web", "--no-open"
        )

        self.assertEqual(result.returncode, 0)
        self.assertEqual(run_web.call_args.args[0].root, self.root)
        self.assertEqual(len(run_web.call_args.kwargs["collection"]), 0)

    @mock.patch("bot_todo.cli.run_web")
    def test_explicit_web_configuration_fails_before_the_server_binds(
        self, run_web: mock.Mock
    ) -> None:
        """Catch malformed --config reaching run_web."""
        config = self.root / "config.toml"
        config.write_text("this is not toml = [\n", encoding="utf-8")

        result = invoke(
            "--config", str(config), "--root", str(self.root), "web", "--no-open"
        )

        self.assertEqual(result.returncode, 1)
        run_web.assert_not_called()
```

Update `test_web_selects_one_repository_and_passes_launch_options` so the kwargs assertion expects `collection` rather than `name`. With the isolated empty default config, `len(collection) == 0`.

- [ ] **Step 2: Run the focused CLI tests and verify failure**

Run:

```bash
make pytest ARGS="tests/test_cli.py::WebCommandTests -q"
```

Expected: FAIL because `--all web` and `--config --root ... web` are rejected and `run_web` still accepts `name` rather than `collection`.

- [ ] **Step 3: Implement the minimum CLI dispatch and constructor handoff**

Keep `AGGREGATE_COMMANDS` query-only. In `RepositorySelector.validate`, allow `web` through both the `--config` selector rule and the `--all` rule without adding it to `AggregateRunner`'s dispatch set:

```python
        if (
            self.config is not None
            and self.repo is None
            and not self.aggregate
            and command != "web"
        ):
            raise TodoError("--config requires --repo or --all", "usage")
        if self.aggregate and command != "web" and command not in AGGREGATE_COMMANDS:
            raise TodoError(f"--all does not support {command}", "usage")
```

Update the `RepositorySelector` class docstring. It currently says configuration is loaded only for `--repo` and `--all`. Web now loads the collection for every launch form; `--root` and local discovery still report no Repository Name of their own.

In the `web` branch of `main`, load exactly one collection, derive the launch store without calling `selector.collection()` again, and call the new interface:

```python
        elif arguments.command == "web":
            collection = selector.collection()
            if arguments.all:
                store = None
            elif arguments.repo is not None:
                store = TodoStore(collection.entry(arguments.repo).path)
            else:
                store = selector.select(arguments.command).store
            run_web(
                store,
                collection=collection,
                port=arguments.port,
                open_browser=not arguments.no_open,
            )
            return 0
```

Do not change non-web selector behavior.

Import `RepositoryCollection` in `src/bot_todo/web.py`. Change `KanbanWebApp.__init__` to `(store, collection, csrf_token=None)`, store `self.collection`, and keep rendering from `self.store` when it is not `None`. Remove the `name` argument. Change `run_web` to the Task 1 signature; construct `KanbanWebApp(store, collection)` and keep printing `app.origin` without a query. `store is None` is accepted at the boundary and unused until Task 2.

In `tests/test_web.py`, import `RepositoryCollection` from `bot_todo.config` and update the two call sites:

```python
        self.app = KanbanWebApp(
            self.store,
            RepositoryCollection(()),
            csrf_token="test-token",
        )
```

```python
            run_web(
                self.store,
                collection=RepositoryCollection(()),
                port=0,
                open_browser=True,
            )
```

Leave the `test_run_web_prints_and_opens_the_actual_bound_url` URL assertion as `Kanban Board: http://127.0.0.1:<port>` until Task 2.

- [ ] **Step 4: Run CLI selection regression tests and existing board tests**

Run:

```bash
make pytest ARGS="tests/test_cli.py::WebCommandTests tests/test_cli.py::ConfiguredSelectionTests tests/test_cli.py::AggregateSelectorTests tests/test_web.py::KanbanWebTests -q"
```

Expected: PASS. Occupied-port and GET/POST board tests must pass because they now call the new constructor and `run_web` keyword. If the aggregate selector class has a different current name, use `rg -n "class .*Aggregate.*Selector" tests/test_cli.py` and pass that exact class to `make pytest`.

- [ ] **Step 5: Commit Task 1**

```bash
git add src/bot_todo/cli.py src/bot_todo/web.py tests/test_cli.py tests/test_web.py
git commit -m "feat: load repository collection for web"
```

---

### Task 2: Resolve request-local selections and render the menu

**Files:**

- Modify: `tests/test_web.py`
- Modify: `src/bot_todo/web.py`

**Interfaces:**

- Consumes: `RepositoryCollection`, optional launch `TodoStore`, and the raw URL query from `urlsplit(self.path).query`.
- Produces:
  - `BoardSelection(key: str, name: str | None, store: TodoStore | None)`; `store is None` only for All.
  - `KanbanWebApp.resolve_selection(query: str) -> BoardSelection | None`.
  - `KanbanWebApp.selection_path(selection: BoardSelection) -> str` returning `/?repo=<encoded key>`.
  - `KanbanWebApp.render_board(selection: BoardSelection) -> str`.

- [ ] **Step 1: Add failing selection, menu, and generic-404 tests**

Existing single-repository tests already construct an empty collection from Task 1. Add tests that build a collection with configured names, including a name containing punctuation allowed by the configuration contract:

```python
    def test_repository_menu_uses_configured_name_and_all_links(self) -> None:
        """Catch a local configured path rendered as duplicate Current."""
        collection = RepositoryCollection(
            (
                RepositoryEntry("alpha.one", self.root),
                RepositoryEntry("beta", self.root.parent / "beta"),
            )
        )
        app = KanbanWebApp(self.store, collection, csrf_token="test-token")

        self.assertEqual(app.resolve_selection("").key, "alpha.one")
        body = app.render_board(app.resolve_selection("repo=alpha.one"))
        self.assertIn("/?repo=all", body)
        self.assertIn("/?repo=alpha.one", body)
        self.assertIn("/?repo=beta", body)
        self.assertNotIn(">Current<", body)

    def test_unconfigured_launch_repository_adds_current(self) -> None:
        """Catch loss of an existing local/root web launch."""
        app = KanbanWebApp(
            self.store,
            RepositoryCollection(()),
            csrf_token="test-token",
        )

        self.assertEqual(app.resolve_selection("").key, "current")
        self.assertEqual(app.resolve_selection("repo=current").store.root, self.root)
        self.assertIsNone(app.resolve_selection("repo=missing"))
```

Import `RepositoryEntry` from `bot_todo.config`. Through the real loopback helper, add subtests proving `/?repo=missing`, `/?repo=`, `/?repo=all&repo=beta`, `/?repo`, and `/?other=beta` return the generic 404. Add a configured selection test that initializes a second repository, puts it in the collection, and proves `/?repo=beta` renders beta's task title rather than the launch repository's tasks.

- [ ] **Step 2: Run the new selection tests and verify failure**

Run:

```bash
make pytest ARGS="tests/test_web.py::KanbanWebTests::test_repository_menu_uses_configured_name_and_all_links tests/test_web.py::KanbanWebTests::test_unconfigured_launch_repository_adds_current -q"
```

Expected: FAIL because the selection methods do not exist.

- [ ] **Step 3: Add immutable selection state and exact query parsing**

Add `dataclass`, `RepositoryEntry` if needed, and `urlencode` imports. Define this value beside `KanbanWebApp` with full Napoleon documentation and `#:` field comments:

```python
@dataclass(frozen=True)
class BoardSelection:
    """Identify one request's Kanban Board selection.

    Args:
        key: Query value identifying All, Current, or a Repository Entry.
        name: Configured Repository Name, or ``None`` for All and Current.
        store: Selected Task Repository, or ``None`` for All.
    """

    #: Query value identifying the selection.
    key: str
    #: Configured Repository Name, when one entry is selected.
    name: str | None
    #: Selected Task Repository; ``None`` means All.
    store: TodoStore | None
```

Keep the Task 1 constructor `(store, collection, csrf_token=None)`. Store only immutable launch facts: collection, an optional unmatched Current store, and a default `BoardSelection`. Match configured entries by resolved `entry.path == store.root`. If `store is None`, default key is `all`. If the launch path matches one entry, default key is that Repository Name and Current does not exist. Otherwise default key is `current`.

Implement `resolve_selection` so `parse_qs` failures become `None`, not 500s:

```python
    def resolve_selection(self, query: str) -> BoardSelection | None:
        """Resolve one request's ``repo`` query.

        Args:
            query: Raw query string from ``urlsplit(self.path).query``.

        Returns:
            The launch selection when ``query`` is empty, a concrete selection
            for one valid ``repo`` value, or ``None`` for any invalid query.
        """
        if query == "":
            return self.default_selection
        try:
            parsed = parse_qs(
                query,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=1,
            )
        except ValueError:
            return None
        values = parsed.get("repo")
        if list(parsed.keys()) != ["repo"] or values is None or len(values) != 1:
            return None
        key = values[0]
        if key == "all":
            return BoardSelection("all", None, None)
        if key == "current":
            if self.default_selection.key != "current":
                return None
            return self.default_selection
        if not key:
            return None
        try:
            entry = self.collection.entry(key)
        except TodoError:
            return None
        return BoardSelection(entry.name, entry.name, TodoStore(entry.path))
```

Never assign a resolved store back onto the application.

Implement `selection_path` only with the standard library:

```python
    def selection_path(self, selection: BoardSelection) -> str:
        """Build the canonical path for one board selection.

        Args:
            selection: Selection to encode.

        Returns:
            Root board path with one encoded ``repo`` query.
        """
        return f"/?{urlencode({'repo': selection.key})}"
```

- [ ] **Step 4: Pass selection through rendering and GET handling**

Change `render_board`, `_page`, `render_error`, and `render_not_found` to receive the resolved selection where needed. Render a Tabler dropdown in `_page`; list All, collection entries in configuration order, and Current only when `default_selection.key == "current"`. The button text is `All`, the configured name, or `Current`. Use ordinary `<a class="dropdown-item">` links from `selection_path` plus Tabler's existing `data-bs-toggle="dropdown"`; add no custom script. Escape Repository Names in the button and items with `html.escape`. Keep the navbar brand `href="/"` as the launch selection.

In `do_GET`, split the URL once, resolve its query, return generic 404 for `None`, and call `render_board(selection)` only for path `/`. Keep every security header and host check unchanged. Host-forbidden pages may render the menu from `default_selection`.

Do not change form `action` attributes or POST redirects in this task. Existing mutation tests still assert `action="/tasks"` and `Location: /` until Task 4.

- [ ] **Step 5: Make `run_web` open the canonical initial selection URL**

Keep the Task 1 interface. Construct `KanbanWebApp(store, collection)`, bind first, then print and optionally open `app.origin + app.selection_path(app.default_selection)`. Keep `app.origin` free of a query so exact Origin checks continue to work.

Update `test_run_web_prints_and_opens_the_actual_bound_url` to expect `/?repo=current` after the port when the collection is empty:

```python
        self.assertRegex(
            url,
            r"^Kanban Board: http://127\.0\.0\.1:\d+/\?repo=current$",
        )
        open_browser.assert_called_once_with(url.removeprefix("Kanban Board: "))
```

- [ ] **Step 6: Run focused and existing GET tests**

Run:

```bash
make pytest ARGS="tests/test_web.py::KanbanWebTests -q"
```

Expected: PASS, including the generic-404 subtests. Mutation tests must still pass because form actions and redirects are unchanged. If a mutation assertion fails, revert any accidental form-action change; those belong to Task 4.

- [ ] **Step 7: Commit Task 2**

```bash
git add src/bot_todo/web.py tests/test_web.py
git commit -m "feat: switch Kanban repositories by request"
```

---

### Task 3: Render a strict, read-only All board

**Files:**

- Modify: `tests/test_web.py`
- Modify: `src/bot_todo/web.py`

**Interfaces:**

- Consumes: `BoardSelection` with `store is None`, Repository Entries in configuration order, and fresh `RepositorySnapshot` values.
- Produces:
  - `BoardTask(task: Task, repository_name: str | None)` for collision-safe rendering provenance.
  - `KanbanWebApp._collection_columns() -> tuple[tuple[str, list[BoardTask]], ...]`.
  - A `TodoError(..., "aggregate_partial_failure")` naming every failed repository when strict reading fails.

- [ ] **Step 1: Add a two-repository loopback fixture and failing All tests**

Create `CollectionKanbanWebTests` in `tests/test_web.py`. Copy the `get` / `post` / `request` helpers from `KanbanWebTests`. Setup creates `alpha.one` and `beta` under one temporary directory, initializes both with `TodoStore(...).initialize(...)`, constructs a `RepositoryCollection` in that order, starts one `KanbanWebApp(None, collection, csrf_token="test-token")`, and binds an ephemeral server.

Add one behavior test that creates colliding `T001` tasks with these exact titles and states:

```python
        with TodoStore(self.alpha).transaction() as transaction:
            transaction.add(
                title="alpha.one P2", priority="P2", task_type="chore", simple=True
            )
            completed = transaction.add(
                title="alpha.one done", priority="P2", task_type="chore", simple=True
            )
            cancelled = transaction.add(
                title="alpha.one cancelled",
                priority="P2",
                task_type="docs",
                simple=True,
            )
            transaction.close(completed.task_id, "completed")
            transaction.close(cancelled.task_id, "cancelled", "obsolete")
        with TodoStore(self.beta).transaction() as transaction:
            transaction.add(
                title="beta P0", priority="P0", task_type="bug", simple=True
            )
            reviewing = transaction.add(
                title="beta review", priority="P1", task_type="feature", simple=True
            )
            transaction.review(reviewing.task_id)
```

Assert:

```python
        status, _, body = self.get("/?repo=all")
        self.assertEqual(status, 200)
        self.assertIn("All repositories is read-only", body)
        self.assertNotIn("bot-todo migrate", body)
        self.assertNotIn(">New task<", body)
        self.assertNotIn('action="/tasks', body)
        self.assertLess(body.index("beta P0"), body.index("alpha.one P2"))
        self.assertIn("alpha.one", body)
        self.assertIn("beta", body)
        self.assertIn('id="task-', body)
```

Assert the two `T001` card `data-bs-target` values are distinct and that each target has a matching modal `id`. Use names `alpha.one` and `alpha-one` in a focused collision test so punctuation normalization cannot collapse IDs.

Add a strict-failure test by configuring one initialized repository plus one missing path. Assert status 500, both the failed Repository Name and `repository_not_found` appear, the menu still contains the healthy repository link, and no healthy task title appears.

Add an empty-collection test asserting All returns 200 with four empty columns and no Current choice when launched with `store=None`.

- [ ] **Step 2: Run All tests and verify failure**

Run:

```bash
make pytest ARGS="tests/test_web.py::CollectionKanbanWebTests -q"
```

Expected: FAIL because All has no collection projection or provenance rendering.

- [ ] **Step 3: Add the minimal board row value and strict reader**

Define `BoardTask` with a documented class contract and `#:` field comments:

```python
@dataclass(frozen=True)
class BoardTask:
    """Pair a board-visible Task with optional Repository Name provenance.

    Args:
        task: Task rendered on the board.
        repository_name: Source Repository Name on All, otherwise ``None``.
    """

    #: Task rendered on the board.
    task: Task
    #: Source Repository Name on a collection-wide board.
    repository_name: str | None = None
```

Implement `_collection_columns` directly in `KanbanWebApp`:

1. Visit every entry in configuration order and attempt `TodoStore(entry.path).snapshot()`.
2. Catch `TodoError` and `OSError` like `AggregateRunner._read`. Collect every failure before raising. Match that method's concise message shape: `<failed> of <total> repositories failed: name (code), ...` and code `aggregate_partial_failure`. Map non-`TodoError` failures to `io_error`.
3. Build Open and Review with priority outermost, repository order next, and task-file order innermost.
4. Build Completed and Cancelled with repository order outermost and each snapshot's `document.done` order innermost.

Keep this board-specific loop in `web.py`:

```python
        # ponytail: keep the four-state board projection local; extract it only
        # when a third collection consumer needs the same contract.
```

- [ ] **Step 4: Thread `BoardTask` through card, column, and modal rendering**

Change `_render_column`, `_render_card`, and `_render_task_detail_modal` to consume `BoardTask`. Single-repository rendering wraps tasks with `repository_name=None` and remains visually unchanged.

On All:

- Render a Repository Name badge on every card. Escape the name with `html.escape`.
- Include the escaped Repository Name in each modal heading.
- Do not set `writable=False` and reuse the v1 migrate branch. Keep three presentations: writable single-repository, v1 migrate banner, All banner. All hides the New task button, hides every lifecycle/edit form, and renders exactly `All repositories is read-only. Select a repository to make changes.` Even if a member repository is v1, All must not show `bot-todo migrate`.
- Preserve the six-card Completed/Cancelled disclosure after rows are combined.

Generate an internal CSS-selector-safe modal ID without lossy normalization, and use that same id for the modal `id`, the title button `data-bs-target`, and any `aria-labelledby` / `aria-controls` that point at it:

```python
    def _modal_id(self, row: BoardTask) -> str:
        """Build a collision-proof modal id for one board row.

        Args:
            row: Board row receiving the id.

        Returns:
            Existing task-only id for one repository, or a repository-qualified
            id for All.
        """
        if row.repository_name is None:
            return f"task-{row.task.task_id}-modal"
        encoded_name = row.repository_name.encode("utf-8").hex()
        return f"task-{encoded_name}-{row.task.task_id}-modal"
```

- [ ] **Step 5: Preserve the menu on collection errors**

Pass the resolved `BoardSelection` into `_send_todo_error` and `render_error`. Map `aggregate_partial_failure` to status 500 explicitly for readability; keep the existing `Repository error` title. The error body must use `str(error)`, which names repositories and codes but not partial tasks. Change the error page's `Return to Kanban Board` link from `href="/"` to `self.selection_path(selection)`.

- [ ] **Step 6: Run All and single-board rendering regressions**

Run:

```bash
make pytest ARGS="tests/test_web.py::CollectionKanbanWebTests tests/test_web.py::KanbanWebTests -q"
```

Expected: PASS except any selection-preserving POST assertions that were intentionally deferred to Task 4. `test_format_one_repository_is_browsable_but_read_only` must still show the migrate banner on a single v1 repository.

- [ ] **Step 7: Commit Task 3**

```bash
git add src/bot_todo/web.py tests/test_web.py
git commit -m "feat: render read-only collection Kanban board"
```

---

### Task 4: Preserve selection across repository mutations

**Files:**

- Modify: `tests/test_web.py`
- Modify: `src/bot_todo/web.py`

**Interfaces:**

- Consumes: one resolved `BoardSelection` on every POST.
- Produces:
  - `KanbanWebApp._writable_store(selection: BoardSelection) -> TodoStore`.
  - `add_task(selection, fields)`, `edit_task(selection, task_id, fields)`, and `transition_task(selection, task_id, fields)`.
  - `303 Location: /?repo=<encoded selection>` for successful mutations.

- [ ] **Step 1: Add failing scoped-mutation tests**

In the collection fixture, select beta and submit add/edit/transition forms with `?repo=beta`. Assert only beta changes and every successful response redirects to `/?repo=beta`:

```python
    def test_selected_repository_mutations_stay_on_that_repository(self) -> None:
        """Catch add/edit/transition writing the launch repository or losing ?repo=."""
        alpha_before = (self.alpha / "TODO.md").read_text(encoding="utf-8")

        status, headers, _ = self.post(
            "/tasks?repo=beta",
            {
                "title": "Beta only",
                "priority": "P2",
                "task_type": "chore",
                "simple": "on",
            },
        )
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/?repo=beta")
        self.assertEqual(
            (self.alpha / "TODO.md").read_text(encoding="utf-8"), alpha_before
        )
        beta_added = TodoStore(self.beta).snapshot().find("T001")
        self.assertEqual(beta_added.title, "Beta only")

        status, headers, _ = self.post(
            "/tasks/T001/transition?repo=beta",
            {"action": "review"},
        )
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/?repo=beta")
        self.assertEqual(TodoStore(self.beta).snapshot().find("T001").state, "review")

        status, headers, _ = self.post(
            "/tasks/T001/edit?repo=beta",
            {
                "title": "Beta edited",
                "priority": "P1",
                "task_type": "feature",
                "acceptance": "Edited on beta",
                "tags": "",
                "context": "",
                "related": "",
                "blocked_by": "",
            },
        )
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/?repo=beta")
        edited = TodoStore(self.beta).snapshot().find("T001")
        self.assertEqual(edited.title, "Beta edited")
        self.assertEqual(
            (self.alpha / "TODO.md").read_text(encoding="utf-8"), alpha_before
        )
```

Add a crafted All POST test and a CSRF-order test:

```python
    def test_all_rejects_a_crafted_mutation_before_opening_a_transaction(self) -> None:
        """Catch collection-wide writes through hidden controls or crafted requests."""
        alpha_before = (self.alpha / "TODO.md").read_text(encoding="utf-8")
        beta_before = (self.beta / "TODO.md").read_text(encoding="utf-8")

        status, _, body = self.post(
            "/tasks?repo=all",
            {"title": "Wrong scope", "priority": "P2", "task_type": "chore", "simple": "on"},
        )

        self.assertEqual(status, 409)
        self.assertIn("All repositories is read-only", body)
        self.assertEqual((self.alpha / "TODO.md").read_text(encoding="utf-8"), alpha_before)
        self.assertEqual((self.beta / "TODO.md").read_text(encoding="utf-8"), beta_before)

    def test_all_post_without_csrf_is_forbidden_not_conflict(self) -> None:
        """Catch All POST skipping Host/Origin/CSRF before the read-only guard."""
        status, _, body = self.request(
            "POST",
            "/tasks?repo=all",
            urlencode(
                {
                    "title": "Wrong scope",
                    "priority": "P2",
                    "task_type": "chore",
                    "simple": "on",
                }
            ),
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.app.origin,
            },
        )

        self.assertEqual(status, 403)
        self.assertIn("Forbidden", body)
```

Update existing single-repository markup assertions so add, edit, and transition form actions end in `?repo=current`, and update successful redirect assertions from `/` to `/?repo=current`.

- [ ] **Step 2: Run mutation tests and verify failure**

Run:

```bash
make pytest ARGS="tests/test_web.py -q"
```

Expected: FAIL because POST dispatch ignores repository selection and redirects to `/`.

- [ ] **Step 3: Resolve POST selection after trust checks, then guard All centrally**

In `do_POST`, keep the current order through Host, Origin, media type, body length, parse, and CSRF. After a valid CSRF token, call `resolve_selection(urlsplit(self.path).query)`. Return generic 404 for an invalid selection. Pass the selection into every mutation method.

Add one central guard:

```python
    def _writable_store(self, selection: BoardSelection) -> TodoStore:
        """Return the repository selected for a mutation.

        Args:
            selection: Request-local board selection.

        Returns:
            Selected Task Repository.

        Raises:
            TodoError: If All was selected.
        """
        if selection.store is None:
            raise TodoError("All repositories is read-only", "conflict")
        return selection.store
```

Call this before `store.transaction()` in `add_task`, `edit_task`, and `transition_task`. Do not add an All repository selector to any form.

- [ ] **Step 4: Canonicalize form actions and redirects**

Pass `BoardSelection` into `_render_add_form`, `_render_task_edit_modal`, and `_render_actions`. Append the query produced by `urlencode({"repo": selection.key})` to each action. After a successful POST:

```python
        self.send_header("Location", self.app.selection_path(selection))
```

Keep Host, Origin, CSRF, media type, body length, field count, and error mapping behavior unchanged.

- [ ] **Step 5: Run the complete web suite**

Run:

```bash
make pytest ARGS="tests/test_web.py -q"
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add src/bot_todo/web.py tests/test_web.py
git commit -m "feat: preserve Kanban repository selection"
```

---

### Task 5: Update public guidance and run the repository gate

**Files:**

- Modify: `README.md`
- Modify: `src/bot_todo/skill_assets/todo/SKILL.md`
- Verify only: `CONTEXT.md`
- Verify only: `.scratch/kanban-web-frontend/spec.md`
- Verify only: `docs/adr/0011-keep-collection-kanban-selection-request-scoped-and-read-only.md`
- Verify only: `.scratch/kanban-web-frontend/t018-repository-switcher-plan.md`

**Interfaces:**

- Consumes: the implemented command and HTTP contracts.
- Produces: public human and agent guidance matching the implementation; T018 moved to Review after every gate passes.

- [ ] **Step 1: Update README command and board guidance**

Change the command table entry to describe switching among configured repositories and All. In `Local Kanban Board`, include these examples:

```bash
bot-todo web
bot-todo --config ~/.config/bot-todo/config.toml --root ~/Programming/bot_todo web
bot-todo --repo bot-todo web
bot-todo --all web
```

Document the dropdown, `Current`, four-state All ordering, strict read failure, and the read-only banner. Replace the statement that `web` rejects `--all`; retain `--json` rejection. Replace “multi-repository boards remain CLI-only” with the precise boundary that All is visible but collection-wide mutations remain CLI-inexpressible and browser-disabled. Update the selector table so `--all` allows `list`, `critical`, `actionable`, and human-only `web`.

- [ ] **Step 2: Update the bundled todo skill without broadening mutation authority**

In `src/bot_todo/skill_assets/todo/SKILL.md`, change the supported-command sentence to:

```markdown
`list`, `critical`, `actionable`, and the human-only `web` command accept
`--all`. Aggregate task-query results name each source repository; the All
Kanban Board is read-only. No mutation accepts `--all`.
```

Do not tell agents to launch `web` as part of ordinary task mutation workflow, and retain every existing `--json` rule for commands that return data.

- [ ] **Step 3: Run focused tests, then the full test target**

Run:

```bash
make pytest ARGS="tests/test_cli.py::WebCommandTests tests/test_web.py -q"
make pytest
```

Expected: PASS.

- [ ] **Step 4: Run every required quality gate**

Run:

```bash
ruff check src/bot_todo/cli.py src/bot_todo/web.py tests/test_cli.py tests/test_web.py
mypy src/bot_todo/cli.py src/bot_todo/web.py tests/test_cli.py tests/test_web.py
make napoleon-gate
```

Expected: all commands exit 0. Fix every reported issue before proceeding.

Loopback HTTP tests are the automated UI gate. Do not treat a single screenshot as verification. Human Review of T018 confirms the Tabler dropdown opens and switches boards in a real browser.

- [ ] **Step 5: Validate the task repository and move T018 to Review**

Run:

```bash
bot-todo --json --root . validate
bot-todo --json --root . review T018
bot-todo --json --root . validate
```

Expected: both validations succeed and T018 reports `state: review`. Do not complete T018; acceptance still needs human validation.

- [ ] **Step 6: Commit Task 5**

```bash
git add README.md src/bot_todo/skill_assets/todo/SKILL.md TODO.md
git commit -m "docs: describe repository-switching Kanban board"
```

---

## Self-review

**Spec coverage:** Task 1 covers launch selectors (`--all`, `--repo`, `--root`/`--config`, missing default `--all`), explicit configuration, startup loading, JSON rejection, config isolation, and the `run_web` handoff so occupied-port tests keep passing. Task 2 covers request-local selection, Current matching, query validation including `parse_qs` `ValueError`, menu navigation, and canonical launch URLs. Task 3 covers all four states, deterministic ordering with named titles, provenance, collision-proof modal ids used by both cards and modals, three presentation modes, strict failures, empty collections, and retained menus. Task 4 covers selected-store mutations, canonical redirects, crafted All POST rejection after CSRF, and CSRF-before-All-guard ordering. Task 5 covers public guidance, full tests, repository gates, and Review handoff.

**Deliberate exclusions:** No configuration hot reload, shared aggregation subsystem, collection mutation UI, authentication, non-loopback binding, custom JavaScript, polling, full archive, new dependency, or repository-core change. Add one only when its excluded requirement becomes real. Human visual confirmation of the dropdown is T018 Review, not a separate implementation task.

**Type consistency:** `run_web` receives `TodoStore | None` plus `RepositoryCollection`; `KanbanWebApp` receives the same launch facts; `BoardSelection.store is None` uniquely means All; `BoardTask.repository_name` is present only for All; mutation methods consume `BoardSelection`; `selection_path` is the sole redirect/link encoder; `_modal_id` is the sole card/modal id encoder.
