# Choose delivery phases and acceptance gates

Type: grilling
Status: resolved
Blocked by: 04, 05, 06, 07, 08, 09, 10, 11, 12, 13, 16

## Question

What are the smallest independently shippable implementation phases, their dependency order, acceptance criteria, compatibility gates, and explicit deferrals from extraction parity through aggregate queries and four-target skill installation?

## Answer

Use four cumulative implementation phases in strict dependency order. Each
phase is an internal, mergeable milestone that remains usable from source; no
phase is a separately published release or a public compatibility promise. The
first public release happens only after all four phases and the final release
gate pass.

### Gates shared by every phase

Every phase passes its cumulative functional tests, Ruff, mypy, the Napoleon
gate, and a built-wheel smoke test. The smoke test installs the wheel into a
disposable temporary virtual environment, invokes its installed `bot-todo`
executable, verifies any packaged resources introduced by that phase, and then
discards the environment. It never installs or updates a persistent system UV
tool, and it does not rely on the checkout or project virtual environment.

Task Data Format 1 compatibility is non-negotiable from Phase 1 onward:
existing valid Task Repositories retain their data and lifecycle semantics
without migration. Until the final public release, the CLI layout and wording,
JSON Schema Version 1, and Configuration Schema Version 1 remain provisional
and may change to satisfy the settled specification.

### Phase 1: Extract the single-repository core

Create the installable package and provisional human CLI around one Task
Repository. Preserve all Task Data Format 1 parsing, validation, lifecycle, and
archive behavior while replacing checkout-bound execution with the packaged
entry point. Introduce the settled shared-read/exclusive-write locking,
crash-recoverable Repository Transaction, coherent Repository Snapshot, and
unsafe-file rejection here so later phases build on the real storage boundary.

The phase passes when:

- the package builds, installs, and runs outside the checkout;
- every Task Data Format 1 lifecycle operation works without migration;
- local discovery and explicit-root operation work for one Task Repository;
- reads, mutations, locking, recovery, and unsafe-file rejection have runnable
  coverage; and
- the repository's existing task data and behavior remain compatible.

### Phase 2: Complete the public CLI contract

After Phase 1, implement the complete settled command hierarchy and
single-repository interface: local, `--root`, and `--repo` selection;
Configuration Schema Version 1 loading and validation; human rendering; JSON
Schema Version 1 success and error documents; and the settled exit statuses.

The phase passes when:

- every public command and selector accepts and rejects the documented shapes;
- single-repository human and JSON workflows pass end to end;
- configuration identity, discovery, precedence, and validation match the
  settled contract; and
- unsupported Task Data Format and Configuration Schema versions fail before
  repository access or writes as required.

### Phase 3: Add aggregate read queries

After Phase 2, add `--all` support only for `list`, `critical`, and
`actionable`. Reuse the configured Repository Collection and per-repository
snapshot boundary; do not add an aggregate mutation abstraction.

The phase passes when:

- all three aggregate queries return the settled deterministic ordering and
  repository provenance;
- duplicate repository identities, missing or invalid entries, and mixed
  repository outcomes follow the strict ordered partial-failure contract;
- snapshot behavior and exit status `3` are covered in human and JSON modes;
  and
- no command can mutate more than one Task Repository.

### Phase 4: Bundle and install the todo skill

After Phase 3, package the canonical portable `todo` skill and Codex metadata
overlay, then implement explicit single-target installation for Codex, Claude,
Cursor, and Grok. The skill is last because its instructions can describe and
exercise the complete released CLI rather than a temporary subset.

The phase passes when:

- wheel and source distribution contain exactly the canonical portable assets
  and Codex-only overlay;
- installed-resource traversal and byte-for-byte materialization work outside
  the checkout;
- dry-run, ownership manifests, deterministic reconciliation, atomic staging,
  backup retention, and forced replacement follow the settled safety contract;
  and
- installation is verified against disposable roots for all four Skill
  Targets without touching real user-level locations.

### Final release gate

After Phase 4, validate the integrated specification against both wheel and
source distribution. Run the full suite on Linux with every supported CPython
and on macOS and Windows with the minimum and current stable CPython, including
both native locking backends. Release only when the cumulative contract,
artifact, target-installation, and Task Data Format 1 compatibility checks all
pass.

### Explicit deferrals

Do not create placeholder phases for repository cloning or scanning,
cross-repository mutation, LLM behavior inside `bot-todo`, ranking heuristics,
multiple Repository Collections, task-data or configuration migration tooling,
additional schema versions, skill uninstallation, marketplace publishing,
automatic Skill Target detection, additional Skill Targets, PyPI publishing,
or release automation. Revisit one only when a concrete requirement moves it
inside a later destination.
