# 9. Kanban task detail lives in a board modal

Status: accepted (2026-08-20)

## Context

T010 served each Task's canonical details at `GET /tasks/{task_id}`, including
Tasks that `RepositorySnapshot.find()` could still reach in the archive. The
New task flow already uses a Tabler modal on the Kanban Board. A second HTML
surface made the board feel inconsistent, and T015 makes the modal the only
detail surface.

## Decision

Render every board-visible Task's details into the `GET /` response as an
accessible Tabler modal, opened from the card title with the same dismiss and
focus attributes as New task. Remove the standalone detail page, its route,
and its render. `GET /tasks/{task_id}` returns the generic not-found page.
Archive lookup and deep links stay on CLI `show`. Lifecycle forms stay on the
cards. Editing is T016's job, not this decision.

This keeps the standard-library server from ADR 0007 and the pinned Tabler
assets from ADR 0008. Detail markup is server-rendered, not fetched, and adds
no custom JavaScript, hash routing, or Python dependency.

## Considered Options

- Keep `GET /tasks/{task_id}` as an archive or bookmark exception while the
  board uses a modal — two HTML surfaces again, and it contradicts T015.
- Fetch detail HTML or JSON when a card is opened — extra JS and a second
  request, against T015's "rendered into the board response" requirement.
- Open a modal from a URL hash — bookmarking without restoring the page, at
  the cost of custom JS and a second addressability scheme.

## Consequences

A Task that has left the recent Done cards is no longer reachable in the
browser. The Kanban Board remains a grouped-by-state view of recent work, not
a Task lookup service. T016 can add an edit form inside the same modal without
bringing the standalone page back.
