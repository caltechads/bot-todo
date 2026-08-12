# Define concurrency and partial-failure policy

Type: grilling
Status: resolved
Blocked by: 01, 07, 08, 11

## Question

What guarantees should single-repository mutations and aggregate reads provide under concurrent processes, unavailable or malformed repositories, interrupted writes, symlinks, permissions failures, and partially valid configurations?

## Answer

### Repository coordination

Every Task Repository has one persistent `.bot-todo.lock`. Reads take a shared
lock and mutations take an exclusive lock. A Repository Transaction holds its
exclusive lock across recovery, load, validation, and commit, so concurrent
writers cannot lose updates or allocate the same task identifier. Repository
initialization uses the same serialization.

Lock acquisition waits for at most five seconds and then reports `conflict`
without writing. The timeout is fixed in the first release; there is no option
or configuration setting for it. Platform-specific locking mechanics belong
to [Choose the supported runtime and platform matrix](13-choose-runtime-and-platform-support.md).

An aggregate read holds at most one shared repository lock at a time and reads
repositories in Repository Collection order. Each result therefore comes from
a coherent Repository Snapshot, but the aggregate does not claim one global
point-in-time snapshot. A repository may change after its snapshot is released.

### Transaction durability

A Repository Transaction stages the complete canonical pair on the same
filesystem and publishes a durable commit marker. An interruption before that
marker retains the old pair; an interruption after it causes the next command
to complete the new pair before proceeding. Recovery runs under exclusive
access and never accepts a mixed-generation pair.

Temporary transaction state is removed after commit or recovery. Malformed
transaction state fails closed as `invalid_document`; an unreadable or
unwritable transaction fails as `io_error`. Neither case permits further
canonical-file changes. Existing canonical-file permission bits are preserved,
and new files use normal platform creation permissions. Permission checks are
not preflighted because they would race the actual filesystem operations.

### Filesystem boundaries

Repository-directory symlinks remain allowed and collapse to their resolved
Task Repository identity. `TODO.md` and `TODO.archive.md` must each be regular,
non-symlink files. A symlink, directory, device, socket, or other special object
at either canonical path reports `invalid_document`; bot-todo never replaces or
follows it as canonical task data. Coordination artifacts are created without
following pre-existing symlinks.

Repository failures use these codes:

- A missing repository directory is `repository_not_found`.
- An existing directory with neither canonical file is `not_initialized`.
- One missing canonical file, malformed task data, or an unsafe canonical file
  type is `invalid_document`.
- An unsupported declared Task Data Format is `unsupported_format_version`.
- Permission and other filesystem failures are `io_error`.

### Aggregate failure

Configuration remains all-or-nothing: a structurally invalid configuration is
`invalid_config` before any repository is read. A missing Repository Entry path
is valid configuration but becomes `repository_not_found` when queried.

For a valid Repository Collection, aggregate commands inspect every repository
in configuration order. If any repository fails, the command returns no task
result, emits `aggregate_partial_failure`, and exits 3. Its structured details
list every failed repository in configuration order with the Repository Name,
resolved path, underlying error code, and human message. Successful repository
data is not returned because missing data could change global ordering or the
selected Critical or Actionable Task.
