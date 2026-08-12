# Phase 4 — Bundle and install the todo skill

## Context

Phases 1–3 shipped the package (`src/bot_todo/{cli,config,repository}.py`), the
full single-repository CLI, JSON Schema 1, and aggregate `--all` reads. The
working skill still lives at the repository root (`skills/todo/SKILL.md`,
`skills/todo/agents/openai.yaml`), deliberately kept there through Phase 3.

Phase 4 is the last implementation phase: move that skill into the package as a
data asset, and add the one command that installs it — `install-skill` — for
Codex, Claude, Cursor, and Grok, without damaging user-managed files.

Verified starting state:

- `pyproject.toml` has **no** `[tool.uv.build-backend]` section; uv_build's
  default `src/bot_todo` layout carries non-Python files under the module dir.
  Phase 4 must *prove* this for wheel **and** sdist rather than assume it.
- `importlib.resources` is used **nowhere** in the codebase today (`cli.py:11`
  imports only `importlib.metadata`). `Path(__file__)` appears once, in a test.
- `cli.py` has no error-code or exit-code enum: bare strings plus
  `EXIT_CODES = {"usage": 2, "aggregate_partial_failure": 3}` defaulting to 1.
  `conflict` and `io_error` already map to exit 1 with no change.
- `OutputWriter` (cli.py:985) already splats `error.details` into the JSON error
  object and writes nothing to stdout on failure — no change needed.
- `CommandRunner.__init__` takes a `SelectedRepository`, so `install-skill`
  cannot ride it; it needs its own branch in `main()`.
- `make napoleon-gate` passes **vacuously**: `~/bin/check_napoleon_gate.py`
  defaults `--target` to `wyrdcraeft`, which does not exist here, and the
  walker silently skips missing targets. Confirmed by running it.

Sources: `spec.md` lines 240–286 (skill packaging and installation) and 326–336
(Phase 4 gate); `issues/09-define-skill-asset-model.md`;
`issues/10-define-safe-skill-installation.md`;
`issues/02-verify-uv-packaging-contracts.md`.

## Decisions confirmed with the user

1. **`SKILL.md` moves nearly as-is.** The current 83-line file already satisfies
   the portable-asset rules — no scripts, no duplicated CLI, no rendered paths,
   no package version. Only the command examples that read as an argument
   catalog get trimmed. The spec's "reduce" is mostly already done; rewriting it
   risks dropping agent-load-bearing guidance for no contract gain.
2. **Fix `make napoleon-gate` to `--target src`.** Phase 4 adds a module the
   documentation contract requires be gated; leaving the gate scanning zero
   files would make this phase's own verification claim false.
3. **No new dependency and no new exit code.** `hashlib`, `shutil`, `tempfile`,
   `json`, and `importlib.resources` cover the installer. `conflict` and
   `io_error` are already in the error-code set and already exit 1.

## Implementation

### 1. Assets — `git mv`, not copy

```text
skills/todo/SKILL.md          → src/bot_todo/skill_assets/todo/SKILL.md
skills/todo/agents/openai.yaml → src/bot_todo/skill_assets/todo/agents/openai.yaml
```

Remove the root `skills/` tree in the same change. No `__init__.py` under
`skill_assets/` — these are data, and `files("bot_todo").joinpath(...)` traverses
subdirectories regardless. `openai.yaml` contains a curly apostrophe
(`repository’s`); every copy path is bytes, never text, so it round-trips.

`SKILL.md` edits: trim the exhaustive mutation-example block to a representative
few, and keep the existing `--all`, `--json`, validate-before/after, and
merge-collision sections intact.

### 2. New module — `src/bot_todo/skill_installation.py`

Module constants (each with a `#:` doc-comment, per the Napoleon gate):

```python
SKILL_DIRECTORY = "todo"
MANIFEST_NAME = ".bot-todo-install.json"
MANIFEST_SCHEMA_VERSION = 1
TARGET_ROOTS = {
    "codex": "~/.agents/skills",
    "claude": "~/.claude/skills",
    "cursor": "~/.cursor/skills",
    "grok": "~/.grok/skills",
}
TARGET_ASSETS = {
    "codex": ("SKILL.md", "agents/openai.yaml"),
    "claude": ("SKILL.md",),
    "cursor": ("SKILL.md",),
    "grok": ("SKILL.md",),
}
```

Three cohesive types (AGENTS.md prefers classes over loose functions):

```python
@dataclass(frozen=True)
class InstallationResult:
    target: str
    skill_root: Path
    skill_path: Path
    action: str            # install | adopt | update | noop | replace
    dry_run: bool
    backup_path: Path | None

class SkillAssets:
    """Read the packaged target view as bytes through importlib.resources."""
    def view(self, target: str) -> dict[str, bytes]: ...

class SkillInstaller:
    def __init__(self, target, destination, *, dry_run, force) -> None: ...
    def run(self) -> InstallationResult: ...
```

`SkillAssets.view` reads eagerly with
`files("bot_todo").joinpath("skill_assets", "todo", *parts).read_bytes()`. The
assets are two small files, so eager bytes sidesteps the 3.11 limitation that
directory-level `as_file()` needs 3.12 — no `Traversable` directory walk, no
`Path(__file__)`, no cwd assumption.

**Root resolution.** `Path(destination or TARGET_ROOTS[target]).expanduser()`
then resolve to absolute. An existing root that is not a directory is
`io_error`. Root parents are created only during a real (non-dry-run)
installation. The final path is always `<root>/todo`.

**Classification** — exactly one action, computed from an `os.lstat` of
`<root>/todo` plus a tree scan that never follows links:

| observed | action |
| --- | --- |
| absent | `install` |
| directory, no manifest, contents byte-for-byte equal to the view, no extras | `adopt` |
| directory, valid manifest for this target, every recorded file present/regular/digest-matching, no extras, digests equal the view | `noop` |
| same but digests differ from the view | `update` |
| anything else (symlink, regular file, special entry, extra or missing or modified file, malformed manifest, unknown manifest schema, target mismatch) | `conflict` → `TodoError(..., "conflict")`, or `replace` with `--force` |

`--force` is permission to replace a conflict, not a request to replace a clean
tree: a clean tree still classifies `noop`/`update` and creates no backup.

**Commit.** Stage first, always: `tempfile.mkdtemp(prefix="todo.staging-",
dir=root)` gives a unique sibling atomically, materialize and validate the full
view inside it, then commit by rename.

- `install` — `os.rename(staging, skill_path)`; any `OSError` (a racing
  creation) is `conflict`, never an overwrite.
- `update` — `os.rename(skill_path, rollback/"todo")` into a private
  `tempfile.mkdtemp(prefix=".todo.rollback-", dir=root)`, rename staging into
  place, then `shutil.rmtree(rollback)`. A handled commit failure renames the old
  tree back.
- `replace` — the existing entry itself moves to a unique timestamped
  `todo.backup-<YYYYmmddHHMMSS>` sibling (rename never follows a symlink, so a
  symlink's target is untouched), then staging moves into place. The backup is
  retained and its absolute path is reported. Commit failure restores it.
- `adopt` — revalidate the tree, then write the manifest through a temp file in
  `skill_path` plus `os.replace`.
- `noop` — nothing.

Handled failures remove staging and private rollback paths where safe. No
persistent lock, journal, or background recovery — the spec explicitly defers
those.

**Manifest** (`.bot-todo-install.json`, never hashes itself):

```json
{"schema_version": 1, "target": "codex", "package_version": "0.1.0",
 "assets": {"SKILL.md": "<sha256 hex>", "agents/openai.yaml": "<sha256 hex>"}}
```

`package_version` is informational only; reuse `cli._package_version()`. A clean
managed tree reconciles to the running package's assets even on an apparent
downgrade — no version comparison anywhere.

**`--dry-run`** runs asset loading, root validation, and classification, then
returns before any filesystem mutation — no root parents, staging, manifest,
rollback, or backup. A conflict still fails unless `--force` is present; a
dry-run `replace` reports `backup_path: null`.

### 3. CLI wiring — `src/bot_todo/cli.py`

Grammar, in `_build_parser` after the `archive` parser (cli.py:1164):

```python
install = commands.add_parser("install-skill", help="install the bundled todo skill")
install.add_argument("--target", choices=sorted(TARGET_ROOTS), required=True)
install.add_argument("--destination", type=Path)
install.add_argument("--dry-run", action="store_true")
install.add_argument("--force", action="store_true")
```

Selector rejection, first in `RepositorySelector.validate` (cli.py:172) so it
precedes the existing `--config` rule:

```python
if command == "install-skill":
    if self.root or self.repo or self.aggregate or self.config:
        raise TodoError("install-skill accepts no repository selector", "usage")
    return
```

Dispatch, in `main` (cli.py:1197) as a third branch — `install-skill` touches no
repository, so it must not reach `selector.select()`:

```python
if arguments.command == "install-skill":
    outcome = _install_skill(arguments)
elif arguments.all:
    ...
```

`_install_skill(arguments) -> CommandOutcome` is a module-level function beside
`_package_version` / `_json_requested`: it constructs `SkillInstaller` from the
namespace, calls `run()`, and renders both halves. `data` is exactly the six
documented keys with absolute string paths:

```json
{"target": "codex", "skill_root": "...", "skill_path": ".../todo",
 "action": "install", "dry_run": false, "backup_path": null}
```

Human output is one concise line naming the action and path, plus the backup
path when one exists. No changes to `OutputWriter`, `EXIT_CODES`,
`CommandRunner`, or `AggregateRunner`.

### 4. Makefile

Change the three `napoleon-gate` recipes to pass `--target src` so the gate
actually inspects the package.

### Not in this phase

Skill uninstallation, target auto-detection, multi-target installs, reload
verification, CI workflows, marketplace/PyPI publishing, release automation, a
persistent install lock or journal. Do not scaffold for them.

## Repository bookkeeping

- Copy this plan to `.scratch/installable-bot-todo/phase-4-plan.md`, matching
  the `phase-1-plan.md` … `phase-3-plan.md` convention.
- Add the Phase 4 task to `TODO.md` **through the CLI** (it will be T005) and
  complete it at the end, per the AGENTS.md task-management contract.
- Add **Skill Manifest** and **Reconciliation Action** entries to `CONTEXT.md`;
  *Skill Target*, *Skill Root*, *Managed Skill Installation*, and *todo skill*
  are already defined there.
- No ADR: this plan makes no departure from the spec.

## Verification

Standard gate (AGENTS.md), all of which must pass:

```bash
uv sync
make pytest
ruff check src tests && ruff format --check src tests
mypy src tests            # strict for src — annotate everything new
make napoleon-gate        # now with --target src; baseline is 0 violations
```

New file **`tests/test_skill_installation.py`**, house style: `unittest.TestCase`,
no docstrings on `test_*` methods, `tempfile.TemporaryDirectory` in `setUp`,
driven through `tests/support.py`'s in-process `invoke` / `run_json`. **Every
test passes `--destination <tmpdir>`** so no user location is ever touched.

- **Target views** — the load-bearing test. `codex` installs `SKILL.md` and
  `agents/openai.yaml`; `claude`, `cursor`, and `grok` install `SKILL.md` only
  and create no `agents/` directory. Bytes equal the packaged assets exactly,
  including the curly apostrophe in `openai.yaml`.
- **Actions** — `install` on an empty root (parents created); `noop` on a second
  run; `update` after rewriting a managed file *and* its manifest digest to a
  consistent-but-stale pair; `adopt` on a hand-copied view with no manifest.
- **Conflicts**, each exit 1 with code `conflict` and an **unchanged** tree:
  extra file, missing managed file, modified managed file, malformed manifest
  JSON, `schema_version: 2`, target mismatch (install codex then run claude),
  `todo` as a symlink, `todo` as a regular file.
- **Forced replacement** — each conflict above with `--force` reports `replace`,
  retains a `todo.backup-*` sibling holding the old entry, and returns its
  absolute path. The symlink case backs up the link itself and leaves its target
  untouched. `--force` on a clean tree still yields `noop`/`update` and creates
  no backup.
- **Dry run** — `install` on an empty root creates nothing at all (the root
  itself must not appear); a conflict still exits 1; `--force` on a conflict
  reports `replace` with `backup_path: null` and mutates nothing.
- **Paths** — `--destination` replaces the root and the final path is always
  `<root>/todo`; a root that exists as a regular file is `io_error`; default
  roots resolve per target under a patched `HOME`, never the real one.
- **Usage** — missing `--target`, an unknown target, and each of `--root`,
  `--repo`, `--all`, `--config` combined with `install-skill` exit **2** with
  code `usage`.
- **JSON envelope** — success `data` has exactly the six documented keys with
  absolute path strings.

Extend **`tests/test_distribution.py`** (its `_build`/`_install`/`_run` helpers
already exist) to cover the Phase 4 gate — assets exact in *both* archives and
resource traversal working outside the checkout:

```bash
uv build --sdist --wheel --out-dir dist        # note: README.md is 0 bytes — confirm the sdist still builds
python -c "import zipfile;print(zipfile.ZipFile('dist/bot_todo-0.1.0-py3-none-any.whl').namelist())" \
  | grep -c 'bot_todo/skill_assets/todo/\(SKILL.md\|agents/openai.yaml\)'   # expect 2
tar tzf dist/bot_todo-0.1.0.tar.gz | grep skill_assets                       # expect the same two files
cd $(mktemp -d) && uv venv && uv pip install /path/to/dist/bot_todo-0.1.0-*.whl
./.venv/bin/bot-todo --json install-skill --target codex --destination ./skills
diff -r ./skills/todo <expected two-file tree>
```

If `uv build` turns out to exclude non-Python files from the sdist, add the
minimal `[tool.uv.build-backend] source-include` entry — but only after the test
proves it is needed.

Compatibility against this repository's own live files, which must still pass
unchanged and must not rewrite anything on a read:

```bash
bot-todo --root . validate && bot-todo --root . list
git diff --stat TODO.md TODO.archive.md    # must be empty
```

Phase 4 is done when the packaged asset set is exact in wheel and sdist,
traversal works from an installed wheel outside the checkout, all five
reconciliation actions plus every conflict, forced-replacement, and dry-run path
have runnable coverage against disposable roots for all four targets, the root
`skills/` tree is gone, and the Phase 1–3 contracts pass unchanged.
