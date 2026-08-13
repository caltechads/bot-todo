"""Shared harness for exercising bot-todo through its command-line interface."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bot_todo.cli import main


@dataclass(frozen=True)
class CliResult:
    """Captured outcome of one in-process CLI invocation."""

    returncode: int
    stdout: str
    stderr: str


def invoke(*arguments: str) -> CliResult:
    """
    Run the CLI in this process and capture its streams.

    Args:
        *arguments: Arguments excluding the executable name.

    Returns:
        Captured exit status and output.

    """
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        returncode = main(list(arguments))
    return CliResult(returncode, out.getvalue(), err.getvalue())


class TodoCliTestCase(unittest.TestCase):
    """Exercise todo operations through their public command-line interface."""

    def setUp(self) -> None:
        """
        Create an isolated repository root for each test.

        Side Effects:
            Creates a temporary directory and initializes the canonical file.
        """
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self._temporary_directory.name).resolve()
        self.run_cli("init", "--name", "Example")

    def tearDown(self) -> None:
        """
        Remove the isolated repository root.

        Side Effects:
            Deletes the temporary directory and its contents.
        """
        self._temporary_directory.cleanup()

    def run_cli(self, *arguments: str, check: bool = True) -> CliResult:
        """
        Run the CLI against the isolated repository.

        Args:
            *arguments: Command and command-specific arguments.

        Keyword Args:
            check: Fail the test when the command exits unsuccessfully.

        Returns:
            Captured exit status and output.
        """
        result = invoke("--root", str(self.root), *arguments)
        if check and result.returncode != 0:
            message = f"command failed ({result.returncode}): {result.stderr}"
            raise AssertionError(message)
        return result

    def run_json(self, *arguments: str) -> dict[str, Any]:
        """
        Run a successful command in JSON mode and parse its document.

        Args:
            *arguments: Command and command-specific arguments.

        Returns:
            The parsed success document.

        """
        result = self.run_cli("--json", *arguments)
        parsed: dict[str, Any] = json.loads(result.stdout)
        return parsed

    def run_json_error(self, *arguments: str) -> dict[str, Any]:
        """
        Run a failing command in JSON mode and parse its error document.

        Asserts that a failure emits nothing on stdout.

        Args:
            *arguments: Command and command-specific arguments.

        Returns:
            The parsed ``error`` object.

        """
        result = self.run_cli("--json", *arguments, check=False)
        if result.returncode == 0:
            raise AssertionError("command unexpectedly succeeded")
        if result.stdout:
            raise AssertionError(f"failure wrote stdout: {result.stdout!r}")
        document: dict[str, Any] = json.loads(result.stderr)
        error: dict[str, Any] = document["error"]
        return error

    def added_id(self, *arguments: str) -> str:
        """
        Add a task through the CLI and return its allocated ID.

        Args:
            *arguments: Arguments to ``add`` after the command name.

        Returns:
            The allocated task ID from the human confirmation.
        """
        result = self.run_cli("add", *arguments)
        return task_id_from_confirmation(result.stdout)

    def add_simple(self, title: str, priority: str = "P2") -> str:
        """
        Add a simple chore and return its allocated ID.

        Args:
            title: Task title.

        Keyword Args:
            priority: Priority section for the task.

        Returns:
            The allocated task ID.
        """
        return self.added_id(
            title, "--priority", priority, "--type", "chore", "--simple"
        )


def task_id_from_confirmation(stdout: str) -> str:
    """
    Read the Task ID from a human mutation confirmation.

    Args:
        stdout: Human confirmation text.

    Returns:
        The Task ID, which is the second whitespace token.
    """
    return stdout.split()[1]
