# Define the public bot-todo CLI contract

Type: grilling
Status: resolved
Blocked by: 01

## Question

What command hierarchy, repository-selection behavior, human output, JSON schema, exit codes, and compatibility guarantees form the stable public interface used by humans and the `todo` skill?

## Answer

The first public `bot-todo` release establishes a new contract. The existing
embedded script is an implementation and data-behavior reference, not a public
compatibility surface.

### Command hierarchy

The canonical invocation is:

```text
bot-todo [--json] [--root PATH | --repo NAME | --all] COMMAND [command options]
```

Global options precede the command. Commands remain flat:

```text
init validate list show critical actionable
add edit claim release complete cancel archive
install-skill
```

`critical` returns the highest-ranked open Task; `actionable` returns the
highest-ranked Task that is unblocked and unclaimed. Either result may be empty.
The aggregate-semantics decision owns their exact ranking and filtering rules.

The current mutation argument shapes remain useful: positional Task IDs and
titles, repeatable tag and blocker options, explicit claim actor, and a required
cancellation reason. Public terminology uses `init --name NAME`, not
`init --project`. `edit` also supports `--simple`, `--clear-context`,
`--clear-related`, and `--clear-blockers`; an edit requesting no change is a
usage error.

The CLI provides `-h`/`--help` and global `--version`. Both emit human text and
exit successfully even when `--json` is present. Long-option abbreviation,
undocumented aliases, and short options other than `-h` are not accepted.

### Task Repository selection

With no selector, a task command uses the current directory's Task Repository.
The mutually exclusive selectors are:

- `--root PATH`: one Task Repository at an explicit path.
- `--repo NAME`: one configured Task Repository.
- `--all`: every configured Task Repository in the active collection.

`--root` and `--repo` work with every task command. `--all` works only with the
read-only `list`, `critical`, and `actionable` queries. `install-skill` accepts
no Task Repository selector. Configuration, naming, identity, and local
discovery details belong to the repository-configuration decision.

### Human and shell behavior

Human-readable output is the default and is informational rather than a stable
machine interface:

- `list`, `critical`, and `actionable` emit concise Task summary lines;
  aggregate lines include repository provenance.
- `show` emits canonical Task Markdown.
- Mutations emit a short confirmation containing the affected Task ID.
- `init`, `validate`, and `archive` emit a short status or count.
- An empty `list` emits nothing; an empty singular query emits an explanatory
  line and still succeeds.

Commands do not prompt, request confirmation, start a pager, emit ANSI styling,
or consume stdin. Results use stdout and diagnostics use stderr. Exact wording,
spacing, and help layout are not contractual.

### JSON success contract

`--json` is the stable automation interface. A successful command emits exactly
one UTF-8 JSON document followed by a newline and no ANSI styling:

```json
{
  "schema_version": 1,
  "command": "list",
  "data": {}
}
```

`list` places an array in `data.tasks`. `show`, `critical`, and `actionable`
place a Task or `null` in `data.task`. Task mutations return the resulting full
Task. `init`, `validate`, `archive`, and `install-skill` use small
command-specific result objects; the installer decision owns the last one's
exact fields.

Every Task object contains every documented key. Optional values are `null`,
collections are arrays, dates use `YYYY-MM-DD`, and repository paths are
absolute and resolved:

```json
{
  "repository": {
    "name": null,
    "path": "/absolute/resolved/path"
  },
  "id": "T001",
  "title": "Define the public CLI",
  "state": "open",
  "priority": "P1",
  "type": "docs",
  "tags": [],
  "simple": false,
  "acceptance": "Done when...",
  "context": null,
  "related": null,
  "blocked_by": [],
  "claim": null,
  "actionable": true,
  "closed_on": null,
  "reason": null
}
```

`state` is `open`, `completed`, or `cancelled`. JSON does not expose the
Markdown checkbox or a duplicate outcome field. `type` and `simple` are
separate from ordinary user `tags`. A populated claim has `actor`,
`claimed_on`, and `branch`. A simple Task has `acceptance: null`; a completed
Task has `reason: null`; a cancelled Task requires a reason. Closed or claimed
Tasks are not actionable. Repository `name` is nullable for an unconfigured
path unless configuration identifies it.

JSON object key order and insignificant whitespace are not contractual.

### JSON errors and exit codes

When `--json` is present, an expected failure emits no stdout and one versioned
error object to stderr:

```json
{
  "schema_version": 1,
  "error": {
    "code": "unknown_task",
    "message": "unknown task ID T999"
  }
}
```

Schema version 1 starts with these stable symbolic codes: `usage`,
`repository_not_found`, `not_initialized`, `already_initialized`,
`invalid_document`, `unknown_task`, `invalid_transition`, `conflict`, and
`io_error`. New error codes are additive, and clients must tolerate unknown
codes. Human-readable messages are not stable. The partial-failure decision
owns aggregate failure details.

Exit meanings are:

- `0`: success, including an empty query result.
- `1`: operational, domain, task-data, or filesystem failure.
- `2`: command-line usage failure.
- `3`: aggregate partial failure.

### Compatibility boundary

No wrapper, deprecated alias, legacy script path, command name, exit behavior,
or exact output is preserved merely for compatibility with the unreleased
embedded CLI. This resolved contract becomes the initial public baseline.
Documented command semantics and versioned JSON are stable once released;
their evolution rules belong to the compatibility-and-migration decision.
