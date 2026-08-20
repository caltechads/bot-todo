# Local Kanban Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a localhost-only Kanban Board over one Task Repository with a responsive Tabler presentation.

**Architecture:** A standard-library HTTP adapter renders semantic HTML and delegates all reads and writes to `TodoStore`. The existing CLI selects the repository and launches the blocking server; pinned Tabler assets provide the browser presentation without adding Python runtime dependencies.

**Tech Stack:** Python 3.11+, `http.server`, `html`, `urllib.parse`, existing bot-todo repository core, Tabler Core 1.4.0, and Tabler Icons 3.46.0.

**Spec:** `.scratch/kanban-web-frontend/spec.md`

## Global Constraints

- Bind only to `127.0.0.1`; do not expose a host option.
- Add no Python runtime dependencies, JSON API, template files, or packaged static assets.
- Load only the approved pinned Tabler Core and Tabler Icons assets from jsDelivr with Subresource Integrity metadata.
- Preserve the existing Task State and Repository Transaction contracts.
- Follow the repository's Napoleon documentation contract.

---

### Task 1: Web behavior

**Files:**
- Create: `src/bot_todo/web.py`
- Create: `tests/test_web.py`

**Interfaces:**
- Consumes: `TodoStore.snapshot()` and `TodoStore.transaction()`.
- Produces: `run_web(store: TodoStore, *, name: str | None, port: int, open_browser: bool) -> None`.

- [x] Write failing loopback HTTP tests for the board, details, adds, transitions, read-only Format 1, request validation, and security headers.
- [x] Run `make pytest ARGS="tests/test_web.py -q"` and confirm the missing module/behavior failures.
- [x] Implement the minimal `KanbanWebApp`, `KanbanRequestHandler`, HTML renderer, and `run_web` entry point.
- [x] Re-run the focused tests until they pass.

### Task 2: CLI integration

**Files:**
- Modify: `src/bot_todo/cli.py`
- Modify: `tests/test_cli.py`

**Interfaces:**
- Consumes: `run_web(...)` from Task 1.
- Produces: `bot-todo [selectors] web [--port PORT] [--no-open]`.

- [x] Write failing CLI tests for selector handling, port/open arguments, and `--all`/`--json` rejection.
- [x] Run the focused CLI tests and confirm the expected failures.
- [x] Add parser and dispatch support without changing existing command output.
- [x] Re-run the focused tests until they pass.

### Task 3: Documentation and release verification

**Files:**
- Modify: `README.md`
- Modify: `CONTEXT.md`
- Create: `docs/adr/0007-serve-the-local-kanban-with-the-python-standard-library.md`

- [x] Document launch behavior, supported lifecycle actions, and the localhost-only boundary.
- [x] Run Ruff and mypy on touched Python files.
- [x] Run `make napoleon-gate`, `make pytest`, and the distribution build/smoke checks.
- [x] Move T010 to Review after every gate passes.

### Task 4: Tabler presentation revision

**Files:**
- Modify: `src/bot_todo/web.py`
- Modify: `tests/test_web.py`

**Interfaces:**
- Consumes: the existing `KanbanWebApp` render and mutation methods without changing HTTP routes.
- Produces: one shared Tabler shell for every HTML response and the existing add form as a Tabler modal.

**Exact assets:**
- Tabler CSS: `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css`, integrity `sha384-kz+I4+mczbNiZfLAJMxOlJaZmnbRYhARHNkR2k6tal4gz7OL33/0puDD3SvkiNX9`.
- Tabler JS: `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js`, integrity `sha384-pku3birjgGovaJ9ngF7SaxKkF/eYUvBjiMJ+jTtWbNesIj2Rud2K63+4JD7EF4gk`.
- Tabler Icons CSS: `https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css`, integrity `sha384-ND+q1IVc0KDElX60dZaqKc7Xl9cdxd2PpU2JfVUHcurCkFVtVLFdt9vJfxtHSL3p`.
- Add `crossorigin="anonymous"` to each asset and allow only jsDelivr for remote styles, scripts, and fonts; allow `data:` images required by Tabler.

- [x] Write failing tests for exact CDN assets and SRI, CSP, the shared shell, responsive state columns and counts, six-item terminal disclosure, and complete modal fields.
- [x] Run `make pytest ARGS="tests/test_web.py -q"` and confirm the new assertions fail for missing Tabler behavior.
- [x] Implement the minimum markup and inline board-specific CSS needed to reproduce approved design Option 1 using Tabler classes and Tabler Icons.
- [x] Re-run the focused web tests until they pass without changing repository or HTTP behavior.

### Task 5: Redesign documentation and visual verification

**Files:**
- Modify: `.scratch/kanban-web-frontend/spec.md`
- Create: `.scratch/kanban-web-frontend/design-option-1.png`
- Modify: `docs/adr/0007-serve-the-local-kanban-with-the-python-standard-library.md`
- Create: `docs/adr/0008-use-pinned-tabler-assets-for-the-kanban-presentation.md`
- Create: `design-qa.md`

- [x] Preserve the approved Option 1 image beside the T010 spec and update the presentation/security decisions in the spec.
- [x] Record ADR 0008 and mark ADR 0007's presentation choice as amended without changing its standard-library server decision.
- [x] Verify the board and primary interactions at 1440x1024, 1024px, and 390px; compare the desktop implementation directly with the source image and record a passing design QA report.
- [x] Run Ruff, mypy, `make napoleon-gate`, and `make pytest`, then return T010 to Review.
