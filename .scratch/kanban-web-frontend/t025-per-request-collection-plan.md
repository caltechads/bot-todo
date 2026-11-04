# T025 Per-Request Repository Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A running `bot-todo web` picks up `repos add` / `repos remove` on the next page load, without a restart.

**Architecture:** `KanbanWebApp` holds a `CollectionStore` instead of a loaded `RepositoryCollection`. Each request calls `CollectionStore.load()` once (shared lock), and the resulting snapshot rides on the request's `BoardSelection`, so every render step of that request sees the same snapshot. The launch `TodoStore` stays fixed; its label (named entry vs Current) is derived per request from the snapshot.

**Tech Stack:** Python stdlib `http.server`, `unittest` run via `make pytest`, existing `bot_todo.config.CollectionStore`.

**Spec:** `docs/adr/0014-read-the-repository-collection-per-web-request.md` (amends ADR 0011); acceptance in `bot-todo show T025`.

## Global Constraints

- One request uses one snapshot from start to finish; the app keeps no process-lifetime collection (ADR 0014).
- Read through `CollectionStore.load` only (it takes the shared config lock).
- `repo=current` resolves only while the launch path is unconfigured in that request's snapshot.
- Config missing (explicit), malformed, or unreadable → that request fails with the configuration error. No last-good cache.
- `/board-version` hashes the request snapshot's `TODO.md` paths; it does **not** stat `config.toml`.
- Startup behavior unchanged: `web` still loads the collection once at launch to resolve `--repo` and to fail before bind on a bad `--config`.
- Repo rules: Napoleon docstrings + `#:` attribute comments; `ruff`, `mypy`, `make napoleon-gate`, `make pytest` must pass.

## Review Focus

1. Broken config while a board tab is open: `/board-version` must return a non-200 (the live-reload script ignores non-OK, so no reload loop). Test in Task 1.
2. POST against a board after the config breaks must fail with the config error and write nothing. Test in Task 1.
3. POST to `?repo=beta` after `beta` was removed must 404 and not mutate beta's `TODO.md`. Test in Task 1.
4. Rejections before the load (bad Origin or CSRF from a stale tab after a restart) and the config-error page must link back to bare `/`, never `/?repo=current`, even when the launch repo is configured. Test in Task 1.
5. Untrusted-host 403 pages must not read the config (a broken config must still yield 403, not 500) and must not list configured Repository Names. Test in Task 1.
6. A `repos add` holding the exclusive lock while a request loads: the request waits up to the lock timeout, then gets 409 `conflict`. Already covered by `RepositoryLock` tests; no new test.

---

### Task 1: Read the collection per request

**Files:**
- Modify: `src/bot_todo/web.py` (`BoardSelection`, `KanbanWebApp.__init__`/`_launch_selection`/`resolve_selection`/`_collection_columns`/`board_version`/`render_board`/`render_not_found`/`render_error`/`_render_repository_menu`, `KanbanRequestHandler.do_GET`/`do_POST`/`_send_todo_error`, `run_web`)
- Modify: `src/bot_todo/cli.py:1680-1693` (web dispatch)
- Test: `tests/test_web.py`, `tests/test_cli.py:587-688`

**Interfaces:**
- Produces:
  - `BoardSelection(key: str, name: str | None, store: TodoStore | None, collection: RepositoryCollection)` — new last field `collection`, `#: Repository Collection snapshot this request resolved against.`
  - `KanbanWebApp(store: TodoStore | None, collections: CollectionStore, csrf_token: str | None = None)`; attribute `collections` replaces `collection`; `default_selection` is removed.
  - `KanbanWebApp.launch_selection(collection: RepositoryCollection) -> BoardSelection` (renamed public from `_launch_selection`; same rules, result carries `collection`).
  - `KanbanWebApp.resolve_selection(query: str, collection: RepositoryCollection) -> BoardSelection | None` — empty query → `launch_selection(collection)`; `repo=all` → `BoardSelection("all", None, None, collection)`; `repo=current` → the launch selection only if its key is `"current"`; named entry looked up in `collection`. **Every** returned selection carries `collection`, and so do the path-only `BoardSelection(...)` values `_render_repository_menu` builds (pass `selection.collection`).
  - `render_not_found(selection=None)`, `render_error(title, message, selection=None)`, `_send_todo_error(error, selection=None)`, `_page(..., selection: BoardSelection | None)`: `None` now means **no snapshot** — the page renders the navbar without the repository menu, and the return link is bare `/` (which always resolves to the launch board once the config is good). Used by every rejection before the load (host, Origin, media type, body, CSRF) and by the config-error page. Never fabricate a launch selection from an empty collection: it would label a configured launch repo as Current and link to `/?repo=current`, which 404s.
  - `run_web(store, *, collections: CollectionStore, port: int, open_browser: bool)`.
  - Test helper in `tests/test_web.py`: `write_collection(path: Path, *entries: RepositoryEntry) -> CollectionStore` — writes `schema_version = 1` plus one `[[repositories]]` table per entry (quote values with `json.dumps`), returns `CollectionStore(path)`.

- [ ] **Step 1: Migrate existing web tests to the new constructor**

Replace every `KanbanWebApp(..., RepositoryCollection(...), ...)` (lines 33, 141, 158, 217, 1452, 1587, 1628, 1662) with `write_collection(<tmp>/"config.toml", *entries)`; `run_web(... collection=...)` at 1078 becomes `collections=write_collection(...)`. Direct calls at 143-174 become `app.resolve_selection(q, app.collections.load())`. Put each config file in a temp dir the test already owns. In `KanbanWebTests.setUp`, keep the store on the test — `self.collections = write_collection(self.root / "config.toml")` — and pass **that object** to `KanbanWebApp`, so tests mutate the store the running server reads.

- [ ] **Step 2: Write the failing acceptance tests** in `KanbanWebTests` against the `setUp` server and `self.collections`. Add a helper `_beta(self) -> Path` that creates `self.root / "beta"`, runs `TodoStore(beta).initialize("Beta")`, adds simple chore `"Beta only work"`, and returns the path (an uninitialized entry would fail the whole All board). `self.root` is already resolved, so `self.collections.add(str(self.root), "alpha")` matches `self.store.root`. `ADD = {"title": "Never written", "priority": "P2", "task_type": "chore", "simple": "on"}`.

```python
def test_repos_add_appears_on_next_load_without_restart(self):
    beta = self._beta()                     # server started with empty config
    _, _, before = self.get("/")
    self.assertNotIn("/?repo=beta", before)
    self.collections.add(str(beta), "beta")
    status, _, after = self.get("/")
    self.assertIn("/?repo=beta", after)
    self.assertEqual(self.get("/?repo=beta")[0], 200)
    self.assertIn("Beta only work", self.get("/?repo=all")[2])

def test_repos_remove_disappears_on_next_load(self):
    self.collections.add(str(self._beta()), "beta")
    self.assertIn("Beta only work", self.get("/?repo=all")[2])
    self.collections.remove("beta")
    self.assertNotIn("/?repo=beta", self.get("/")[2])
    self.assertEqual(self.get("/?repo=beta")[0], 404)
    self.assertNotIn("Beta only work", self.get("/?repo=all")[2])

def test_launch_repo_added_later_appears_once_by_name(self):
    self.collections.add(str(self.root), "alpha")
    body = self.get("/")[2]
    self.assertEqual(body.count("/?repo=alpha\""), 1)   # menu entry once
    self.assertNotIn(">Current<", body)
    self.assertEqual(self.get("/?repo=current")[0], 404)

def test_launch_repo_removed_stays_reachable_as_current(self):
    self.collections.add(str(self.root), "alpha")
    self.assertNotIn(">Current<", self.get("/")[2])
    self.collections.remove("alpha")
    status, _, body = self.get("/")
    self.assertEqual(status, 200)
    self.assertIn(">Current<", body)
    self.assertEqual(self.get("/?repo=current")[0], 200)
    self.assertEqual(self.get("/?repo=alpha")[0], 404)

def test_malformed_config_fails_the_request_with_the_config_error(self):
    config = self.collections.path
    before = self.store.todo_path.read_bytes()
    config.write_text("this is not toml = [\n", encoding="utf-8")
    status, _, body = self.get("/")
    self.assertEqual(status, 500)
    self.assertIn("is not valid TOML", body)
    self.assertIn('href="/"', body)                              # Review Focus 4
    self.assertNotIn("/?repo=current", body)
    self.assertNotEqual(self.get("/board-version")[0], 200)      # Review Focus 1
    status, _, body = self.post("/tasks", ADD)                   # Review Focus 2
    self.assertEqual(status, 500)
    self.assertIn("is not valid TOML", body)
    self.assertEqual(self.store.todo_path.read_bytes(), before)
    config.unlink()
    self.assertIn("configuration file not found", self.get("/")[2])
    write_collection(config)                                      # repaired
    self.assertEqual(self.get("/")[0], 200)

def test_post_to_removed_repository_is_not_found(self):          # Review Focus 3
    beta = self._beta()
    self.collections.add(str(beta), "beta")
    before = (beta / "TODO.md").read_bytes()
    self.collections.remove("beta")
    status, _, _ = self.post("/tasks?repo=beta", ADD)
    self.assertEqual(status, 404)
    self.assertEqual((beta / "TODO.md").read_bytes(), before)

def test_pre_load_rejection_links_to_bare_root(self):            # Review Focus 4
    self.collections.add(str(self.root), "alpha")
    body = urlencode({"_csrf": "wrong", **ADD})
    status, _, page = self.request("POST", "/tasks", body, {
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": self.app.origin,
    })
    self.assertEqual(status, 403)
    self.assertIn('href="/"', page)
    self.assertNotIn("/?repo=current", page)

def test_untrusted_host_never_reads_the_config(self):            # Review Focus 5
    self.collections.add(str(self._beta()), "beta")
    self.collections.path.write_text("this is not toml = [\n", encoding="utf-8")
    status, _, page = self.request("GET", "/", headers={"Host": "evil.example"})
    self.assertEqual(status, 403)
    self.assertNotIn("beta", page)
```

Use `CollectionStore.add(path: str, name: str | None)` / `.remove(name: str)` for mutations (same code path as `bot-todo repos`). In `CollectionKanbanWebTests`, add `test_collection_change_moves_only_the_all_token`: record `/board-version?repo=all` and `/board-version?repo=alpha.one`; `self.app.collections.add(str(gamma), "gamma")` with an initialized `gamma`; assert the All token changed **and** the `alpha.one` token is identical (catches `/board-version` starting to hash `config.toml`, which ADR 0014 excludes).

- [ ] **Step 3: Run tests to verify they fail**

Run: `make pytest ARGS="tests/test_web.py -q"`
Expected: new tests FAIL (menu still shows startup snapshot / malformed config still 200); migrated tests fail on the constructor signature.

- [ ] **Step 4: Implement in `src/bot_todo/web.py`**

  - `__init__` stores `self.collections`; drop `self.collection` and `self.default_selection`.
  - Every former `self.collection` read uses `selection.collection` (`_collection_columns(selection)`, `board_version`, `_render_repository_menu`); the menu adds Current when `self.launch_selection(selection.collection).key == "current"`.
  - `do_GET`: after the host check, `collection = self.app.collections.load()` inside `try/except TodoError → self._send_todo_error(error); return`, then `resolve_selection(parts.query, collection)`; on `None`, `render_not_found(self.app.launch_selection(collection))`.
  - `do_POST`: same load **after** the CSRF check, before `resolve_selection`. Rejections before that pass no selection (menu-less page, `/` return link).
  - `_page`/`render_error`: when `selection is None`, omit `_render_repository_menu` and use `/` as the return link.
  - `run_web` prints `app.selection_path(app.launch_selection(collections.load()))`.

- [ ] **Step 5: Wire the CLI** in `src/bot_todo/cli.py` web branch

Keep `collection = selector.collection()` (startup `--repo` resolution and fail-before-bind), and call `run_web(store, collections=CollectionStore(selector.explicit_path()), port=..., open_browser=...)`. Update the five `test_cli.py` web tests instead of inspecting entries. The three `--config` tests assert `run_web.call_args.kwargs["collections"].path == config.resolve()`. The two default-config tests (`test_all_web_with_missing_default_config_passes_an_empty_collection`, `test_web_selects_one_repository_and_passes_launch_options`) assert `collections.explicit is False` and `len(collections.load()) == 0`. A path check alone would pass `CollectionStore(default_path())`, which is explicit and fails every request when the default file is absent; `test_explicit_web_configuration_fails_before_the_server_binds` stays as is.

- [ ] **Step 6: Run tests to verify they pass**

Run: `make pytest`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add src/bot_todo/web.py src/bot_todo/cli.py tests/test_web.py tests/test_cli.py
git commit -m "feat: read the Repository Collection per web request (T025)"
```

### Task 2: Quality gate and hand-off

**Files:**
- Modify: `TODO.md` via CLI only

- [ ] **Step 1:** `uv run ruff check src/bot_todo/web.py src/bot_todo/cli.py tests/test_web.py tests/test_cli.py` → no findings.
- [ ] **Step 2:** `uv run mypy src/bot_todo/web.py src/bot_todo/cli.py` → `Success`.
- [ ] **Step 3:** `make napoleon-gate` → no new violations (watch the new `BoardSelection.collection` `#:` comment and the renamed `launch_selection` docstring).
- [ ] **Step 4:** Manual smoke: `bot-todo web --no-open`, then in another shell `bot-todo repos add <dir>`; reload the page and see the repo in the selector; `repos remove` it; reload; gone.
- [ ] **Step 5:** Move to review (plan link already in T025's context): `bot-todo --json --root . review T025`, then `validate`.
- [ ] **Step 6:** Commit `TODO.md` with `chore: move T025 to review`.
