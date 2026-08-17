"""Cover the packaged Task Management Snippet."""

from __future__ import annotations

import json
import unittest

from bot_todo.task_management_snippet import TaskManagementSnippet
from tests.support import invoke

#: Settled consuming-repo Task Management section.
EXPECTED = """\
## Task Management

- Use `TODO.md` as the repository backlog.
- ANY request to add, change, claim, close, or look up a task — however it is phrased ("add an ops task", "put this on the list", "what's next") — MUST start by invoking the `todo` skill. Do not inspect `TODO.md` or search the filesystem first.
- Use the `bot-todo` CLI with `--json` for all agent mutations; never hand-edit `TODO.md`.
- Run `bot-todo --json validate` before and after task-file changes.
- Claim a task before planning or implementing it.
- When specs, ADRs, or plans are written to the filesystem, add a link to the files in the corresponding TODO task.
"""


class TaskManagementSnippetTests(unittest.TestCase):
    """Load the packaged markdown used by init and snippet."""

    def test_text_is_the_settled_consuming_repo_section(self) -> None:
        snippet = TaskManagementSnippet()

        self.assertEqual(snippet.text(), EXPECTED.rstrip("\n"))
        self.assertIn(
            "Claim a task before planning or implementing it.", snippet.text()
        )
        self.assertNotIn(".scratch", snippet.text())


class SnippetCommandTests(unittest.TestCase):
    """Emit the snippet without a Task Repository."""

    def test_human_stdout_is_the_markdown_section(self) -> None:
        result = invoke("snippet")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, EXPECTED)
        self.assertEqual(result.stderr, "")

    def test_json_data_carries_the_snippet(self) -> None:
        result = invoke("--json", "snippet")

        self.assertEqual(result.returncode, 0)
        document = json.loads(result.stdout)
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["command"], "snippet")
        self.assertEqual(document["data"], {"snippet": EXPECTED.rstrip("\n")})

    def test_no_repository_selector_is_accepted(self) -> None:
        selectors = (
            ("--root", "."),
            ("--repo", "demo"),
            ("--all",),
            ("--config", "config.toml"),
        )
        for selector in selectors:
            with self.subTest(selector=selector):
                result = invoke("--json", *selector, "snippet")

                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)["error"]["code"], "usage")
