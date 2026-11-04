# 14. Read the Repository Collection per web request

Status: accepted (2026-11-03); amends ADR 0011

## Context

ADR 0011 made Kanban selection request-scoped because sharing one mutable
`TodoStore` across `ThreadingHTTPServer` requests would let one request affect
another. Its Decision also loaded the Repository Collection once at startup
and fixed the launch selection against that snapshot. That forced a restart
after `bot-todo repos add` or `repos remove`. The restart was not part of the
safety argument: a fresh, request-local read creates no shared selection
state, and every CLI command already rereads the configuration. T025 asks
that a running board pick up collection changes on the next page load.

## Decision

Each web request reads its own Repository Collection snapshot through
`CollectionStore.load`. That load takes the shared configuration lock, so it
cannot block a concurrent `repos add` or `repos remove` from atomically
replacing the file on platforms where an open reader would make the rename
fail. One request uses one snapshot from start to finish. The application
keeps no process-lifetime collection.

The launch Task Repository stays fixed for the server's lifetime. Each
request decides how to label it against its own snapshot. It is the matching
named entry when its path is configured, and Current otherwise. `repo=current`
resolves only while the launch path is unconfigured, so a launch repository
added later appears once under its Repository Name. A removed launch
repository remains reachable at bare `/` as Current.

If the configuration file is missing (when explicit), malformed, or
unreadable, that request fails with the configuration error, the same as a
CLI command. The board does not serve a last-good snapshot.

`/board-version` computes its token from the request's fresh snapshot. It does
not watch `config.toml`. An open All board reloads by itself after a
collection change because its set of `TODO.md` paths changes. A
single-repository board shows the updated selector on its next page load.

ADR 0011's other decisions are unchanged: request-scoped selection, a
read-only All board that fails without partial cards, and board-specific
collection reading kept in the web layer.

## Considered Options

- Keep load-once and require a restart — rejected because it adds an operator
  step and is not needed for request isolation.
- Cache the collection and reload it when `config.toml`'s mtime changes —
  rejected because it brings back shared mutable state and invalidation logic
  to avoid parsing one small TOML file per request.
- Serve the last good snapshot when the configuration breaks — rejected
  because it needs a shared cache and hides an error the CLI would report.
- Add the configuration file to the `/board-version` token — deferred. T025
  only requires the next page load. Revisit if users expect open
  single-repository boards to refresh the selector by themselves.

## Consequences

`repos add` and `repos remove` take effect in a running board without a
restart. Every board request pays for one shared-lock acquisition and one
TOML parse. A configuration mistake breaks the board until it is fixed,
rather than leaving stale data on screen.
