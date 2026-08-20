"""Loopback HTTP tests for the local Kanban Board."""

from __future__ import annotations

import contextlib
import errno
import http.client
import io
import socket
import threading
from http.server import ThreadingHTTPServer
from unittest import mock
from urllib.parse import urlencode

from bot_todo.repository import TodoError, TodoStore
from bot_todo.web import KanbanWebApp, run_web
from tests.support import TodoCliTestCase


class KanbanWebTests(TodoCliTestCase):
    """Exercise the Kanban Board through a real loopback HTTP server."""

    def setUp(self) -> None:
        """Create a repository and start an ephemeral Kanban server."""
        super().setUp()
        self.store = TodoStore(self.root)
        self.app = KanbanWebApp(self.store, csrf_token="test-token")
        self.server = self.app.create_server(0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_port

    def tearDown(self) -> None:
        """Stop the Kanban server and remove its repository."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        super().tearDown()

    def get(self, path: str) -> tuple[int, dict[str, str], str]:
        """Request one board page.

        Args:
            path: Absolute request path.

        Returns:
            Status, response headers, and decoded body.
        """
        return self.request("GET", path)

    def request(
        self,
        method: str,
        path: str,
        body: str | bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, dict[str, str], str]:
        """Send one raw request to the loopback server.

        Args:
            method: HTTP request method.
            path: Absolute request path.
            body: Optional request body.
            headers: Optional request headers.

        Returns:
            Status, response headers, and decoded body.
        """
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        body = response.read().decode()
        headers = dict(response.getheaders())
        connection.close()
        return response.status, headers, body

    def _task_modal(self, body: str, task_id: str) -> str:
        """Return the HTML for one task-detail modal.

        Args:
            body: Board HTML document.
            task_id: Task whose modal should be extracted.

        Returns:
            Modal markup from its opening ``div`` through the next modal or board.

        Raises:
            AssertionError: If the modal id is missing.
        """
        marker = f'<div class="modal modal-blur fade" id="task-{task_id}-modal"'
        self.assertIn(marker, body)
        start = body.index(marker)
        rest = body[start + len(marker) :]
        next_modal = rest.find('<div class="modal modal-blur')
        next_board = rest.find('<div class="board-columns"')
        cuts = [offset for offset in (next_modal, next_board) if offset != -1]
        end_offset = min(cuts) if cuts else len(rest)
        return body[start : start + len(marker) + end_offset]

    def post(
        self, path: str, fields: dict[str, str]
    ) -> tuple[int, dict[str, str], str]:
        """Submit one trusted board form.

        Args:
            path: Absolute request path.
            fields: URL-encoded form fields without the CSRF token.

        Returns:
            Status, response headers, and decoded body.
        """
        body = urlencode({"_csrf": "test-token", **fields})
        return self.request(
            "POST",
            path,
            body,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.app.origin,
            },
        )

    def test_board_groups_tasks_by_state_and_escapes_content(self) -> None:
        """Catch missing columns, wrong state grouping, and unescaped titles."""
        with self.store.transaction() as transaction:
            opened = transaction.add(
                title="Open <script>", priority="P0", task_type="bug", simple=True
            )
            reviewing = transaction.add(
                title="Needs review", priority="P1", task_type="feature", simple=True
            )
            completed = transaction.add(
                title="Finished", priority="P2", task_type="chore", simple=True
            )
            cancelled = transaction.add(
                title="Stopped", priority="P2", task_type="docs", simple=True
            )
            transaction.review(reviewing.task_id)
            transaction.close(completed.task_id, "completed")
            transaction.close(cancelled.task_id, "cancelled", "No longer needed")

        status, _, body = self.get("/")

        self.assertEqual(status, 200)
        for heading in ("Open", "Review", "Completed", "Cancelled"):
            self.assertIn(f"> {heading}</h2>", body)
        self.assertIn("Open &lt;script&gt;", body)
        self.assertNotIn("Open <script>", body)
        self.assertLess(body.index(opened.task_id), body.index(reviewing.task_id))
        self.assertLess(body.index(reviewing.task_id), body.index(completed.task_id))
        self.assertLess(body.index(completed.task_id), body.index(cancelled.task_id))

    def test_board_shows_canonical_details_in_a_tabler_modal(self) -> None:
        """Catch a board that omits persisted task fields or restores a detail page."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="Inspect details",
                priority="P1",
                task_type="feature",
                tags=["browser"],
                acceptance="Every field is visible",
                context="Local operator",
                related="T009",
            )
            transaction.claim(task.task_id, "tester", "test-branch")

        status, _, body = self.get("/")

        self.assertEqual(status, 200)
        modal_id = f"task-{task.task_id}-modal"
        title_id = f"{modal_id}-title"
        self.assertIn(
            f'<button type="button" class="task-title" data-bs-toggle="modal" '
            f'data-bs-target="#{modal_id}">',
            body,
        )
        self.assertNotIn(f'href="/tasks/{task.task_id}"', body)
        modal = self._task_modal(body, task.task_id)
        self.assertIn(f'class="modal modal-blur fade" id="{modal_id}"', modal)
        self.assertIn(f'aria-labelledby="{title_id}"', modal)
        self.assertIn(f'id="{title_id}"', modal)
        self.assertIn(f"{task.task_id} — Inspect details", modal)
        self.assertIn(f'action="/tasks/{task.task_id}/edit"', modal)
        self.assertIn('name="title" value="Inspect details"', modal)
        self.assertIn('<option value="P1" selected>', modal)
        self.assertIn('<option value="feature" selected>', modal)
        self.assertIn("Every field is visible", modal)
        self.assertIn('name="tags" value="browser"', modal)
        self.assertIn("Local operator", modal)
        self.assertIn('name="related" value="T009"', modal)
        self.assertIn('<details class="mt-3" open>', modal)
        self.assertIn("tester | ", modal)
        self.assertIn(
            '<button type="button" class="btn btn-link" data-bs-dismiss="modal">'
            "Cancel</button>",
            modal,
        )
        self.assertIn('type="submit">Save</button>', modal)
        self.assertNotIn(">Close</button>", modal)
        self.assertNotIn(f'action="/tasks/{task.task_id}/transition"', modal)
        self.assertIn(f'action="/tasks/{task.task_id}/transition"', body)

    def test_former_detail_route_returns_generic_not_found(self) -> None:
        """Catch a leftover GET /tasks/<id> page for a task that is on the board."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="Still on the board",
                priority="P2",
                task_type="chore",
                simple=True,
            )

        status, _, body = self.get(f"/tasks/{task.task_id}")

        self.assertEqual(status, 404)
        self.assertIn("The requested page does not exist.", body)
        self.assertNotIn("unknown task ID", body)
        self.assertNotIn("Traceback", body)

    def test_every_html_surface_uses_the_shared_tabler_content_shell(self) -> None:
        """Catch detail and error responses falling outside the Tabler shell."""
        with self.store.transaction() as transaction:
            transaction.add(
                title="Shell check", priority="P2", task_type="chore", simple=True
            )

        responses = (
            self.get("/"),
            self.get("/missing"),
            self.get("/tasks/T999"),
            self.request("GET", "/", headers={"Host": "evil.example"}),
        )

        for status, _, body in responses:
            with self.subTest(status=status):
                self.assertIn(
                    '<main class="page-body"><div class="container-xl">', body
                )
                self.assertIn('class="navbar', body)
                self.assertIn("@tabler/core@1.4.0", body)

    def test_add_form_persists_required_and_advanced_fields(self) -> None:
        """Catch an add route that drops optional repository fields."""
        status, headers, _ = self.post(
            "/tasks",
            {
                "title": "Created in browser",
                "priority": "P1",
                "task_type": "feature",
                "acceptance": "Visible on the board",
                "tags": "browser, local",
                "context": "Human workflow",
                "related": "T009",
                "blocked_by": "",
            },
        )

        task = self.store.snapshot().find("T001")
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/")
        self.assertEqual(task.title, "Created in browser")
        self.assertEqual(task.priority, "P1")
        self.assertEqual(task.task_type, "feature")
        self.assertEqual(task.user_tags, ["browser", "local"])
        self.assertEqual(task.acceptance, "Visible on the board")
        self.assertEqual(task.context, "Human workflow")
        self.assertEqual(task.related, "T009")

    def test_transition_route_applies_each_supported_lifecycle_action(self) -> None:
        """Catch missing or misrouted Kanban lifecycle actions."""
        with self.store.transaction() as transaction:
            review_task = transaction.add(
                title="Review me", priority="P1", task_type="feature", simple=True
            )
            reopen_task = transaction.add(
                title="Reopen me", priority="P1", task_type="bug", simple=True
            )
            complete_task = transaction.add(
                title="Complete me", priority="P2", task_type="chore", simple=True
            )
            cancel_task = transaction.add(
                title="Cancel me", priority="P2", task_type="docs", simple=True
            )
            transaction.review(reopen_task.task_id)

        cases: tuple[tuple[str, str, dict[str, str], str], ...] = (
            (review_task.task_id, "review", {}, "review"),
            (reopen_task.task_id, "reopen", {}, "open"),
            (complete_task.task_id, "complete", {}, "completed"),
            (
                cancel_task.task_id,
                "cancel",
                {"reason": "Superseded"},
                "cancelled",
            ),
        )
        for task_id, action, extra, expected_state in cases:
            with self.subTest(action=action):
                status, headers, _ = self.post(
                    f"/tasks/{task_id}/transition", {"action": action, **extra}
                )
                task = self.store.snapshot().find(task_id)
                self.assertEqual(status, 303)
                self.assertEqual(headers["Location"], "/")
                self.assertEqual(task.state, expected_state)
        self.assertEqual(
            self.store.snapshot().find(cancel_task.task_id).reason, "Superseded"
        )

    def test_board_exposes_add_fields_and_accessible_transition_forms(self) -> None:
        """Catch a board that renders state but offers no human controls."""
        with self.store.transaction() as transaction:
            opened = transaction.add(
                title="Open action", priority="P1", task_type="feature", simple=True
            )
            reviewing = transaction.add(
                title="Review action", priority="P1", task_type="bug", simple=True
            )
            transaction.review(reviewing.task_id)

        status, _, body = self.get("/")

        self.assertEqual(status, 200)
        self.assertIn('<form method="post" action="/tasks">', body)
        self.assertIn('<option value="P2" selected>P2</option>', body)
        for field in (
            "title",
            "priority",
            "task_type",
            "acceptance",
            "simple",
            "tags",
            "context",
            "related",
            "blocked_by",
        ):
            self.assertIn(f'name="{field}"', body)
        self.assertIn(f'action="/tasks/{opened.task_id}/transition"', body)
        self.assertIn(f'action="/tasks/{reviewing.task_id}/transition"', body)
        for action in ("review", "reopen", "complete", "cancel"):
            self.assertIn(f'value="{action}"', body)

    def test_format_one_repository_is_browsable_but_read_only(self) -> None:
        """Catch accidental web mutation of a legacy Task Data Format."""
        self.add_simple("Legacy task")
        todo_path = self.root / "TODO.md"
        todo_path.write_text(
            todo_path.read_text().replace("todo-format: 2", "todo-format: 1")
        )

        status, _, body = self.get("/")

        self.assertEqual(status, 200)
        self.assertIn("Legacy task", body)
        self.assertIn("bot-todo migrate", body)
        self.assertIn('class="alert alert-warning"', body)
        self.assertIn('class="ti ti-lock"', body)
        self.assertNotIn("<form", body)

    def test_request_rejects_a_non_loopback_host(self) -> None:
        """Catch DNS-rebinding exposure through an unchecked Host header."""
        status, _, body = self.request("GET", "/", headers={"Host": "evil.example"})

        self.assertEqual(status, 403)
        self.assertIn("Forbidden", body)

    def test_post_requires_the_process_csrf_token(self) -> None:
        """Catch cross-site form submission without the board secret."""
        body = urlencode(
            {
                "title": "Cross-site task",
                "priority": "P2",
                "task_type": "chore",
                "simple": "on",
            }
        )

        status, _, response_body = self.request(
            "POST",
            "/tasks",
            body,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.app.origin,
            },
        )

        self.assertEqual(status, 403)
        self.assertIn("Forbidden", response_body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_post_requires_the_exact_loopback_origin(self) -> None:
        """Catch a trusted token submitted from an untrusted browser origin."""
        body = urlencode(
            {
                "_csrf": "test-token",
                "title": "Wrong origin",
                "priority": "P2",
                "task_type": "chore",
                "simple": "on",
            }
        )

        status, _, response_body = self.request(
            "POST",
            "/tasks",
            body,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "https://evil.example",
            },
        )

        self.assertEqual(status, 403)
        self.assertIn("Forbidden", response_body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_post_rejects_an_opaque_browser_origin(self) -> None:
        """Catch the null origin browsers send under a no-referrer policy."""
        body = urlencode(
            {
                "_csrf": "test-token",
                "title": "Opaque origin",
                "priority": "P2",
                "task_type": "chore",
                "simple": "on",
            }
        )

        status, _, response_body = self.request(
            "POST",
            "/tasks",
            body,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": "null",
            },
        )

        self.assertEqual(status, 403)
        self.assertIn("Forbidden", response_body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_post_rejects_an_unsupported_media_type(self) -> None:
        """Catch form parsing when the request media type is not supported."""
        body = urlencode(
            {
                "_csrf": "test-token",
                "title": "Plain text task",
                "priority": "P2",
                "task_type": "chore",
                "simple": "on",
            }
        )

        status, _, response_body = self.request(
            "POST",
            "/tasks",
            body,
            {"Content-Type": "text/plain", "Origin": self.app.origin},
        )

        self.assertEqual(status, 415)
        self.assertIn("Unsupported media type", response_body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_post_rejects_a_form_larger_than_64_kib(self) -> None:
        """Catch unbounded request-body reads at the local HTTP boundary."""
        body = "_csrf=test-token&title=" + ("x" * 65_536)

        status, _, response_body = self.request(
            "POST",
            "/tasks",
            body,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.app.origin,
            },
        )

        self.assertEqual(status, 413)
        self.assertIn("Request too large", response_body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_post_rejects_more_than_32_form_fields(self) -> None:
        """Catch unbounded URL-encoded field parsing."""
        fields = {f"field_{number}": "x" for number in range(32)}
        body = urlencode({"_csrf": "test-token", **fields})

        status, _, response_body = self.request(
            "POST",
            "/tasks",
            body,
            {
                "Content-Type": "application/x-www-form-urlencoded",
                "Origin": self.app.origin,
            },
        )

        self.assertEqual(status, 400)
        self.assertIn("Malformed form", response_body)

    def test_post_rejects_malformed_url_encoded_forms(self) -> None:
        """Catch invalid percent, UTF-8, and field syntax reaching the repository."""
        suffix = b"&priority=P2&task_type=chore&simple=on"
        for malformed in (b"title=%FF", b"title=%ZZ", b"title"):
            with self.subTest(malformed=malformed):
                status, _, body = self.request(
                    "POST",
                    "/tasks",
                    b"_csrf=test-token&" + malformed + suffix,
                    {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Origin": self.app.origin,
                    },
                )

                self.assertEqual(status, 400)
                self.assertIn("Malformed form", body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_unknown_task_returns_a_human_404(self) -> None:
        """Catch a restored detail lookup for an unknown task ID."""
        status, _, body = self.get("/tasks/T999")

        self.assertEqual(status, 404)
        self.assertIn("The requested page does not exist.", body)
        self.assertNotIn("unknown task ID", body)
        self.assertNotIn("Traceback", body)

    def test_invalid_transitions_return_a_human_conflict(self) -> None:
        """Catch lifecycle errors escaping as dropped HTTP connections."""
        with self.store.transaction() as transaction:
            reviewing = transaction.add(
                title="Already reviewing",
                priority="P1",
                task_type="feature",
                simple=True,
            )
            cancellable = transaction.add(
                title="Needs a reason",
                priority="P2",
                task_type="chore",
                simple=True,
            )
            transaction.review(reviewing.task_id)

        cases = (
            (reviewing.task_id, {"action": "review"}),
            (cancellable.task_id, {"action": "cancel", "reason": ""}),
        )
        for task_id, fields in cases:
            with self.subTest(task_id=task_id):
                status, _, body = self.post(f"/tasks/{task_id}/transition", fields)
                self.assertEqual(status, 409)
                self.assertIn("Conflict", body)
                self.assertNotIn("Traceback", body)

    def test_add_rejects_values_outside_the_canonical_choices(self) -> None:
        """Catch crafted priority or type values bypassing HTML selects."""
        cases = (
            {"priority": "P9", "task_type": "feature"},
            {"priority": "P2", "task_type": "unknown"},
        )
        for choices in cases:
            with self.subTest(choices=choices):
                status, _, body = self.post(
                    "/tasks",
                    {
                        "title": "Crafted task",
                        "simple": "on",
                        **choices,
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("Bad request", body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_add_rejects_acceptance_together_with_simple(self) -> None:
        """Catch browser forms bypassing the CLI's mutually exclusive inputs."""
        status, _, body = self.post(
            "/tasks",
            {
                "title": "Contradictory task",
                "priority": "P2",
                "task_type": "chore",
                "acceptance": "Done when complete",
                "simple": "on",
            },
        )

        self.assertEqual(status, 400)
        self.assertIn("Bad request", body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_add_maps_repository_input_validation_to_bad_request(self) -> None:
        """Catch malformed browser fields surfacing as server failures."""
        cases = (
            {"title": ""},
            {"title": "Invalid tag", "tags": "two words"},
            {"title": "Multiline field", "context": "first\nsecond"},
            {"title": "Unknown blocker", "blocked_by": "T999"},
        )
        for fields in cases:
            with self.subTest(fields=fields):
                status, _, body = self.post(
                    "/tasks",
                    {
                        "priority": "P2",
                        "task_type": "chore",
                        "simple": "on",
                        **fields,
                    },
                )
                self.assertEqual(status, 400)
                self.assertIn("Bad request", body)
                self.assertNotIn("Traceback", body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_responses_send_browser_security_headers(self) -> None:
        """Catch removal of local-board browser hardening headers."""
        status, headers, _ = self.get("/")

        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Referrer-Policy"], "same-origin")
        policy = headers["Content-Security-Policy"]
        for directive in (
            "default-src 'none'",
            "style-src 'unsafe-inline'",
            "form-action 'self'",
            "base-uri 'none'",
            "frame-ancestors 'none'",
        ):
            self.assertIn(directive, policy)

    def test_unsupported_methods_keep_browser_security_headers(self) -> None:
        """Catch the standard-library 501 path bypassing response hardening."""
        status, headers, _ = self.request("PUT", "/")

        self.assertEqual(status, 501)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")
        self.assertEqual(headers["Referrer-Policy"], "same-origin")
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])

    def test_board_uses_the_tabler_shell_and_restrictive_cdn_policy(self) -> None:
        """Catch a board shell without pinned Tabler assets or its CSP allowances."""
        status, headers, body = self.get("/")

        self.assertEqual(status, 200)
        for asset, integrity in (
            (
                "https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/css/tabler.min.css",
                "sha384-kz+I4+mczbNiZfLAJMxOlJaZmnbRYhARHNkR2k6tal4gz7OL33/0puDD3SvkiNX9",
            ),
            (
                "https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.46.0/dist/tabler-icons.min.css",
                "sha384-ND+q1IVc0KDElX60dZaqKc7Xl9cdxd2PpU2JfVUHcurCkFVtVLFdt9vJfxtHSL3p",
            ),
            (
                "https://cdn.jsdelivr.net/npm/@tabler/core@1.4.0/dist/js/tabler.min.js",
                "sha384-pku3birjgGovaJ9ngF7SaxKkF/eYUvBjiMJ+jTtWbNesIj2Rud2K63+4JD7EF4gk",
            ),
        ):
            self.assertIn(asset, body)
            self.assertIn(f'integrity="{integrity}"', body)
        self.assertEqual(body.count('crossorigin="anonymous"'), 3)
        self.assertIn('class="navbar navbar-expand-md navbar-light py-3"', body)
        self.assertIn('class="container-xl"', body)
        self.assertIn('class="page-wrapper"', body)
        header = body.split("<header", 1)[1].split("</header>", 1)[0]
        self.assertIn('class="navbar-brand fs-2"', header)
        self.assertIn(
            'class="navbar-text border-start ps-3 ms-3 fs-3 d-none d-sm-inline"', header
        )
        self.assertIn("bot-todo", header)
        self.assertIn("Kanban Board", header)
        self.assertIn('data-bs-target="#add-task-modal"', header)
        self.assertNotIn('<h1 class="page-title">Kanban Board</h1>', body)
        policy = headers["Content-Security-Policy"]
        self.assertIn("style-src 'unsafe-inline' https://cdn.jsdelivr.net", policy)
        self.assertIn("script-src https://cdn.jsdelivr.net", policy)
        self.assertIn("font-src https://cdn.jsdelivr.net", policy)
        self.assertIn("img-src data:", policy)

    def test_board_renders_responsive_state_columns_and_terminal_boundaries(
        self,
    ) -> None:
        """Catch wrong breakpoints, empty states, or terminal overflow boundaries."""
        _, _, body = self.get("/")

        for state, icon, message in (
            ("open", "ti-circle", "Open tasks will appear here."),
            ("review", "ti-clock", "Tasks awaiting review will appear here."),
            ("completed", "ti-circle-check", "Completed tasks will appear here."),
            ("cancelled", "ti-ban", "Cancelled tasks will appear here."),
        ):
            column = body.split(f'data-state="{state}"', 1)[1].split("</section>", 1)[0]
            self.assertIn(f'class="ti {icon}"', column)
            self.assertIn(message, column)
        self.assertNotIn('<details class="terminal-overflow">', body)

        with self.store.transaction() as transaction:
            for number in range(6):
                completed = transaction.add(
                    title=f"Completed boundary {number}",
                    priority="P2",
                    task_type="chore",
                    simple=True,
                )
                cancelled = transaction.add(
                    title=f"Cancelled boundary {number}",
                    priority="P2",
                    task_type="chore",
                    simple=True,
                )
                transaction.close(completed.task_id, "completed")
                transaction.close(cancelled.task_id, "cancelled", "No longer needed")

        _, _, body = self.get("/")

        self.assertNotIn('<details class="terminal-overflow">', body)
        with self.store.transaction() as transaction:
            completed = transaction.add(
                title="Completed boundary 6",
                priority="P2",
                task_type="chore",
                simple=True,
            )
            cancelled = transaction.add(
                title="Cancelled boundary 6",
                priority="P2",
                task_type="chore",
                simple=True,
            )
            transaction.close(completed.task_id, "completed")
            transaction.close(cancelled.task_id, "cancelled", "No longer needed")

        _, _, body = self.get("/")

        for state, count in (
            ("open", 0),
            ("review", 0),
            ("completed", 7),
            ("cancelled", 7),
        ):
            self.assertIn(f'data-state="{state}"', body)
            self.assertIn(f'aria-label="{count} {state} tasks"', body)
        self.assertIn('class="board-columns"', body)
        self.assertIn("grid-template-columns:repeat(4,minmax(14rem,1fr))", body)
        self.assertIn(
            "@media(max-width:1199px){.board-columns{grid-template-columns:repeat(2,minmax(14rem,1fr))",
            body,
        )
        self.assertIn(
            "@media(max-width:767px){.board-columns{grid-template-columns:1fr}",
            body,
        )
        self.assertEqual(body.count('<details class="terminal-overflow">'), 2)
        self.assertIn("+ 1 more completed task", body)
        self.assertIn("+ 1 more cancelled task", body)
        self.assertLess(
            body.index("Completed boundary 6"), body.index("Completed boundary 0")
        )
        self.assertLess(
            body.index("Cancelled boundary 6"), body.index("Cancelled boundary 0")
        )

    def test_populated_state_column_headers_include_their_tabler_icons(self) -> None:
        """Catch state icons that disappear once a column has cards."""
        with self.store.transaction() as transaction:
            transaction.add(
                title="Open header", priority="P1", task_type="feature", simple=True
            )
            reviewing = transaction.add(
                title="Review header", priority="P1", task_type="feature", simple=True
            )
            completed = transaction.add(
                title="Completed header", priority="P2", task_type="chore", simple=True
            )
            cancelled = transaction.add(
                title="Cancelled header", priority="P2", task_type="chore", simple=True
            )
            transaction.review(reviewing.task_id)
            transaction.close(completed.task_id, "completed")
            transaction.close(cancelled.task_id, "cancelled", "No longer needed")

        _, _, body = self.get("/")

        for state, icon, color, heading in (
            ("open", "ti-circle", "text-blue", "Open"),
            ("review", "ti-clock", "text-blue", "Review"),
            ("completed", "ti-circle-check", "text-green", "Completed"),
            ("cancelled", "ti-ban", "text-secondary", "Cancelled"),
        ):
            column = body.split(f'data-state="{state}"', 1)[1].split("</section>", 1)[0]
            self.assertIn(
                f'<h2 class="h3 mb-0"><i class="ti {icon} {color}" '
                f'aria-hidden="true"></i> {heading}</h2>',
                column,
            )

    def test_add_form_is_a_tabler_modal_with_every_repository_field(self) -> None:
        """Catch the New task control drifting from the complete add contract."""
        _, _, body = self.get("/")

        self.assertIn('data-bs-toggle="modal"', body)
        self.assertIn('data-bs-target="#add-task-modal"', body)
        self.assertIn('class="modal modal-blur fade" id="add-task-modal"', body)
        self.assertIn('aria-labelledby="add-task-modal-title"', body)
        self.assertIn('id="add-task-modal-title"', body)
        for field in (
            "title",
            "priority",
            "task_type",
            "acceptance",
            "simple",
            "tags",
            "context",
            "related",
            "blocked_by",
            "_csrf",
        ):
            self.assertIn(f'name="{field}"', body)

    def test_lifecycle_controls_use_tabler_buttons_and_icons(self) -> None:
        """Catch lifecycle controls falling back to unstyled native buttons."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="Styled actions", priority="P1", task_type="feature", simple=True
            )

        _, _, body = self.get("/")

        self.assertIn(f'action="/tasks/{task.task_id}/transition"', body)
        self.assertIn('class="btn btn-outline-secondary btn-sm"', body)
        self.assertIn('class="ti ti-arrow-right"', body)
        self.assertIn('class="ti ti-check"', body)
        self.assertIn('class="btn btn-outline-danger btn-sm"', body)
        self.assertIn('class="ti ti-x"', body)

    def test_archived_task_is_not_reachable_from_the_board(self) -> None:
        """Catch a board that still addresses Tasks that left recent Done."""
        first_id = self.add_simple("Archived detail")
        self.run_cli("complete", first_id)
        for number in range(20):
            task_id = self.add_simple(f"Later task {number}")
            self.run_cli("complete", task_id)

        status, _, body = self.get("/")
        missing_status, _, missing_body = self.get(f"/tasks/{first_id}")

        self.assertEqual(status, 200)
        self.assertNotIn("Archived detail", body)
        self.assertNotIn(f'id="task-{first_id}-modal"', body)
        self.assertEqual(missing_status, 404)
        self.assertIn("The requested page does not exist.", missing_body)

    def test_repository_lock_conflict_returns_http_conflict(self) -> None:
        """Catch lock contention escaping as a dropped connection."""
        self.app.store = TodoStore(self.root, lock_timeout=0.05)
        blocker = TodoStore(self.root, lock_timeout=0.05)

        with blocker.lock.exclusive():
            status, _, body = self.post(
                "/tasks",
                {
                    "title": "Blocked write",
                    "priority": "P2",
                    "task_type": "chore",
                    "simple": "on",
                },
            )

        self.assertEqual(status, 409)
        self.assertIn("Conflict", body)
        self.assertEqual(self.store.snapshot().document.tasks, [])

    def test_create_server_reports_an_occupied_port(self) -> None:
        """Catch a raw OSError when the requested loopback port is already bound."""
        holder = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            holder.bind(("127.0.0.1", 0))
            holder.listen(1)
            port = holder.getsockname()[1]
            with self.assertRaises(TodoError) as raised:
                self.app.create_server(port)
        finally:
            holder.close()

        error = raised.exception
        self.assertEqual(error.code, "io_error")
        self.assertEqual(
            str(error),
            (
                f"Kanban Board could not bind 127.0.0.1:{port} because that "
                "port is already in use. Retry with --port PORT, or --port 0 "
                "to let the OS choose a free port."
            ),
        )
        self.assertNotIn("Traceback", str(error))
        self.assertNotIn("OSError", str(error))

    def test_create_server_does_not_rewrite_other_bind_errors(self) -> None:
        """Catch EADDRINUSE handling that swallows unrelated bind failures."""
        with mock.patch(
            "bot_todo.web.ThreadingHTTPServer",
            side_effect=OSError(errno.EACCES, "Permission denied"),
        ):
            with self.assertRaises(OSError) as raised:
                self.app.create_server(80)

        self.assertEqual(raised.exception.errno, errno.EACCES)

    def test_run_web_prints_and_opens_the_actual_bound_url(self) -> None:
        """Catch launch behavior that opens before bind or loses port zero."""
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            mock.patch.object(
                ThreadingHTTPServer,
                "serve_forever",
                side_effect=KeyboardInterrupt,
            ),
            mock.patch("webbrowser.open") as open_browser,
        ):
            run_web(self.store, name=None, port=0, open_browser=True)

        url = output.getvalue().strip()
        self.assertRegex(url, r"^Kanban Board: http://127\.0\.0\.1:\d+$")
        open_browser.assert_called_once_with(url.removeprefix("Kanban Board: "))

    def test_closed_task_detail_modal_stays_read_only(self) -> None:
        """Catch an edit form appearing on a completed or cancelled task."""
        with self.store.transaction() as transaction:
            completed = transaction.add(
                title="Finished work",
                priority="P2",
                task_type="chore",
                simple=True,
            )
            cancelled = transaction.add(
                title="Stopped work",
                priority="P2",
                task_type="docs",
                simple=True,
            )
            transaction.close(completed.task_id, "completed")
            transaction.close(cancelled.task_id, "cancelled", "No longer needed")

        _, _, body = self.get("/")

        for task_id, title in (
            (completed.task_id, "Finished work"),
            (cancelled.task_id, "Stopped work"),
        ):
            modal = self._task_modal(body, task_id)
            self.assertNotIn(f'action="/tasks/{task_id}/edit"', modal)
            self.assertIn(
                '<button type="button" class="btn btn-link" data-bs-dismiss="modal">'
                "Close</button>",
                modal,
            )
            self.assertIn(title, modal)

    def test_review_task_detail_modal_is_editable(self) -> None:
        """Catch Review tasks left on the read-only definition list."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="Needs review",
                priority="P1",
                task_type="feature",
                simple=True,
            )
            transaction.review(task.task_id)

        _, _, body = self.get("/")
        modal = self._task_modal(body, task.task_id)
        self.assertIn(f'action="/tasks/{task.task_id}/edit"', modal)
        self.assertIn('name="simple" checked', modal)
        self.assertIn('<details class="mt-3">', modal)
        self.assertNotIn('<details class="mt-3" open>', modal)

    def test_edit_form_persists_required_and_advanced_fields(self) -> None:
        """Catch an edit POST that drops fields or skips RepositoryTransaction.edit."""
        with self.store.transaction() as transaction:
            blocker = transaction.add(
                title="Blocker",
                priority="P2",
                task_type="chore",
                simple=True,
            )
            task = transaction.add(
                title="Original title",
                priority="P2",
                task_type="chore",
                tags=["old"],
                acceptance="Old acceptance",
                context="Old context",
                related="old-related",
                blocked_by=[blocker.task_id],
            )

        status, headers, _ = self.post(
            f"/tasks/{task.task_id}/edit",
            {
                "title": "Edited in browser",
                "priority": "P1",
                "task_type": "feature",
                "acceptance": "New acceptance",
                "tags": "browser, local",
                "context": "New context",
                "related": "T015",
                "blocked_by": "",
            },
        )

        edited = self.store.snapshot().find(task.task_id)
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/")
        self.assertEqual(edited.title, "Edited in browser")
        self.assertEqual(edited.priority, "P1")
        self.assertEqual(edited.task_type, "feature")
        self.assertEqual(edited.user_tags, ["browser", "local"])
        self.assertEqual(edited.acceptance, "New acceptance")
        self.assertFalse(edited.simple)
        self.assertEqual(edited.context, "New context")
        self.assertEqual(edited.related, "T015")
        self.assertEqual(edited.blocked_by, [])
        _, _, body = self.get("/")
        self.assertIn("Edited in browser", body)

    def test_edit_form_noop_save_redirects_to_the_board(self) -> None:
        """Catch a no-change Save treated as a CLI-style usage error."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="Unchanged",
                priority="P2",
                task_type="chore",
                simple=True,
            )

        status, headers, _ = self.post(
            f"/tasks/{task.task_id}/edit",
            {
                "title": "Unchanged",
                "priority": "P2",
                "task_type": "chore",
                "simple": "on",
                "tags": "",
                "context": "",
                "related": "",
                "blocked_by": "",
            },
        )

        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"], "/")
        self.assertEqual(self.store.snapshot().find(task.task_id).title, "Unchanged")

    def test_edit_rejects_closed_tasks(self) -> None:
        """Catch an edit POST that mutates a completed or cancelled task."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="Done already",
                priority="P2",
                task_type="chore",
                simple=True,
            )
            transaction.close(task.task_id, "completed")

        status, _, body = self.post(
            f"/tasks/{task.task_id}/edit",
            {
                "title": "Should not stick",
                "priority": "P2",
                "task_type": "chore",
                "simple": "on",
            },
        )

        self.assertEqual(status, 409)
        self.assertIn("closed tasks cannot be edited", body)
        self.assertEqual(self.store.snapshot().find(task.task_id).title, "Done already")

    def test_edit_rejects_acceptance_together_with_simple(self) -> None:
        """Catch both Acceptance and Simple submitted on an edit."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="Exclusive fields",
                priority="P2",
                task_type="chore",
                simple=True,
            )

        status, _, _ = self.post(
            f"/tasks/{task.task_id}/edit",
            {
                "title": "Exclusive fields",
                "priority": "P2",
                "task_type": "chore",
                "acceptance": "Done when complete",
                "simple": "on",
            },
        )

        self.assertEqual(status, 400)
        self.assertTrue(self.store.snapshot().find(task.task_id).simple)

    def test_edit_rejects_neither_acceptance_nor_simple(self) -> None:
        """Catch an edit that would drop both Acceptance and #simple."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="Needs one",
                priority="P2",
                task_type="chore",
                acceptance="Keep me or mark simple",
            )

        status, _, _ = self.post(
            f"/tasks/{task.task_id}/edit",
            {
                "title": "Needs one",
                "priority": "P2",
                "task_type": "chore",
                "acceptance": "",
            },
        )

        self.assertEqual(status, 400)
        self.assertEqual(
            self.store.snapshot().find(task.task_id).acceptance,
            "Keep me or mark simple",
        )

    def test_edit_rejects_reserved_words_in_tags(self) -> None:
        """Catch type or simple leaking into the Tags field."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="Reserved tags",
                priority="P2",
                task_type="chore",
                tags=["browser"],
                simple=True,
            )

        for tags in ("browser, feature", "browser, simple", "browser, #bug"):
            with self.subTest(tags=tags):
                status, _, _ = self.post(
                    f"/tasks/{task.task_id}/edit",
                    {
                        "title": "Reserved tags",
                        "priority": "P2",
                        "task_type": "chore",
                        "simple": "on",
                        "tags": tags,
                    },
                )
                self.assertEqual(status, 400)
        self.assertEqual(
            self.store.snapshot().find(task.task_id).user_tags, ["browser"]
        )

    def test_edit_unknown_task_returns_not_found(self) -> None:
        """Catch POST /tasks/<id>/edit treating a missing id as a generic 404."""
        status, _, body = self.post(
            "/tasks/T999/edit",
            {
                "title": "Missing",
                "priority": "P2",
                "task_type": "chore",
                "simple": "on",
            },
        )

        self.assertEqual(status, 404)
        self.assertIn("The requested page does not exist", body)

    def test_get_edit_path_returns_generic_not_found(self) -> None:
        """Catch a standalone GET edit page."""
        with self.store.transaction() as transaction:
            task = transaction.add(
                title="No get edit",
                priority="P2",
                task_type="chore",
                simple=True,
            )

        status, _, body = self.get(f"/tasks/{task.task_id}/edit")

        self.assertEqual(status, 404)
        self.assertIn("The requested page does not exist", body)
