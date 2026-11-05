# T027 Live Repository Selector Refresh

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (one small task) with superpowers:test-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** With `bot-todo web` running, `bot-todo repos add`, `repos remove`, or a rename makes every open board reload by itself within about two seconds, so the repository selector is current. A `config.toml` rewrite that leaves Repository Names and paths unchanged reloads only an open All board, and only when it's a reorder, because All's card order follows configuration order.

**Architecture:** Two small edits in `src/bot_todo/web.py`. `KanbanWebApp.board_version` also hashes the request snapshot's sorted (name, path) pairs. `LIVE_RELOAD_SCRIPT` also reloads on a 404. Decision record: `docs/adr/0015-include-the-repository-collection-in-the-board-version-token.md` (amends ADR 0014 and ADR 0012).

**Tech Stack:** `KanbanWebApp`, `hashlib`, first-party live-reload script, `unittest` in `tests/test_web.py`.

**Locked decisions (grilled 2026-11-05; critique folded in the same day):**

- Applies to **every** selection (named, Current, All): one code path, and All also reloads on a rename.
- The token moves exactly when the page would render differently:
  - Entry pairs are hashed **sorted by Repository Name**, so a reorder leaves single-repository tokens alone (the menu is sorted per T026). Names are unique in a collection, so the name alone is a total order.
  - All's `TODO.md` parts stay in **configuration order** on purpose. All's card order follows configuration order (`_collection_columns`), so a reorder must reload All. This is today's loop, unchanged; add a comment saying the order is deliberate.
- T027's acceptance criteria were narrowed to match: a names-and-paths-unchanged rewrite causes no reload of a single-repository board.
- The token never stats or hashes `config.toml`.
- The script reloads on **404** (subject to `busy()`): a removed `?repo=<name>` tab, or `?repo=current` after the launch path is added, lands on the not-found page with its menu. That page doesn't load the script, so there's no loop. 5xx and network errors are still ignored.
- `CONTEXT.md` is unchanged (no new domain term).
- The spec drops "live configuration reload" from its Exclusions.

## Task 1: Collection-aware board version token

**Files:**
- Modify: `src/bot_todo/web.py`: `board_version` (~line 343), `LIVE_RELOAD_SCRIPT` (~line 51)
- Modify: `.scratch/kanban-web-frontend/spec.md`: live-reload paragraph (~line 112) and Exclusions (~line 131)
- Test: `tests/test_web.py`: `CollectionKanbanWebTests` (replace `test_collection_change_moves_only_the_all_token`, ~line 1780), `KanbanWebTests` (next to the `board_version` tests, ~line 1561)

- [ ] **Step 1: Write the failing tests**

In `CollectionKanbanWebTests` (All launch; `alpha.one` and `beta` configured; `write_collection` rewrites `config.toml` in place at `self.app.collections.path`):

```python
    def tokens(self) -> tuple[str, str]:
        """Return the All and alpha.one board version tokens.

        Returns:
            ``(all_token, alpha_token)``.
        """
        return (
            self.get("/board-version?repo=all")[2],
            self.get("/board-version?repo=alpha.one")[2],
        )

    def test_collection_change_moves_every_token(self) -> None:
        """Catch a single-repository token that ignores repos add."""
        before = self.tokens()
        gamma = self.alpha.parent / "gamma"
        TodoStore(gamma).initialize("Gamma")
        self.app.collections.add(str(gamma), "gamma")
        after = self.tokens()
        self.assertNotEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])

    def test_rename_moves_tokens_without_a_path_change(self) -> None:
        """Catch a token built from paths only."""
        before = self.tokens()
        write_collection(
            self.app.collections.path,
            RepositoryEntry("alpha.one", self.alpha),
            RepositoryEntry("bravo", self.beta),
        )
        after = self.tokens()
        self.assertNotEqual(before[0], after[0])
        self.assertNotEqual(before[1], after[1])

    def test_reorder_moves_only_the_all_token(self) -> None:
        """Catch a reorder reloading identical pages, or leaving All stale."""
        before = self.tokens()
        write_collection(
            self.app.collections.path,
            RepositoryEntry("beta", self.beta),
            RepositoryEntry("alpha.one", self.alpha),
        )
        after = self.tokens()
        self.assertNotEqual(before[0], after[0])
        self.assertEqual(before[1], after[1])

    def test_removed_selection_reloads_once_to_not_found(self) -> None:
        """Pin the 404 the script reloads on, and that the 404 page stops polling."""
        self.app.collections.remove("beta")
        status, _, _ = self.get("/board-version?repo=beta")
        self.assertEqual(status, 404)
        status, _, body = self.get("/?repo=beta")
        self.assertEqual(status, 404)
        self.assertIn('href="/?repo=alpha.one"', body)
        self.assertNotIn("/live-reload.js", body)
```

In `KanbanWebTests`, extend `test_live_reload_script_is_served_same_origin` with `self.assertIn("response.status === 404", body)`. JavaScript behavior is otherwise verified manually (ADR 0012).

Delete `test_collection_change_moves_only_the_all_token`: `test_collection_change_moves_every_token` replaces it.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `make pytest ARGS="tests/test_web.py -k 'token or not_found or live_reload'"`
Expected: `moves_every_token` (alpha token), `rename_moves_tokens` (both tokens), and the script assertion FAIL. `reorder_moves_only_the_all_token` and `removed_selection_reloads_once_to_not_found` already pass; they guard the deliberate ordering and the no-loop 404 against regressions.

- [ ] **Step 3: Implement**

`board_version`: hash the entries before the file parts. Update the docstring: "Fingerprint the Repository Collection and ``TODO.md`` file(s) behind one board selection." Returns: "Opaque SHA-256 hex token over the snapshot's Repository Names and paths, sorted by name, and each selected file's path, mtime, and size; a missing or unreadable file contributes a fixed sentinel."

```python
        digest = hashlib.sha256()
        # Sorted like the menu (T026): a reorder leaves single-repository pages
        # unchanged.
        for entry in sorted(selection.collection, key=lambda entry: entry.name):
            digest.update(f"entry\0{entry.name}\0{entry.path}\n".encode())
        # Configuration order on purpose: All's card order follows it (ADR 0015).
        for path in paths:
            ...  # unchanged
```

`LIVE_RELOAD_SCRIPT`: replace `if (!response.ok) return;` with:

```js
      if (response.status === 404) {
        if (!busy()) location.reload();
        return;
      }
      if (!response.ok) return;
```

Update the module comment above `LIVE_RELOAD_SCRIPT` to: "Board script that reloads once ``/board-version`` reports a new token or 404."

Spec (`.scratch/kanban-web-frontend/spec.md` live-reload paragraph): change "computed from `stat()` of the selected `TODO.md` file(s)" to "computed from the request's Repository Names and paths (sorted by name) and `stat()` of the selected `TODO.md` file(s)". After "the next idle tick reloads instead.", add: "A 404 from the version endpoint (the selection no longer resolves) also reloads, landing on the not-found page; other errors are ignored." Change "See ADR 0012." to "See ADRs 0012 and 0015." In Exclusions, delete "live configuration reload, ".

- [ ] **Step 4: Run the tests to verify they pass**

Run: `make pytest ARGS="tests/test_web.py"`
Expected: PASS, including the existing `board_version` stability, mtime/size, and All-board tests.

- [ ] **Step 5: Quality gate**

Run: `ruff check src/bot_todo/web.py tests/test_web.py && ruff format --check src/bot_todo/web.py tests/test_web.py && mypy src/bot_todo/web.py tests/test_web.py && make napoleon-gate`, then the full `make pytest`.
Expected: clean.

- [ ] **Step 6: Manual check (JavaScript)**

`bot-todo web` from a configured repo with at least two entries. In a browser:
Keep two live tabs open: a single-repository board (A) and an All board (B) with cards from two repositories in the same column (e.g. both have a Completed task).
1. Run `bot-todo repos add <dir>`: both tabs reload within ~2 s and the menu lists the new name.
2. Swap two entries' order in `config.toml` by hand: B reloads and the shared column's card order flips; A does not reload.
3. Run `bot-todo repos remove <dir>`: both tabs reload again.
4. With a modal open in A, repeat step 1: no reload until the modal closes. Then remove `<dir>` again.
5. Last, because the tab stops polling: open `?repo=<other>` in A, then `repos remove <other>`: A reloads to "Not found" with the menu and stays there.

- [ ] **Step 7: Commit and review**

```bash
git add src/bot_todo/web.py tests/test_web.py .scratch/kanban-web-frontend/spec.md
git commit -m "feat: reload open boards when the Repository Collection changes (T027)"
bot-todo --json --root . review T027
```
