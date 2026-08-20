"""Serve one Task Repository as a local Kanban Board."""

from __future__ import annotations

import html
import re
import secrets
import webbrowser
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from bot_todo.repository import (
    PRIORITY_HEADINGS,
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


class KanbanWebApp:
    """Render one Task Repository as a local Kanban Board.

    Args:
        store: Repository read and mutated by the board.
        name: Configured Repository Name, when selected by name.
        csrf_token: Token override used by deterministic tests.
    """

    def __init__(
        self,
        store: TodoStore,
        name: str | None = None,
        csrf_token: str | None = None,
    ) -> None:
        """Initialize a board over one repository.

        Args:
            store: Repository read and mutated by the board.
            name: Configured Repository Name, when selected by name.
            csrf_token: Token override used by deterministic tests.
        """
        #: Repository read and mutated by the board.
        self.store = store
        #: Configured Repository Name, when selected by name.
        self.name = name
        #: Secret required by every state-changing form.
        self.csrf_token = csrf_token or secrets.token_urlsafe(32)
        #: Exact origin assigned after the loopback socket binds.
        self.origin = ""

    def create_server(self, port: int) -> ThreadingHTTPServer:
        """Bind an HTTP server to loopback.

        Args:
            port: Requested TCP port; zero asks the operating system to choose.

        Returns:
            Bound server ready for ``serve_forever``.

        Raises:
            ValueError: If the port is outside the TCP port range.

        Side Effects:
            Binds a loopback TCP socket.
        """
        if not 0 <= port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        handler = partial(KanbanRequestHandler, app=self)
        server = ThreadingHTTPServer(("127.0.0.1", port), handler)
        server.daemon_threads = True
        self.origin = f"http://127.0.0.1:{server.server_port}"
        return server

    def render_board(self) -> str:
        """Render all recent tasks in Task State columns.

        Side Effects:
            Reads the selected Task Repository.

        Returns:
            Complete board HTML document.
        """
        snapshot = self.store.snapshot()
        writable = snapshot.document.format_version == WRITE_FORMAT_VERSION
        active = [
            task
            for priority in PRIORITY_HEADINGS
            for task in snapshot.document.active[priority]
        ]
        columns = (
            ("Open", [task for task in active if task.state == "open"]),
            ("Review", [task for task in active if task.state == "review"]),
            (
                "Completed",
                [task for task in snapshot.document.done if task.state == "completed"],
            ),
            (
                "Cancelled",
                [task for task in snapshot.document.done if task.state == "cancelled"],
            ),
        )
        columns_html = "".join(
            self._render_column(heading, tasks, writable=writable)
            for heading, tasks in columns
        )
        if writable:
            header_action = (
                '<button class="btn btn-primary" type="button" data-bs-toggle="modal" '
                'data-bs-target="#add-task-modal"><i class="ti ti-plus" '
                'aria-hidden="true"></i> New task</button>'
            )
            mutation_area = self._render_add_form()
        else:
            header_action = ""
            mutation_area = (
                '<p role="status" class="alert alert-warning"><i class="ti ti-lock" '
                'aria-hidden="true"></i> This repository is read-only. '
                "Run <code>bot-todo migrate</code> to enable board mutations.</p>"
            )
        content = f'{mutation_area}<div class="board-columns">{columns_html}</div>'
        return self._page("Kanban Board", content, header_action=header_action)

    def render_not_found(self) -> str:
        """Render the generic missing-page response.

        Returns:
            Complete error HTML document.
        """
        return self._page(
            "Not found",
            '<div class="card"><div class="card-body text-center py-6">'
            '<i class="ti ti-file-off fs-1 text-secondary" aria-hidden="true"></i>'
            '<h1 class="h2 mt-2">Not found</h1>'
            '<p class="text-secondary mb-0">The requested page does not exist.</p>'
            "</div></div>",
        )

    def render_error(self, title: str, message: str) -> str:
        """Render one concise error page.

        Args:
            title: Human-readable error title.
            message: Safe error explanation.

        Returns:
            Complete escaped error HTML document.
        """
        content = (
            '<div class="card"><div class="card-body">'
            f'<h1 class="h2">{html.escape(title)}</h1>'
            f"<p>{html.escape(message)}</p>"
            '<a class="btn btn-primary" href="/">Return to Kanban Board</a>'
            "</div></div>"
        )
        return self._page(title, content)

    def render_task(self, task_id: str) -> str:
        """Render one task's canonical details.

        Side Effects:
            Reads the selected Task Repository and may read its archive.

        Args:
            task_id: Task identifier to display.

        Returns:
            Complete task-detail HTML document.

        Raises:
            TodoError: If the task is unknown or repository data is invalid.
        """
        task = self.store.snapshot().find(task_id)
        claim = task.claim
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
            (
                "Claim",
                None
                if claim is None
                else f"{claim.actor} | {claim.claimed_on} | {claim.branch}",
            ),
            ("Reviewed", task.reviewed_on),
            ("Closed", task.closed_on),
            ("Reason", task.reason),
        )
        details = "".join(
            f'<dt class="col-sm-3 text-secondary">{html.escape(label)}</dt>'
            f'<dd class="col-sm-9">{html.escape(value or "—")}</dd>'
            for label, value in values
        )
        title = f"{task.task_id} — {task.title}"
        content = (
            '<div class="card"><div class="card-body">'
            '<p><a href="/"><i class="ti ti-arrow-left" aria-hidden="true"></i> '
            "Kanban Board</a></p>"
            f'<h1 class="h2">{html.escape(title)}</h1>'
            f'<dl class="row mb-0">{details}</dl></div></div>'
        )
        return self._page(title, content)

    def add_task(self, fields: dict[str, str]) -> Task:
        """Add one task from browser form fields.

        Side Effects:
            Mutates the selected Task Repository.

        Args:
            fields: Parsed URL-encoded form fields.

        Returns:
            Newly allocated task.

        Raises:
            TodoError: If form values violate the add contract.
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
        with self.store.transaction() as transaction:
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

    def transition_task(self, task_id: str, fields: dict[str, str]) -> Task:
        """Apply one supported lifecycle action.

        Side Effects:
            Mutates the selected Task Repository.

        Args:
            task_id: Task receiving the transition.
            fields: Parsed form fields including the action.

        Returns:
            Updated task.

        Raises:
            TodoError: If the action is unsupported or invalid for the task.
        """
        action = fields.get("action")
        with self.store.transaction() as transaction:
            if action == "review":
                return transaction.review(task_id)
            if action == "reopen":
                return transaction.reopen(task_id)
            if action == "complete":
                return transaction.close(task_id, "completed")
            if action == "cancel":
                return transaction.close(task_id, "cancelled", fields.get("reason"))
            raise TodoError("unknown transition action", "usage")

    def _render_card(self, task: Task, *, writable: bool) -> str:
        """Render one task card.

        Args:
            task: Task displayed by the card.

        Keyword Args:
            writable: Whether lifecycle forms may be rendered.

        Returns:
            Escaped task card markup.
        """
        task_id = html.escape(task.task_id)
        title = html.escape(task.title)
        actions = self._render_actions(task) if writable else ""
        return (
            '<article class="card card-sm mb-2"><div class="card-body">'
            f'<a class="task-title" href="/tasks/{task_id}"><strong>{task_id}</strong> {title}</a>'
            '<div class="mt-2"><span class="badge bg-blue-lt">'
            f"{html.escape(task.priority or task.state)}</span> "
            f'<span class="badge bg-secondary-lt">{html.escape(task.task_type or "untyped")}'
            f"</span></div>{actions}</div></article>"
        )

    def _render_column(self, heading: str, tasks: list[Task], *, writable: bool) -> str:
        """Render one responsive board column with bounded terminal cards.

        Args:
            heading: Human-readable task state heading.
            tasks: Tasks assigned to the column.

        Keyword Args:
            writable: Whether lifecycle forms may be rendered.

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
        cards = "".join(self._render_card(task, writable=writable) for task in visible)
        overflow = tasks[6:] if state in {"completed", "cancelled"} else []
        if overflow:
            label = f"+ {len(overflow)} more {state} task{'s' if len(overflow) != 1 else ''}"
            cards += (
                '<details class="terminal-overflow"><summary>'
                f"{label}</summary>{''.join(self._render_card(task, writable=writable) for task in overflow)}"
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

    def _render_add_form(self) -> str:
        """Render the task creation form.

        Returns:
            Accessible form covering the repository add contract.
        """
        priorities = "".join(
            f'<option value="{html.escape(priority)}"'
            f"{' selected' if priority == 'P2' else ''}>"
            f"{html.escape(priority)}</option>"
            for priority in PRIORITY_HEADINGS
        )
        task_types = "".join(
            f'<option value="{html.escape(task_type)}">{html.escape(task_type)}</option>'
            for task_type in sorted(TYPE_TAGS)
        )
        return (
            '<div class="modal modal-blur fade" id="add-task-modal" tabindex="-1" '
            'aria-labelledby="add-task-modal-title" aria-hidden="true">'
            '<div class="modal-dialog modal-lg modal-dialog-centered"><div class="modal-content">'
            '<div class="modal-header"><h2 class="modal-title" id="add-task-modal-title">New task</h2>'
            '<button type="button" class="btn-close" data-bs-dismiss="modal" '
            'aria-label="Close"></button></div><form method="post" action="/tasks">'
            f"{self._csrf_field()}"
            '<div class="modal-body"><div class="mb-3"><label class="form-label">Title '
            '<input class="form-control" name="title" required></label></div>'
            '<div class="row"><div class="col-md-6 mb-3"><label class="form-label">Priority '
            f'<select class="form-select" name="priority">{priorities}</select></label></div>'
            '<div class="col-md-6 mb-3"><label class="form-label">Type '
            f'<select class="form-select" name="task_type">{task_types}</select></label></div></div>'
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

    def _render_actions(self, task: Task) -> str:
        """Render legal lifecycle controls for one task.

        Args:
            task: Task whose current state selects available actions.

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
        path = f"/tasks/{html.escape(task.task_id)}/transition"
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

    def _page(self, title: str, content: str, *, header_action: str = "") -> str:
        """Wrap content in the shared HTML document.

        Args:
            title: Browser page title.
            content: Trusted application-rendered markup.

        Keyword Args:
            header_action: Trusted application-rendered navbar action.

        Returns:
            Complete HTML document.
        """
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
            ".task-title{color:var(--tblr-primary);font-weight:600}.actions{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.75rem}.terminal-overflow summary{color:var(--tblr-secondary);cursor:pointer;text-align:center}"
            "@media(max-width:1199px){.board-columns{grid-template-columns:repeat(2,minmax(14rem,1fr))}}"
            "@media(max-width:767px){.board-columns{grid-template-columns:1fr}.board-column{min-height:0}}"
            '</style></head><body><div class="page"><header class="navbar navbar-expand-md navbar-light py-3"><div class="container-xl"><a class="navbar-brand fs-2" href="/"><i class="ti ti-robot text-primary fs-2" aria-hidden="true"></i> bot-todo</a><span class="navbar-text border-start ps-3 ms-3 fs-3 d-none d-sm-inline">Kanban Board</span>'
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
                403, self.app.render_error("Forbidden", "Request host not allowed.")
            )
            return
        path = urlsplit(self.path).path
        try:
            if path == "/":
                self._send_html(200, self.app.render_board())
                return
            if path.startswith("/tasks/") and "/" not in path.removeprefix("/tasks/"):
                self._send_html(200, self.app.render_task(unquote(path[7:])))
                return
        except TodoError as error:
            self._send_todo_error(error)
            return
        self._send_html(404, self.app.render_not_found())

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
        try:
            if path == "/tasks":
                self.app.add_task(fields)
            else:
                parts = path.split("/")
                if len(parts) != 4 or parts[1] != "tasks" or parts[3] != "transition":
                    self._send_html(404, self.app.render_not_found())
                    return
                self.app.transition_task(unquote(parts[2]), fields)
        except TodoError as error:
            if error.code == "invalid_document":
                self._send_html(400, self.app.render_error("Bad request", str(error)))
                return
            self._send_todo_error(error)
            return
        self.send_response(303)
        self.send_header("Location", "/")
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

    def _send_todo_error(self, error: TodoError) -> None:
        """Map a repository error to a concise HTTP response.

        Side Effects:
            Writes an HTML error response to the client socket.

        Args:
            error: Repository failure to present.
        """
        status = {
            "unknown_task": 404,
            "repository_not_found": 404,
            "usage": 400,
            "conflict": 409,
            "invalid_transition": 409,
            "migration_required": 409,
        }.get(error.code, 500)
        title = {
            400: "Bad request",
            404: "Not found",
            409: "Conflict",
            500: "Repository error",
        }[status]
        self._send_html(status, self.app.render_error(title, str(error)))

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
    store: TodoStore,
    *,
    name: str | None,
    port: int,
    open_browser: bool,
) -> None:
    """Serve one repository until interrupted.

    Side Effects:
        Will bind a loopback socket and may open the default browser.

    Args:
        store: Repository served by the board.

    Keyword Args:
        name: Configured Repository Name, when selected by name.
        port: Requested loopback TCP port.
        open_browser: Whether to open the board after binding.
    """
    app = KanbanWebApp(store, name)
    with app.create_server(port) as server:
        print(f"Kanban Board: {app.origin}")
        if open_browser:
            webbrowser.open(app.origin)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
