"""Read, validate, and safely update one Task Repository."""

# ruff: noqa: DTZ011

from __future__ import annotations

import os
import re
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

import portalocker

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from contextlib import AbstractContextManager

#: Canonical active task filename.
TODO_FILENAME = "TODO.md"
#: Append-only archive filename.
ARCHIVE_FILENAME = "TODO.archive.md"
#: Persistent repository coordination filename.
LOCK_FILENAME = ".bot-todo.lock"
#: Fixed lock acquisition timeout in seconds.
LOCK_TIMEOUT_SECONDS = 5.0
#: Interval between lock acquisition attempts in seconds.
LOCK_CHECK_INTERVAL_SECONDS = 0.05
#: Only task data format version this release understands.
SUPPORTED_FORMAT_VERSION = 1
#: Supported task type tags.
TYPE_TAGS = {"bug", "chore", "docs", "feature", "ops"}
#: Marker tag for a task that deliberately carries no acceptance criteria.
SIMPLE_TAG = "simple"
#: Active priority section headings in selection order.
PRIORITY_HEADINGS = {
    "P0": "## P0 — Critical / Blocking",
    "P1": "## P1 — High Priority",
    "P2": "## P2 — Backlog",
}
#: Heading for recently closed tasks.
DONE_HEADING = "## Done (recent)"
#: Number of recently closed tasks kept in the active file.
DONE_LIMIT = 20
#: Minimum number of digits in a formatted task ID.
MIN_ID_WIDTH = 3
#: Number of pipe-separated parts in claim metadata.
CLAIM_PART_COUNT = 3
#: Metadata declaration stored in the active file.
METADATA_RE = re.compile(r"^<!-- todo-format: (\d+); next-id: (\d+) -->$")
#: Canonical task-line grammar.
TASK_RE = re.compile(r"^- \[([ x])\] \*\*(T(\d+))\*\* (.+)$")
#: Canonical subordinate task-field grammar.
FIELD_RE = re.compile(r"^  - ([A-Za-z ]+): (.+)$")
#: Valid task and dependency identifier grammar.
ID_RE = re.compile(r"^T\d{3,}$")
#: Valid tag grammar without its leading hash.
TAG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
#: Stable render order for subordinate task fields.
FIELD_ORDER = (
    "Acceptance",
    "Context",
    "Related",
    "Blocked by",
    "Claimed",
    "Outcome",
    "Closed",
    "Reason",
)


class TodoError(ValueError):
    """
    Report invalid todo input or an unsupported state transition.

    Args:
        message: Human-readable diagnostic.
        code: Machine-readable code from the settled error-code set.
        details: Extra machine-readable fields for this error code.

    """

    def __init__(
        self,
        message: str,
        code: str = "invalid_document",
        details: dict[str, object] | None = None,
    ) -> None:
        """
        Initialize a coded domain failure.

        Args:
            message: Human-readable diagnostic.
            code: Machine-readable code from the settled error-code set.
            details: Extra machine-readable fields merged into JSON errors.

        """
        super().__init__(message)
        #: Machine-readable code from the settled error-code set.
        self.code = code
        #: Extra machine-readable fields merged into JSON error documents.
        self.details = details or {}


@dataclass(frozen=True)
class Claim:
    """
    Hold the parsed ownership metadata of one claimed task.

    Args:
        actor: Agent or person holding the claim.
        claimed_on: ISO calendar date the claim was taken.
        branch: Working branch named by the claim.

    """

    #: Agent or person holding the claim.
    actor: str
    #: ISO calendar date the claim was taken.
    claimed_on: str
    #: Working branch named by the claim.
    branch: str


@dataclass
class Task:
    """
    Represent one canonical Markdown task.

    Args:
        task_id: Stable repository task identifier.
        title: Human-readable task title.
        priority: Active priority, or ``None`` for a closed task.
        checked: Whether the task is closed.
        tags: Ordered tags without leading hashes.
        fields: Named subordinate task fields.

    """

    #: Stable repository task identifier.
    task_id: str
    #: Human-readable task title.
    title: str
    #: Active priority, or ``None`` for a closed task.
    priority: str | None
    #: Whether the task is closed.
    checked: bool
    #: Ordered tags without leading hashes.
    tags: list[str]
    #: Named subordinate task fields.
    fields: dict[str, str] = field(default_factory=dict)

    @property
    def state(self) -> str:
        """
        Report the task lifecycle state.

        Returns:
            One of ``open``, ``completed``, or ``cancelled``.

        """
        if not self.checked:
            return "open"
        return self.fields.get("Outcome", "completed")

    @property
    def task_type(self) -> str | None:
        """
        Report the single classifying type tag.

        Returns:
            Type tag, or ``None`` when the task carries none.

        """
        return next((tag for tag in self.tags if tag in TYPE_TAGS), None)

    @property
    def user_tags(self) -> list[str]:
        """
        Report ordinary tags without the type or ``simple`` markers.

        Returns:
            Ordered tags excluding the reserved classifying tags.

        """
        return [tag for tag in self.tags if tag not in TYPE_TAGS and tag != SIMPLE_TAG]

    @property
    def simple(self) -> bool:
        """
        Report whether the task deliberately omits acceptance criteria.

        Returns:
            ``True`` when the task carries the ``simple`` marker tag.

        """
        return SIMPLE_TAG in self.tags

    @property
    def acceptance(self) -> str | None:
        """
        Report the acceptance criteria.

        Returns:
            Acceptance text, or ``None`` for a simple task.

        """
        return self.fields.get("Acceptance")

    @property
    def context(self) -> str | None:
        """
        Report the supporting context reference.

        Returns:
            Context text, or ``None`` when unset.

        """
        return self.fields.get("Context")

    @property
    def related(self) -> str | None:
        """
        Report the related-work reference.

        Returns:
            Related text, or ``None`` when unset.

        """
        return self.fields.get("Related")

    @property
    def closed_on(self) -> str | None:
        """
        Report the closing date.

        Returns:
            ISO calendar date, or ``None`` while the task is open.

        """
        return self.fields.get("Closed")

    @property
    def reason(self) -> str | None:
        """
        Report the cancellation reason.

        Returns:
            Reason text, or ``None`` unless the task was cancelled.

        """
        return self.fields.get("Reason")

    @property
    def blocked_by(self) -> list[str]:
        """
        Report the blocker task identifiers.

        Returns:
            Ordered blocker IDs, empty when the task is unblocked.

        """
        value = self.fields.get("Blocked by")
        if not value:
            return []
        return [item.strip() for item in value.split(",") if item.strip()]

    @property
    def claim(self) -> Claim | None:
        """
        Report the parsed ownership claim.

        Returns:
            Parsed claim, or ``None`` when the task is unclaimed.

        """
        value = self.fields.get("Claimed")
        if not value:
            return None
        parts = value.split(" | ")
        if len(parts) != CLAIM_PART_COUNT:
            return None
        return Claim(parts[0], parts[1], parts[2])

    def render(self) -> str:
        """
        Render the task in canonical Markdown.

        Returns:
            Canonical task Markdown without a trailing blank line.

        """
        checkbox = "x" if self.checked else " "
        tags = " ".join(f"#{tag}" for tag in self.tags)
        lines = [f"- [{checkbox}] **{self.task_id}** {self.title} {tags}"]
        lines.extend(
            f"  - {name}: {self.fields[name]}"
            for name in FIELD_ORDER
            if name in self.fields
        )
        return "\n".join(lines)


@dataclass
class TodoDocument:
    """
    Hold the parsed contents of one active task file.

    Args:
        project: Project name shown in file headings.
        next_id: Next unallocated numeric task identifier.
        active: Active tasks grouped by priority.
        done: Recently closed tasks, newest first.

    """

    #: Project name shown in file headings.
    project: str
    #: Next unallocated numeric task identifier.
    next_id: int
    #: Active tasks grouped by priority.
    active: dict[str, list[Task]]
    #: Recently closed tasks, newest first.
    done: list[Task]

    @property
    def tasks(self) -> list[Task]:
        """
        Return every task held in the active file.

        Returns:
            Tasks from active priority sections followed by Done.

        """
        return [
            *(task for priority in PRIORITY_HEADINGS for task in self.active[priority]),
            *self.done,
        ]

    def render(self) -> str:
        """
        Render the active task file.

        Returns:
            Canonical active-file Markdown.

        """
        lines = [
            f"# TODO — {self.project}",
            (
                f"<!-- todo-format: {SUPPORTED_FORMAT_VERSION};"
                f" next-id: {self.next_id} -->"
            ),
            "",
        ]
        for priority, heading in PRIORITY_HEADINGS.items():
            lines.append(heading)
            lines.extend(_render_task_collection(self.active[priority]))
        lines.append(DONE_HEADING)
        lines.extend(_render_task_collection(self.done))
        return "\n".join(lines).rstrip() + "\n"


class TaskArchive:
    """
    Append-only history of tasks retired from the active task file.

    The archive is never rewritten, never validated against the active file, and
    never consulted while deciding whether a mutation is legal. It exists so
    closed tasks stay readable after they leave the active file.

    Args:
        path: Path to the archive file.

    """

    def __init__(self, path: Path) -> None:
        """
        Initialize an archive at one path.

        Args:
            path: Path to the archive file.

        """
        #: Path to the append-only archive file.
        self.path = path

    def append(self, tasks: Sequence[Task], project: str) -> None:
        """
        Append retired tasks to the archive.

        Side Effects:
            Creates the archive when absent and appends durably.

        Args:
            tasks: Tasks leaving the active file, in retirement order.
            project: Project name used when creating the archive heading.

        """
        if not tasks:
            return
        _require_regular_or_absent(self.path)
        heading = "" if self.path.exists() else f"# TODO Archive — {project}\n"
        body = "".join(f"\n{task.render()}\n" for task in tasks)
        with self.path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(heading + body)
            handle.flush()
            os.fsync(handle.fileno())

    def find(self, task_id: str) -> Task | None:
        """
        Look up one archived task.

        Args:
            task_id: Task identifier to locate.

        Returns:
            Archived task, or ``None`` when the archive lacks it.

        Raises:
            TodoError: If the archive holds malformed task content.

        """
        _require_regular_or_absent(self.path)
        try:
            text = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        tasks = _parse_task_lines(text.splitlines()[1:], None, ARCHIVE_FILENAME)
        return next((task for task in tasks if task.task_id == task_id), None)


class RepositoryLock:
    """
    Serialize repository access with shared reads and exclusive mutations.

    Args:
        path: Path to the persistent lock file.
        timeout: Seconds to wait before reporting a conflict.

    """

    def __init__(self, path: Path, timeout: float = LOCK_TIMEOUT_SECONDS) -> None:
        """
        Initialize a lock over one repository.

        Args:
            path: Path to the persistent lock file.
            timeout: Seconds to wait before reporting a conflict.

        """
        #: Path to the persistent lock file.
        self.path = path
        #: Seconds to wait before reporting a conflict.
        self.timeout = timeout

    def shared(self) -> AbstractContextManager[None]:
        """
        Hold a shared read lock for the duration of the context.

        Returns:
            Context manager holding the shared lock.

        """
        return self._hold(portalocker.LOCK_SH)

    def exclusive(self) -> AbstractContextManager[None]:
        """
        Hold an exclusive mutation lock for the duration of the context.

        Returns:
            Context manager holding the exclusive lock.

        """
        return self._hold(portalocker.LOCK_EX)

    @contextmanager
    def _hold(self, flags: int) -> Iterator[None]:
        """
        Acquire and release the lock file with the requested flags.

        Side Effects:
            Creates the persistent lock file when absent.

        Args:
            flags: Portalocker lock flags to combine with non-blocking mode.

        Yields:
            ``None`` while the lock is held.

        Raises:
            TodoError: If the lock is contended or cannot be opened.

        """
        try:
            os.close(os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o644))
        except OSError as error:
            raise TodoError(
                f"cannot open lock file {self.path}: {error}", "io_error"
            ) from error
        lock = portalocker.Lock(
            self.path,
            mode="a+",
            flags=flags | portalocker.LOCK_NB,
            timeout=self.timeout,
            check_interval=LOCK_CHECK_INTERVAL_SECONDS,
        )
        try:
            lock.acquire()
        except portalocker.AlreadyLocked as error:
            raise TodoError(
                f"{self.path.parent} is locked by another process", "conflict"
            ) from error
        except portalocker.LockException as error:
            raise TodoError(f"cannot lock {self.path}: {error}", "io_error") from error
        try:
            yield
        finally:
            lock.release()


@dataclass(frozen=True)
class RepositorySnapshot:
    """
    Hold one coherent read of a Task Repository.

    Args:
        root: Resolved Task Repository path.
        document: Validated active-file contents.
        archive: Archive backing the snapshot's closed-task lookups.

    """

    #: Resolved Task Repository path.
    root: Path
    #: Validated active-file contents.
    document: TodoDocument
    #: Archive backing the snapshot's closed-task lookups.
    archive: TaskArchive

    def find(self, task_id: str) -> Task:
        """
        Look up one task, falling back to the archive.

        Args:
            task_id: Task identifier to locate.

        Returns:
            Matching task.

        Raises:
            TodoError: If neither the active file nor the archive has it.

        """
        # ponytail: linear scans suit Markdown backlogs; index if files grow large.
        for task in self.document.tasks:
            if task.task_id == task_id:
                return task
        archived = self.archive.find(task_id)
        if archived is None:
            raise TodoError(f"unknown task ID {task_id}", "unknown_task")
        return archived

    def critical(self) -> Task | None:
        """
        Select the highest-priority open task, blocked or claimed or not.

        Returns:
            Critical task, or ``None`` when nothing is open.

        """
        return _find_critical(self.document)

    def actionable(self) -> Task | None:
        """
        Select the first unclaimed task whose blockers completed.

        Returns:
            Actionable task, or ``None`` when none is eligible.

        """
        return _find_next(self.document)

    def is_actionable(self, task: Task) -> bool:
        """
        Report whether one task of this snapshot may be started now.

        Args:
            task: Task to test.

        Returns:
            ``True`` when the task is open, unclaimed, and unblocked.

        """
        return _is_actionable(self.document, task)


class RepositoryTransaction:
    """
    Apply one serialized mutation to a Task Repository.

    The caller obtains a transaction from :meth:`TodoStore.transaction`, which
    holds the exclusive lock across load, mutation, validation, and commit.

    Args:
        store: Repository being mutated.
        document: Validated document loaded under the exclusive lock.

    """

    def __init__(self, store: TodoStore, document: TodoDocument) -> None:
        """
        Initialize a transaction over a loaded document.

        Args:
            store: Repository being mutated.
            document: Validated document loaded under the exclusive lock.

        """
        #: Repository being mutated.
        self.store = store
        #: Document mutated by this transaction.
        self.document = document
        #: Tasks retired from Done and owed to the archive at commit.
        self._retired: list[Task] = []

    def add(
        self,
        *,
        title: str,
        priority: str,
        task_type: str,
        tags: Sequence[str] | None = None,
        acceptance: str | None = None,
        simple: bool = False,
        context: str | None = None,
        related: str | None = None,
        blocked_by: Sequence[str] | None = None,
    ) -> Task:
        """
        Allocate and add one active task.

        Keyword Args:
            title: Human-readable task title.
            priority: Target priority section.
            task_type: Required type tag.
            tags: Additional tags without leading hashes.
            acceptance: Acceptance criteria text.
            simple: Whether the task needs no acceptance criteria.
            context: Context field text.
            related: Related field text.
            blocked_by: Blocking task identifiers.

        Returns:
            Added task.

        Raises:
            TodoError: If neither acceptance criteria nor ``simple`` is given.

        """
        if not acceptance and not simple:
            raise TodoError("add requires --acceptance or --simple", "usage")
        task_tags = [task_type, *_normalize_tags(tags or [])]
        if simple:
            task_tags.append(SIMPLE_TAG)
        fields = _optional_fields(
            (("Acceptance", acceptance), ("Context", context), ("Related", related))
        )
        if blocked_by:
            fields["Blocked by"] = ", ".join(blocked_by)
        task = Task(
            task_id=_format_id(self.document.next_id),
            title=_require_title(title),
            priority=priority,
            checked=False,
            tags=_deduplicate(task_tags),
            fields=fields,
        )
        self.document.next_id += 1
        self.document.active[priority].append(task)
        return task

    def edit(
        self,
        task_id: str,
        *,
        title: str | None = None,
        priority: str | None = None,
        task_type: str | None = None,
        add_tags: Sequence[str] | None = None,
        remove_tags: Sequence[str] | None = None,
        acceptance: str | None = None,
        context: str | None = None,
        related: str | None = None,
        blocked_by: Sequence[str] | None = None,
        clear_acceptance: bool = False,
        clear_context: bool = False,
        clear_related: bool = False,
    ) -> Task:
        """
        Update supported fields on one active task.

        Args:
            task_id: Task to update.

        Keyword Args:
            title: Replacement title.
            priority: Replacement priority section.
            task_type: Replacement type tag.
            add_tags: Tags to add.
            remove_tags: Non-type tags to remove.
            acceptance: Replacement acceptance criteria.
            context: Replacement context text.
            related: Replacement related text.
            blocked_by: Replacement blockers, or an empty sequence to clear
                them; ``None`` leaves existing blockers untouched.
            clear_acceptance: Drop acceptance criteria and mark the task simple.
            clear_context: Drop the context field.
            clear_related: Drop the related field.

        Returns:
            Updated task.

        Raises:
            TodoError: If the task is closed or a type tag is removed directly.

        """
        task = self._find_active(task_id)
        if task.checked or task.priority is None:
            raise TodoError("closed tasks cannot be edited", "invalid_transition")
        if title:
            task.title = _require_title(title)
        if priority and priority != task.priority:
            self.document.active[task.priority].remove(task)
            task.priority = priority
            self.document.active[task.priority].append(task)
        if task_type:
            task.tags = [tag for tag in task.tags if tag not in TYPE_TAGS]
            task.tags.insert(0, task_type)
        for tag in _normalize_tags(add_tags or []):
            if tag not in task.tags:
                task.tags.append(tag)
        for tag in _normalize_tags(remove_tags or []):
            if tag in TYPE_TAGS:
                raise TodoError(
                    "use --type to replace a type tag", "invalid_transition"
                )
            if tag in task.tags:
                task.tags.remove(tag)
        for field_name, value, clear in (
            ("Acceptance", acceptance, clear_acceptance),
            ("Context", context, clear_context),
            ("Related", related, clear_related),
        ):
            if clear:
                task.fields.pop(field_name, None)
                if field_name == "Acceptance" and SIMPLE_TAG not in task.tags:
                    task.tags.append(SIMPLE_TAG)
            elif value:
                task.fields[field_name] = _require_text(value, field_name)
                if field_name == "Acceptance" and SIMPLE_TAG in task.tags:
                    task.tags.remove(SIMPLE_TAG)
        if blocked_by is not None:
            if blocked_by:
                task.fields["Blocked by"] = ", ".join(blocked_by)
            else:
                task.fields.pop("Blocked by", None)
        return task

    def claim(self, task_id: str, actor: str, branch: str | None) -> Task:
        """
        Record an advisory claim on an active task.

        Args:
            task_id: Task to claim.
            actor: Short claimant label.
            branch: Branch override, or ``None`` to detect it.

        Returns:
            Claimed task.

        Raises:
            TodoError: If the task is closed or already claimed.

        """
        task = self._find_active(task_id)
        _require_open(task)
        if "Claimed" in task.fields:
            raise TodoError(f"{task_id} is already claimed", "invalid_transition")
        branch_name = branch or _current_branch(self.store.root)
        actor_name = _require_text(actor, "actor")
        task.fields["Claimed"] = (
            f"{actor_name} | {date.today().isoformat()} | {branch_name}"
        )
        return task

    def release(self, task_id: str) -> Task:
        """
        Remove an advisory claim from an active task.

        Args:
            task_id: Task whose claim should be removed.

        Returns:
            Released task.

        Raises:
            TodoError: If the task is closed or unclaimed.

        """
        task = self._find_active(task_id)
        _require_open(task)
        if "Claimed" not in task.fields:
            raise TodoError(f"{task_id} is not claimed", "invalid_transition")
        task.fields.pop("Claimed")
        return task

    def close(self, task_id: str, outcome: str, reason: str | None = None) -> Task:
        """
        Complete or cancel an active task.

        Args:
            task_id: Task to close.
            outcome: Terminal outcome, ``completed`` or ``cancelled``.
            reason: Required cancellation reason.

        Returns:
            Closed task.

        Raises:
            TodoError: If the task is closed or a cancellation lacks a reason.

        """
        task = self._find_active(task_id)
        _require_open(task)
        if outcome == "cancelled" and not reason:
            raise TodoError("cancellation requires a reason", "invalid_transition")
        if task.priority is None:
            raise TodoError(f"{task.task_id} is closed", "invalid_transition")
        self.document.active[task.priority].remove(task)
        task.priority = None
        task.checked = True
        task.fields.pop("Claimed", None)
        task.fields["Outcome"] = outcome
        task.fields["Closed"] = date.today().isoformat()
        if reason:
            task.fields["Reason"] = _require_text(reason, "reason")
        self.document.done.insert(0, task)
        self.retire_overflow()
        return task

    def retire_overflow(self) -> int:
        """
        Move Done entries beyond the retention limit toward the archive.

        Returns:
            Number of tasks retired by this call.

        """
        retired = _archive_overflow(self.document)
        self._retired.extend(retired)
        return len(retired)

    def commit(self) -> None:
        """
        Validate and durably publish the mutated document.

        Side Effects:
            Appends retired tasks to the archive, then atomically replaces the
            active task file.

        Raises:
            TodoError: If the mutated document violates the format contract.

        """
        _validate_document(self.document)
        text = self.document.render()
        _validate_document(_parse_document(text))
        # ponytail: a crash between the append and the replace can duplicate an
        # archive entry; dedupe on append if that ever matters.
        self.store.archive.append(self._retired, self.document.project)
        _write_document(self.store.todo_path, text)

    def _find_active(self, task_id: str) -> Task:
        """
        Find a task held in the active file.

        Args:
            task_id: Task identifier to locate.

        Returns:
            Matching task.

        Raises:
            TodoError: If the active file lacks the identifier.

        """
        for task in self.document.tasks:
            if task.task_id == task_id:
                return task
        raise TodoError(f"unknown task ID {task_id}", "unknown_task")


class TodoStore:
    """
    Own the canonical files, coordination, and durability of one repository.

    Args:
        root: Task Repository root containing the canonical files.
        lock_timeout: Seconds to wait before reporting a lock conflict.

    """

    def __init__(self, root: Path, lock_timeout: float = LOCK_TIMEOUT_SECONDS) -> None:
        """
        Initialize paths and coordination for one Task Repository.

        Args:
            root: Task Repository root containing the canonical files.
            lock_timeout: Seconds to wait before reporting a lock conflict.

        """
        #: Resolved Task Repository root.
        self.root = root.resolve()
        #: Path to the canonical active task file.
        self.todo_path = self.root / TODO_FILENAME
        #: Append-only archive beside the active task file.
        self.archive = TaskArchive(self.root / ARCHIVE_FILENAME)
        #: Coordination lock serializing access to this repository.
        self.lock = RepositoryLock(self.root / LOCK_FILENAME, lock_timeout)

    @classmethod
    def discover(cls, start: Path) -> TodoStore:
        """
        Find the nearest Task Repository at or above one directory.

        Args:
            start: Directory to search from.

        Returns:
            Store for the nearest ancestor holding an active task file.

        Raises:
            TodoError: If no ancestor holds an active task file.

        """
        resolved = start.resolve()
        for candidate in (resolved, *resolved.parents):
            if os.path.lexists(candidate / TODO_FILENAME):
                return cls(candidate)
        raise TodoError(
            f"no task repository at or above {resolved}", "repository_not_found"
        )

    def initialize(self, project: str | None = None) -> None:
        """
        Create an empty active task file.

        Side Effects:
            Creates the repository directory and ``TODO.md``.

        Args:
            project: Project name to place in file headings. ``None`` uses
                the repository directory basename.

        Raises:
            TodoError: If the active task file already exists.

        """
        name = _require_text(
            project if project is not None else self.root.name,
            "project",
        )
        self.root.mkdir(parents=True, exist_ok=True)
        with self.lock.exclusive():
            if os.path.lexists(self.todo_path):
                raise TodoError(
                    f"{self.todo_path} already exists", "already_initialized"
                )
            document = TodoDocument(
                project=name,
                next_id=1,
                active={priority: [] for priority in PRIORITY_HEADINGS},
                done=[],
            )
            _write_document(self.todo_path, document.render())

    def snapshot(self) -> RepositorySnapshot:
        """
        Read one coherent view of the repository.

        Returns:
            Validated snapshot taken under a shared lock.

        Raises:
            TodoError: If the repository is missing, unsafe, or malformed.

        """
        self._require_repository()
        with self.lock.shared():
            return RepositorySnapshot(self.root, self._read_document(), self.archive)

    @contextmanager
    def transaction(self) -> Iterator[RepositoryTransaction]:
        """
        Hold the exclusive lock across load, mutation, and commit.

        Side Effects:
            Commits the mutated document when the context exits cleanly.

        Yields:
            Transaction over the loaded document.

        Raises:
            TodoError: If the repository is missing, unsafe, or malformed.

        """
        self._require_repository()
        with self.lock.exclusive():
            transaction = RepositoryTransaction(self, self._read_document())
            yield transaction
            transaction.commit()

    def _require_repository(self) -> None:
        """
        Require an existing repository directory before locking it.

        Raises:
            TodoError: If the repository directory is missing.

        """
        if not self.root.is_dir():
            raise TodoError(
                f"no task repository at {self.root}", "repository_not_found"
            )

    def _read_document(self) -> TodoDocument:
        """
        Parse and validate the active task file.

        Returns:
            Parsed, validated document.

        Raises:
            TodoError: If the file is missing, unsafe, or malformed.

        """
        try:
            info = os.lstat(self.todo_path)
        except FileNotFoundError as error:
            raise TodoError(
                f"{self.root} has no {TODO_FILENAME}", "not_initialized"
            ) from error
        if not stat.S_ISREG(info.st_mode):
            raise TodoError(f"{self.todo_path} is not a regular file")
        _require_regular_or_absent(self.archive.path)
        document = _parse_document(self.todo_path.read_text(encoding="utf-8"))
        _validate_document(document)
        return document


def _render_task_collection(tasks: Sequence[Task]) -> list[str]:
    """
    Render a collection with canonical blank-line separation.

    Args:
        tasks: Tasks to render.

    Returns:
        Markdown lines including the leading section separator.

    """
    lines = [""]
    for task in tasks:
        lines.extend(task.render().splitlines())
        lines.append("")
    return lines


def _parse_document(todo_text: str) -> TodoDocument:
    """
    Parse active-file Markdown into one document.

    Args:
        todo_text: Active-file Markdown.

    Returns:
        Parsed document pending semantic validation.

    Raises:
        TodoError: If structural Markdown is malformed or the declared task
            data format version is unsupported.

    """
    todo_lines = todo_text.splitlines()
    if len(todo_lines) < MIN_ID_WIDTH or not todo_lines[0].startswith("# TODO — "):
        raise TodoError("TODO.md:1 must be '# TODO — <project>'")
    project = todo_lines[0].removeprefix("# TODO — ").strip()
    metadata = METADATA_RE.fullmatch(todo_lines[1])
    if not metadata:
        raise TodoError("TODO.md:2 must declare todo-format 1 and next-id")
    version = int(metadata.group(1))
    if version != SUPPORTED_FORMAT_VERSION:
        raise TodoError(
            f"unsupported task data format version {version}",
            "unsupported_format_version",
            {"encountered": version, "supported": [SUPPORTED_FORMAT_VERSION]},
        )
    headings = [*PRIORITY_HEADINGS.values(), DONE_HEADING]
    indices: list[int] = []
    for heading in headings:
        try:
            indices.append(todo_lines.index(heading))
        except ValueError as error:
            raise TodoError(f"TODO.md is missing section '{heading}'") from error
    if indices != sorted(indices):
        raise TodoError("TODO.md priority sections are out of order")
    if any(line for line in todo_lines[2 : indices[0]]):
        raise TodoError("TODO.md has unsupported content before P0")
    unknown_headings = [
        line for line in todo_lines if line.startswith("## ") and line not in headings
    ]
    if unknown_headings:
        raise TodoError(f"TODO.md has unsupported section '{unknown_headings[0]}'")
    active: dict[str, list[Task]] = {}
    priorities = list(PRIORITY_HEADINGS)
    for position, priority in enumerate(priorities):
        active[priority] = _parse_task_lines(
            todo_lines[indices[position] + 1 : indices[position + 1]],
            priority,
            TODO_FILENAME,
        )
    done = _parse_task_lines(todo_lines[indices[-1] + 1 :], None, TODO_FILENAME)
    return TodoDocument(project, int(metadata.group(2)), active, done)


def _parse_task_lines(
    lines: Sequence[str], priority: str | None, source: str
) -> list[Task]:
    """
    Parse task blocks from one section.

    Args:
        lines: Markdown lines within a task section.
        priority: Active priority, or ``None`` for closed tasks.
        source: Filename used in diagnostics.

    Returns:
        Parsed tasks.

    Raises:
        TodoError: If a line violates the canonical task grammar.

    """
    tasks: list[Task] = []
    current: Task | None = None
    for line in lines:
        if not line:
            continue
        task_match = TASK_RE.fullmatch(line)
        if task_match:
            checked = task_match.group(1) == "x"
            title, tags = _split_title_and_tags(task_match.group(4), source)
            current = Task(task_match.group(2), title, priority, checked, tags)
            tasks.append(current)
            continue
        field_match = FIELD_RE.fullmatch(line)
        if field_match and current:
            name, value = field_match.groups()
            if name not in FIELD_ORDER:
                raise TodoError(f"{source} has unsupported field '{name}'")
            if name in current.fields:
                raise TodoError(f"{source} repeats field '{name}' on {current.task_id}")
            current.fields[name] = value
            continue
        raise TodoError(f"{source} has malformed task content: {line}")
    return tasks


def _split_title_and_tags(value: str, source: str) -> tuple[str, list[str]]:
    """
    Separate a task title from its trailing tags.

    Args:
        value: Task-line content after the identifier.
        source: Filename used in diagnostics.

    Returns:
        Title and ordered tags without leading hashes.

    Raises:
        TodoError: If no trailing tags exist.

    """
    parts = value.split()
    first_tag = next(
        (index for index, part in enumerate(parts) if part.startswith("#")), None
    )
    if first_tag is None:
        raise TodoError(f"{source} task is missing its required type tag")
    title = " ".join(parts[:first_tag]).strip()
    raw_tags = parts[first_tag:]
    if not title or any(not part.startswith("#") for part in raw_tags):
        raise TodoError(f"{source} task title or tags are malformed")
    tags = [part.removeprefix("#") for part in raw_tags]
    _normalize_tags(tags)
    return title, tags


def _validate_document(document: TodoDocument) -> None:
    """
    Enforce task identity and lifecycle invariants.

    Args:
        document: Parsed document to validate.

    Raises:
        TodoError: If any invariant is violated.

    """
    if not document.project:
        raise TodoError("project name must not be empty")
    seen: dict[str, Task] = {}
    for task in document.tasks:
        if not ID_RE.fullmatch(task.task_id):
            raise TodoError(f"invalid task ID {task.task_id}")
        if task.task_id in seen:
            raise TodoError(f"duplicate task ID {task.task_id}")
        seen[task.task_id] = task
        type_tags = TYPE_TAGS.intersection(task.tags)
        if len(type_tags) != 1:
            raise TodoError(f"{task.task_id} must have exactly one type tag")
        if len(task.tags) != len(set(task.tags)):
            raise TodoError(f"{task.task_id} repeats a tag")
        for field_name, value in task.fields.items():
            _require_text(value, f"{task.task_id} {field_name}")
        if "Claimed" in task.fields:
            _validate_claim(task)
        if "Acceptance" not in task.fields and "simple" not in task.tags:
            raise TodoError(f"{task.task_id} requires Acceptance or #simple")
        if task.priority is None:
            if not task.checked:
                raise TodoError(f"closed task {task.task_id} must be checked")
            if task.fields.get("Outcome") not in {"completed", "cancelled"}:
                raise TodoError(f"closed task {task.task_id} requires a valid Outcome")
            if "Closed" not in task.fields:
                raise TodoError(f"closed task {task.task_id} requires a Closed date")
            _validate_date(task.task_id, "Closed", task.fields["Closed"])
            if (
                task.fields.get("Outcome") == "cancelled"
                and "Reason" not in task.fields
            ):
                raise TodoError(f"cancelled task {task.task_id} requires a Reason")
        elif task.checked:
            raise TodoError(f"active task {task.task_id} must be unchecked")
        elif "Outcome" in task.fields or "Closed" in task.fields:
            raise TodoError(f"active task {task.task_id} has terminal fields")
    maximum = max((int(task.task_id[1:]) for task in document.tasks), default=0)
    if document.next_id <= maximum:
        raise TodoError(f"next-id must be greater than {maximum}")
    for task in document.tasks:
        blockers = _blockers(task)
        if task.task_id in blockers:
            raise TodoError(f"{task.task_id} cannot block itself")
        for blocker in blockers:
            if blocker not in seen:
                raise TodoError(f"{task.task_id} references unknown blocker {blocker}")


def _blockers(task: Task) -> list[str]:
    """
    Return parsed blocker IDs for a task.

    Args:
        task: Task whose blockers should be parsed.

    Returns:
        Ordered blocker IDs.

    Raises:
        TodoError: If a blocker is malformed.

    """
    value = task.fields.get("Blocked by")
    if not value:
        return []
    blockers = [item.strip() for item in value.split(",")]
    invalid = next((item for item in blockers if not ID_RE.fullmatch(item)), None)
    if invalid:
        raise TodoError(f"{task.task_id} has invalid blocker {invalid}")
    return blockers


def _validate_claim(task: Task) -> None:
    """
    Require actor, date, and branch claim metadata.

    Args:
        task: Claimed task to validate.

    Raises:
        TodoError: If claim metadata is malformed.

    """
    parts = task.fields["Claimed"].split(" | ")
    if len(parts) != CLAIM_PART_COUNT or any(not part.strip() for part in parts):
        raise TodoError(f"{task.task_id} has malformed Claimed metadata")
    _validate_date(task.task_id, "Claimed", parts[1])


def _validate_date(task_id: str, field_name: str, value: str) -> None:
    """
    Require an ISO calendar date.

    Args:
        task_id: Task identifier used in diagnostics.
        field_name: Field name used in diagnostics.
        value: Candidate date.

    Raises:
        TodoError: If the date is not valid ``YYYY-MM-DD`` text.

    """
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise TodoError(f"{task_id} has invalid {field_name} date {value}") from error
    if parsed.isoformat() != value:
        raise TodoError(f"{task_id} has invalid {field_name} date {value}")


def _archive_overflow(document: TodoDocument) -> list[Task]:
    """
    Remove Done entries beyond the retention limit.

    A closed task still named by an open task's blockers is retained past the
    limit, so every blocker reference stays resolvable from the active file
    alone and a cancelled blocker keeps blocking.

    Args:
        document: Document to mutate.

    Returns:
        Tasks removed from Done, in retirement order.

    """
    referenced = {
        blocker
        for task in document.tasks
        if task.priority is not None
        for blocker in _blockers(task)
    }
    overflow = document.done[DONE_LIMIT:]
    retired = [task for task in overflow if task.task_id not in referenced]
    document.done = document.done[:DONE_LIMIT] + [
        task for task in overflow if task.task_id in referenced
    ]
    return retired


def _format_id(number: int) -> str:
    """
    Format a numeric ID with a minimum width of three digits.

    Args:
        number: Positive identifier number.

    Returns:
        Canonical task identifier.

    """
    return f"T{number:0{MIN_ID_WIDTH}d}"


def _normalize_tags(tags: Sequence[str]) -> list[str]:
    """
    Validate and normalize tags without leading hashes.

    Args:
        tags: Raw tags.

    Returns:
        Normalized tags.

    Raises:
        TodoError: If any tag is malformed.

    """
    normalized = [tag.removeprefix("#") for tag in tags]
    invalid = next((tag for tag in normalized if not TAG_RE.fullmatch(tag)), None)
    if invalid is not None:
        raise TodoError(f"invalid tag '{invalid}'")
    return normalized


def _deduplicate(values: Sequence[str]) -> list[str]:
    """
    Return values once while retaining their first-seen order.

    Args:
        values: Values to deduplicate.

    Returns:
        Ordered unique values.

    """
    return list(dict.fromkeys(values))


def _require_text(value: str, name: str) -> str:
    """
    Return stripped non-empty single-line text.

    Args:
        value: Candidate text.
        name: Field name used in diagnostics.

    Returns:
        Stripped text.

    Raises:
        TodoError: If text is empty or contains a newline.

    """
    stripped = value.strip()
    if not stripped or "\n" in stripped or "\r" in stripped:
        raise TodoError(f"{name} must be non-empty single-line text")
    return stripped


def _require_title(value: str) -> str:
    """
    Return an unambiguous title without hashtag-like tokens.

    Args:
        value: Candidate task title.

    Returns:
        Validated title.

    Raises:
        TodoError: If the title could be reinterpreted as tags.

    """
    title = _require_text(value, "title")
    if any(part.startswith("#") for part in title.split()):
        raise TodoError("title tokens cannot start with '#'; use --tag or --related")
    return title


def _optional_fields(candidates: Sequence[tuple[str, str | None]]) -> dict[str, str]:
    """
    Collect populated values as canonical fields.

    Args:
        candidates: Canonical field names paired with their raw values.

    Returns:
        Canonically named populated fields.

    """
    return {name: _require_text(value, name) for name, value in candidates if value}


def _require_open(task: Task) -> None:
    """
    Require an active task.

    Args:
        task: Task to inspect.

    Raises:
        TodoError: If the task is closed.

    """
    if task.checked or task.priority is None:
        raise TodoError(f"{task.task_id} is closed", "invalid_transition")


def _require_regular_or_absent(path: Path) -> None:
    """
    Require a path to be either absent or a regular file.

    Args:
        path: Path that bot-todo may read or replace.

    Raises:
        TodoError: If the path exists but is not a regular file.

    """
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(info.st_mode):
        raise TodoError(f"{path} is not a regular file")


def _current_branch(root: Path) -> str:
    """
    Return the current Git branch or a portable fallback.

    Args:
        root: Repository root.

    Returns:
        Branch name, or ``no-branch`` outside Git.

    """
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=root,
        capture_output=True,
        check=False,
        text=True,
    )
    return result.stdout.strip() or "no-branch"


def _write_document(path: Path, content: str) -> None:
    """
    Atomically replace one UTF-8 text file, preserving its permissions.

    Side Effects:
        Creates a temporary sibling file and replaces the target path.

    Args:
        path: Target file path.
        content: Complete replacement content.

    """
    mode: int | None = None
    try:
        mode = stat.S_IMODE(os.lstat(path).st_mode)
    except FileNotFoundError:
        pass
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}."
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        if mode is not None:
            temporary_path.chmod(mode)
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()
    _fsync_directory(path.parent)


def _fsync_directory(path: Path) -> None:
    """
    Flush a directory entry so a rename survives a crash.

    Side Effects:
        Opens and synchronizes the directory when the platform allows it.

    Args:
        path: Directory whose entries were just replaced.

    """
    # ponytail: Windows cannot open a directory for fsync; the replace is still
    # atomic there, only the ordering guarantee is weaker.
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _is_actionable(document: TodoDocument, task: Task) -> bool:
    """
    Report whether one open task is unclaimed and fully unblocked.

    A cancelled blocker never satisfies a dependency, so a task blocked by one
    stays unactionable.

    Args:
        document: Validated todo document resolving blocker references.
        task: Task to test.

    Returns:
        ``True`` when the task may be started now.

    """
    if task.checked or "Claimed" in task.fields:
        return False
    # ponytail: rebuilds the index per call, so scanning a document is O(n^2);
    # hoist the index into the caller if a backlog ever grows large enough.
    tasks = {other.task_id: other for other in document.tasks}
    return all(
        tasks[blocker].fields.get("Outcome") == "completed"
        for blocker in _blockers(task)
    )


def _find_critical(document: TodoDocument) -> Task | None:
    """
    Select the highest-priority open task regardless of claims or blockers.

    Args:
        document: Validated todo document.

    Returns:
        Critical task, or ``None`` when nothing is open.

    """
    for priority in PRIORITY_HEADINGS:
        for task in document.active[priority]:
            return task
    return None


def _find_next(document: TodoDocument) -> Task | None:
    """
    Select the first unclaimed task whose blockers completed.

    Args:
        document: Validated todo document.

    Returns:
        Next task, or ``None`` when none is eligible.

    """
    for priority in PRIORITY_HEADINGS:
        for task in document.active[priority]:
            if _is_actionable(document, task):
                return task
    return None
