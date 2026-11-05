# 15. Include the Repository Collection in the board version token

Status: accepted (2026-11-05); amends the `/board-version` decision in ADR 0014 and the token definition in ADR 0012

## Context

ADR 0014 made each web request read its own Repository Collection snapshot,
but kept the `/board-version` token over `TODO.md` files only. An open All
board reloaded after `repos add` or `repos remove` because its set of paths
changed, but a single-repository board showed a stale repository selector
until someone reloaded it by hand, and a rename that kept the path changed
nothing at all. ADR 0014 deferred this until users expected open boards to
refresh the selector by themselves. T027 records that they now do.

One gap remains even with a collection-aware token. A tab whose selection
stops resolving, either a removed `?repo=<name>` or `?repo=current` after the
launch path is added, gets 404 from `/board-version`, and the script ignored
any non-OK response, so that tab would never reload.

## Decision

Every selection's token (a named Repository Entry, Current, and All) hashes
the request snapshot's Repository Entries as (Repository Name, path) pairs
sorted by Repository Name, alongside the existing `TODO.md` `st_mtime_ns` and
`st_size` parts. The token does not stat or hash `config.toml`. The goal is
that the token moves exactly when the page would render differently:

- The repository menu is sorted by name (T026), so the entry pairs are
  sorted. Reordering `config.toml` does not move a single-repository token.
- The All board orders cards across repositories by configuration order (it
  breaks ties in Open and Review, and fully decides Completed and
  Cancelled). All's `TODO.md` parts therefore stay in configuration order on
  purpose, so a reorder reloads All, whose card order really changed.

The live-reload script also reloads, subject to the same busy check, when
`/board-version` answers 404. The tab lands on the not-found page, which
keeps the repository menu and does not load the script, so it reloads once.
Other non-OK responses (a broken configuration's 5xx) and network errors are
still ignored. Reloading into an error page would stop polling and leave the
tab stuck after the configuration is fixed.

## Considered Options

- Stat `config.toml` (mtime and size) — rejected because any rewrite,
  including a no-op or a reorder, would reload every open tab, and the file's
  identity is not what the page shows.
- Hash the entry pairs in configuration order — rejected because a reorder
  would reload a single-repository board to an identical page.
- Also sort All's `TODO.md` parts so a reorder never reloads anything —
  rejected because an open All board would keep showing the old card order
  until some `TODO.md` changed.
- Fingerprint the collection only for single-repository boards — rejected
  because one code path is simpler, and All also needs a reload on a rename
  to refresh its card labels and menu.
- On 404, navigate to `/` (the launch board) — rejected because it silently
  switches the board; the not-found page says what happened and the menu
  offers every remaining repository.

## Consequences

`repos add`, `repos remove`, and renames reach every open board within about
two seconds, including a tab whose own repository was removed. Each poll
already loaded the snapshot, so the extra cost is hashing a few short
strings. A `config.toml` edit that changes nothing visible reloads nothing.
A reorder reloads open All boards and no other board.
