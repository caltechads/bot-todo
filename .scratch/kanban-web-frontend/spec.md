# Local Kanban Board Design

## Goal

Provide one local human with a browser view over either one selected Task
Repository or the configured Repository Collection without creating a second
task model or mutation path.

## Command

`bot-todo [--config PATH] [--root PATH | --repo NAME | --all] web [--port PORT]
[--no-open]` loads the Repository Collection once, resolves the launch
selection, binds `127.0.0.1`, prints the selected URL, and opens it unless
`--no-open` is set. No selector starts on the discovered Task Repository,
`--root` starts on that exact Task Repository, `--repo` starts on the named
Repository Entry, and `--all` starts on the collection-wide view. A local or
`--root` path matching a Repository Entry uses its Repository Name; otherwise
the running board exposes it as `Current`. `--config` chooses the collection
for every web launch form. A missing default configuration is an empty
collection; a missing explicit or malformed configuration fails before the
server binds.

The default port is 8765; port 0 requests an ephemeral port. An occupied
requested port is a coded CLI failure that names 127.0.0.1 and the port,
explains that the Kanban Board could not bind, and tells the user to retry with
--port (including --port 0). The server does not choose another port. `web`
rejects `--json`.

## HTTP interface

- `GET /` renders the launch selection. Exactly one `repo` query selects
  `all`, a configured Repository Name, or `current` when an unconfigured launch
  repository exists. Missing `repo` uses the launch selection. Duplicate,
  blank, malformed, unknown, and unavailable selections return the generic
  not-found page.
- A single-repository selection renders the add form, Open, Review, Completed,
  and Cancelled columns, and one server-rendered Tabler detail modal per
  board-visible Task from a fresh `RepositorySnapshot`. Card titles open that
  modal.
- The `all` selection snapshots every Repository Entry sequentially and fails
  without cards if any snapshot fails. It shows all four Task State columns,
  labels every card and modal with its Repository Name, and is read-only.
  Open and Review are ordered by priority, configuration order, then task-file
  order. Completed and Cancelled are ordered by configuration order, then each
  repository's existing recent-Done order.
- `GET /tasks/{task_id}` returns the generic not-found page. Archive lookup
  stays on CLI `show`.
- `POST /tasks` maps the full add form to `RepositoryTransaction.add()` for
  the selected Task Repository.
- `POST /tasks/{task_id}/transition` maps `review`, `reopen`, `complete`, and
  `cancel` to the selected repository's existing transaction methods. Cancel
  requires a reason.
- `POST /tasks/{task_id}/edit` maps the detail-modal form onto the selected
  repository's `RepositoryTransaction.edit()` for open and Review tasks. Empty
  Context, Related, Tags, and Blockers clear those fields. Completed and
  cancelled tasks have no edit form.
- Every single-repository form carries the same `repo` query as its board.
  Successful POSTs redirect to `/?repo=<selection>`. A crafted `all` POST
  returns 409 before opening a Repository Transaction.

The single-repository board displays active tasks in canonical priority and
file order, partitions the active file's recent Done entries by terminal
state, and never lists the full archive. Task Data Format 1 remains readable
but shows a migration banner and no mutation controls. The collection-wide
board retains the existing six-card disclosure after combining each terminal
state.

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

The header contains a Tabler repository dropdown whose button names `All`, the
selected Repository Name, or `Current`. Its ordinary GET links list `All`,
every Repository Entry in configuration order, and `Current` only for an
unconfigured launch repository. No custom selection JavaScript is added.

The `container-xl` board grid presents four columns on desktop, two columns at
medium widths, and one column on narrow screens. Every state column has an
icon, text heading, count, and an icon-plus-text empty-state message. Completed
and Cancelled columns show at most six cards initially, with the remainder in
a native disclosure. The complete add form opens in a centered `modal-lg`.
Each board-visible card title opens a matching Tabler detail modal. On a
writable board, open and Review modals are a pre-filled edit form with
read-only ID, State, Claim, and Reviewed above the fields; completed and
cancelled tasks stay a read-only definition list of canonical fields. All
renders every modal read-only, includes the Repository Name in its heading,
and uses collision-proof repository-qualified modal IDs. It hides mutation
controls and shows `All repositories is read-only. Select a repository to make
changes.` Task values are escaped, and state is conveyed with text as well as
color.

Each POST requires a process-local CSRF token, an exact loopback Host and
Origin, URL-encoded input, at most 32 fields, and at most 64 KiB. Responses
disable storage, framing, sniffing, and cross-origin referrers. The content
security policy permits jsDelivr only for remote styles, scripts, and fonts;
same-origin scripts and `fetch()` for live reload; `data:` images remain
allowed for Tabler; and all other sources remain restricted.

Live reload: every 200 board page embeds an opaque `data-board-version` token,
computed from `stat()` of the selected `TODO.md` file(s) before the snapshot
read, and loads the same-origin `/live-reload.js`. While the tab is visible the
script polls `GET /board-version?repo=<key>` every 2 seconds and reloads when
the token differs, unless a modal, a card Cancel-reason form, or a focused form
control is in use; the next idle tick reloads instead. All covers every
configured repository. Error pages never load the script. See ADR 0012.

Unknown paths, including former `GET /tasks/{task_id}` URLs, return 404;
malformed forms return 400; request trust failures
return 403; oversized bodies return 413; unsupported form media types return
415. Repository, transition, and edit failures render concise human error
pages without tracebacks. A strict collection read failure returns a 500
Repository error naming every failed Repository Name and error code, retains
the repository menu, and renders no partial task cards.

## Exclusions

Authentication, non-loopback binding, collection-wide mutations,
drag-and-drop, claims, full archive listing, live configuration reload,
WebSockets, and a JSON API remain outside this board. Task editing of
open and Review work is available after selecting one Task Repository; the
collection-wide view remains read-only.
