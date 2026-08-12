# Wayfinder Map: Make bot-todo an installable multi-repository tool

## Destination

A build-ready architecture specification and phased implementation plan for extracting `bot-todo` into a UV-installed CLI package, retaining a thin bundled `todo` skill, adding deterministic multi-repository queries, and safely installing that skill for Codex, Claude, Cursor, and Grok.

## Notes

- This map produces decisions and a specification; it does not implement production code.
- Read `CONTEXT.md` and use the Wayfinder, Grilling, Domain Modeling, and Ponytail skills when resolving decision tickets.
- Phase 1 preserves the current task-file format, lifecycle rules, and repository data without migration; the unreleased CLI may be redesigned before its first public contract.
- The distribution and executable are `bot-todo`; the agent skill is `todo`.
- The CLI remains deterministic. The skill translates natural-language intent into CLI commands.
- Aggregate sources are configured local Task Repositories. Initial aggregate operations are read-only.
- Human-readable output remains the default; stable JSON is an additive agent interface.
- Initial configuration contains one user-level collection, with explicit CLI and environment overrides.
- Existing priorities are globally comparable. Configuration order and task-file order break ties.
- Skill installation defaults to user-level target locations and permits an explicit destination override.

## Decisions so far

- [Inventory the existing CLI compatibility contract](issues/01-inventory-existing-cli-contract.md) — The embedded stdlib CLI establishes the v1 data and lifecycle reference plus useful relocation seams, but not a released interface that constrains the new public contract.
- [Verify UV tool packaging and bundled-resource contracts](issues/02-verify-uv-packaging-contracts.md) — A standard `src/bot_todo` package can own the console entry point and one canonical in-package skill tree, accessed through `importlib.resources` and verified from built artifacts.
- [Verify agent skill installation contracts](issues/03-verify-agent-skill-installation-contracts.md) — Codex, Claude, Cursor, and Grok all accept portable filesystem skills, with native user roots and target-specific discovery, precedence, and reload behavior.
- [Define the public bot-todo CLI contract](issues/04-define-public-cli-contract.md) — Use a strict flat non-interactive CLI, explicit single/all-repository selectors, concise human output, and a versioned normalized JSON interface without pre-release compatibility baggage.
- [Choose the package and repository layout](issues/05-choose-package-and-repository-layout.md) — Use a minimal `src/bot_todo` package with one canonical packaged skill tree, root-level behavior and distribution tests, and no duplicate assets or speculative modules.
- [Choose the CLI framework](issues/06-choose-cli-framework.md) — Retain strict stdlib `argparse`, centralize human and JSON errors at `main()`, and keep parser namespaces out of Task Repository operations.
- [Define Task Repository discovery and aggregate configuration](issues/07-define-repository-configuration.md) — Use one strict ordered TOML collection, explicit config-file overrides, nearest-ancestor local discovery, and resolved filesystem paths as repository identity.
- [Define aggregate query semantics](issues/08-define-aggregate-query-semantics.md) — Open tasks share one priority-first deterministic order; critical ignores blockers and claims, actionable requires completed blockers and no claim, and aggregate output always carries repository provenance.
- [Define the bundled skill asset model](issues/09-define-skill-asset-model.md) — Package one portable script-free SKILL.md plus a Codex-only metadata overlay, materialized byte-for-byte through importlib.resources without checkout or physical-path assumptions.
- [Define safe skill installation behavior](issues/10-define-safe-skill-installation.md) — Install one explicit target through strict ownership manifests, deterministic reconciliation, dry runs, atomic staging, and backup-preserving forced replacement.
- [Define compatibility and migration policy](issues/11-define-compatibility-and-migration-policy.md) — Freeze format-1 semantics, evolve task and JSON versions independently, reject unsupported formats without writes, and require explicit recoverable future migration.
- [Define concurrency and partial-failure policy](issues/12-define-concurrency-and-failure-policy.md) — Serialize each repository, make its file pair crash-recoverable, use per-repository read snapshots, reject unsafe files, and fail aggregate queries strictly with ordered source errors.
- [Choose the supported runtime and platform matrix](issues/13-choose-runtime-and-platform-support.md) — Support dependency-free CPython 3.11+ on Linux, macOS, and Windows with native locking backends and a reduced cross-platform CI matrix.
- [Define configuration schema evolution policy](issues/16-define-configuration-schema-evolution.md) — Freeze each configuration version's closed contract, reject unsupported versions without side effects, and defer explicit recoverable migration until a new schema requires it.
- [Choose delivery phases and acceptance gates](issues/14-choose-delivery-phases-and-gates.md) — Deliver four cumulative internal phases, preserve Task Data Format 1 throughout, verify wheels in disposable environments, and reserve the full platform matrix for the final release gate.
- [Validate the integrated architecture specification](issues/15-validate-integrated-architecture-specification.md) — Accept the build-ready specification after aligning skill migration with Phase 4, adopting phased responsibility-based modules, and leaving transaction encodings internal.

## Not yet specified

## Out of scope

- Production implementation during this wayfinding effort.
- Repository cloning, remote discovery, or filesystem-wide repository scanning.
- Cross-repository bulk mutation.
- Natural-language or LLM behavior inside `bot-todo`.
- Project weighting, due dates, heuristic scoring, or multiple repository collections.
- Skill uninstallation, marketplace publishing, automatic target detection, and support for additional agent tools.
- PyPI publishing and release automation in the first delivery.
- A task-data migration or deliberate change to todo format version 1 in Phase 1.
