# 8. Use pinned Tabler assets for the Kanban presentation

Status: accepted (2026-08-19)

## Context

The local Kanban Board needs the approved responsive Option 1 presentation,
including its modal workflow and state iconography. ADR 0007 deliberately
kept the server in the Python standard library, but its original inline-CSS
and no-client-JavaScript presentation choice cannot provide that approved
interface without recreating a substantial UI framework locally.

## Decision

Keep the standard-library, loopback-only server from ADR 0007. Load these
presentation-only assets from jsDelivr instead of adding a Python dependency
or packaged static files:

- Tabler Core CSS 1.4.0: `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css`, integrity `sha384-kz+I4+mczbNiZfLAJMxOlJaZmnbRYhARHNkR2k6tal4gz7OL33/0puDD3SvkiNX9`.
- Tabler Core JavaScript 1.4.0: `https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js`, integrity `sha384-pku3birjgGovaJ9ngF7SaxKkF/eYUvBjiMJ+jTtWbNesIj2Rud2K63+4JD7EF4gk`.
- Tabler Icons webfont CSS 3.46.0: `https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css`, integrity `sha384-ND+q1IVc0KDElX60dZaqKc7Xl9cdxd2PpU2JfVUHcurCkFVtVLFdt9vJfxtHSL3p`.

Each asset uses `crossorigin="anonymous"`. The Content Security Policy allows
jsDelivr only for remote styles, scripts, and fonts, and permits `data:` only
for images required by Tabler. There is no offline fallback.

## Consequences

The board matches the approved responsive presentation while retaining no
Python runtime dependency and the existing server, repository, and security
boundaries. Browsers require internet access to load the Tabler assets; an
offline launch can still serve HTML but cannot provide the intended styling,
icons, fonts, or modal behavior. Asset version or integrity updates require a
deliberate ADR/spec and CSP review.
