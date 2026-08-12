"""Verify the packaged todo skill tells agents how to invoke the CLI."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

#: Canonical packaged skill document.
SKILL_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "bot_todo"
    / "skill_assets"
    / "todo"
    / "SKILL.md"
)
#: Fenced code blocks in the skill, including an optional language tag.
FENCE = re.compile(r"```(?:\w+)?\n(.*?)```", re.DOTALL)


class SkillGuidanceTests(unittest.TestCase):
    """Cover agent invocation rules encoded in the packaged skill."""

    def setUp(self) -> None:
        """Load the packaged skill text."""
        self.text = SKILL_PATH.read_text(encoding="utf-8")
        self.examples = FENCE.findall(self.text)

    def command_lines(self) -> list[str]:
        """
        Collect ``bot-todo`` example lines from fenced blocks.

        Returns:
            Stripped command lines that invoke ``bot-todo``.

        """
        lines: list[str] = []
        for block in self.examples:
            for raw in block.splitlines():
                stripped = raw.strip()
                if stripped.startswith("bot-todo"):
                    lines.append(stripped)
        return lines

    def test_data_returning_examples_include_json(self) -> None:
        for line in self.command_lines():
            if "--help" in line or "--version" in line:
                continue
            self.assertIn("--json", line, line)

    def test_all_appears_in_at_most_one_example(self) -> None:
        with_all = [line for line in self.command_lines() if "--all" in line]
        self.assertLessEqual(len(with_all), 1, with_all)

    def test_all_is_restricted_to_explicit_all_project_requests(self) -> None:
        self.assertRegex(
            self.text,
            r"only when the person explicitly asks",
        )
