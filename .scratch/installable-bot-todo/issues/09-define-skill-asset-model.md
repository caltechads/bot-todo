# Define the bundled skill asset model

Type: grilling
Status: resolved
Blocked by: 02, 03, 05

## Question

Which skill files are canonical, which target-specific overlays are necessary, and how should installed code locate and materialize those packaged resources without assuming a source checkout?

## Answer

The package owns one canonical skill source tree at
`src/bot_todo/skill_assets/todo/`:

```text
todo/
├── SKILL.md
└── agents/
    └── openai.yaml
```

`SKILL.md` is the portable core. It translates agent intent into calls to the
installed `bot-todo` executable and contains only the guidance agents need to
use it safely: intent routing, task-lifecycle invariants, validation before and
after mutations, the exceptional manual merge-collision repair, and
representative commands. Normal examples use human-readable output; workflows
that parse results or branch on them use `--json`. Exhaustive arguments, output
schemas, error catalogs, and installation instructions remain CLI or public
documentation concerns.

The skill contains no Python scripts, tests, duplicated CLI implementation,
generated references, or packaged executable path. It invokes `bot-todo` by
name and contains no installation path or package version that would require
rendering.

`agents/openai.yaml` is the sole target-specific overlay. It retains Codex
display metadata and its `$todo` default prompt but introduces no behavioral
instructions. Codex installations receive `SKILL.md` and
`agents/openai.yaml`; Claude, Cursor, and Grok installations receive only
`SKILL.md`. No empty overlay directories are created, and no other target
overlay is added until a target requires actual metadata.

Runtime code locates the canonical tree with
`importlib.resources.files("bot_todo").joinpath("skill_assets", "todo")`.
It treats the result as a `Traversable` and recursively copies each selected
file's bytes. Installation does not depend on `Path(__file__)`, the current
directory, checkout-relative traversal, symlinks, or directory-level
`as_file()` support. Selected assets are copied byte-for-byte without
templating.

Distribution tests verify the exact canonical asset set in both wheel and
source distribution, resource traversal from an installed wheel, target view
composition, and byte-for-byte materialization outside the checkout. Ownership
markers, hashes, backups, replacement rules, and installer transaction behavior
remain owned by **Define safe skill installation behavior**.
