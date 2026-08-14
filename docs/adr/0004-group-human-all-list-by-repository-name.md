# 4. Group human `--all list` by Repository Name

Status: accepted (2026-08-14)

## Context

An Aggregate Query is ordered by priority, then configuration order, then
task-file order. Human `--all list` used that same stream and prefixed every
line with the Repository Name (`alpha T001 P0 title`) so repository-local IDs
stayed unambiguous.

That layout fights a person scanning a collection: the eye re-reads the
repository on every line, and a repository's tasks are interleaved with other
repositories' higher-priority work. JSON consumers (agents, `--json`) still
need the Aggregate Query order so `list`, `critical`, and `actionable` share
one ranking.

## Decision

Treat human `--all list` as a grouped view of the same Aggregate Query, not a
change to the query.

- JSON `--all list`, and both formats of `critical` and `actionable`, keep
  priority-then-configuration-then-file order.
- Human `--all list` groups open tasks under a bare Repository Name header, in
  Repository Collection order. Task lines omit the name. Groups with no open
  tasks are omitted. A header is still printed when only one repository has
  open tasks.
- Inside a group, order remains P0, then P1, then P2, then task-file order.
- Human `list` lines (single-repository and `--all`) append the classifying
  type hash and ordinary Tags (`#chore #auth`). `simple` stays off the line.
  `summary_line` / `aggregate_line` stay tag-free so singular queries do not
  pick up hashes.

## Consequences

- Human `--all list` and JSON `--all list` can disagree on row order. That is
  intentional: the machine document is the Aggregate Query; the human document
  is grouped for reading.
- README must state both contracts. CONTEXT.md does not describe the grouped
  view; it remains a glossary. **Tag** is the ordinary label distinct from
  type and `simple`.
- `TaskPresenter.summary_line` cannot grow Tags, because `critical` and
  `actionable` share it.
