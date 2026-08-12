# Phase 1 — Extract the single-repository core

## Context

`.scratch/installable-bot-todo/spec.md` is an accepted handoff to turn this repo into a
UV-installable `bot-todo` CLI. Today the real CLI is a 1138-line script buried at
`skills/todo/scripts/todo.py`, runnable only from inside a checkout; `pyproject.toml` is a
stub with no build backend and `requires-python = ">=3.14"`; `main.py` is an unrelated
`Hello from bot-todo!` placeholder.

Phase 1 makes the tool installable and puts a real storage boundary underneath it: process
locking, an explicit Repository Snapshot / Repository Transaction split, ancestor
discovery, and unsafe-file rejection — so Phases 2–4 build on that boundary rather than on
`load` → mutate → `save`. Phase 1 does **not** add `--json`, `--repo`, `--all`,
configuration, or the skill installer.

### Decisions that change the spec

The spec was written under two constraints the user has since lifted — no dependencies, and
frozen Task Data Format 1. Three decisions follow, and they shrink Phase 1 substantially:

1. **Depend on `portalocker`.** It provides `LOCK_SH`/`LOCK_EX` with a timeout on both Unix
   and Windows (verified: `portalocker.Lock(..., flags=LOCK_SH | LOCK_NB, timeout=5.0,
   check_interval=...)` raises `AlreadyLocked` on expiry). That is exactly ticket 12's
   contract, and it deletes a hand-rolled `fcntl`/`msvcrt` adapter whose Windows shared-lock
   path could not be tested here. Everything else stays stdlib — `argparse` and `tomllib`
   are already sufficient, so no CLI framework.

2. **Decouple the archive, and drop the two-file transaction machinery with it.**
   `TODO.archive.md` becomes append-only history that is not part of the transaction and not
   cross-validated against `TODO.md`. Ticket 12's staged pair, durable commit marker and
   replay-on-next-command recovery existed *only* to keep two mutually-consistent files in
   step; with one transactional file a mutation is a single atomic `os.replace`, which is
   already crash-safe. This removes the largest and riskiest part of Phase 1 at the cost of
   one benign failure mode (see *Archive coupling* below).

3. **Keep sequential `T001` IDs.** Readability is worth the rare manual merge fix that
   `SKILL.md` already documents, and every existing task ID stays valid.

Decisions 1 and 2 contradict tickets 12 and 13, so record them in `docs/adr/` (the location
AGENTS.md names, which does not exist yet) as part of this phase.

**No migration is required.** `TODO.md`'s bytes are unchanged, so the format marker stays
`todo-format: 1`, existing pairs stay valid, and files written by the new CLI stay readable
by the old script. The only behavior removals are named under *Intentional removals*.

## Target layout

```text
pyproject.toml               # rewritten: uv_build, >=3.11, [project.scripts], portalocker
Makefile                     # add the pytest target AGENTS.md requires
docs/adr/0001-*.md           # the two deviations above
src/bot_todo/
├── __init__.py              # package docstring only, no re-exports
├── cli.py                   # parser, dispatch, rendering, exit mapping, main()
└── repository.py            # format 1, lock, archive, snapshot, transaction, store
tests/
├── __init__.py
├── test_repository.py       # lock, transaction, archive, file safety, discovery
├── test_cli.py              # ported end-to-end CLI behavior
└── test_distribution.py     # wheel smoke test in a disposable venv
skills/todo/SKILL.md         # examples retargeted to `bot-todo`
skills/todo/agents/openai.yaml
```

Deleted: `main.py`, `skills/todo/scripts/`, `skills/todo/tests/`.
Not created: `config.py`, `skill_installation.py`, `skill_assets/`, `__main__.py`,
compatibility shims, placeholder modules (ticket 05).

## Implementation

### 1. Packaging

Rewrite `pyproject.toml`: `[build-system]` with `uv_build` (pin the range `uv build`
actually generates under uv 0.12.3 — verify, do not guess), `requires-python = ">=3.11"`,
`dependencies = ["portalocker>=2.7"]` (pin what `uv add portalocker` resolves),
`[project.scripts] bot-todo = "bot_todo.cli:main"`,
`[dependency-groups] dev = ["pytest", "ruff", "mypy"]`, plus
`[tool.pytest.ini_options] testpaths = ["tests"]`, `[tool.mypy] strict`,
`[tool.ruff] target-version = "py311"`. `src/bot_todo` is uv_build's default layout, so no
package-data declaration is needed until Phase 4.

Add to `Makefile` (mirroring `~/Programming/workspace/ledger/Makefile:121`):

```make
pytest::
	@if [ -z "$(ARGS)" ]; then uv run pytest -c pyproject.toml; \
	else uv run pytest -c pyproject.toml $(ARGS); fi
```

3.11 is the floor: `tomllib` (Phase 2) and `contextlib.chdir` (tests) both land there, and
the existing code uses no 3.12+ syntax.

### 2. `repository.py` — format 1 carried over

Move `Task`, `TodoDocument`, `_parse_document`, `_parse_task_lines`,
`_split_title_and_tags`, `_validate_document`, `_validate_claim`, `_validate_date`,
`_blockers`, `_format_id`, `_normalize_tags`, `_deduplicate`, `_require_*`,
`_current_branch`, `_find_next` and every module constant across **unchanged**. This is the
compatibility surface; do not "improve" it.

Changes:

- `TodoError(ValueError)` gains `code: str` (default `"invalid_document"`), set at every
  raise site. Phase 1 codes: `usage`, `repository_not_found`, `not_initialized`,
  `already_initialized`, `invalid_document`, `unsupported_format_version`, `unknown_task`,
  `invalid_transition`, `conflict`, `io_error`. Phase 2 then adds `--json` and the config
  codes by reading a field that already exists.
- `METADATA_RE` loosens to capture the declared version, so `todo-format: 2` raises
  `unsupported_format_version` before reading task content rather than failing as generic
  malformed input.
- `TodoDocument` loses its `archived` field and `_parse_document` loses both the archive
  argument and the `# TODO Archive — {project}` header identity check.
- Drop `_optional_fields` (it exists only to read an `argparse.Namespace`).

### 3. Archive coupling

```python
class TaskArchive:            # path
    def append(self, tasks: Sequence[Task]) -> None: ...   # append + fsync, never rewrite
    def find(self, task_id: str) -> Task | None: ...       # lazy scan, for `show` only
```

- **Overflow order**: append to the archive and `fsync` it *first*, then atomically replace
  `TODO.md`. `TODO.md` is authoritative throughout. A crash in between leaves a task present
  in both Done and the archive; the next overflow appends it to the archive a second time.
  Nothing reads the archive for correctness, so this is cosmetic. Mark it:
  `# ponytail: crash between append and replace can duplicate an archive entry; dedupe on append if it ever matters.`
- **Blocker safety**: `_archive_overflow` must not archive a task still referenced in any
  open task's `Blocked by`. Such a task stays in Done past the 20-limit. This is ~3 lines and
  it is what lets blocker validation stay strictly checkable from `TODO.md` alone — every
  referenced blocker is guaranteed present, so no validation is relaxed and a cancelled
  blocker still blocks.
- **`show`** falls back to `TaskArchive.find` when the ID is absent from `TODO.md`, so
  archived tasks remain inspectable.
- The archive is never validated and never rewritten. A missing archive file is not an
  error; it is created on first overflow.

### 4. `RepositoryLock`

A thin wrapper (~20 lines) over `portalocker.Lock` on a persistent `.bot-todo.lock`:

```python
class RepositoryLock:
    def __init__(self, path: Path, timeout: float = LOCK_TIMEOUT_SECONDS) -> None: ...
    @contextmanager
    def shared(self) -> Iterator[None]: ...      # LOCK_SH | LOCK_NB
    @contextmanager
    def exclusive(self) -> Iterator[None]: ...   # LOCK_EX | LOCK_NB
```

Ensure the lock file exists first with `os.open(..., O_CREAT | O_NOFOLLOW)` so a
pre-existing symlink is never followed, then hand the path to `portalocker.Lock`. Translate
`portalocker.AlreadyLocked` into `TodoError(code="conflict")` and `LockException` into
`io_error`; no partial write ever happens on the conflict path. The 5-second timeout is
fixed with no CLI option or config knob (ticket 12); the constructor default exists so tests
can run fast.

### 5. Snapshot, transaction, store

```python
@dataclass(frozen=True)
class RepositorySnapshot:      # root, document; find(task_id), next_actionable()

class RepositoryTransaction:   # context manager: exclusive lock, load, validate
    document: TodoDocument     # commits on clean __exit__, always releases the lock
    def add(self, *, title, priority, task_type, tags, acceptance, simple,
            context, related, blocked_by) -> Task: ...
    def edit(self, task_id, *, title=None, priority=None, ...) -> Task: ...
    def claim(...) / release(...) / complete(...) / cancel(...) / archive(...)

class TodoStore:               # root, initialize(project), snapshot(), transaction()
    @classmethod
    def discover(cls, start: Path) -> TodoStore: ...
```

The lifecycle *bodies* move over verbatim from `TodoStore.add/edit/claim/release/close/
archive` (`todo.py:321-515`); only their signatures change — `argparse.Namespace` becomes
explicit keyword arguments, which the spec requires ("Parser namespaces do not enter
repository operations") and which `edit`'s existing `None`-vs-`[]` sentinel convention
survives unchanged.

**Commit** is now one operation: render `TODO.md`, re-parse and re-validate the rendered
text (keep the round-trip check at `todo.py:278-281`), append any overflow to the archive,
then write a same-directory temp file (`fsync`, `chmod` to the existing file's mode to
preserve permissions), `os.replace` it onto `TODO.md`, and `fsync` the directory. No staged
pair, no commit marker, no recovery pass. This retires
`# ponytail: exception rollback only; add a journal for crash recovery.`

`snapshot()` takes the shared lock, checks file safety, reads, parses and validates —
one coherent snapshot per read. `initialize` takes the exclusive lock and raises
`already_initialized` if `TODO.md` exists.

**Unsafe-file rejection** — `os.lstat` before reading:

| State | Code |
| --- | --- |
| Root directory missing | `repository_not_found` |
| Directory exists, no `TODO.md` | `not_initialized` |
| `TODO.md` is a symlink, directory, device, socket or FIFO | `invalid_document` |
| `TODO.archive.md` exists but is not a regular file | `invalid_document` |

bot-todo never replaces or follows such an object as canonical task data.

**Discovery** — `TodoStore.discover(start)` resolves `start` and walks it and each parent
for `TODO.md`, with no Git boundary. First hit wins: an invalid file there fails rather than
continuing upward. Nothing found → `repository_not_found`.

### 6. `cli.py`

One `ArgumentParser` subclass for the root and every subparser, with `allow_abbrev=False`
and `prog="bot-todo"` (the current script sets no `prog`, so a console script would
otherwise change the program name), `error()` routed to the shared error path, and argparse
color disabled where the attribute exists.

The command set stays the **existing** one — `init validate list show next add edit claim
release complete cancel archive` — with the same human output strings. Phase 2 owns the
settled grammar (`next` → `actionable`, plus `critical`), rendering and `--json`; do not
preempt it. Add `--version` via `importlib.metadata.version`, since the wheel smoke test
needs something to invoke and it is one line.

Selection: `--root PATH` is exact; with no selector `init` targets the exact cwd (allowing
intentional nesting) and every other command uses `TodoStore.discover(Path.cwd())`.

Exit mapping in `main()`: success 0; `TodoError` → `bot-todo: error: {message}` on stderr,
exit 1; `OSError` wrapped as `io_error`, exit 1; argparse usage failure exit 2; `-h/--help`
and `--version` exit 0. This replaces the old blanket exit 2 for domain errors and avoids
rewriting the tests twice.

### 7. Retarget the skill and repo instructions

- Delete `main.py`, `skills/todo/scripts/`, `skills/todo/tests/`.
- `skills/todo/SKILL.md`: rewrite every `python3 scripts/todo.py --root <repo> …` example as
  `bot-todo --root <repo> …`, and drop `TODO.archive.md` from the *Vocabulary* description of
  what agents may rely on. No other edits — Phase 4 does the real reduction.
- `AGENTS.md:96`: `python3 skills/todo/scripts/todo.py --root . validate` →
  `bot-todo --root . validate`.
- Write `docs/adr/0001-…` covering the portalocker dependency and the decoupled archive.
- Add a Phase 1 task to this repo's own `TODO.md` via the CLI and complete it, per
  AGENTS.md's task-management contract.

### 8. Intentional removals

State these plainly in the ADR; each has an existing test that must be deleted, not fixed:

- Duplicate IDs across `TODO.md` and the archive no longer fail validation
  (`test_todo.py` "duplicate ID across active and archive"). IDs stay unique in practice
  because `next-id` only ever moves forward.
- The archive header no longer has to match the project name.
- Done may exceed 20 entries when a closed task is still referenced as a blocker.

### 9. Tests

`tests/test_cli.py` ports the existing tests from `skills/todo/tests/test_todo.py` with
assertions intact, minus the removals above. Replace the `subprocess` + `SCRIPT` harness:
`run_cli(*args, check=True)` calls `bot_todo.cli.main([...])` in-process under
`redirect_stdout`/`redirect_stderr` and returns a small result object exposing
`returncode`/`stdout`/`stderr`, so existing `assertIn`/`assertNotEqual` assertions do not
change. Use `contextlib.chdir` for cwd-discovery cases. The two failure-injection tests
currently patching `todo_module._atomic_write` now patch the single commit write.

`tests/test_repository.py` adds Phase 1's new coverage:

- **Locking** — two `TodoStore` instances on one root conflict (`portalocker` locks are
  per-file-descriptor, so no subprocess is needed); acquisition fails as `conflict` after the
  timeout without writing.
- **Durability** — an injected failure during commit leaves `TODO.md` byte-for-byte intact;
  a failed `initialize` leaves no file behind; an interrupted overflow leaves `TODO.md`
  authoritative with the archive holding a harmless extra entry.
- **Archive** — overflow appends and never rewrites; a task still referenced as a blocker is
  retained in Done past the limit; `show` finds an archived task; a cancelled blocker still
  blocks after its blocker is archived.
- **File safety** — symlinked, directory and FIFO `TODO.md` each raise `invalid_document`;
  a symlinked repository directory resolves to one identity.
- **Permissions** — a `0600` `TODO.md` is still `0600` after a mutation.
- **Discovery** — found from a nested cwd; an invalid file at the first hit fails instead of
  continuing upward; nothing found raises `repository_not_found`; `init` targets the exact
  cwd inside an existing repository.
- **Format version** — `todo-format: 2` raises `unsupported_format_version`.
- **Exit codes** — domain error 1, unknown flag 2, rejected long-option abbreviation 2.

`tests/test_distribution.py` is the wheel smoke test, skipped when `uv` is absent:
`uv build` into a temp dir, `uv venv` + `uv pip install <wheel>` in a temp dir **outside the
checkout**, then run the installed `bot-todo` (`--version`, then `init`/`add`/`list` against
a third temp dir) and discard the environment. It never touches a persistent UV tool or the
project venv.

Tests must never touch this repo's real `TODO.md`.

## Verification

```bash
uv sync
make pytest
ruff check src tests && ruff format --check src tests
mypy src tests
make napoleon-gate            # ~/bin/check_napoleon_gate.py; aim for napoleon-gate-strict clean
```

The documentation contract applies to all new non-test code: Napoleon docstrings with only
the applicable sections, and `#:` comments on every module global, class attribute and
`__init__`-assigned instance attribute.

Compatibility, against this repo's own live files:

```bash
bot-todo --root . validate                 # must pass unchanged on the existing TODO.md
bot-todo --root . list
git diff --stat TODO.md TODO.archive.md    # a read must not rewrite either file
python3 -c "…"                             # old script's parser still accepts new output
```

End-to-end outside the checkout — the phase gate:

```bash
uv build
cd $(mktemp -d) && uv venv && uv pip install /path/to/bot_todo/dist/bot_todo-0.1.0-*.whl
./.venv/bin/bot-todo --version
mkdir demo && ./.venv/bin/bot-todo --root demo init --project Demo
./.venv/bin/bot-todo --root demo add "Try it" --type chore --simple
cd demo/nested/dir && ../../.venv/bin/bot-todo list   # ancestor discovery
```

Phase 1 is done when: the wheel installs and runs outside the checkout; every format-1
lifecycle operation works with no migration; discovery and `--root` both work; locking,
commit durability, archive decoupling and unsafe-file rejection have runnable coverage; and
this repository's existing task data still validates.

## Deferred to later phases

`--json`, `--repo`, `--all`, `--config`, `config.py`, Configuration Schema 1, the
`critical`/`actionable` rename, exit 3, aggregate queries, `skill_installation.py`,
`skill_assets/`, removing `skills/todo/`, and CI. Do not scaffold for them.
