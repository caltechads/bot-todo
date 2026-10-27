# T024 — `install-skill --target all`

Decision record: [ADR 0013](../../docs/adr/0013-select-every-skill-target-with-target-all.md).

## Settled behavior

- `bot-todo install-skill --target all [--dry-run] [--force]` installs every
  Skill Target in `sorted(TARGET_ROOTS)` order (`claude`, `codex`, `cursor`,
  `grok`). These are always the native user-level Skill Roots, with no attempt
  to detect which tools are installed.
- Preflight: classify every target before committing any. Collect every
  `conflict` failure, then raise one `TodoError(..., "conflict",
  {"conflicts": [paths]})` that names them all. Nothing is written. Any other
  classification failure, such as an `io_error` because a Skill Root is a file,
  is raised immediately. That also happens before anything is written.
- `--target all --destination PATH` → `TodoError("--destination cannot be
  combined with --target all", "usage")`, exit 2, nothing touched.
- `--dry-run` / `--force` pass through to every target.
- JSON: single target unchanged. `all` → `data = {"installations": [<same
  per-target object>, ...]}`. `JSON_SCHEMA_VERSION` stays 2.
- Human output: one existing per-target line (plus `backed up to …`) per
  target, joined by newlines.

## Code changes

### `src/bot_todo/skill_installation.py`

1. Add a module constant:
   ```python
   #: ``--target`` choice that expands to every Skill Target.
   ALL_TARGETS = "all"
   ```
2. Split classification out of `SkillInstaller.run()` into a public
   `classify() -> str`. It reads the view, resolves the root, and returns the
   Reconciliation Action, with the same raises as today. `run()` keeps calling
   the existing steps, so its behavior does not change. Commit-time races are
   still re-checked by `run()` because it classifies again.
3. Add `class SkillTargetSetInstaller` (constructor injection like
   `SkillInstaller`: `targets: Sequence[str]`, kw `dry_run`, `force`). It
   represents the "all targets" workflow boundary and gets a full Napoleon
   docstring and `#:` attributes:
   ```python
   def run(self) -> list[InstallationResult]:
       installers = [SkillInstaller(t, None, dry_run=..., force=...) for t in self.targets]
       conflicts = []
       for installer in installers:
           try:
               installer.classify()
           except TodoError as error:
               if error.code != "conflict":
                   raise
               conflicts.append(str(installer.skill_path()))
       if conflicts:
           raise TodoError(
               f"not clean managed todo skill installations: {', '.join(conflicts)}",
               "conflict",
               {"conflicts": conflicts},
           )
       return [installer.run() for installer in installers]
   ```
   Add a public `SkillInstaller.skill_path() -> Path` that returns
   `self._root() / SKILL_DIRECTORY`, and use it in `run()` too.

### `src/bot_todo/cli.py`

1. Import `ALL_TARGETS` and `SkillTargetSetInstaller`.
2. Parser (`cli.py:1596`):
   `choices=[*sorted(TARGET_ROOTS), ALL_TARGETS]`.
3. `_install_skill` (`cli.py:1389`):
   - Pull the existing result→dict/human mapping into a module-level helper
     `_installation_outcome(result) -> CommandOutcome` (reuse, unchanged text).
   - If `arguments.target == ALL_TARGETS`: reject `arguments.destination` with
     the usage error, then run `SkillTargetSetInstaller(sorted(TARGET_ROOTS),
     ...)`. Build `data={"installations": [o.data ...]}` and
     `human="\n".join(o.human ...)`.
   - Otherwise keep the current path through the helper.
   - Update the docstring: "one Skill Target or every Skill Target".

No selector changes. The global `--all` is still rejected for
`install-skill`.

## Docs

- `README.md`
  - Command table: `install-skill --target TARGET` → note `TARGET` may be `all`.
  - "Agent skill" section: add `bot-todo install-skill --target all`. Add one
    paragraph covering all four default roots, conflicts checked before
    anything is written, `--destination` disallowed, and the
    `data.installations` JSON.
- `CONTEXT.md`: Skill Target entry gains "`all` selects every Skill Target; it
  is not itself one." (done during grilling).
- `src/bot_todo/skill_assets/todo/SKILL.md`: no change, because it does not
  mention `install-skill`.

## Tests (`tests/test_skill_installation.py`, new `AllTargetsTests`)

Use the `HOME`/`USERPROFILE` patch pattern from
`SkillRootTests.test_each_target_defaults_to_its_own_user_root`. Use the TDD
order and write each test red first:

1. `--target all` installs every target under its default root. The
   `installations` list has the sorted target order, every `action ==
   "install"`, and each tree matches `SkillAssets().view(target)`.
2. A second run gives every target `noop`.
3. A conflicting `~/.claude/skills/todo` (edited SKILL.md) gives exit 1, code
   `conflict`, and `conflicts` lists that path. A snapshot of the whole fake
   home is unchanged, so no other target was installed.
4. Two conflicting targets are both listed in `conflicts`.
5. `--force` with a conflict replaces it with a backup and installs the others.
6. `--dry-run` creates nothing and reports four `would install` lines (human
   mode) / four installations.
7. `--destination` with `all` gives exit 2, code `usage`, and the destination
   is not created.
8. Existing `test_a_missing_or_unknown_target_is_a_usage_failure` still passes.
   The global `--all` rejection test still passes.

## Verification gate

```bash
make pytest tests/test_skill_installation.py
make pytest
ruff check src/bot_todo/cli.py src/bot_todo/skill_installation.py tests/test_skill_installation.py
ruff format --check <same>
mypy src/bot_todo/cli.py src/bot_todo/skill_installation.py
make napoleon-gate
bot-todo --json validate
```

Manual smoke: `HOME=$(mktemp -d) bot-todo install-skill --target all` then
run it again (expect four `noop`).

Then `bot-todo --json review T024`.
