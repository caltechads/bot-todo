"""Manage canonical repository task files."""

from __future__ import annotations

import argparse
import inspect
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, NoReturn

from bot_todo import package_version
from bot_todo.config import CONFIG_ENV_VAR, RepositoryCollection
from bot_todo.repository import (
    PRIORITY_HEADINGS,
    TYPE_TAGS,
    Task,
    TodoError,
    TodoStore,
)
from bot_todo.skill_installation import TARGET_ROOTS, SkillInstaller

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from bot_todo.repository import RepositorySnapshot

#: Executable name used in help output and diagnostics.
PROGRAM_NAME = "bot-todo"
#: Compatibility version of machine-readable success and error documents.
JSON_SCHEMA_VERSION = 1
#: Exit status for an operational, domain, data, or filesystem failure.
EXIT_FAILURE = 1
#: Exit status for a usage failure.
EXIT_USAGE = 2
#: Exit status for an aggregate query with any failed repository.
EXIT_AGGREGATE = 3
#: Exit status per error code, defaulting to ``EXIT_FAILURE``.
EXIT_CODES = {"usage": EXIT_USAGE, "aggregate_partial_failure": EXIT_AGGREGATE}
#: Commands the ``--all`` selector supports.
AGGREGATE_COMMANDS = frozenset({"list", "critical", "actionable"})
#: Whether this interpreter's argparse accepts the ``color`` keyword.
SUPPORTS_COLOR_OPTION = (
    "color" in inspect.signature(argparse.ArgumentParser.__init__).parameters
)
#: Options whose presence makes an ``edit`` request a real change.
EDIT_OPTIONS = (
    "title",
    "priority",
    "type",
    "add_tag",
    "remove_tag",
    "acceptance",
    "context",
    "related",
    "blocked_by",
    "simple",
    "clear_context",
    "clear_related",
    "clear_blockers",
)


class _Parser(argparse.ArgumentParser):
    """
    Reject long-option abbreviation and ANSI styling on every parser.

    Args:
        *args: Positional arguments forwarded to ``ArgumentParser``.

    Keyword Args:
        **kwargs: Keyword arguments forwarded to ``ArgumentParser``.

    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Configure one parser with the settled argument-parsing policy.

        Args:
            *args: Positional arguments forwarded to ``ArgumentParser``.

        Keyword Args:
            **kwargs: Keyword arguments forwarded to ``ArgumentParser``.

        """
        kwargs.setdefault("allow_abbrev", False)
        if SUPPORTS_COLOR_OPTION:
            kwargs.setdefault("color", False)
        super().__init__(*args, **kwargs)

    def error(self, message: str) -> NoReturn:
        """
        Route a parse failure into the shared error path.

        Args:
            message: Diagnostic produced by argparse.

        Raises:
            TodoError: Always, so the selected renderer reports the failure.

        """
        raise TodoError(message, "usage")


@dataclass(frozen=True)
class CommandOutcome:
    """
    Carry one command result in both output formats.

    Args:
        data: Machine-readable ``data`` object for JSON mode.
        human: Human-readable text, empty when the command prints nothing.

    """

    #: Machine-readable ``data`` object for JSON mode.
    data: dict[str, Any] = field(default_factory=dict)
    #: Human-readable text, empty when the command prints nothing.
    human: str = ""


@dataclass(frozen=True)
class SelectedRepository:
    """
    Name the single Task Repository one command operates on.

    Args:
        store: Store for the resolved repository.
        name: Configured Repository Name, or ``None`` when unconfigured.

    """

    #: Store for the resolved repository.
    store: TodoStore
    #: Configured Repository Name, or ``None`` when unconfigured.
    name: str | None


class RepositorySelector:
    """
    Resolve the settled selector options into one Task Repository.

    Configuration is loaded only for ``--repo`` and ``--all``; an explicit
    ``--root`` and local discovery never read it and report a ``None``
    Repository Name.

    Args:
        root: Exact repository path from ``--root``.
        repo: Configured Repository Name from ``--repo``.
        aggregate: Whether ``--all`` selected the whole Repository Collection.
        config: Configuration path from ``--config``.

    """

    def __init__(
        self,
        root: Path | None,
        repo: str | None,
        aggregate: bool,
        config: Path | None,
    ) -> None:
        """
        Initialize a selector over one command's selector options.

        Args:
            root: Exact repository path from ``--root``.
            repo: Configured Repository Name from ``--repo``.
            aggregate: Whether ``--all`` selected the whole collection.
            config: Configuration path from ``--config``.

        """
        #: Exact repository path from ``--root``.
        self.root = root
        #: Configured Repository Name from ``--repo``.
        self.repo = repo
        #: Whether ``--all`` selected the whole Repository Collection.
        self.aggregate = aggregate
        #: Configuration path from ``--config``.
        self.config = config

    def validate(self, command: str) -> None:
        """
        Reject the selector combinations the contract forbids.

        Args:
            command: Command being run.

        Raises:
            TodoError: If the selector options do not suit the command.

        """
        if command == "install-skill":
            if self.root or self.repo or self.aggregate or self.config:
                raise TodoError(
                    "install-skill accepts no repository selector or configuration",
                    "usage",
                )
            return
        if self.config is not None and self.repo is None and not self.aggregate:
            raise TodoError("--config requires --repo or --all", "usage")
        if self.aggregate and command not in AGGREGATE_COMMANDS:
            raise TodoError(f"--all does not support {command}", "usage")

    def collection(self) -> RepositoryCollection:
        """
        Load the configured Repository Collection.

        Side Effects:
            Reads the configuration file.

        Returns:
            Every configured Repository Entry in configuration order.

        Raises:
            TodoError: If configuration is missing or invalid.

        """
        return RepositoryCollection.load(self._explicit())

    def select(self, command: str) -> SelectedRepository:
        """
        Resolve the Task Repository for one command.

        Side Effects:
            Reads configuration for ``--repo`` and creates a configured
            repository directory for ``init``.

        Args:
            command: Command being run, which decides ``init`` behavior.

        Returns:
            Selected repository and its Repository Name.

        Raises:
            TodoError: If configuration or discovery cannot resolve one
                repository.

        """
        if self.repo is not None:
            return self._configured(self.repo, command)
        if self.root is not None:
            return SelectedRepository(TodoStore(self.root), None)
        if command == "init":
            return SelectedRepository(TodoStore(Path.cwd()), None)
        return SelectedRepository(TodoStore.discover(Path.cwd()), None)

    def _configured(self, repo: str, command: str) -> SelectedRepository:
        """
        Resolve one configured Repository Entry.

        A configured path may not exist yet, so ``init`` creates it.

        Side Effects:
            Reads configuration and may create the repository directory.

        Args:
            repo: Repository Name to resolve.
            command: Command being run.

        Returns:
            Selected repository carrying its Repository Name.

        Raises:
            TodoError: If configuration is invalid or the entry is unknown.

        """
        entry = self.collection().entry(repo)
        if command == "init":
            entry.path.mkdir(parents=True, exist_ok=True)
        return SelectedRepository(TodoStore(entry.path), entry.name)

    def _explicit(self) -> Path | None:
        """
        Resolve the explicitly requested configuration path.

        ``--config`` overrides ``BOT_TODO_CONFIG``; neither means the platform
        default applies.

        Returns:
            Explicit configuration path, or ``None`` when none was requested.

        """
        if self.config is not None:
            return self.config
        environment = os.environ.get(CONFIG_ENV_VAR)
        return Path(environment).expanduser() if environment else None


class TaskPresenter:
    """
    Render one repository's tasks in both output formats.

    Args:
        name: Configured Repository Name, or ``None`` when unconfigured.
        path: Resolved Task Repository path.

    """

    def __init__(self, name: str | None, path: Path) -> None:
        """
        Initialize a presenter bound to one repository's provenance.

        Args:
            name: Configured Repository Name, or ``None`` when unconfigured.
            path: Resolved Task Repository path.

        """
        #: Configured Repository Name, or ``None`` when unconfigured.
        self.name = name
        #: Resolved Task Repository path.
        self.path = path

    def repository(self) -> dict[str, Any]:
        """
        Build the repository provenance object.

        Returns:
            Nullable Repository Name and absolute resolved path.

        """
        return {"name": self.name, "path": str(self.path)}

    def as_json(self, task: Task, *, actionable: bool) -> dict[str, Any]:
        """
        Project one task into a JSON Schema 1 Task object.

        Args:
            task: Task to project.

        Keyword Args:
            actionable: Whether the task may be started now.

        Returns:
            Task object carrying every documented key.

        """
        claim = task.claim
        return {
            "repository": self.repository(),
            "id": task.task_id,
            "title": task.title,
            "state": task.state,
            "priority": task.priority,
            "type": task.task_type,
            "tags": task.user_tags,
            "simple": task.simple,
            "acceptance": task.acceptance,
            "context": task.context,
            "related": task.related,
            "blocked_by": task.blocked_by,
            "claim": None
            if claim is None
            else {
                "actor": claim.actor,
                "claimed_on": claim.claimed_on,
                "branch": claim.branch,
            },
            "actionable": actionable,
            "closed_on": task.closed_on,
            "reason": task.reason,
        }

    def summary_line(self, task: Task) -> str:
        """
        Build one concise human task summary.

        Args:
            task: Task to summarize.

        Returns:
            Single-line summary.

        """
        return f"{task.task_id} {task.priority or task.state} {task.title}"

    def aggregate_line(self, task: Task) -> str:
        """
        Build one aggregate human summary carrying its provenance.

        Repository-local task IDs are ambiguous across repositories, so an
        aggregate row names its repository. The punctuation is not contractual.
        Every aggregate row comes from configuration and therefore has a name.

        Args:
            task: Task to summarize.

        Returns:
            Single-line summary prefixed with the Repository Name.

        """
        return f"{self.name} {self.summary_line(task)}"


class CommandRunner:
    """
    Execute one parsed command against a selected Task Repository.

    Args:
        selected: Repository the command operates on.

    """

    def __init__(self, selected: SelectedRepository) -> None:
        """
        Initialize a runner bound to one repository.

        Args:
            selected: Repository the command operates on.

        """
        #: Store for the selected repository.
        self.store = selected.store
        #: Presenter carrying the selected repository's provenance.
        self.presenter = TaskPresenter(selected.name, selected.store.root)

    def run(self, command: str, arguments: argparse.Namespace) -> CommandOutcome:
        """
        Dispatch one command to its handler.

        Side Effects:
            Reads and may update the selected repository's task files.

        Args:
            command: Command name.
            arguments: Parsed CLI arguments.

        Returns:
            Result in both output formats.

        """
        handlers = {
            "init": self._init,
            "validate": self._validate,
            "list": self._list,
            "show": self._show,
            "critical": self._critical,
            "actionable": self._actionable,
            "add": self._add,
            "edit": self._edit,
            "claim": self._claim,
            "release": self._release,
            "complete": self._complete,
            "cancel": self._cancel,
            "archive": self._archive,
        }
        return handlers[command](arguments)

    def _init(self, arguments: argparse.Namespace) -> CommandOutcome:
        """
        Create the canonical task file.

        Side Effects:
            Writes a new ``TODO.md``.

        Args:
            arguments: Parsed CLI arguments.

        Returns:
            Repository provenance and a short status line.

        """
        self.store.initialize(arguments.name)
        return CommandOutcome(
            {"repository": self.presenter.repository()}, "initialized"
        )

    def _validate(self, _arguments: argparse.Namespace) -> CommandOutcome:
        """
        Validate the canonical task file.

        Side Effects:
            Reads the canonical task file.

        Args:
            _arguments: Parsed CLI arguments, unused.

        Returns:
            Repository provenance and a short status line.

        """
        self.store.snapshot()
        return CommandOutcome({"repository": self.presenter.repository()}, "valid")

    def _list(self, _arguments: argparse.Namespace) -> CommandOutcome:
        """
        List every open task.

        Side Effects:
            Reads the canonical task file.

        Args:
            _arguments: Parsed CLI arguments, unused.

        Returns:
            Every open task, empty when the backlog is clear.

        """
        snapshot = self.store.snapshot()
        tasks = [
            task
            for priority in PRIORITY_HEADINGS
            for task in snapshot.document.active[priority]
        ]
        return CommandOutcome(
            {"tasks": [self._project(snapshot, task) for task in tasks]},
            "\n".join(self.presenter.summary_line(task) for task in tasks),
        )

    def _show(self, arguments: argparse.Namespace) -> CommandOutcome:
        """
        Show one task.

        Side Effects:
            Reads the canonical task file and may read the archive.

        Args:
            arguments: Parsed CLI arguments.

        Returns:
            The task as JSON and as canonical Markdown.

        """
        snapshot = self.store.snapshot()
        task = snapshot.find(arguments.task_id)
        return CommandOutcome({"task": self._project(snapshot, task)}, task.render())

    def _critical(self, _arguments: argparse.Namespace) -> CommandOutcome:
        """
        Select the highest-priority open task.

        Side Effects:
            Reads the canonical task file.

        Args:
            _arguments: Parsed CLI arguments, unused.

        Returns:
            The critical task, or a null result when nothing is open.

        """
        snapshot = self.store.snapshot()
        return self._singular(snapshot, snapshot.critical(), "no open task")

    def _actionable(self, _arguments: argparse.Namespace) -> CommandOutcome:
        """
        Select the first open, unclaimed, unblocked task.

        Side Effects:
            Reads the canonical task file.

        Args:
            _arguments: Parsed CLI arguments, unused.

        Returns:
            The actionable task, or a null result when none is eligible.

        """
        snapshot = self.store.snapshot()
        return self._singular(snapshot, snapshot.actionable(), "no actionable task")

    def _add(self, arguments: argparse.Namespace) -> CommandOutcome:
        """
        Add one open task.

        Side Effects:
            Updates the canonical task file.

        Args:
            arguments: Parsed CLI arguments.

        Returns:
            The added task.

        """
        with self.store.transaction() as transaction:
            task = transaction.add(
                title=arguments.title,
                priority=arguments.priority,
                task_type=arguments.type,
                tags=arguments.tag,
                acceptance=arguments.acceptance,
                simple=arguments.simple,
                context=arguments.context,
                related=arguments.related,
                blocked_by=arguments.blocked_by,
            )
        return self._mutated(task)

    def _edit(self, arguments: argparse.Namespace) -> CommandOutcome:
        """
        Update supported fields on one open task.

        Side Effects:
            Updates the canonical task file.

        Args:
            arguments: Parsed CLI arguments.

        Returns:
            The updated task.

        Raises:
            TodoError: If the request asks for no change at all.

        """
        if not any(getattr(arguments, option) for option in EDIT_OPTIONS):
            raise TodoError("edit requires at least one change", "usage")
        blocked_by = [] if arguments.clear_blockers else arguments.blocked_by
        with self.store.transaction() as transaction:
            task = transaction.edit(
                arguments.task_id,
                title=arguments.title,
                priority=arguments.priority,
                task_type=arguments.type,
                add_tags=arguments.add_tag,
                remove_tags=arguments.remove_tag,
                acceptance=arguments.acceptance,
                context=arguments.context,
                related=arguments.related,
                blocked_by=blocked_by,
                clear_acceptance=arguments.simple,
                clear_context=arguments.clear_context,
                clear_related=arguments.clear_related,
            )
        return self._mutated(task)

    def _claim(self, arguments: argparse.Namespace) -> CommandOutcome:
        """
        Record an advisory claim.

        Side Effects:
            Updates the canonical task file.

        Args:
            arguments: Parsed CLI arguments.

        Returns:
            The claimed task.

        """
        with self.store.transaction() as transaction:
            task = transaction.claim(
                arguments.task_id, arguments.actor, arguments.branch
            )
        return self._mutated(task)

    def _release(self, arguments: argparse.Namespace) -> CommandOutcome:
        """
        Release an advisory claim.

        Side Effects:
            Updates the canonical task file.

        Args:
            arguments: Parsed CLI arguments.

        Returns:
            The released task.

        """
        with self.store.transaction() as transaction:
            task = transaction.release(arguments.task_id)
        return self._mutated(task)

    def _complete(self, arguments: argparse.Namespace) -> CommandOutcome:
        """
        Complete one open task.

        Side Effects:
            Updates the canonical task file.

        Args:
            arguments: Parsed CLI arguments.

        Returns:
            The completed task.

        """
        with self.store.transaction() as transaction:
            task = transaction.close(arguments.task_id, "completed")
        return self._mutated(task)

    def _cancel(self, arguments: argparse.Namespace) -> CommandOutcome:
        """
        Cancel one open task.

        Side Effects:
            Updates the canonical task file.

        Args:
            arguments: Parsed CLI arguments.

        Returns:
            The cancelled task.

        """
        with self.store.transaction() as transaction:
            task = transaction.close(arguments.task_id, "cancelled", arguments.reason)
        return self._mutated(task)

    def _archive(self, _arguments: argparse.Namespace) -> CommandOutcome:
        """
        Enforce Done retention.

        Side Effects:
            Appends retired tasks to the archive and updates the task file.

        Args:
            _arguments: Parsed CLI arguments, unused.

        Returns:
            How many tasks were retired.

        """
        with self.store.transaction() as transaction:
            moved = transaction.retire_overflow()
        return CommandOutcome({"archived": moved}, str(moved))

    def _project(self, snapshot: RepositorySnapshot, task: Task) -> dict[str, Any]:
        """
        Project one task with its actionability resolved.

        Args:
            snapshot: Snapshot resolving blocker references.
            task: Task to project.

        Returns:
            JSON Schema 1 Task object.

        """
        return self.presenter.as_json(task, actionable=snapshot.is_actionable(task))

    def _singular(
        self, snapshot: RepositorySnapshot, task: Task | None, empty: str
    ) -> CommandOutcome:
        """
        Build the result of a query returning at most one task.

        Args:
            snapshot: Snapshot the query ran against.
            task: Selected task, or ``None``.
            empty: Explanatory line for an empty result.

        Returns:
            Nullable task result that still succeeds when empty.

        """
        if task is None:
            return CommandOutcome({"task": None}, empty)
        return CommandOutcome(
            {"task": self._project(snapshot, task)},
            self.presenter.summary_line(task),
        )

    def _mutated(self, task: Task) -> CommandOutcome:
        """
        Build the result of a mutation, re-reading for actionability.

        Side Effects:
            Reads the committed canonical task file.

        Args:
            task: Task the mutation produced.

        Returns:
            The resulting task and a short confirmation.

        """
        snapshot = self.store.snapshot()
        return CommandOutcome({"task": self._project(snapshot, task)}, task.task_id)


@dataclass(frozen=True)
class AggregateRow:
    """
    Pair one task with the provenance and snapshot that resolve it.

    Aggregate results interleave repositories, so each task has to carry the
    repository it came from rather than inheriting one from the command.

    Args:
        presenter: Presenter carrying the source repository's provenance.
        snapshot: Snapshot resolving that repository's blocker references.
        task: Task the row reports.

    """

    #: Presenter carrying the source repository's provenance.
    presenter: TaskPresenter
    #: Snapshot resolving that repository's blocker references.
    snapshot: RepositorySnapshot
    #: Task the row reports.
    task: Task

    def as_json(self) -> dict[str, Any]:
        """
        Project the row into a JSON Schema 1 Task object.

        Returns:
            Task object carrying its repository provenance.

        """
        return self.presenter.as_json(
            self.task, actionable=self.snapshot.is_actionable(self.task)
        )

    def summary_line(self) -> str:
        """
        Build the row's human summary.

        Returns:
            Single-line summary naming its repository.

        """
        return self.presenter.aggregate_line(self.task)


class AggregateRunner:
    """
    Run one read query across the whole configured Repository Collection.

    Every configured repository is inspected in configuration order, holding at
    most one shared lock at a time. The result is therefore a sequence of
    coherent Repository Snapshots rather than one global point-in-time snapshot.

    Args:
        collection: Repository Collection the query runs against.

    """

    def __init__(self, collection: RepositoryCollection) -> None:
        """
        Initialize a runner bound to one Repository Collection.

        Args:
            collection: Repository Collection the query runs against.

        """
        #: Repository Collection the query runs against.
        self.collection = collection

    def run(self, command: str) -> CommandOutcome:
        """
        Dispatch one aggregate query to its handler.

        Side Effects:
            Reads every configured repository's canonical task file.

        Args:
            command: Aggregate-capable query name.

        Returns:
            Result in both output formats.

        Raises:
            TodoError: If any configured repository cannot be read.

        """
        rows = list(self._rows())
        handlers = {
            "list": self._list,
            "critical": self._critical,
            "actionable": self._actionable,
        }
        return handlers[command](rows)

    def _list(self, rows: Sequence[AggregateRow]) -> CommandOutcome:
        """
        List every open task across the collection.

        Args:
            rows: Every open task in aggregate order.

        Returns:
            Every open task, empty when no backlog has open work.

        """
        return CommandOutcome(
            {"tasks": [row.as_json() for row in rows]},
            "\n".join(row.summary_line() for row in rows),
        )

    def _critical(self, rows: Sequence[AggregateRow]) -> CommandOutcome:
        """
        Select the highest-priority open task in the collection.

        Blocked and claimed tasks remain eligible.

        Args:
            rows: Every open task in aggregate order.

        Returns:
            The critical task, or a null result when nothing is open.

        """
        return self._singular(next(iter(rows), None), "no open task")

    def _actionable(self, rows: Sequence[AggregateRow]) -> CommandOutcome:
        """
        Select the first startable task in the collection.

        Blocker references stay local to each repository.

        Args:
            rows: Every open task in aggregate order.

        Returns:
            The actionable task, or a null result when none is eligible.

        """
        startable = (row for row in rows if row.snapshot.is_actionable(row.task))
        return self._singular(next(startable, None), "no actionable task")

    def _singular(self, row: AggregateRow | None, empty: str) -> CommandOutcome:
        """
        Build the result of a query returning at most one task.

        Args:
            row: Selected row, or ``None``.
            empty: Explanatory line for an empty result.

        Returns:
            Nullable task result that still succeeds when empty.

        """
        if row is None:
            return CommandOutcome({"task": None}, empty)
        return CommandOutcome({"task": row.as_json()}, row.summary_line())

    def _rows(self) -> Iterator[AggregateRow]:
        """
        Yield every open task in the settled aggregate order.

        The order is priority first, then Repository Collection order, then
        existing task-file order, so the repository loop sits between the two.

        Side Effects:
            Reads every configured repository's canonical task file.

        Yields:
            Each open task paired with its repository.

        Raises:
            TodoError: If any configured repository cannot be read.

        """
        repositories = self._read()
        for priority in PRIORITY_HEADINGS:
            for presenter, snapshot in repositories:
                for task in snapshot.document.active[priority]:
                    yield AggregateRow(presenter, snapshot, task)

    def _read(self) -> list[tuple[TaskPresenter, RepositorySnapshot]]:
        """
        Snapshot every configured repository, failing strictly.

        Successful repositories are discarded when any repository fails, because
        missing data could change the global order or the selected task.

        Side Effects:
            Reads every configured repository's canonical task file.

        Returns:
            Each repository's presenter and snapshot in configuration order.

        Raises:
            TodoError: If any configured repository cannot be read, listing
                every failure in configuration order.

        """
        repositories = []
        failures: list[dict[str, str]] = []
        for entry in self.collection:
            try:
                store = TodoStore(entry.path)
                snapshot = store.snapshot()
            except (TodoError, OSError) as error:
                failures.append(
                    {
                        "name": entry.name,
                        "path": str(entry.path),
                        "code": error.code
                        if isinstance(error, TodoError)
                        else "io_error",
                        "message": str(error),
                    }
                )
            else:
                repositories.append((TaskPresenter(entry.name, store.root), snapshot))
        if failures:
            named = ", ".join(f"{one['name']} ({one['code']})" for one in failures)
            raise TodoError(
                f"{len(failures)} of {len(self.collection)} repositories failed: "
                f"{named}",
                "aggregate_partial_failure",
                {"failures": failures},
            )
        return repositories


class OutputWriter:
    """
    Render results and failures in the selected output format.

    Args:
        json_mode: Whether ``--json`` selected the machine-readable format.

    """

    def __init__(self, *, json_mode: bool) -> None:
        """
        Initialize a writer for one invocation's output format.

        Keyword Args:
            json_mode: Whether ``--json`` selected the machine-readable format.

        """
        #: Whether ``--json`` selected the machine-readable format.
        self.json_mode = json_mode

    def success(self, command: str, outcome: CommandOutcome) -> None:
        """
        Write one successful result to stdout.

        Side Effects:
            Writes to stdout.

        Args:
            command: Command that produced the result.
            outcome: Result in both output formats.

        """
        if self.json_mode:
            document = {
                "schema_version": JSON_SCHEMA_VERSION,
                "command": command,
                "data": outcome.data,
            }
            print(json.dumps(document, ensure_ascii=False))
        elif outcome.human:
            print(outcome.human)

    def failure(self, error: TodoError) -> None:
        """
        Write one expected failure to stderr, leaving stdout empty.

        Side Effects:
            Writes to stderr.

        Args:
            error: Failure to report.

        """
        if self.json_mode:
            document = {
                "schema_version": JSON_SCHEMA_VERSION,
                "error": {"code": error.code, "message": str(error), **error.details},
            }
            print(json.dumps(document, ensure_ascii=False), file=sys.stderr)
        else:
            print(f"{PROGRAM_NAME}: error: {error}", file=sys.stderr)


def _install_skill(arguments: argparse.Namespace) -> CommandOutcome:
    """
    Install the packaged todo skill for one Skill Target.

    Side Effects:
        Creates, updates, replaces, or backs up an installed skill tree.

    Args:
        arguments: Parsed ``install-skill`` options.

    Returns:
        Machine-readable installation result and its human summary.

    Raises:
        TodoError: If the Skill Root is unusable or an unforced conflict
            exists.

    """
    result = SkillInstaller(
        arguments.target,
        arguments.destination,
        dry_run=arguments.dry_run,
        force=arguments.force,
    ).run()
    data = {
        "target": result.target,
        "skill_root": str(result.skill_root),
        "skill_path": str(result.skill_path),
        "action": result.action,
        "dry_run": result.dry_run,
        "backup_path": None if result.backup_path is None else str(result.backup_path),
    }
    prefix = "would " if result.dry_run else ""
    human = f"{prefix}{result.action} {result.target} skill at {result.skill_path}"
    if result.backup_path is not None:
        human = f"{human}\nbacked up to {result.backup_path}"
    return CommandOutcome(data=data, human=human)


def _json_requested(argv: Sequence[str]) -> bool:
    """
    Detect ``--json`` before a namespace exists.

    A parse failure has to pick a renderer before argparse has run, so the raw
    arguments are scanned for an exact ``--json`` token ahead of any ``--``
    terminator. Abbreviations such as ``--js`` deliberately do not count.

    Args:
        argv: Raw arguments excluding the executable name.

    Returns:
        ``True`` when the machine-readable format was requested.

    """
    for argument in argv:
        if argument == "--":
            return False
        if argument == "--json":
            return True
    return False


def _build_parser() -> argparse.ArgumentParser:
    """
    Build the public command-line parser.

    Returns:
        Configured argument parser.

    """
    parser = _Parser(prog=PROGRAM_NAME, description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit one machine-readable document"
    )
    parser.add_argument("--config", type=Path, help="configuration file path")
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument("--root", type=Path, help="exact task repository path")
    selector.add_argument("--repo", help="configured repository name")
    selector.add_argument(
        "--all", action="store_true", help="every configured repository"
    )
    parser.add_argument(
        "--version", action="version", version=f"{PROGRAM_NAME} {package_version()}"
    )
    commands = parser.add_subparsers(
        dest="command", required=True, parser_class=_Parser
    )

    initialize = commands.add_parser("init", help="create the canonical task file")
    initialize.add_argument("--name", required=True)
    commands.add_parser("validate", help="validate the canonical task file")
    commands.add_parser("list", help="list open tasks")

    show = commands.add_parser("show", help="show one task")
    show.add_argument("task_id")
    commands.add_parser("critical", help="select the highest-priority open task")
    commands.add_parser("actionable", help="select the first startable task")

    add = commands.add_parser("add", help="add an open task")
    add.add_argument("title")
    add.add_argument("--priority", choices=PRIORITY_HEADINGS, default="P2")
    add.add_argument("--type", choices=sorted(TYPE_TAGS), required=True)
    add.add_argument("--tag", action="append")
    acceptance = add.add_mutually_exclusive_group()
    acceptance.add_argument("--acceptance")
    acceptance.add_argument("--simple", action="store_true")
    add.add_argument("--context")
    add.add_argument("--related")
    add.add_argument("--blocked-by", action="append")

    edit = commands.add_parser("edit", help="edit an open task")
    edit.add_argument("task_id")
    edit.add_argument("--title")
    edit.add_argument("--priority", choices=PRIORITY_HEADINGS)
    edit.add_argument("--type", choices=sorted(TYPE_TAGS))
    edit.add_argument("--add-tag", action="append")
    edit.add_argument("--remove-tag", action="append")
    edit_acceptance = edit.add_mutually_exclusive_group()
    edit_acceptance.add_argument("--acceptance")
    edit_acceptance.add_argument("--simple", action="store_true")
    edit_context = edit.add_mutually_exclusive_group()
    edit_context.add_argument("--context")
    edit_context.add_argument("--clear-context", action="store_true")
    edit_related = edit.add_mutually_exclusive_group()
    edit_related.add_argument("--related")
    edit_related.add_argument("--clear-related", action="store_true")
    edit_blockers = edit.add_mutually_exclusive_group()
    edit_blockers.add_argument("--blocked-by", action="append")
    edit_blockers.add_argument("--clear-blockers", action="store_true")

    claim = commands.add_parser("claim", help="claim an open task")
    claim.add_argument("task_id")
    claim.add_argument("--actor", required=True)
    claim.add_argument("--branch")
    release = commands.add_parser("release", help="release an open claim")
    release.add_argument("task_id")
    complete = commands.add_parser("complete", help="complete an open task")
    complete.add_argument("task_id")
    cancel = commands.add_parser("cancel", help="cancel an open task")
    cancel.add_argument("task_id")
    cancel.add_argument("--reason", required=True)
    commands.add_parser("archive", help="enforce Done retention")

    install = commands.add_parser(
        "install-skill", help="install the bundled todo skill"
    )
    install.add_argument("--target", choices=sorted(TARGET_ROOTS), required=True)
    install.add_argument("--destination", type=Path, help="skill root override")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--force", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """
    Run the bot-todo CLI.

    Side Effects:
        Executes a requested task-file operation and prints its result.

    Args:
        argv: Optional arguments excluding the executable name.

    Returns:
        Process exit status.

    """
    raw = list(sys.argv[1:] if argv is None else argv)
    writer = OutputWriter(json_mode=_json_requested(raw))
    try:
        arguments = _build_parser().parse_args(raw)
    except SystemExit as exit_request:
        return int(exit_request.code or 0)
    except TodoError as error:
        writer.failure(error)
        return EXIT_USAGE
    writer = OutputWriter(json_mode=arguments.json)
    try:
        selector = RepositorySelector(
            arguments.root, arguments.repo, arguments.all, arguments.config
        )
        selector.validate(arguments.command)
        if arguments.command == "install-skill":
            outcome = _install_skill(arguments)
        elif arguments.all:
            outcome = AggregateRunner(selector.collection()).run(arguments.command)
        else:
            outcome = CommandRunner(selector.select(arguments.command)).run(
                arguments.command, arguments
            )
    except TodoError as error:
        writer.failure(error)
        return EXIT_CODES.get(error.code, EXIT_FAILURE)
    except OSError as error:
        writer.failure(TodoError(str(error), "io_error"))
        return EXIT_FAILURE
    writer.success(arguments.command, outcome)
    return 0
