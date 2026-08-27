# 11. Keep collection Kanban selection request-scoped and read-only

Status: accepted (2026-08-26)

## Context

T018 makes the local Kanban Board switch among `All`, configured Repository
Entries, and an unconfigured launch repository. The existing board owns one
mutable `TodoStore`, while `ThreadingHTTPServer` serves concurrent requests.
Changing that shared store when a user switches repositories would let one
request affect another. Reusing the CLI `AggregateRunner` would also conflate
two contracts: an Aggregate Query contains active tasks only, while the Kanban
Board includes recent Completed and Cancelled tasks and supports mutations when
one Task Repository is selected.

## Decision

Load the Repository Collection once when `bot-todo web` starts and keep the
application's collection and launch selection immutable. Resolve the `repo`
query independently for every request; never switch shared selection state.
Single-repository requests continue to snapshot and mutate one `TodoStore`
through the existing repository API. The `All` selection snapshots every
configured repository sequentially, fails without partial cards when any read
fails, renders all four Task State columns with Repository Name provenance,
and exposes no mutation controls. Board-specific collection reading stays in
the web layer instead of generalizing the CLI aggregate subsystem.

## Considered Options

- Generalize and relocate `AggregateRunner` — rejected because its active-only,
  machine/human output contract does not model recent Done work or browser
  mutations.
- Mutate one application's selected `TodoStore` — rejected because selection
  would become shared request state in a threaded server.
- Add repository selection to every All-mode mutation — rejected because T018
  requires switching and provenance, not collection-wide writes, and creation
  has no unambiguous destination.

## Consequences

The board gains deterministic collection navigation without a new dependency,
client-side router, or persistence path. All remains safe and understandable,
while selecting one repository restores the existing add, edit, and lifecycle
flows. Collection configuration changes require restarting the local server.
If a third consumer later needs the board's four-state collection projection,
the duplicated read loop can then justify a shared abstraction.
