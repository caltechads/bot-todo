# Define aggregate query semantics

Type: grilling
Status: resolved
Blocked by: 01, 07

## Question

How should `bot-todo` distinguish Critical Tasks from Actionable Tasks across configured Task Repositories, filter and order results, report provenance, and preserve deterministic tie-breaking?

## Answer

`list`, `critical`, and `actionable` operate on open tasks only. Closed tasks
are excluded. `list` returns every open task; the first public release adds no
filter flags. Focused selection is provided by the two singular queries:

- `critical` returns the first open task under the aggregate ordering, even if
  that task is claimed or blocked.
- `actionable` returns the first open, unclaimed task whose blockers are all
  completed. A cancelled blocker remains unsatisfied.

Both singular queries succeed with a null result when no matching task exists.
Blocker references and their completion state remain local to each Task
Repository.

Every result uses one deterministic global ordering:

1. Priority: P0, then P1, then P2.
2. Repository order in the configured Repository Collection.
3. Existing task-file order within the priority section.

Single-repository queries use the same rule with the repository-order step
omitted. No title, ID, claim date, or other secondary sort is applied.

For `--all`, each human-readable task summary is prefixed with its Repository
Name so repository-local task IDs remain unambiguous. The exact punctuation is
not contractual. JSON Task objects always include the resolved repository
object established by the public CLI contract: its nullable configured name
and absolute resolved path. Aggregate JSON arrays preserve the ordering above.

Unavailable or invalid configured repositories and aggregate partial failures
remain owned by **Define concurrency and partial-failure policy**.
