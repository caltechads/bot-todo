# Define Task Repository discovery and aggregate configuration

Type: grilling
Status: resolved

## Question

What configuration format, user-level location, environment and CLI overrides, repository naming rules, path semantics, local discovery behavior, and duplicate/worktree identity rules should select one or many Task Repositories?

## Answer

Use one strict, versioned TOML configuration containing an ordered Repository
Collection:

```toml
schema_version = 1

[[repositories]]
name = "bot-todo"
path = "~/Programming/bot_todo"
```

Only `schema_version` and `repositories` are valid top-level keys. Each
Repository Entry requires exactly `name` and `path`; unknown keys, malformed
entries, duplicate names, duplicate resolved paths, and unsupported versions
make the complete configuration invalid. Repository Names are unique lowercase
slugs matching `[a-z0-9][a-z0-9._-]*`. Configuration order is preserved for
aggregate tie-breaking.

The default path is `${XDG_CONFIG_HOME:-~/.config}/bot-todo/config.toml` on
macOS, Linux, and other Unix systems, and `%APPDATA%\bot-todo\config.toml` on
Windows. `--config PATH` overrides `BOT_TODO_CONFIG`, which overrides the
default. Override paths expand `~`, and relative override paths resolve from
the current directory. `--config` is valid only with `--repo` or `--all`; no
`BOT_TODO_ROOT` or `BOT_TODO_REPO` variables are added.

Repository Entry paths may be absolute, start with `~`, or be relative to the
configuration file. Environment variables inside entry paths are not expanded.
Paths are resolved before identity and duplicate checks. A missing path remains
valid configuration so `init --repo NAME` can create it; other single-repository
commands report `repository_not_found`.

Configuration is loaded and fully validated only for `--repo` and `--all`.
Local discovery and `--root` do not load it and report a `null` Repository Name
in JSON. A missing default configuration represents an empty Repository
Collection: `--all` succeeds with an empty result and `--repo NAME` reports
`repository_not_found`. A missing explicit `--config` reports
`config_not_found`; an existing empty or invalid file reports `invalid_config`.
Aggregate handling of missing or invalid Repository Entries belongs to the
partial-failure decision.

Without a selector, non-`init` task commands resolve the current directory and
search it and each parent through the filesystem root for the nearest
`TODO.md`. Discovery has no Git boundary. Once a candidate is found, a missing
archive or malformed task-file pair reports `invalid_document` rather than
continuing upward. `init` always targets the exact current directory, so nested
Task Repositories are allowed intentionally. Explicit `--root` remains exact.

A Task Repository's identity is its resolved filesystem directory. Symlink
aliases therefore collapse to one identity and duplicate configured paths are
errors. Separate Git worktrees remain separate Task Repositories; bot-todo does
not use Git identity.
