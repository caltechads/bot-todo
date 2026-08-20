# Bot Todo

Bot Todo provides a canonical task model that humans and development agents operate through one command-line interface.

## Language

**bot-todo**:
The installable Python distribution and command-line executable that is the sole programmatic interface to task data.
_Avoid_: todo CLI, embedded CLI

**todo skill**:
The thin agent instruction bundle that translates user intent into `bot-todo` commands.
_Avoid_: CLI skill, bundled CLI

**Task Management Snippet**:
The packaged markdown section consuming repositories copy into `AGENTS.md` or `CLAUDE.md`.
_Avoid_: AGENTS.md snippet, instruction block

**Task Repository**:
A local directory containing one canonical `TODO.md` and `TODO.archive.md` pair.
Its identity is its resolved filesystem directory; separate Git worktrees are
separate Task Repositories. A configured Task Repository may also have a name.
_Avoid_: Project, source repository

**Kanban Board**:
The local human-facing view of one Task Repository, grouped by Task State.
_Avoid_: Web frontend, web UI, task dashboard

**Repository Name**:
A unique lowercase slug that identifies a Repository Entry.
_Avoid_: Project name, repository alias

**Repository Entry**:
A named configuration record that points to a prospective or existing Task
Repository. Its path may not exist yet.
_Avoid_: Task Repository

**Repository Collection**:
The ordered set of Repository Entries loaded from one configuration file for
aggregate queries.
_Avoid_: Task list, repository list, workspace, repository group

**Repository Snapshot**:
A coherent, validated view of one Task Repository's canonical task-file pair.
_Avoid_: Global snapshot, aggregate snapshot

**Repository Transaction**:
One serialized, crash-recoverable mutation of a Task Repository's canonical
task-file pair.
_Avoid_: File write, atomic write

**Aggregate Query**:
One read-only query answered across the whole Repository Collection, ordered by
priority, then configuration order, then task-file order. It fails entirely when
any single repository fails.
_Avoid_: Bulk query, global query, cross-repository operation

**Tag**:
An ordinary label on a Task. It is not the classifying type and not the
`simple` marker.
_Avoid_: Type, hashtag, label, keyword

**Task State**:
One of open, review, completed, or cancelled.
_Avoid_: Status

**Review**:
The Task State of a Task whose work is finished but not yet accepted as completed.
_Avoid_: In review, needs review, needs validation

**Critical Task**:
The highest-priority open task, whether or not it can currently be acted upon.
_Avoid_: Next task

**Actionable Task**:
An open task whose blockers are completed and which has no active claim.
_Avoid_: Critical task

**Skill Target**:
One supported agent tool selected for a `todo` skill installation: Codex,
Claude, Cursor, or Grok.
_Avoid_: Agent, platform

**Skill Root**:
The directory under which a Skill Target's `todo` skill directory is installed.
It is either the target's native user-level location or an explicit override.
_Avoid_: Destination, skill directory

**Managed Skill Installation**:
A `todo` skill installation that `bot-todo` can identify as its own and safely
check, update, or replace.
_Avoid_: Installed skill, owned directory

**Skill Manifest**:
The `.bot-todo-install.json` ownership record inside a Managed Skill
Installation, naming its Skill Target and the digest of every managed asset.
_Avoid_: Lock file, install marker

**Reconciliation Action**:
The single outcome one `install-skill` invocation classifies: install, adopt,
update, noop, or a forced replace.
_Avoid_: Install mode, operation

**Task Data Format**:
The versioned Markdown structure and lifecycle semantics of a Task Repository.
Its version is independent of the `bot-todo` release and JSON Schema Version.
_Avoid_: File schema, CLI version

**JSON Schema Version**:
The compatibility version of `bot-todo` machine-readable success and error
documents. It is independent of the Task Data Format and `bot-todo` release.
_Avoid_: Task format version, package version

**Configuration Schema Version**:
The compatibility version of the TOML structure used to define a Repository
Collection. It is independent of the Task Data Format and JSON Schema Version.
_Avoid_: Config version, JSON Schema Version
