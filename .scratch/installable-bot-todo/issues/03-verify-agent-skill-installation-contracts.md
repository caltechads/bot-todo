# Verify agent skill installation contracts

Type: research
Status: resolved

## Question

What are the current, authoritative user-level skill formats, directories, naming constraints, overwrite expectations, and platform differences for Codex, Claude, Cursor, and Grok?

## Answer

All four targets currently support reusable filesystem skills built around `<skill-name>/SKILL.md`. The portable [Agent Skills specification](https://agentskills.io/specification) requires `name` and `description`; names use lowercase letters, digits, and hyphens, are at most 64 characters, match the parent directory, and have no invalid edge or consecutive hyphens. Optional `scripts/`, `references/`, and `assets/` directories are portable. The existing `todo` metadata satisfies this common denominator.

### Native user-level targets

- **Codex**: `~/.agents/skills/todo/SKILL.md`, with optional OpenAI-specific `agents/openai.yaml`. Codex supports symlinked skill directories, detects additions automatically, and recommends restart if an update does not appear. See [Build skills for Codex and ChatGPT](https://learn.chatgpt.com/docs/build-skills).
- **Claude Code**: `~/.claude/skills/todo/SKILL.md`. Existing watched roots live-reload; creating the top-level skills directory after session start may require restart. Personal skills override project skills on collision. See [Claude Code skills](https://code.claude.com/docs/en/skills).
- **Cursor**: `~/.cursor/skills/todo/SKILL.md`. Cursor also reads several shared/competitor roots, but its native location avoids cross-tool side effects. Official documentation states automatic loading but does not promise live reload. See [Cursor skills](https://cursor.com/docs/skills).
- **Grok Build**: `~/.grok/skills/todo/SKILL.md`. Grok also discovers shared Agent Skills and other tool roots, reloads changes within seconds, and exposes `/skills` and `grok inspect` verification. Project/local skills can shadow user skills. See [Grok skills, plugins, and marketplaces](https://docs.x.ai/build/features/skills-plugins-marketplaces) and the [Grok Build user guide](https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-pager/docs/user-guide/08-skills.md).

### Installer implications

Use one portable asset tree with target-native destination adapters. Copy resources rather than depending on symlinks because only Codex explicitly guarantees them. None of the platforms defines safe third-party overwrite/update behavior, so `bot-todo` must own that contract: no-op for identical managed content, refuse unknown or modified trees, require an explicit force path for replacement, and consider a backup plus an installer-owned version/hash sidecar.

Installation verification is target-specific, and a successful copy does not guarantee precedence when another same-name project or enterprise skill shadows the user-level skill.
