# Define safe skill installation behavior

Type: grilling
Status: resolved
Blocked by: 03, 09

## Question

What exact `install-skill` command contract should provide explicit target selection, user-level defaults, destination overrides, idempotent updates, ownership detection, conflict handling, dry runs, and forced replacement without damaging user-managed files?

## Answer

### Command and destination

The sole command shape is:

```text
bot-todo [--json] install-skill --target {codex,claude,cursor,grok}
    [--destination PATH] [--dry-run] [--force]
```

Exactly one Skill Target is required. The command does not infer targets,
install more than one target, prompt, or provide aliases. The default Skill
Roots are `~/.agents/skills` for Codex, `~/.claude/skills` for Claude,
`~/.cursor/skills` for Cursor, and `~/.grok/skills` for Grok.
`--destination` replaces that root; it does not name the final skill directory.
The installed path is always `<skill-root>/todo`.

The target selects the asset view settled by **Define the bundled skill asset
model**: Codex receives `SKILL.md` and `agents/openai.yaml`; the other targets
receive only `SKILL.md`.

### Path safety

The installer expands `~` and resolves the Skill Root to an absolute path.
Missing root parents are created only during a real installation. An existing
root that is not a directory is an `io_error`. Resolved parent symlinks are
allowed, but classification uses filesystem entries without following links
inside `todo`.

A `todo` symlink or other special entry is a conflict. With `--force`, the
installer moves that entry itself to backup and never traverses or modifies its
target. Assets, manifests, and existing trees containing unsafe relative paths,
symlinks, special files, or paths escaping `todo` are never accepted as clean.

### Ownership manifest

A Managed Skill Installation contains `.bot-todo-install.json` with:

- manifest `schema_version` 1;
- the Skill Target;
- the installing `bot-todo` version for information only; and
- a mapping from each managed relative asset path to its SHA-256 digest.

The manifest does not hash itself. A valid manifest identifies the tree as
managed; its hashes determine whether the managed files remain unchanged.
Unknown manifest schemas, malformed manifests, target mismatches, missing or
changed managed files, and unrecorded files or directories are conflicts.

Version comparison has no behavioral role and needs no packaging-version
dependency. A clean managed tree is reconciled to the assets bundled with the
currently running `bot-todo`, even when that appears to be a downgrade.

### Reconciliation actions

Every successful invocation classifies exactly one stable action:

- `install`: `todo` does not exist; create the current target view and manifest.
- `adopt`: an unmarked `todo` tree has exactly the current target view as
  regular files, byte-for-byte, with no extras; add the manifest.
- `update`: a clean Managed Skill Installation differs from the current target
  view; replace it with that view and a current manifest.
- `noop`: the clean managed files and current target view already match.
- `replace`: a conflict exists and `--force` authorizes replacement.

`--force` is permission to replace conflicts, not a request to replace a clean
tree. Without it, unknown, modified, malformed, or target-mismatched content
fails with `conflict` and is not changed.

### Transaction and backups

The installer materializes and validates a complete new tree in a unique
sibling staging path before changing the destination. A new installation is
committed by renaming that tree into place. Adoption revalidates the tree and
atomically creates the manifest.

For an ordinary update, the current tree moves to a private sibling rollback
path, the staged tree moves into place, and the rollback is removed after
success. A handled commit failure restores the old tree. For forced
replacement, the existing entry instead moves to a unique timestamped
`todo.backup-*` sibling. The installer restores it if the final commit fails;
after success the backup remains until the user removes it and its absolute
path is reported.

Handled failures clean staging and private rollback paths where safe. Unique
sibling names and last-moment validation turn filesystem races into `conflict`
or `io_error` rather than overwriting an unexpected entry. The first release
adds no persistent lock, transaction journal, or background recovery system.

### Dry runs and results

`--dry-run` performs the same asset loading, path validation, classification,
and conflict checks without creating directories, files, staging trees,
manifests, rollbacks, or backups. A conflict still fails unless `--force` is
present. A dry-run replacement reports action `replace`, but `backup_path` is
`null` because no backup exists.

Within the standard JSON success envelope, `data` contains exactly:

```json
{
  "target": "codex",
  "skill_root": "/absolute/path",
  "skill_path": "/absolute/path/todo",
  "action": "install",
  "dry_run": false,
  "backup_path": null
}
```

`backup_path` is non-null only after a real forced replacement created that
backup. Expected failures use the existing `usage`, `conflict`, and `io_error`
contracts and exit meanings. Human output concisely reports the action and
paths, including a created backup, and may include target-specific reload
guidance.

Success guarantees the expected filesystem state only. The installer does not
invoke agent executables, inspect running sessions, resolve skill precedence,
or promise that a target has loaded the skill.
