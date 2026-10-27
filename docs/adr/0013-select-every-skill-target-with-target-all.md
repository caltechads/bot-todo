# 13. Select every Skill Target with `--target all`, not `--all`

Status: accepted (2026-10-27)

## Context

T024 lets one `install-skill` run install the `todo` skill for every Skill
Target. The obvious spelling, `install-skill --all`, collides with the global
`--all` selector, which already means "every Repository Entry in the Repository
Collection" and which `install-skill` rejects. `bot-todo install-skill --all`
would succeed while `bot-todo --all install-skill` fails with a usage error, so
the same word would mean different things depending on where it is placed. The
packaged `todo` skill also tells agents to use `--all` only for cross-repository
requests.

## Decision

Add `all` as one more `--target` choice. `all` is not a Skill Target. It expands
to every supported Skill Target in sorted order. Each target's classification
runs before anything is written. If any target conflicts and `--force` was not
given, the run fails, names every conflicting path, and writes nothing.
`--destination` combined with `all` is a usage error, because every target would
share one `<root>/todo`. `--dry-run` and `--force` apply to each target. A
single-target success document keeps its existing `data` object. An `all`
success document returns `data.installations`, a list of those objects, so the
JSON Schema Version stays the same.

## Considered Options

- `install-skill --all`: the original request. Rejected because it overloads the
  Repository Collection selector and makes the meaning depend on position.
- A repeatable `--target`: more flexible, but nobody has asked to install a
  subset of targets.
- Installing as many targets as possible and exiting with status 3 (partial
  failure): rejected because the user would have to clean up a half-applied
  run. Checking every target first catches every conflict. A rare I/O failure
  during the writes can still leave earlier targets installed. Each target
  install is idempotent, so rerunning the command repairs that.
- Installing only targets whose tool appears to be installed: rejected because
  detection is heuristic, and `~/.agents` is not specific to Codex.
