"""Serve one Task Repository as a local Kanban Board."""

from __future__ import annotations

import errno
import html
import re
import secrets
import webbrowser
from dataclasses import dataclass
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlencode, urlsplit

from bot_todo.config import RepositoryCollection
from bot_todo.repository import (
    PRIORITY_HEADINGS,
    SIMPLE_TAG,
    TYPE_TAGS,
    WRITE_FORMAT_VERSION,
    Task,
    TodoError,
    TodoStore,
)

#: Maximum accepted URL-encoded request body.
MAX_FORM_BYTES = 64 * 1024
#: Headers applied to every board response.
SECURITY_HEADERS = (
    ("Cache-Control", "no-store"),
    ("X-Content-Type-Options", "nosniff"),
    ("X-Frame-Options", "DENY"),
    # "no-referrer" would make browsers send "Origin: null" on the board's form
    # posts, which the origin check in do_POST rejects; keep a policy that
    # preserves the same-origin Origin header.
    ("Referrer-Policy", "same-origin"),
    (
        "Content-Security-Policy",
        (
            "default-src 'none'; style-src 'unsafe-inline' https://cdn.jsdelivr.net; "
            "script-src https://cdn.jsdelivr.net; font-src https://cdn.jsdelivr.net; "
            "img-src data:; form-action 'self'; base-uri 'none'; frame-ancestors 'none'"
        ),
    ),
)


@dataclass(frozen=True)
class BoardSelection:
    """Identify one request's Kanban Board selection.

    Args:
        key: Query value identifying All, Current, or a Repository Entry.
        name: Configured Repository Name, or ``None`` for All and Current.
        store: Selected Task Repository, or ``None`` for All.
    """

    #: Query value identifying the selection.
    key: str
    #: Configured Repository Name, when one entry is selected.
    name: str | None
    #: Selected Task Repository; ``None`` means All.
    store: TodoStore | None


@dataclass(frozen=True)
class BoardTask:
    """Pair a board-visible Task with optional Repository Name provenance.

    Args:
        task: Task rendered on the board.
        repository_name: Source Repository Name on All, otherwise ``None``.
    """

    #: Task rendered on the board.
    task: Task
    #: Source Repository Name on a collection-wide board.
    repository_name: str | None = None


class KanbanWebApp:
    """Render a Kanban Board over a launch repository and collection.

    Args:
        store: Launch Task Repository, or ``None`` when the launch selection
            is All.
        collection: Immutable Repository Collection loaded before bind.
        csrf_token: Token override used by deterministic tests.
    """

    def __init__(
        self,
        store: TodoStore | None,
        collection: RepositoryCollection,
        csrf_token: str | None = None,
    ) -> None:
        """Initialize a board over one launch selection and collection.

        Args:
            store: Launch Task Repository, or ``None`` when All is selected.
            collection: Immutable Repository Collection loaded before bind.
            csrf_token: Token override used by deterministic tests.
        """
        #: Launch Task Repository, or ``None`` when All is selected.
        self.store = store
        #: Immutable Repository Collection loaded before the server binds.
        self.collection = collection
        #: Secret required by every state-changing form.
        self.csrf_token = csrf_token or secrets.token_urlsafe(32)
        #: Exact origin assigned after the loopback socket binds.
        self.origin = ""
        #: Launch selection used for bare ``/`` and unmatched Current.
        self.default_selection = self._launch_selection(store, collection)

    def _launch_selection(
        self, store: TodoStore | None, collection: RepositoryCollection
    ) -> BoardSelection:
        """Derive the immutable launch selection from constructor facts.

        Args:
            store: Launch Task Repository, or ``None`` for All.
            collection: Immutable Repository Collection loaded before bind.

        Returns:
            All, a matching configured entry, or Current for an unmatched path.
        """
        if store is None:
            return BoardSelection("all", None, None)
        for entry in collection:
            if entry.path == store.root:
                return BoardSelection(entry.name, entry.name, store)
        return BoardSelection("current", None, store)

    def resolve_selection(self, query: str) -> BoardSelection | None:
        """Resolve one request's ``repo`` query.

        Args:
            query: Raw query string from ``urlsplit(self.path).query``.

        Returns:
            The launch selection when ``query`` is empty, a concrete selection
            for one valid ``repo`` value, or ``None`` for any invalid query.
        """
        if query == "":
            return self.default_selection
        try:
            parsed = parse_qs(
                query,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=1,
            )
        except ValueError:
            return None
        values = parsed.get("repo")
        if list(parsed.keys()) != ["repo"] or values is None or len(values) != 1:
            return None
        key = values[0]
        if key == "all":
            return BoardSelection("all", None, None)
        if key == "current":
            if self.default_selection.key != "current":
                return None
            return self.default_selection
        if not key:
            return None
        try:
            entry = self.collection.entry(key)
        except TodoError:
            return None
        return BoardSelection(entry.name, entry.name, TodoStore(entry.path))

    def selection_path(self, selection: BoardSelection) -> str:
        """Build the canonical path for one board selection.

        Args:
            selection: Selection to encode.

        Returns:
            Root board path with one encoded ``repo`` query.
        """
        return f"/?{urlencode({'repo': selection.key})}"

    def create_server(self, port: int) -> ThreadingHTTPServer:
        """Bind an HTTP server to loopback.

        Args:
            port: Requested TCP port; zero asks the operating system to choose.

        Returns:
            Bound server ready for ``serve_forever``.

        Raises:
            ValueError: If the port is outside the TCP port range.
            TodoError: If the requested loopback port is already in use.

        Side Effects:
            Binds a loopback TCP socket.
        """
        if not 0 <= port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        handler = partial(KanbanRequestHandler, app=self)
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError as error:
            in_use = {errno.EADDRINUSE}
            winsock_in_use = getattr(errno, "WSAEADDRINUSE", None)
            if winsock_in_use is not None:
                in_use.add(winsock_in_use)
            if error.errno not in in_use:
                raise
            raise TodoError(
                (
                    f"Kanban Board could not bind 127.0.0.1:{port} because that "
                    "port is already in use. Retry with --port PORT, or --port 0 "
                    "to let the OS choose a free port."
                ),
                "io_error",
            ) from error
        server.daemon_threads = True
        self.origin = f"http://127.0.0.1:{server.server_port}"
        return server

    def _modal_id(self, row: BoardTask) -> str:
        """Build a collision-proof modal id for one board row.

        Args:
            row: Board row receiving the id.

        Returns:
            Existing task-only id for one repository, or a repository-qualified
            id for All.
        """
        if row.repository_name is None:
            return f"task-{row.task.task_id}-modal"
        encoded_name = row.repository_name.encode("utf-8").hex()
        return f"task-{encoded_name}-{row.task.task_id}-modal"

    def _collection_columns(self) -> tuple[tuple[str, list[BoardTask]], ...]:
        """Project every configured repository onto the four board columns.

        Side Effects:
            Reads every configured Task Repository.

        Returns:
            Open, Review, Completed, and Cancelled rows in board order.

        Raises:
            TodoError: If any configured repository cannot be read.
        """
        # ponytail: keep the four-state board projection local; extract it only
        # when a third collection consumer needs the same contract.
        snapshots: list[tuple[str, Any]] = []
        failures: list[dict[str, str]] = []
        for entry in self.collection:
            try:
                snapshot = TodoStore(entry.path).snapshot()
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
                snapshots.append((entry.name, snapshot))
        if failures:
            named = ", ".join(f"{one['name']} ({one['code']})" for one in failures)
            raise TodoError(
                f"{len(failures)} of {len(self.collection)} repositories failed: "
                f"{named}",
                "aggregate_partial_failure",
                {"failures": failures},
            )
        open_rows: list[BoardTask] = []
        review_rows: list[BoardTask] = []
        for priority in PRIORITY_HEADINGS:
            for name, snapshot in snapshots:
                for task in snapshot.document.active[priority]:
                    row = BoardTask(task, name)
                    if task.state == "open":
                        open_rows.append(row)
                    elif task.state == "review":
                        review_rows.append(row)
        completed_rows: list[BoardTask] = []
        cancelled_rows: list[BoardTask] = []
        for name, snapshot in snapshots:
            for task in snapshot.document.done:
                row = BoardTask(task, name)
                if task.state == "completed":
                    completed_rows.append(row)
                elif task.state == "cancelled":
                    cancelled_rows.append(row)
        return (
            ("Open", open_rows),
            ("Review", review_rows),
            ("Completed", completed_rows),
            ("Cancelled", cancelled_rows),
        )

    def render_board(self, selection: BoardSelection) -> str:
        """Render all recent tasks in Task State columns.

        Side Effects:
            Reads the selected Task Repository, or none when All is selected.

        Args:
            selection: Request-local board selection.

        Returns:
            Complete board HTML document.
        """
        columns: tuple[tuple[str, list[BoardTask]], ...]
        if selection.store is None:
            columns = self._collection_columns()
            writable = False
            header_action = ""
            mutation_area = (
                '<p role="status" class="alert alert-info"><i class="ti ti-lock" '
                'aria-hidden="true"></i> All repositories is read-only. '
                "Select a repository to make changes.</p>"
            )
        else:
            snapshot = selection.store.snapshot()
            writable = snapshot.document.format_version == WRITE_FORMAT_VERSION
            active = [
                task
                for priority in PRIORITY_HEADINGS
                for task in snapshot.document.active[priority]
            ]
            columns = (
                (
                    "Open",
                    [
                        BoardTask(task)
                        for task in active
                        if task.state == "open"
                    ],
                ),
                (
                    "Review",
                    [
                        BoardTask(task)
                        for task in active
                        if task.state == "review"
                    ],
                ),
                (
                    "Completed",
                    [
                        BoardTask(task)
                        for task in snapshot.document.done
                        if task.state == "completed"
                    ],
                ),
                (
                    "Cancelled",
                    [
                        BoardTask(task)
                        for task in snapshot.document.done
                        if task.state == "cancelled"
                    ],
                ),
            )
            if writable:
                header_action = (
                    '<button class="btn btn-primary" type="button" data-bs-toggle="modal" '
                    'data-bs-target="#add-task-modal"><i class="ti ti-plus" '
                    'aria-hidden="true"></i> New task</button>'
                )
                mutation_area = self._render_add_form(selection)
            else:
                header_action = ""
                mutation_area = (
                    '<p role="status" class="alert alert-warning"><i class="ti ti-lock" '
                    'aria-hidden="true"></i> This repository is read-only. '
                    "Run <code>bot-todo migrate</code> to enable board mutations.</p>"
                )
        columns_html = "".join(
            self._render_column(
                heading, tasks, writable=writable, selection=selection
            )
            for heading, tasks in columns
        )
        detail_modals = "".join(
            self._render_task_detail_modal(
                row, writable=writable, selection=selection
            )
            for _, tasks in columns
            for row in tasks
        )
        content = (
            f"{mutation_area}{detail_modals}"
            f'<div class="board-columns">{columns_html}</div>'
        )
        return self._page(
            "Kanban Board",
            content,
            selection=selection,
            header_action=header_action,
        )

    def render_not_found(self, selection: BoardSelection | None = None) -> str:
        """Render the generic missing-page response.

        Args:
            selection: Selection used for the repository menu.

        Returns:
            Complete error HTML document.
        """
        if selection is None:
            selection = self.default_selection
        return self._page(
            "Not found",
            '<div class="card"><div class="card-body text-center py-6">'
            '<i class="ti ti-file-off fs-1 text-secondary" aria-hidden="true"></i>'
            '<h1 class="h2 mt-2">Not found</h1>'
            '<p class="text-secondary mb-0">The requested page does not exist.</p>'
            "</div></div>",
            selection=selection,
        )

    def render_error(
        self,
        title: str,
        message: str,
        selection: BoardSelection | None = None,
    ) -> str:
        """Render one concise error page.

        Args:
            title: Human-readable error title.
            message: Safe error explanation.
            selection: Selection used for the repository menu.

        Returns:
            Complete escaped error HTML document.
        """
        if selection is None:
            selection = self.default_selection
        content = (
            '<div class="card"><div class="card-body">'
            f'<h1 class="h2">{html.escape(title)}</h1>'
            f"<p>{html.escape(message)}</p>"
            f'<a class="btn btn-primary" href="'
            f'{html.escape(self.selection_path(selection), quote=True)}">'
            "Return to Kanban Board</a>"
            "</div></div>"
        )
        return self._page(title, content, selection=selection)

    def _writable_store(self, selection: BoardSelection) -> TodoStore:
        """Return the repository selected for a mutation.

        Args:
            selection: Request-local board selection.

        Returns:
            Selected Task Repository.

        Raises:
            TodoError: If All was selected.
        """
        if selection.store is None:
            raise TodoError("All repositories is read-only", "conflict")
        return selection.store

    def add_task(self, selection: BoardSelection, fields: dict[str, str]) -> Task:
        """Add one task from browser form fields.

        Side Effects:
            Mutates the selected Task Repository.

        Args:
            selection: Request-local board selection.
            fields: Parsed URL-encoded form fields.

        Returns:
            Newly allocated task.

        Raises:
            TodoError: If All was selected or form values violate the add
                contract.
        """
        priority = fields.get("priority", "")
        task_type = fields.get("task_type", "")
        if priority not in PRIORITY_HEADINGS:
            raise TodoError("unknown priority", "usage")
        if task_type not in TYPE_TAGS:
            raise TodoError("unknown task type", "usage")
        acceptance = fields.get("acceptance") or None
        simple = fields.get("simple") == "on"
        if acceptance and simple:
            raise TodoError("choose acceptance or simple, not both", "usage")
        tags = [value.strip() for value in fields.get("tags", "").split(",")]
        blockers = [value.strip() for value in fields.get("blocked_by", "").split(",")]
        store = self._writable_store(selection)
        with store.transaction() as transaction:
            return transaction.add(
                title=fields.get("title", ""),
                priority=priority,
                task_type=task_type,
                tags=[value for value in tags if value],
                acceptance=acceptance,
                simple=simple,
                context=fields.get("context") or None,
                related=fields.get("related") or None,
                blocked_by=[value for value in blockers if value],
            )

    def edit_task(
        self, selection: BoardSelection, task_id: str, fields: dict[str, str]
    ) -> Task:
        """Replace editable fields on one open or review task.

        Side Effects:
            Mutates the selected Task Repository.

        Args:
            selection: Request-local board selection.
            task_id: Task receiving the edit.
            fields: Parsed URL-encoded form fields.

        Returns:
            Updated task.

        Raises:
            TodoError: If All was selected, form values violate the edit
                contract, or the task is closed.
        """
        priority = fields.get("priority", "")
        task_type = fields.get("task_type", "")
        if priority not in PRIORITY_HEADINGS:
            raise TodoError("unknown priority", "usage")
        if task_type not in TYPE_TAGS:
            raise TodoError("unknown task type", "usage")
        acceptance = fields.get("acceptance") or None
        simple = fields.get("simple") == "on"
        if acceptance and simple:
            raise TodoError("choose acceptance or simple, not both", "usage")
        if not acceptance and not simple:
            raise TodoError("choose acceptance or simple", "usage")
        tags = [value.strip() for value in fields.get("tags", "").split(",")]
        submitted = [value for value in tags if value]
        reserved = TYPE_TAGS | {SIMPLE_TAG}
        if any(value.removeprefix("#") in reserved for value in submitted):
            raise TodoError("use type and simple controls, not tags", "usage")
        blockers = [
            value.strip()
            for value in fields.get("blocked_by", "").split(",")
            if value.strip()
        ]
        store = self._writable_store(selection)
        current = store.snapshot().find(task_id)
        current_tags = list(current.user_tags) if current is not None else []
        add_tags = [tag for tag in submitted if tag not in current_tags]
        remove_tags = [tag for tag in current_tags if tag not in submitted]
        context = fields.get("context") or None
        related = fields.get("related") or None
        with store.transaction() as transaction:
            return transaction.edit(
                task_id,
                title=fields.get("title", ""),
                priority=priority,
                task_type=task_type,
                add_tags=add_tags,
                remove_tags=remove_tags,
                acceptance=None if simple else acceptance,
                context=context,
                related=related,
                blocked_by=blockers,
                clear_acceptance=simple,
                clear_context=not context,
                clear_related=not related,
            )

    def transition_task(
        self, selection: BoardSelection, task_id: str, fields: dict[str, str]
    ) -> Task:
        """Apply one supported lifecycle action.

        Side Effects:
            Mutates the selected Task Repository.

        Args:
            selection: Request-local board selection.
            task_id: Task receiving the transition.
            fields: Parsed form fields including the action.

        Returns:
            Updated task.

        Raises:
            TodoError: If All was selected or the action is unsupported or
                invalid for the task.
        """
        action = fields.get("action")
        store = self._writable_store(selection)
        with store.transaction() as transaction:
            if action == "review":
                return transaction.review(task_id)
            if action == "reopen":
                return transaction.reopen(task_id)
            if action == "complete":
                return transaction.close(task_id, "completed")
            if action == "cancel":
                return transaction.close(task_id, "cancelled", fields.get("reason"))
            raise TodoError("unknown transition action", "usage")

    def _render_card(
        self, row: BoardTask, *, writable: bool, selection: BoardSelection
    ) -> str:
        """Render one task card.

        Args:
            row: Board row displayed by the card.

        Keyword Args:
            writable: Whether lifecycle forms may be rendered.
            selection: Request-local board selection for form actions.

        Returns:
            Escaped task card markup.
        """
        task = row.task
        task_id = html.escape(task.task_id)
        title = html.escape(task.title)
        modal_id = html.escape(self._modal_id(row), quote=True)
        actions = (
            self._render_actions(task, selection) if writable else ""
        )
        provenance = ""
        if row.repository_name is not None:
            provenance = (
                f'<span class="badge bg-azure-lt">'
                f"{html.escape(row.repository_name)}</span> "
            )
        return (
            '<article class="card card-sm mb-2"><div class="card-body">'
            f'<button type="button" class="task-title" data-bs-toggle="modal" '
            f'data-bs-target="#{modal_id}"><strong>{task_id}</strong> '
            f"{title}</button>"
            f'<div class="mt-2">{provenance}<span class="badge bg-blue-lt">'
            f"{html.escape(task.priority or task.state)}</span> "
            f'<span class="badge bg-secondary-lt">{html.escape(task.task_type or "untyped")}'
            f"</span></div>{actions}</div></article>"
        )

    def _render_column(
        self,
        heading: str,
        tasks: list[BoardTask],
        *,
        writable: bool,
        selection: BoardSelection,
    ) -> str:
        """Render one responsive board column with bounded terminal cards.

        Args:
            heading: Human-readable task state heading.
            tasks: Board rows assigned to the column.

        Keyword Args:
            writable: Whether lifecycle forms may be rendered.
            selection: Request-local board selection for form actions.

        Returns:
            Escaped board-column markup.
        """
        state = heading.lower()
        icon, message, color = {
            "open": ("ti-circle", "Open tasks will appear here.", "text-blue"),
            "review": (
                "ti-clock",
                "Tasks awaiting review will appear here.",
                "text-blue",
            ),
            "completed": (
                "ti-circle-check",
                "Completed tasks will appear here.",
                "text-green",
            ),
            "cancelled": (
                "ti-ban",
                "Cancelled tasks will appear here.",
                "text-secondary",
            ),
        }[state]
        visible = tasks if state not in {"completed", "cancelled"} else tasks[:6]
        cards = "".join(
            self._render_card(row, writable=writable, selection=selection)
            for row in visible
        )
        overflow = tasks[6:] if state in {"completed", "cancelled"} else []
        if overflow:
            label = f"+ {len(overflow)} more {state} task{'s' if len(overflow) != 1 else ''}"
            cards += (
                '<details class="terminal-overflow"><summary>'
                f"{label}</summary>"
                f"{''.join(self._render_card(row, writable=writable, selection=selection) for row in overflow)}"
                "</details>"
            )
        if not cards:
            cards = (
                '<div class="board-empty text-secondary"><i class="ti '
                f'{icon}" aria-hidden="true"></i><span>{message}</span></div>'
            )
        return (
            f'<section class="board-column" data-state="{state}" '
            f'aria-label="{len(tasks)} {state} tasks">'
            '<div class="d-flex justify-content-between align-items-center mb-3">'
            f'<h2 class="h3 mb-0"><i class="ti {icon} {color}" aria-hidden="true"></i> '
            f'{heading}</h2><span class="badge bg-secondary-lt">'
            f"{len(tasks)}</span></div>{cards}</section>"
        )

    def _render_task_detail_modal(
        self, row: BoardTask, *, writable: bool, selection: BoardSelection
    ) -> str:
        """Render one Tabler modal for a board-visible task.

        Args:
            row: Board row whose canonical fields are displayed or edited.

        Keyword Args:
            writable: Whether open and review tasks may include an edit form.
            selection: Request-local board selection for form actions.

        Returns:
            Escaped modal markup matching the New task dismiss contract.
        """
        if writable and row.task.state in {"open", "review"}:
            return self._render_task_edit_modal(row, selection)
        return self._render_task_readonly_modal(row)

    def _modal_heading(self, row: BoardTask) -> str:
        """Build an escaped modal heading for one board row.

        Args:
            row: Board row whose heading is rendered.

        Returns:
            Escaped heading including Repository Name provenance on All.
        """
        heading = f"{html.escape(row.task.task_id)} — {html.escape(row.task.title)}"
        if row.repository_name is not None:
            heading = f"{html.escape(row.repository_name)} {heading}"
        return heading

    def _render_task_readonly_modal(self, row: BoardTask) -> str:
        """Render a read-only detail modal.

        Args:
            row: Board row whose canonical fields are displayed.

        Returns:
            Escaped modal markup with a definition list and Close control.
        """
        task = row.task
        modal_id = html.escape(self._modal_id(row), quote=True)
        title_id = f"{modal_id}-title"
        values = (
            ("ID", task.task_id),
            ("Title", task.title),
            ("State", task.state),
            ("Priority", task.priority),
            ("Type", task.task_type),
            ("Tags", ", ".join(task.user_tags)),
            ("Simple", "yes" if task.simple else "no"),
            ("Acceptance", task.acceptance),
            ("Context", task.context),
            ("Related", task.related),
            ("Blocked by", ", ".join(task.blocked_by)),
            ("Claim", self._claim_text(task)),
            ("Reviewed", task.reviewed_on),
            ("Closed", task.closed_on),
            ("Reason", task.reason),
        )
        heading = self._modal_heading(row)
        return (
            f'<div class="modal modal-blur fade" id="{modal_id}" tabindex="-1" '
            f'aria-labelledby="{title_id}" aria-hidden="true">'
            '<div class="modal-dialog modal-lg modal-dialog-centered">'
            '<div class="modal-content"><div class="modal-header">'
            f'<h2 class="modal-title" id="{title_id}">{heading}</h2>'
            '<button type="button" class="btn-close" data-bs-dismiss="modal" '
            'aria-label="Close"></button></div>'
            f'<div class="modal-body"><dl class="row mb-0">'
            f"{self._definition_rows(values)}</dl></div>"
            '<div class="modal-footer"><button type="button" class="btn btn-link" '
            'data-bs-dismiss="modal">Close</button></div></div></div></div>'
        )

    def _render_task_edit_modal(
        self, row: BoardTask, selection: BoardSelection
    ) -> str:
        """Render a pre-filled edit form in the detail modal.

        Args:
            row: Open or review board row to edit.
            selection: Request-local board selection for the form action.

        Returns:
            Escaped modal markup posting to ``/tasks/{id}/edit``.
        """
        task = row.task
        task_id = html.escape(task.task_id)
        title = html.escape(task.title)
        modal_id = html.escape(self._modal_id(row), quote=True)
        title_id = f"{modal_id}-title"
        metadata = (
            ("ID", task.task_id),
            ("State", task.state),
            ("Claim", self._claim_text(task)),
            ("Reviewed", task.reviewed_on),
        )
        open_attr = (
            " open"
            if task.user_tags or task.context or task.related or task.blocked_by
            else ""
        )
        checked = " checked" if task.simple else ""
        heading = self._modal_heading(row)
        return (
            f'<div class="modal modal-blur fade" id="{modal_id}" tabindex="-1" '
            f'aria-labelledby="{title_id}" aria-hidden="true">'
            '<div class="modal-dialog modal-lg modal-dialog-centered">'
            '<div class="modal-content"><div class="modal-header">'
            f'<h2 class="modal-title" id="{title_id}">{heading}</h2>'
            '<button type="button" class="btn-close" data-bs-dismiss="modal" '
            'aria-label="Close"></button></div>'
            f'<form method="post" action="/tasks/{task_id}/edit?{urlencode({"repo": selection.key})}">'
            f"{self._csrf_field()}"
            '<div class="modal-body">'
            f'<dl class="row">{self._definition_rows(metadata)}</dl>'
            '<div class="mb-3"><label class="form-label">Title '
            f'<input class="form-control" name="title" value="{title}" required>'
            "</label></div>"
            '<div class="row"><div class="col-md-6 mb-3"><label class="form-label">Priority '
            f'<select class="form-select" name="priority">'
            f"{self._priority_options(task.priority or 'P2')}</select></label></div>"
            '<div class="col-md-6 mb-3"><label class="form-label">Type '
            f'<select class="form-select" name="task_type">'
            f"{self._type_options(task.task_type)}</select></label></div></div>"
            '<div class="mb-3"><label class="form-label">Acceptance '
            f'<textarea class="form-control" name="acceptance">'
            f"{html.escape(task.acceptance or '')}</textarea></label></div>"
            '<label class="form-check"><input class="form-check-input" type="checkbox" '
            f'name="simple"{checked}><span class="form-check-label">Simple task'
            "</span></label>"
            f'<details class="mt-3"{open_attr}><summary>Advanced fields</summary>'
            '<div class="mt-3"><label class="form-label">Tags '
            f'<input class="form-control" name="tags" value="'
            f'{html.escape(", ".join(task.user_tags))}" '
            'placeholder="browser, local"></label>'
            '<label class="form-label">Context '
            f'<textarea class="form-control" name="context">'
            f"{html.escape(task.context or '')}</textarea></label>"
            '<label class="form-label">Related '
            f'<input class="form-control" name="related" value="'
            f'{html.escape(task.related or "")}"></label>'
            '<label class="form-label">Blocked by '
            f'<input class="form-control" name="blocked_by" value="'
            f'{html.escape(", ".join(task.blocked_by))}" '
            'placeholder="T001, T002"></label></div></details></div>'
            '<div class="modal-footer"><button type="button" class="btn btn-link" '
            'data-bs-dismiss="modal">Cancel</button>'
            '<button class="btn btn-primary" type="submit">Save</button>'
            "</div></form></div></div></div>"
        )

    def _definition_rows(self, values: tuple[tuple[str, str | None], ...]) -> str:
        """Render definition-list rows.

        Args:
            values: Label and display value pairs.

        Returns:
            Escaped ``dt``/``dd`` markup.
        """
        return "".join(
            f'<dt class="col-sm-3 text-secondary">{html.escape(label)}</dt>'
            f'<dd class="col-sm-9">{html.escape(value or "—")}</dd>'
            for label, value in values
        )

    def _claim_text(self, task: Task) -> str | None:
        """Format a claim for display.

        Args:
            task: Task whose claim should be shown.

        Returns:
            ``actor | date | branch`` text, or ``None`` when unclaimed.
        """
        claim = task.claim
        if claim is None:
            return None
        return f"{claim.actor} | {claim.claimed_on} | {claim.branch}"

    def _priority_options(self, selected: str) -> str:
        """Render priority ``<option>`` elements.

        Args:
            selected: Priority key marked ``selected``.

        Returns:
            Escaped option markup.
        """
        return "".join(
            f'<option value="{html.escape(priority)}"'
            f"{' selected' if priority == selected else ''}>"
            f"{html.escape(priority)}</option>"
            for priority in PRIORITY_HEADINGS
        )

    def _type_options(self, selected: str | None) -> str:
        """Render type ``<option>`` elements.

        Args:
            selected: Type tag marked ``selected``, if any.

        Returns:
            Escaped option markup.
        """
        return "".join(
            f'<option value="{html.escape(task_type)}"'
            f"{' selected' if task_type == selected else ''}>"
            f"{html.escape(task_type)}</option>"
            for task_type in sorted(TYPE_TAGS)
        )

    def _render_add_form(self, selection: BoardSelection) -> str:
        """Render the task creation form.

        Args:
            selection: Request-local board selection for the form action.

        Returns:
            Accessible form covering the repository add contract.
        """
        action = f"/tasks?{urlencode({'repo': selection.key})}"
        return (
            '<div class="modal modal-blur fade" id="add-task-modal" tabindex="-1" '
            'aria-labelledby="add-task-modal-title" aria-hidden="true">'
            '<div class="modal-dialog modal-lg modal-dialog-centered"><div class="modal-content">'
            '<div class="modal-header"><h2 class="modal-title" id="add-task-modal-title">New task</h2>'
            '<button type="button" class="btn-close" data-bs-dismiss="modal" '
            f'aria-label="Close"></button></div><form method="post" action="{html.escape(action, quote=True)}">'
            f"{self._csrf_field()}"
            '<div class="modal-body"><div class="mb-3"><label class="form-label">Title '
            '<input class="form-control" name="title" required></label></div>'
            '<div class="row"><div class="col-md-6 mb-3"><label class="form-label">Priority '
            f'<select class="form-select" name="priority">'
            f"{self._priority_options('P2')}</select></label></div>"
            '<div class="col-md-6 mb-3"><label class="form-label">Type '
            f'<select class="form-select" name="task_type">'
            f"{self._type_options(None)}</select></label></div></div>"
            '<div class="mb-3"><label class="form-label">Acceptance '
            '<textarea class="form-control" name="acceptance"></textarea></label></div>'
            '<label class="form-check"><input class="form-check-input" type="checkbox" '
            'name="simple"><span class="form-check-label">Simple task</span></label>'
            '<details class="mt-3"><summary>Advanced fields</summary><div class="mt-3">'
            '<label class="form-label">Tags <input class="form-control" name="tags" '
            'placeholder="browser, local"></label><label class="form-label">Context '
            '<textarea class="form-control" name="context"></textarea></label>'
            '<label class="form-label">Related <input class="form-control" name="related"></label>'
            '<label class="form-label">Blocked by <input class="form-control" name="blocked_by" '
            'placeholder="T001, T002"></label></div></details></div>'
            '<div class="modal-footer"><button type="button" class="btn btn-link" '
            'data-bs-dismiss="modal">Cancel</button><button class="btn btn-primary" '
            'type="submit">Add task</button></div></form></div></div></div>'
        )

    def _render_actions(self, task: Task, selection: BoardSelection) -> str:
        """Render legal lifecycle controls for one task.

        Args:
            task: Task whose current state selects available actions.
            selection: Request-local board selection for form actions.

        Returns:
            Forms for legal transitions, empty for terminal tasks.
        """
        if task.state == "open":
            actions = (
                ("review", "Move to Review", "ti-arrow-right"),
                ("complete", "Complete", "ti-check"),
            )
        elif task.state == "review":
            actions = (
                ("reopen", "Reopen", "ti-arrow-back-up"),
                ("complete", "Complete", "ti-check"),
            )
        else:
            return ""
        path = (
            f"/tasks/{html.escape(task.task_id)}/transition"
            f"?{urlencode({'repo': selection.key})}"
        )
        controls = "".join(
            f'<form method="post" action="{path}">{self._csrf_field()}'
            '<button class="btn btn-outline-secondary btn-sm" '
            f'name="action" value="{action}"><i class="ti {icon}" '
            f'aria-hidden="true"></i> {label}</button></form>'
            for action, label, icon in actions
        )
        cancel = (
            '<details><summary class="btn btn-outline-danger btn-sm">'
            '<i class="ti ti-x" aria-hidden="true"></i> Cancel</summary>'
            f'<form method="post" action="{path}">{self._csrf_field()}'
            '<label>Reason <input name="reason" required></label>'
            '<button class="btn btn-danger btn-sm" name="action" value="cancel">'
            '<i class="ti ti-x" aria-hidden="true"></i> Cancel task</button>'
            "</form></details>"
        )
        return f'<div class="actions">{controls}{cancel}</div>'

    def _csrf_field(self) -> str:
        """Render the hidden CSRF token field.

        Returns:
            Escaped hidden input markup.
        """
        return (
            f'<input type="hidden" name="_csrf" value="{html.escape(self.csrf_token)}">'
        )

    def _selection_label(self, selection: BoardSelection) -> str:
        """Return the dropdown label for one selection.

        Args:
            selection: Selection whose visible name should be shown.

        Returns:
            ``All``, ``Current``, or the configured Repository Name.
        """
        if selection.key == "all":
            return "All"
        if selection.key == "current":
            return "Current"
        return selection.name or selection.key

    def _render_repository_menu(self, selection: BoardSelection) -> str:
        """Render the Tabler repository dropdown.

        Args:
            selection: Currently displayed board selection.

        Returns:
            Navbar dropdown markup listing All, configured entries, and Current.
        """
        items = [
            (
                "All",
                self.selection_path(BoardSelection("all", None, None)),
            )
        ]
        items.extend(
            (entry.name, self.selection_path(BoardSelection(entry.name, entry.name, None)))
            for entry in self.collection
        )
        if self.default_selection.key == "current":
            items.append(
                (
                    "Current",
                    self.selection_path(self.default_selection),
                )
            )
        options = "".join(
            f'<a class="dropdown-item" href="{html.escape(path, quote=True)}">'
            f"{html.escape(label)}</a>"
            for label, path in items
        )
        label = html.escape(self._selection_label(selection))
        return (
            '<div class="dropdown ms-3">'
            '<button class="btn dropdown-toggle" type="button" '
            'data-bs-toggle="dropdown" aria-expanded="false">'
            f"{label}</button>"
            f'<div class="dropdown-menu">{options}</div></div>'
        )

    def _page(
        self,
        title: str,
        content: str,
        *,
        selection: BoardSelection,
        header_action: str = "",
    ) -> str:
        """Wrap content in the shared HTML document.

        Args:
            title: Browser page title.
            content: Trusted application-rendered markup.

        Keyword Args:
            selection: Selection whose menu and label should be shown.
            header_action: Trusted application-rendered navbar action.

        Returns:
            Complete HTML document.
        """
        menu = self._render_repository_menu(selection)
        return (
            '<!doctype html><html lang="en"><head>'
            '<meta charset="utf-8"><meta name="viewport" '
            'content="width=device-width, initial-scale=1">'
            f"<title>{html.escape(title)}</title>"
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css" '
            'integrity="sha384-kz+I4+mczbNiZfLAJMxOlJaZmnbRYhARHNkR2k6tal4gz7OL33/0puDD3SvkiNX9" crossorigin="anonymous">'
            '<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css" '
            'integrity="sha384-ND+q1IVc0KDElX60dZaqKc7Xl9cdxd2PpU2JfVUHcurCkFVtVLFdt9vJfxtHSL3p" crossorigin="anonymous">'
            "<style>"
            ".board-columns{display:grid;grid-template-columns:repeat(4,minmax(14rem,1fr));gap:1rem}"
            ".board-column{min-height:28rem;padding:1rem;border:1px solid var(--tblr-border-color);border-radius:var(--tblr-border-radius);background:var(--tblr-bg-surface-secondary)}"
            ".board-empty{display:grid;min-height:20rem;place-content:center;gap:.5rem;text-align:center}.board-empty .ti{font-size:2rem}"
            ".task-title{color:var(--tblr-primary);font-weight:600;border:0;background:transparent;padding:0;text-align:left;cursor:pointer}.actions{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.75rem}.terminal-overflow summary{color:var(--tblr-secondary);cursor:pointer;text-align:center}"
            "@media(max-width:1199px){.board-columns{grid-template-columns:repeat(2,minmax(14rem,1fr))}}"
            "@media(max-width:767px){.board-columns{grid-template-columns:1fr}.board-column{min-height:0}}"
            '</style></head><body><div class="page"><header class="navbar navbar-expand-md navbar-light py-3"><div class="container-xl"><a class="navbar-brand fs-2" href="/"><i class="ti ti-robot text-primary fs-2" aria-hidden="true"></i> bot-todo</a><span class="navbar-text border-start ps-3 ms-3 fs-3 d-none d-sm-inline">Kanban Board</span>'
            f"{menu}"
            f'<div class="ms-auto">{header_action}</div></div></header><div class="page-wrapper">'
            '<main class="page-body"><div class="container-xl">'
            f"{content}</div></main></div></div>"
            '<script src="https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js" integrity="sha384-pku3birjgGovaJ9ngF7SaxKkF/eYUvBjiMJ+jTtWbNesIj2Rud2K63+4JD7EF4gk" crossorigin="anonymous"></script>'
            "</body></html>"
        )


class KanbanRequestHandler(BaseHTTPRequestHandler):
    """Adapt loopback HTTP requests to a :class:`KanbanWebApp`.

    Args:
        *args: Arguments supplied by ``ThreadingHTTPServer``.

    Keyword Args:
        app: Board application handling requests.
        **kwargs: Arguments supplied by ``ThreadingHTTPServer``.
    """

    def __init__(self, *args: Any, app: KanbanWebApp, **kwargs: Any) -> None:
        """Initialize one request handler.

        Args:
            *args: Arguments supplied by ``ThreadingHTTPServer``.

        Keyword Args:
            app: Board application handling requests.
            **kwargs: Arguments supplied by ``ThreadingHTTPServer``.
        """
        #: Board application handling requests.
        self.app = app
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        """Serve one board page.

        Side Effects:
            Reads a repository and writes an HTTP response.
        """
        if not self._trusted_host():
            self._send_html(
                403,
                self.app.render_error(
                    "Forbidden",
                    "Request host not allowed.",
                    self.app.default_selection,
                ),
            )
            return
        parts = urlsplit(self.path)
        selection = self.app.resolve_selection(parts.query)
        if selection is None:
            self._send_html(404, self.app.render_not_found(self.app.default_selection))
            return
        try:
            if parts.path == "/":
                self._send_html(200, self.app.render_board(selection))
                return
        except TodoError as error:
            self._send_todo_error(error, selection)
            return
        self._send_html(404, self.app.render_not_found(selection))

    def do_POST(self) -> None:
        """Apply one board mutation.

        Side Effects:
            Reads a form, mutates a repository, and writes an HTTP response.
        """
        if not self._trusted_host():
            self._send_html(
                403, self.app.render_error("Forbidden", "Request host not allowed.")
            )
            return
        if self.headers.get("Origin") != self.app.origin:
            self._send_html(
                403, self.app.render_error("Forbidden", "Request origin not allowed.")
            )
            return
        media_type = self.headers.get_content_type()
        if media_type != "application/x-www-form-urlencoded":
            self._send_html(
                415,
                self.app.render_error(
                    "Unsupported media type", "Submit a URL-encoded form."
                ),
            )
            return
        path = urlsplit(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_html(
                400, self.app.render_error("Malformed form", "Invalid body length.")
            )
            return
        if length < 0:
            self._send_html(
                400, self.app.render_error("Malformed form", "Invalid body length.")
            )
            return
        if length > MAX_FORM_BYTES:
            self.close_connection = True
            self._send_html(
                413,
                self.app.render_error(
                    "Request too large", "Form bodies are limited to 64 KiB."
                ),
            )
            return
        try:
            encoded_form = self.rfile.read(length).decode("ascii")
            if re.search(r"%(?![0-9A-Fa-f]{2})", encoded_form):
                raise ValueError("invalid percent escape")
            parsed = parse_qs(
                encoded_form,
                keep_blank_values=True,
                max_num_fields=32,
                encoding="utf-8",
                errors="strict",
                strict_parsing=True,
            )
        except (UnicodeDecodeError, ValueError):
            self._send_html(
                400, self.app.render_error("Malformed form", "Invalid form encoding.")
            )
            return
        fields = {key: values[-1] for key, values in parsed.items()}
        supplied_token = fields.get("_csrf", "")
        if not secrets.compare_digest(supplied_token, self.app.csrf_token):
            self._send_html(
                403, self.app.render_error("Forbidden", "Invalid form token.")
            )
            return
        selection = self.app.resolve_selection(urlsplit(self.path).query)
        if selection is None:
            self._send_html(404, self.app.render_not_found(self.app.default_selection))
            return
        try:
            if path == "/tasks":
                self.app.add_task(selection, fields)
            else:
                parts = path.split("/")
                if (
                    len(parts) != 4
                    or parts[1] != "tasks"
                    or parts[3] not in {"transition", "edit"}
                ):
                    self._send_html(404, self.app.render_not_found(selection))
                    return
                task_id = unquote(parts[2])
                if parts[3] == "edit":
                    self.app.edit_task(selection, task_id, fields)
                else:
                    self.app.transition_task(selection, task_id, fields)
        except TodoError as error:
            if error.code == "invalid_document":
                self._send_html(
                    400, self.app.render_error("Bad request", str(error), selection)
                )
                return
            if error.code == "unknown_task" and path.endswith("/edit"):
                self._send_html(404, self.app.render_not_found(selection))
                return
            self._send_todo_error(error, selection)
            return
        self.send_response(303)
        self.send_header("Location", self.app.selection_path(selection))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def end_headers(self) -> None:
        """Apply browser hardening and finish the response headers.

        Side Effects:
            Writes security headers and the terminating header block.
        """
        self._send_security_headers()
        super().end_headers()

    def _trusted_host(self) -> bool:
        """Report whether the request names the bound loopback origin.

        Returns:
            ``True`` only for the exact bound host and port.
        """
        return self.headers.get("Host") == self.app.origin.removeprefix("http://")

    def _send_todo_error(
        self, error: TodoError, selection: BoardSelection | None = None
    ) -> None:
        """Map a repository error to a concise HTTP response.

        Side Effects:
            Writes an HTML error response to the client socket.

        Args:
            error: Repository failure to present.
            selection: Selection used for the repository menu and return link.
        """
        if selection is None:
            selection = self.app.default_selection
        status = {
            "unknown_task": 404,
            "repository_not_found": 404,
            "usage": 400,
            "conflict": 409,
            "invalid_transition": 409,
            "migration_required": 409,
            "aggregate_partial_failure": 500,
        }.get(error.code, 500)
        title = {
            400: "Bad request",
            404: "Not found",
            409: "Conflict",
            500: "Repository error",
        }[status]
        self._send_html(
            status, self.app.render_error(title, str(error), selection)
        )

    def log_message(self, _format: str, *args: Any) -> None:
        """Suppress standard-library access logging.

        Args:
            _format: Standard-library log format, unused.
            *args: Standard-library log values, unused.
        """

    def _send_html(self, status: int, body: str) -> None:
        """Write one HTML response.

        Side Effects:
            Writes status, headers, and body to the client socket.

        Args:
            status: HTTP response status.
            body: Complete HTML document.
        """
        encoded = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_security_headers(self) -> None:
        """Write browser hardening headers.

        Side Effects:
            Adds headers to the current HTTP response.
        """
        for name, value in SECURITY_HEADERS:
            self.send_header(name, value)


def run_web(
    store: TodoStore | None,
    *,
    collection: RepositoryCollection,
    port: int,
    open_browser: bool,
) -> None:
    """Serve the Kanban Board until interrupted.

    Side Effects:
        Will bind a loopback socket and may open the default browser.

    Args:
        store: Launch Task Repository, or ``None`` when All is selected.

    Keyword Args:
        collection: Immutable Repository Collection loaded before bind.
        port: Requested loopback TCP port.
        open_browser: Whether to open the board after binding.
    """
    app = KanbanWebApp(store, collection)
    with app.create_server(port) as server:
        url = f"{app.origin}{app.selection_path(app.default_selection)}"
        print(f"Kanban Board: {url}")
        if open_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
