# Inventory the existing CLI compatibility contract

Type: research
Status: resolved

## Question

What observable task-file, command, output, error, exit-code, discovery, and lifecycle behavior does the current embedded CLI implement, and which code seams can be relocated without changing that contract?

## Answer

The compatibility baseline is the current `TODO.md` plus `TODO.archive.md` pair and the observable behavior of `skills/todo/scripts/todo.py`.

### Data contract

- Format version 1 requires exact project headers, P0/P1/P2/Done section order, repository-unique `T` identifiers, one type tag, acceptance criteria or `#simple`, canonical subordinate fields, and a high-water mark above every allocated ID (`todo.py:21-59`, `551-722`).
- Blockers must reference existing tasks and cannot self-reference. A blocker satisfies `next` only when its outcome is `completed`; cancellation remains blocking (`todo.py:716-746`, `980-1001`).
- Closed tasks carry `Outcome` and ISO `Closed`; cancellation additionally requires `Reason`. The newest twenty remain in Done and older entries move to the archive (`todo.py:465-515`, `692-712`, `787-802`).
- Parsing tolerates blank lines and noncanonical field order, but every successful mutation rewrites canonical ordering and newline structure (`todo.py:94-110`, `518-632`).

### CLI contract

- Global `--root` defaults to the current working directory. There is no ancestor, Git-root, environment, or configuration discovery (`todo.py:195-208`, `1004-1062`).
- Commands are `init`, `validate`, `list`, `show`, `next`, `add`, `edit`, `claim`, `release`, `complete`, `cancel`, and `archive`. Successful output is deliberately small: fixed status text, task IDs, canonical task Markdown, list rows, or an archive count (`todo.py:1004-1113`).
- Success returns 0. `TodoError` and `OSError` print `todo: error: <message>` to stderr and return 2. Argparse help/syntax behavior uses its normal 0/2 exits; moving to a console entry point changes the displayed program name unless `prog` is fixed (`todo.py:1115-1134`).
- The current CLI has no JSON output, aggregate/config mode, delete/reopen operation, or skill installer.

### Lifecycle and durability

- IDs allocate monotonically; edits apply only to active tasks; claims record actor, local date, and branch; `next` scans P0/P1/P2 in file order while skipping claimed or blocked tasks (`todo.py:321-515`, `931-1001`).
- Individual file writes use same-directory temporary files, flush, `fsync`, and atomic replacement (`todo.py:952-977`). The two-file pair is not crash-atomic, and load-modify-save has no process lock or optimistic revision check; concurrent writers can lose updates or allocate the same ID (`todo.py:264-298`).

### Relocation seam

- Relocate the current module intact first. `main(argv) -> int`, `_build_parser`, `_run`, and `TodoStore` already separate the console entry point, parsing/dispatch, and domain/storage behavior (`todo.py:186-515`, `1004-1138`).
- The module is standard-library-only. `TodoStore.add` and `edit` currently accept `argparse.Namespace`; replacing argparse during extraction would mix packaging with a compatibility-sensitive refactor.
- Tests execute the nested script and import its module for failure injection, so relocation must update those seams while retaining behavioral assertions (`skills/todo/tests/test_todo.py:15-18`, `43-64`, `226-245`, `404-428`).
- `pyproject.toml` is only a stub: it has no console entry point, build system, package-data declaration, or dependencies. `main.py` is an unrelated placeholder. Skill assets can move independently of the task-data contract.
