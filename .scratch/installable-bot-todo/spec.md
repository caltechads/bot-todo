# Installable bot-todo architecture

Status: accepted implementation handoff

## Goal

Turn this repository into a dependency-free, UV-installable `bot-todo` CLI
that preserves Task Data Format 1, reads one or many configured Task
Repositories deterministically, and safely installs the bundled `todo` skill
for Codex, Claude, Cursor, and Grok.

The first public release is the compatibility baseline for the CLI,
Configuration Schema Version 1, and JSON Schema Version 1. The current embedded
script remains the behavioral reference for Task Data Format 1, not a public
CLI contract.

## Scope boundaries

The release does not include repository cloning or scanning, aggregate
mutation, LLM behavior in the CLI, ranking heuristics, multiple Repository
Collections, migration tooling, skill uninstallation, target auto-detection,
marketplace or PyPI publishing, or release automation.

## Architecture

### Package growth by phase

Create modules only when their behavior enters a phase:

```text
src/bot_todo/
├── __init__.py
├── cli.py                    # parser, dispatch, renderers, main()
├── repository.py             # Task Data Format 1, store, lock, snapshot, transaction
├── config.py                 # added in Phase 2
└── skill_installation.py     # added in Phase 4
    
src/bot_todo/skill_assets/    # added in Phase 4
└── todo/
    ├── SKILL.md
    └── agents/openai.yaml

tests/
├── test_cli.py
├── test_repository.py
├── test_distribution.py
├── test_config.py            # added in Phase 2
└── test_skill_installation.py # added in Phase 4
```

`cli.py` owns only argument parsing, command dispatch, output rendering, and
exit-status mapping. It uses one `ArgumentParser` subclass for the root and all
subparsers, disables long-option abbreviation, conditionally disables argparse
color where supported, and converts parse failures into the shared error path.

`repository.py` retains the existing `Task`, `TodoDocument`, and `TodoStore`
concepts while adding explicit `RepositorySnapshot` and
`RepositoryTransaction` boundaries. Parser namespaces do not enter repository
operations. Do not split parsing, validation, or rendering into more modules
until a concrete implementation pressure requires it.

`config.py` owns configuration discovery, strict TOML parsing, Repository Entry
validation, and Repository Collection ordering. Aggregate query orchestration
can remain here unless it grows beyond loading repositories and merging their
snapshots.

`skill_installation.py` owns packaged-asset selection, installation
classification, manifests, staging, backups, and commit/rollback. It accesses
assets only through `importlib.resources` `Traversable` objects.

### Packaging

Use `uv_build`, a `src/bot_todo` package, `requires-python = ">=3.11"`, no
runtime dependencies, and:

```toml
[project.scripts]
bot-todo = "bot_todo.cli:main"
```

Remove `main.py` with the Phase 1 extraction. Remove the root `skills/todo/`
tree only when its portable replacement enters the package in Phase 4, so the
working skill is not deleted three phases before replacement.

## Task Repository contract

A Task Repository is the resolved directory containing one regular,
non-symlink `TODO.md` and `TODO.archive.md` pair. Separate Git worktrees are
separate Task Repositories; symlink aliases to the same resolved directory are
one identity.

Task Data Format 1 retains the existing fields, P0/P1/P2/Done order, monotonic
IDs and high-water mark, lifecycle transitions, claims, blocker rules,
cancellation reasons, and newest-20 Done/archive behavior. Existing tolerated
blank lines and noncanonical field order remain valid input. Mutations may
rewrite canonical Markdown.

### Coordination and durability

Every Task Repository uses a persistent `.bot-todo.lock`. Reads take a shared
lock; mutations and recovery take an exclusive lock. Acquisition waits at most
five seconds and then fails with `conflict` without writing.

A read validates both canonical files while holding one shared lock and returns
a coherent Repository Snapshot. An aggregate command releases one repository
lock before acquiring the next; it does not promise a global point-in-time
snapshot.

A Repository Transaction holds the exclusive lock across recovery, load,
validation, staging, and commit. It stages the complete canonical pair on the
same filesystem and durably publishes a commit marker. Before the marker, the
old pair is authoritative. After the marker, recovery completes the new pair
before any command proceeds. Malformed transaction state fails closed. The
marker and staging filenames are internal, not compatibility surfaces.

Existing canonical-file permissions are preserved. New files use normal
platform creation permissions. Canonical symlinks or special files fail as
`invalid_document`; coordination artifacts never follow pre-existing
symlinks.

## CLI contract

```text
bot-todo [--json] [--config PATH]
    [--root PATH | --repo NAME | --all]
    COMMAND [command options]
```

Global options precede the command. Long-option abbreviation and undocumented
aliases are rejected. `-h`/`--help` and `--version` always emit human text and
succeed, including when `--json` is present.

Commands are flat:

```text
init validate list show critical actionable
add edit claim release complete cancel archive
install-skill
```

Commands never prompt, page, read stdin, or emit ANSI styling. Human results go
to stdout and diagnostics to stderr. Human wording and layout are not stable.

### Repository selection

| Selector | Meaning | Allowed commands |
| --- | --- | --- |
| none | nearest ancestor Task Repository; `init` uses exact cwd | task commands |
| `--root PATH` | exact Task Repository path | task commands |
| `--repo NAME` | one configured Repository Entry | task commands |
| `--all` | complete configured Repository Collection | `list`, `critical`, `actionable` |

`--config PATH` is valid only with `--repo` or `--all`; it overrides
`BOT_TODO_CONFIG`, which overrides the platform default. `install-skill`
accepts no repository selector or configuration option.

Without a selector, non-`init` commands search the resolved current directory
and each parent for the nearest `TODO.md`, without a Git boundary. Once found,
an invalid pair fails instead of continuing upward. `init` targets the exact
selected directory, allowing intentionally nested Task Repositories.

### Queries

`list` returns all open tasks. `critical` returns the first open task even when
blocked or claimed. `actionable` returns the first open, unclaimed task whose
blockers are all completed; a cancelled blocker remains unsatisfied.

Ordering is priority P0/P1/P2, then Repository Collection order for aggregate
queries, then task-file order. There is no additional sorting. Aggregate human
rows carry Repository Name provenance; every JSON Task carries its nullable
Repository Name and absolute resolved path.

### Configuration Schema Version 1

The strict TOML shape is:

```toml
schema_version = 1

[[repositories]]
name = "bot-todo"
path = "~/Programming/bot_todo"
```

Only `schema_version` and `repositories` are valid at the top level. Each entry
has exactly `name` and `path`. Names match `[a-z0-9][a-z0-9._-]*`. Duplicate
names or resolved paths invalidate the whole configuration. Entry paths may be
absolute, `~`-relative, or config-file-relative; environment variables are not
expanded. Missing entry paths are valid configuration so `init --repo NAME`
can create them.

The default is `${XDG_CONFIG_HOME:-~/.config}/bot-todo/config.toml` on Unix and
`%APPDATA%\\bot-todo\\config.toml` on Windows. A missing default means an empty
collection. A missing explicit config is `config_not_found`; malformed or
structurally invalid configuration is `invalid_config`.

Configuration versions are closed contracts. Unsupported versions fail before
repository access or writes. Adding another supported version is additive;
removing one after 1.0 requires a package-major release. Normal commands never
migrate configuration.

## JSON and process contract

`--json` success emits exactly one UTF-8 JSON document plus newline to stdout:

```json
{"schema_version": 1, "command": "list", "data": {"tasks": []}}
```

Expected failure emits no stdout and one JSON error document to stderr:

```json
{"schema_version": 1, "error": {"code": "unknown_task", "message": "unknown task ID T999"}}
```

Task objects always include all documented keys. Optional values are `null`,
collections are arrays, dates are `YYYY-MM-DD`, paths are absolute and resolved,
and object key order is not contractual. The complete initial error-code set is:

```text
usage repository_not_found not_initialized already_initialized
invalid_document unsupported_format_version unknown_task invalid_transition
conflict io_error config_not_found invalid_config unsupported_config_version
aggregate_partial_failure
```

Version-specific error details add fields inside `error`: unsupported-version
errors include encountered and supported versions; aggregate partial failure
includes every failed repository in configuration order with name, resolved
path, underlying code, and message.

Exit statuses are `0` success (including empty queries), `1` operational,
domain, data, configuration, or filesystem failure, `2` usage failure, and `3`
aggregate partial failure. Aggregate commands inspect every configured
repository but return no task data if any repository fails.

JSON Schema Version 1 permits additive object keys and error codes but preserves
existing key meaning, type, presence, and nullability. Breaking JSON changes
after 1.0 require a schema-version increment and a package-major release.

## Skill packaging and installation

The canonical portable `SKILL.md` contains intent routing, lifecycle
invariants, validation-before/after mutation guidance, merge-collision repair,
and representative `bot-todo` commands. It contains no scripts, duplicated CLI,
generated references, exhaustive argument catalog, or rendered install paths.

Codex receives `SKILL.md` plus `agents/openai.yaml`; Claude, Cursor, and Grok
receive only `SKILL.md`. Assets are traversed and copied byte-for-byte through
`importlib.resources.files("bot_todo")`.

```text
bot-todo [--json] install-skill --target {codex,claude,cursor,grok}
    [--destination PATH] [--dry-run] [--force]
```

Exactly one target is required. Defaults are `~/.agents/skills`,
`~/.claude/skills`, `~/.cursor/skills`, and `~/.grok/skills`; an explicit
destination replaces the Skill Root. The final path is always `<root>/todo`.

A Managed Skill Installation has `.bot-todo-install.json` with manifest schema
1, target, informational package version, and SHA-256 for every managed asset.
Classification produces exactly one action: `install`, `adopt`, `update`,
`noop`, or forced `replace`. Unknown, modified, malformed, target-mismatched,
symlinked, special, or extra content is a conflict unless `--force` permits a
backup-preserving replacement.

The installer fully materializes and validates a unique sibling staging tree
before commit. Ordinary updates use a private rollback sibling. Forced
replacement moves the old entry itself to a retained timestamped
`todo.backup-*` sibling and reports that path. Handled commit failure restores
the prior entry. `--dry-run` performs classification and validation without any
filesystem mutation.

The installer guarantees filesystem state only. It does not run target tools,
inspect sessions, resolve precedence, or guarantee reload.

## Runtime and platform support

Support dependency-free CPython 3.11 through each current stable release on
Linux, macOS, and Windows; WSL follows Linux and other Unix is best-effort.
Unix locking uses `fcntl.flock`; Windows uses a reserved byte with
`msvcrt.locking`. Network, FUSE, and synchronized filesystems are best-effort.

Linux CI runs every supported CPython. macOS and Windows run the minimum and
current stable versions, covering both locking adapters without a full
Cartesian matrix.

## Delivery plan

Every phase must pass its cumulative tests, Ruff, mypy, the Napoleon gate, and
a wheel smoke test installed into a disposable virtual environment outside the
checkout. Task Data Format 1 compatibility is mandatory from Phase 1 onward.

### Phase 1: Extract the single-repository core

- Create the package, console entry point, repository module, and provisional
  human CLI.
- Preserve format-1 parsing, validation, lifecycle, archive, local discovery,
  and explicit-root behavior.
- Add locking, Repository Snapshots, Repository Transactions, recovery, and
  unsafe-file rejection.
- Move the CLI tests, remove `main.py`, and leave the working root skill in
  place until Phase 4.

Gate: build/install/run outside the checkout; all format-1 workflows,
concurrency, recovery, file-safety, discovery, and compatibility checks pass.

### Phase 2: Complete the public single-repository CLI

- Add configuration, `--repo`, the full command grammar, human rendering, JSON
  Schema Version 1, complete error mapping, and settled exits.

Gate: all command/selector shapes, single-repository human and JSON workflows,
configuration precedence/validation, and unsupported-version rejection pass.

### Phase 3: Add aggregate read queries

- Add `--all` only for `list`, `critical`, and `actionable`.
- Merge per-repository snapshots in the settled deterministic order without an
  aggregate mutation abstraction.

Gate: provenance, ordering, strict partial failure, exit 3, and the prohibition
on multi-repository mutation have runnable coverage.

### Phase 4: Bundle and install the todo skill

- Move and reduce the root skill to the canonical packaged portable asset and
  Codex overlay; remove the old root skill tree in the same change.
- Add explicit single-target installation, manifests, reconciliation, staging,
  backups, dry-run, and forced replacement.

Gate: wheel and sdist assets are exact; installed-resource traversal works
outside checkout; installer behavior passes against disposable roots for all
four targets without touching user locations.

### Final release gate

Validate wheel and sdist, run the full Linux CPython range and minimum/current
macOS and Windows jobs, and release only when cumulative contracts, native lock
paths, installed assets, and Task Data Format 1 compatibility pass.

## Integrated validation decisions

The integrated review accepted these corrections:

1. Keep the working root skill through Phase 3, then move it into the package
   in Phase 4. This resolves the conflict between the Phase 1 extraction and
   the Phase 4 packaged-skill introduction.
2. Use the smallest responsibility-based module growth shown above rather than
   one large `cli.py`. The resolved snapshot, transaction,
   configuration, and installation boundaries are now concrete enough that a
   single `cli.py` would hide the architecture the specification is meant to
   communicate.
3. Leave transaction staging filenames and commit-marker encoding to
   implementation while requiring the specified crash-recovery behavior and
   runnable verification.

Everything else composes without a contradictory public or data contract.
Human output wording and class-private helper shapes remain implementation
choices verified against the stated behavior.

## Decision sources

The detailed rationale and edge cases remain in the Wayfinder tickets linked
from [the map](map.md). This specification is the implementation handoff, not a
replacement for their decision history.
