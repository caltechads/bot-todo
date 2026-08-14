# Repository Collection CLI — implementation plan

Contract: [spec.md](./spec.md). Task: T007.

## Context

`config.py` only loads and validates a Repository Collection. Every change
means editing the TOML by hand. T007 adds CLI management of that file for
humans (default output) and agents (`--json`).

Starting state:

- [`src/bot_todo/config.py`](../../src/bot_todo/config.py) parses Configuration
  Schema Version 1 (`schema_version`, `[[repositories]]` with `name` and
  `path`). Missing default → empty collection. Missing explicit path →
  `config_not_found`.
- [`src/bot_todo/cli.py`](../../src/bot_todo/cli.py) `RepositorySelector.validate`
  requires `--config` to pair with `--repo` or `--all`. Commands are flat.
  `install-skill` already has its own `main()` branch.
- [`src/bot_todo/repository.py`](../../src/bot_todo/repository.py) `_write_document`
  is the atomic UTF-8 replace to reuse or extract.
- No TOML writer dependency. Do not add `tomli-w`.

## Architecture

Prefer cohesive classes over free functions:

1. **`CollectionStore`** in `config.py` (split only if that file becomes
   unwieldy). Owns the active config path, load/validate, add/remove, canonical
   emit, lock, and atomic write. Reuse `RepositoryEntry`, `RepositoryCollection`,
   and `_parse` validation. Do not fork the schema.
2. **`RepositoryCollection.resolve_path(explicit)`** so `repos path` and
   first-add share precedence without requiring the file to exist.
3. **`CollectionRunner`** in `cli.py`. Nested `repos` subparser with
   `dest="operation"`. `main()` branches here when `command == "repos"` instead
   of selecting a Task Repository.
4. **`RepositorySelector.validate`**: `repos` allows `--config` and rejects
   `--root`, `--repo`, and `--all`.

## Implementation order

### 1. Spec artifacts (this directory) and ADR

Already writing this plan and [spec.md](./spec.md). During implementation, add
[`docs/adr/0003-nest-repository-collection-commands.md`](../../docs/adr/0003-nest-repository-collection-commands.md):
nested `repos` amends issue 04’s flat command list because `add` already means
add a task, and the group noun is the Repository Collection’s entries.

No `CONTEXT.md` glossary change unless a new term actually appears. Do not
introduce “global”.

### 2. `CollectionStore` (TDD)

Tests in `tests/test_config.py` (or a sibling) using the existing temporary
directory fixture style.

Cover:

- Missing default vs missing explicit path.
- First add creates the default file and parent directories.
- Explicit missing `--config` does not create a file.
- Canonical TOML: home-relative `~/...` vs absolute, configuration order,
  string escaping.
- Name inference from lowercased basename; `--name` override; invalid basename
  requires `--name`.
- Bare-slug PATH rejected; `.`, `~`, absolute, and separator paths accepted.
- Duplicate name and duplicate resolved path → `duplicate_repository`.
- Remove by name, by `.`, and by path; name wins when both could apply.
- Invalid or unsupported existing file is not rewritten.
- Written file round-trips through `_parse`.

Then implement `CollectionStore` against those tests. Exclusive `portalocker`
lock beside the config file. Atomic replace matching `_write_document`.

### 3. CLI (`CollectionRunner`)

Nested argparse:

```text
repos = commands.add_parser("repos", ...)
ops = repos.add_subparsers(dest="operation", required=True, parser_class=_Parser)
ops.add_parser("path")
ops.add_parser("list")
add = ops.add_parser("add")
add.add_argument("path", nargs="?", default=".")
add.add_argument("--name")
remove = ops.add_parser("remove")
remove.add_argument("target")
```

JSON envelope:

```json
{"schema_version": 1, "command": "repos", "data": {
  "operation": "add",
  "config_path": "/Users/glenn/.config/bot-todo/config.toml",
  "entry": {"name": "bot-todo", "path": "/Users/glenn/Programming/workspace/bot_todo"}
}}
```

CLI tests via `tests.support.invoke`:

- `--json` envelope (`command=repos`, `operation`, `config_path`).
- `--root` / `--repo` / `--all` → usage.
- `--config` accepted.
- Human add/remove confirmations.
- Empty default `repos list` succeeds.

### 4. Docs and skill

- [`README.md`](../../README.md) configuration section: `repos` examples,
  including `repos add` from the current directory. `--config` is valid with
  `repos` as well as `--repo` / `--all`.
- [`src/bot_todo/skill_assets/todo/SKILL.md`](../../src/bot_todo/skill_assets/todo/SKILL.md):
  agent commands with `--json` for `repos path`, `repos list`, `repos add`,
  and `repos remove`.

### 5. Quality gate

On touched files, then the repo:

```bash
ruff check <touched>
mypy <touched>
make napoleon-gate
make pytest
```

## Out of scope

Rename, reorder, init-on-add, comment-preserving TOML round-trip.
