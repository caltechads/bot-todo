# Choose the supported runtime and platform matrix

Type: grilling
Status: resolved
Blocked by: 02, 03

## Question

Which Python versions and operating systems must `bot-todo` support, given UV installation, standard-library availability, packaged-resource behavior, configuration locations, and the four required skill targets?

## Answer

### Python runtime

The first release supports CPython 3.11 through the current stable CPython
release, initially 3.14. The package declares `requires-python = ">=3.11"`
without an upper bound. A newly stable CPython release joins the supported
range only after its CI job passes; prereleases and alternative interpreters
such as PyPy are not supported.

Python 3.11 is the minimum because it supplies `tomllib` without a dependency.
The packaged skill already uses recursive `importlib.resources` traversal, so
it does not need Python 3.12's directory-level `as_file()` support. Nothing in
UV installation or the four Skill Targets requires a newer runtime.

### Operating systems

Linux, macOS, and Windows are first-class platforms. WSL follows the Linux
contract. `bot-todo` maintains no separate OS-version table: an OS version is
supported when both UV and a supported CPython run on it. Other Unix variants
are best-effort.

The configuration locations already defined for Unix and Windows remain the
platform contract. The four Skill Targets use their native user-level roots
on every supported OS and do not change the runtime floor.

### Repository locking

Keep locking dependency-free behind one small platform adapter. Unix uses
`fcntl.flock`; Windows uses a reserved byte in the persistent lock file with
`msvcrt.locking`. Both implementations provide the previously decided shared
read lock, exclusive mutation lock, and fixed five-second acquisition timeout.

Concurrency and process-crash recovery guarantees apply on ordinary local
filesystems across all three platform families. Network, FUSE, and
synchronized filesystems are best-effort because they may weaken advisory
locking, flush, or atomic-replacement semantics.

### Verification matrix

CI runs the full suite on Linux with CPython 3.11, 3.12, 3.13, and 3.14. It
also runs the full suite on macOS and Windows at the minimum and current stable
versions, initially 3.11 and 3.14. This verifies every supported runtime and
both platform-specific locking paths without a full Cartesian matrix.
