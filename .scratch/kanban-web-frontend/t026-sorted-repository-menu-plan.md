# T026 Sorted Repository Menu

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (one small task) with superpowers:test-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Kanban Board's repository dropdown lists `All`, then the configured Repository Entries sorted by Repository Name (case-insensitively), then `Current` when it's shown. Tabler dividers separate the groups.

**Architecture:** This is a presentation-only change to `KanbanWebApp._render_repository_menu` in `src/bot_todo/web.py`. The Repository Collection, Aggregate Queries, the All board, and `repos list` all keep configuration order.

**Tech Stack:** `KanbanWebApp`, Tabler 1.4.0 / Bootstrap 5 `<div class="dropdown-divider"></div>`, `unittest` in `tests/test_web.py`.

Builds on T025 (branch `t026-sorted-repository-menu` was cut from `t025-per-request-collection`), so the menu reads `selection.collection`, the per-request snapshot.

**Locked decisions (grilled 2026-11-05; critique folded in the same day):**

- Menu layout: `All | divider | sorted names | divider | Current`.
- A divider appears only *between* non-empty groups. There's never a leading, trailing, or doubled divider:
  - empty collection, no Current → `All`
  - empty collection, Current → `All | divider | Current`
  - names, no Current → `All | divider | names` (the ordinary case: launch path matches an entry)
- Sort key: `entry.name.casefold()`. `NAME_RE` already forces lowercase, so today this is the same as a plain sort. Casefold keeps the acceptance wording true if the name rule is ever relaxed.
- Scope: the dropdown only. The Repository Collection stays "ordered" (CONTEXT.md), and ADR 0004 (human `--all list` grouping) relies on configuration order.
- The menu contract lives in `.scratch/kanban-web-frontend/spec.md` (header paragraph, ~line 82), which currently says "configuration order". Update it in the same change so a later edit doesn't "fix" the menu back.
- No ADR (cheap to reverse, not surprising) and no `CONTEXT.md` change (no new domain term).

## Task 1: Sort and divide the repository menu

**Files:**
- Modify: `src/bot_todo/web.py` (`_render_repository_menu`, ~line 1137)
- Modify: `.scratch/kanban-web-frontend/spec.md` (repository dropdown paragraph, ~line 82)
- Test: `tests/test_web.py` (`KanbanWebTests`, next to `test_repository_menu_uses_configured_name_and_all_links`, ~line 157)

- [ ] **Step 1: Write the failing tests**

Add one assertion helper and three tests to `KanbanWebTests`. The helper slices the dropdown menu out of the page, requires the markers to appear in order, and requires the divider count to match exactly. That makes a misplaced, leading, trailing, or doubled divider fail.

Test-fixture rules:
- Render only selections whose store is `self.store` (a named launch entry, or Current). Rendering All opens every configured repo (`board_version`, `_collection_columns`), so it would hit sibling paths that don't exist. Entry paths in the menu are never opened otherwise.
- Paths run in the *opposite* order to the names, and configuration order differs from both. A path sort or a configuration-order menu then fails.

```python
    DIVIDER = '<div class="dropdown-divider"></div>'

    def assert_menu_order(self, body: str, *markers: str) -> None:
        """Assert the dropdown menu lists ``markers`` in order with exact dividers.

        Args:
            body: Rendered board page.
            *markers: Expected substrings in menu order, including dividers.
        """
        start = body.index('<div class="dropdown-menu">')
        menu = body[start : body.index("</div></div>", start)]
        position = -1
        for marker in markers:  # ValueError if missing or out of order
            position = menu.index(marker, position + 1)
        self.assertEqual(menu.count(self.DIVIDER), markers.count(self.DIVIDER))

    def test_repository_menu_sorts_names_between_all_and_current(self) -> None:
        """Catch the menu following configuration or path order, or losing dividers."""
        parent = self.root.parent
        app = KanbanWebApp(
            self.store,
            write_collection(
                self.root / "config.toml",
                RepositoryEntry("zeta", parent / "aaa"),
                RepositoryEntry("alpha", parent / "zzz"),
                RepositoryEntry("mid", parent / "mmm"),
            ),
            csrf_token="test-token",
        )
        launch = app.resolve_selection("", app.collections.load())
        assert launch is not None
        self.assertEqual(launch.key, "current")
        self.assert_menu_order(
            app.render_board(launch),
            ">All<", self.DIVIDER, ">alpha<", ">mid<", ">zeta<", self.DIVIDER, ">Current<",
        )

    def test_repository_menu_without_current_has_one_divider(self) -> None:
        """Catch a trailing divider in the ordinary configured-launch menu."""
        app = KanbanWebApp(
            self.store,
            write_collection(
                self.root / "config.toml",
                RepositoryEntry("beta", self.root.parent / "aaa"),
                RepositoryEntry("alpha", self.root),
            ),
            csrf_token="test-token",
        )
        launch = app.resolve_selection("", app.collections.load())
        assert launch is not None
        self.assertEqual(launch.key, "alpha")
        body = app.render_board(launch)
        self.assert_menu_order(body, ">All<", self.DIVIDER, ">alpha<", ">beta<")
        self.assertNotIn(">Current<", body)

    def test_repository_menu_omits_dividers_around_empty_groups(self) -> None:
        """Catch a dangling, doubled, or misplaced divider when a group is empty."""
        collections = write_collection(self.root / "config.toml")
        app = KanbanWebApp(self.store, collections, csrf_token="test-token")
        launch = app.resolve_selection("", app.collections.load())
        assert launch is not None
        self.assert_menu_order(
            app.render_board(launch), ">All<", self.DIVIDER, ">Current<"
        )
        # Regression check only: already true before this change.
        all_only = KanbanWebApp(None, collections, csrf_token="test-token")
        launch = all_only.resolve_selection("", all_only.collections.load())
        assert launch is not None
        self.assert_menu_order(all_only.render_board(launch), ">All<")
```

Run `ruff format` after pasting; the long marker lists will wrap.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `make pytest ARGS="tests/test_web.py -k repository_menu"`
Expected: the three new tests FAIL. The All-only assertion inside the third test would pass on its own (see the comment), but the `All | divider | Current` assertion before it fails first.

- [ ] **Step 3: Implement**

In `_render_repository_menu`, build three groups and join the non-empty ones with a divider:

```python
        collection = selection.collection
        divider = '<div class="dropdown-divider"></div>'
        groups = [
            [("All", self.selection_path(BoardSelection("all", None, None, collection)))],
            [
                (
                    entry.name,
                    self.selection_path(
                        BoardSelection(entry.name, entry.name, None, collection)
                    ),
                )
                for entry in sorted(collection, key=lambda e: e.name.casefold())
            ],
        ]
        launch = self.launch_selection(collection)
        if launch.key == "current":
            groups.append([("Current", self.selection_path(launch))])
        options = divider.join(
            "".join(
                f'<a class="dropdown-item" href="{html.escape(path, quote=True)}">'
                f"{html.escape(label)}</a>"
                for label, path in group
            )
            for group in groups
            if group
        )
```

The rest of the method (toggle button and wrapper) is unchanged. Update the `Returns:` docstring to: "Navbar dropdown markup listing All, configured entries sorted by Repository Name, and Current, with dividers between non-empty groups."

Then replace the menu sentence in `.scratch/kanban-web-frontend/spec.md` ("Its ordinary GET links list `All`, every Repository Entry in configuration order, and `Current` only for an unconfigured launch repository.") with:

> Its ordinary GET links list `All`, then a Tabler `dropdown-divider`, then every Repository Entry sorted by Repository Name (case-insensitively, by `name.casefold()`), then a second divider and `Current` only for an unconfigured launch repository. Dividers appear only between non-empty groups. Sorting is menu-only; the Repository Collection keeps configuration order.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `make pytest ARGS="tests/test_web.py"`
Expected: PASS, including the existing T018/T025 menu tests (their `>Current<` and `/?repo=` assertions don't depend on order).

- [ ] **Step 5: Quality gate**

Run: `ruff check src/bot_todo/web.py tests/test_web.py && ruff format --check src/bot_todo/web.py tests/test_web.py && mypy src/bot_todo/web.py tests/test_web.py && make napoleon-gate`
Expected: clean. Then run the full `make pytest`.

- [ ] **Step 6: Manual check (optional)**

`bot-todo web` with two or more configured repos, launched from an unconfigured directory: open the dropdown and confirm All, a rule, the sorted names, a rule, and Current.

- [ ] **Step 7: Commit and review**

```bash
git add src/bot_todo/web.py tests/test_web.py .scratch/kanban-web-frontend/spec.md
git commit -m "feat: sort the web board repository menu with All and Current pinned (T026)"
bot-todo --json --root . review T026
```
