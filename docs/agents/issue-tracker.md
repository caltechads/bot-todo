# Issue tracker: Local Markdown

Issues and specs for this repository live as Markdown files in `.scratch/`.

## Conventions

- One effort per directory: `.scratch/<effort-slug>/`.
- A specification is `.scratch/<effort-slug>/spec.md`.
- Issues are `.scratch/<effort-slug>/issues/<NN>-<slug>.md`, numbered from `01`.
- Comments and conversation history append under `## Comments`.

## Wayfinding operations

- **Map**: `.scratch/<effort>/map.md`.
- **Child ticket**: `.scratch/<effort>/issues/NN-<slug>.md` with `Type:` and `Status:` lines.
- **Blocking**: `Blocked by: NN, NN`. A ticket is unblocked when every listed ticket is resolved.
- **Frontier**: open, unblocked, unclaimed children in numeric order.
- **Claim**: set `Status: claimed` before work.
- **Resolve**: append the answer under `## Answer`, set `Status: resolved`, and append a named context pointer to the map's `Decisions so far`.
