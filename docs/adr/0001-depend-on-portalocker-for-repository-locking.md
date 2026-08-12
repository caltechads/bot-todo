# 1. Depend on portalocker for repository locking

Status: accepted (2026-08-11)

## Context

`.scratch/installable-bot-todo/spec.md` and
[ticket 13](../../.scratch/installable-bot-todo/issues/13-choose-runtime-and-platform-support.md)
required a dependency-free distribution and specified a hand-written locking
adapter: `fcntl.flock` on Unix, a reserved byte with `msvcrt.locking` on
Windows, both providing a shared read lock, an exclusive mutation lock, and a
fixed five-second acquisition timeout.

Two problems surfaced during Phase 1. `msvcrt.locking` has no shared mode, so
the Windows branch could only approximate the shared read lock the contract
specifies. That branch also could not be exercised on the development platform,
so the least testable code in the phase would have been the code guarding
against lost updates and duplicate task identifiers.

The dependency-free constraint was then lifted: `bot-todo` is installed as a UV
tool, so a runtime dependency costs the user nothing at install time.

## Decision

Depend on `portalocker` and reduce `RepositoryLock` to a thin translation
layer over it.

`portalocker.Lock` accepts `LOCK_SH` and `LOCK_EX` combined with `LOCK_NB`, a
`timeout`, and a `check_interval`, raising `AlreadyLocked` when the timeout
expires. That is the settled contract exactly. `RepositoryLock` translates
`AlreadyLocked` into `TodoError(code="conflict")` and `LockException` into
`io_error`, and continues to create the persistent `.bot-todo.lock` with
`O_NOFOLLOW` so a pre-existing symlink is never followed.

No other dependency is added. `argparse` and `tomllib` remain sufficient, so
the CLI keeps its standard-library parser.

## Consequences

- The Windows shared read lock is now a real shared lock rather than an
  exclusive approximation, and both platform paths are maintained upstream.
- The five-second timeout stays fixed with no CLI option or configuration
  setting, as ticket 12 requires. `RepositoryLock` takes a constructor default
  only so tests can run with a short timeout.
- Ticket 13's locking section is superseded on mechanics; its runtime and
  platform matrix still stands.
- The distribution is no longer dependency-free. Anything that assumed a
  single-file, zero-dependency install must install from the wheel instead.
