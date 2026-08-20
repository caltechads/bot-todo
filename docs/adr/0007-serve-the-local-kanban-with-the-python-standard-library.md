# 7. Serve the local Kanban Board with the Python standard library

Status: accepted (2026-08-18); presentation amended by ADR 0008

## Context

T010 adds a browser interface for one local Task Repository. The interface is
single-user, binds only to loopback, needs ordinary request/response forms, and
must preserve the CLI and repository core as the programmatic and persistence
boundaries. NiceGUI would add a broad FastAPI, Vue, and WebSocket stack;
Starlette would still require an ASGI server despite no async or remote-serving
requirement.

## Decision

Serve the Kanban Board with `ThreadingHTTPServer` and server-rendered semantic
HTML. The web layer calls `TodoStore.snapshot()` and `RepositoryTransaction`
directly, binds only to `127.0.0.1`, and adds no Python runtime dependency.
State-changing forms use an in-memory CSRF token plus strict Host and Origin
checks. The original inline-CSS/no-client-JavaScript presentation choice is
amended by ADR 0008; this ADR's standard-library server decision remains in
force.

## Consequences

The packaged tool stays dependency-light and cross-platform, but this server
is deliberately local-only and is not a foundation for authentication,
multi-user deployment, WebSockets, or a public HTTP API. Revisit the framework
choice only if one of those requirements becomes real.
