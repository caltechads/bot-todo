# 12. Poll a board version token for live reload

Status: accepted (2026-10-23); amends the CSP in ADR 0008 and the client-script note in ADR 0010

## Context

T022 requires an open Kanban Board to reflect external `TODO.md` edits (CLI or
editor) within a few seconds, for one Task Repository and for All, without
discarding an open modal or a half-filled form. Every `GET /` already re-reads
`TODO.md`, so the server never serves stale data; only the browser needs to
learn that a reload is worthwhile. ADR 0010 left Tabler's script as the only
client script, and the CSP allowed scripts only from jsDelivr and no
`connect-src`, so neither inline script nor `fetch()` could run.

## Decision

Add `GET /board-version?repo=<key>`, resolved like `GET /` and behind the same
Host check. It returns a plain-text opaque token: a SHA-256 of each selected
repository's `TODO.md` `st_mtime_ns` and `st_size`, with a sentinel for a
missing or unreadable file. All covers every configured repository. The board
embeds the token, computed before its snapshot read, as `data-board-version`.

A first-party script served same-origin at `GET /live-reload.js` polls the
endpoint every 2 seconds while the tab is visible. When the token differs, it
calls `location.reload()` unless the user is busy (an open modal, an open card
Cancel-reason form, or a focused form control); a busy tick is skipped and the
still-different token reloads on the next idle tick. Only the 200 board page
loads the script, never error pages, because reloading a POST result would
resubmit it. The CSP adds `'self'` to `script-src` and adds `connect-src
'self'`.

First-party client JavaScript is acceptable on the board whenever it is the
simplest correct fit; ADR 0010's "only client script" note no longer applies.

## Considered Options

- Filesystem watching (watchdog) plus a push channel — adds a dependency and
  long-lived connections for a single local user.
- Server-Sent Events or WebSockets — long-lived connections in a
  `ThreadingHTTPServer`, which ADR 0007 says is not a foundation for them.
- Inline script with a CSP hash — silently breaks when the script is edited
  without updating the hash.
- Content hash of `TODO.md` — reads every file each poll; mtime plus size is
  enough for atomic `os.replace` writes and coarse-mtime filesystems.
- A "Board changed" banner instead of deferred auto-reload — extra UI for no
  data-safety gain.

## Consequences

The board refreshes itself within about two seconds of an external change and
never interrupts editing. Each open tab issues one cheap `stat`-only request
every 2 seconds while visible. Expanded "+N more" overflow lists collapse on a
reload. The JavaScript is verified manually in a browser; pytest covers the
endpoint, token embedding, script route, and CSP.
