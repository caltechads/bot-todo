# 10. Edit open and review tasks in the Kanban detail modal

Status: accepted (2026-08-20)

## Context

T010 left task editing on the CLI. T015 made the board modal the only HTML
detail surface and left that modal read-only. The CLI `edit` contract is a
patch: omitted flags leave fields unchanged, and clearing needs `--simple`,
`--clear-context`, `--clear-related`, or `--clear-blockers`. A browser form
always submits every field, so the Kanban Board cannot copy that flag shape
without extra Clear checkboxes or custom JavaScript.

## Decision

Open and Review tasks are edited inside the existing board detail modal.
`POST /tasks/{task_id}/edit` maps the submitted form onto
`RepositoryTransaction.edit`. The form is a full replacement of the editable
fields (title, priority, type, tags, acceptance or simple, context, related,
blockers). Empty Context, Related, Tags, and Blockers clear those values.
Completed and cancelled tasks stay a read-only definition list; a crafted
edit POST is rejected. `GET /tasks/{task_id}` stays the generic not-found
page.

The form is server-rendered into `GET /` because the modal is already a
pre-filled form and does not need a second request. This change does not add
fetch or custom JavaScript; Tabler's modal script from ADR 0008 remains the
only client script. That is YAGNI for this UX, not a standing ban.

## Considered Options

- Restore a standalone edit page — a second HTML surface, against T015.
- Patch via explicit Clear checkboxes — extra fields, easy to miss, worse
  than covering the same fields the add form already uses.
- Fetch the form or toggle it with custom JS — extra request and script for
  a UX that already fits in the `GET /` response.

## Consequences

Board edits and CLI edits share one mutation path but not one request shape.
A future reader who expects empty inputs to mean "leave unchanged" will be
wrong on the Kanban Board. Format 1 boards remain mutation-free. Claims stay
CLI-only.
