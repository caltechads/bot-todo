# Local Kanban Board Design

## Goal

Provide one local human with a browser view over one Task Repository without
creating a second task model or mutation path.

## Command

`bot-todo [--root PATH | --repo NAME] web [--port PORT] [--no-open]` resolves
one repository through the existing selector, binds `127.0.0.1`, prints the
actual URL, and opens it unless `--no-open` is set. The default port is 8765;
port 0 requests an ephemeral port. `web` rejects `--all` and `--json`.

## HTTP interface

- `GET /` renders the add form, Open, Review, Completed, and Cancelled
  columns, and one server-rendered Tabler detail modal per board-visible
  Task from a fresh `RepositorySnapshot`. Card titles open that modal.
- `GET /tasks/{task_id}` returns the generic not-found page. Archive lookup
  stays on CLI `show`.
- `POST /tasks` maps the full add form to `RepositoryTransaction.add()`.
- `POST /tasks/{task_id}/transition` maps `review`, `reopen`, `complete`, and
  `cancel` to the existing transaction methods. Cancel requires a reason.
- `POST /tasks/{task_id}/edit` maps the detail-modal form onto
  `RepositoryTransaction.edit()` for open and Review tasks. Empty Context,
  Related, Tags, and Blockers clear those fields. Completed and cancelled
  tasks have no edit form.

Successful POSTs redirect to `/`. The board displays active tasks in canonical
priority and file order, partitions the active file's recent Done entries by
terminal state, and never lists the full archive. Task Data Format 1 remains
readable but shows a migration banner and no mutation controls.

## Presentation and safety

The response is semantic, keyboard-operable HTML using the approved Tabler
presentation: Tabler Core 1.4.0 and Tabler Icons 3.46.0 load only from
jsDelivr, at their pinned URLs, with the approved Subresource Integrity values
and `crossorigin="anonymous"`. The board retains only the small inline CSS
needed for its layout and loads Tabler's JavaScript for modal behavior. It has
no Python dependency, packaged static asset, or offline fallback; therefore an
internet connection is required to load the presentation assets.

- Tabler Core CSS: `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css`, SRI `sha384-kz+I4+mczbNiZfLAJMxOlJaZmnbRYhARHNkR2k6tal4gz7OL33/0puDD3SvkiNX9`.
- Tabler Core JavaScript: `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js`, SRI `sha384-pku3birjgGovaJ9ngF7SaxKkF/eYUvBjiMJ+jTtWbNesIj2Rud2K63+4JD7EF4gk`.
- Tabler Icons webfont CSS: `https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css`, SRI `sha384-ND+q1IVc0KDElX60dZaqKc7Xl9cdxd2PpU2JfVUHcurCkFVtVLFdt9vJfxtHSL3p`.

The `container-xl` board grid presents four columns on desktop, two columns at
medium widths, and one column on narrow screens. Every state column has an
icon, text heading, count, and an icon-plus-text empty-state message. Completed
and Cancelled columns show at most six cards initially, with the remainder in
a native disclosure. The complete add form opens in a centered `modal-lg`.
Each board-visible card title opens a matching Tabler detail modal. On a
writable board, open and Review modals are a pre-filled edit form with
read-only ID, State, Claim, and Reviewed above the fields; completed and
cancelled tasks stay a read-only definition list of canonical fields. Task
values are escaped, and state is conveyed with text as well as color.

Each POST requires a process-local CSRF token, an exact loopback Host and
Origin, URL-encoded input, at most 32 fields, and at most 64 KiB. Responses
disable storage, framing, sniffing, and cross-origin referrers. The content
security policy permits jsDelivr only for remote styles, scripts, and fonts;
`data:` images remain allowed for Tabler; and all other sources remain
restricted.

Unknown paths, including former `GET /tasks/{task_id}` URLs, return 404;
malformed forms return 400; request trust failures
return 403; oversized bodies return 413; unsupported form media types return
415. Repository, transition, and edit failures render concise human error
pages without tracebacks.

## Exclusions

Authentication, non-loopback binding, multi-repository boards, drag-and-drop,
claims, full archive listing, polling, WebSockets, and a JSON API remain
outside this board. Task editing of open and Review work is in the detail
modal (T016); it is no longer a T010 exclusion.
