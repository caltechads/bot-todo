"""Verify the nested repos command group through the public CLI."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bot_todo.config import CONFIG_ENV_VAR
from tests.support import invoke


class ReposCliTestCase(unittest.TestCase):
    """Exercise repos commands against an isolated default configuration."""

    def setUp(self) -> None:
        """
        Create an isolated XDG configuration root.

        Side Effects:
            Creates a temporary directory.
        """
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._temporary_directory.name).resolve()
        self.config_path = self.directory / "bot-todo" / "config.toml"
        self.environment = {"XDG_CONFIG_HOME": str(self.directory)}

    def tearDown(self) -> None:
        """
        Remove the isolated directory.

        Side Effects:
            Deletes the temporary directory and its contents.
        """
        self._temporary_directory.cleanup()

    def run_cli(self, *arguments: str, check: bool = True) -> tuple[int, str, str]:
        """
        Run the CLI against this test's default configuration.

        Side Effects:
            May read or write the isolated configuration file.

        Args:
            *arguments: Arguments excluding the executable name.

        Keyword Args:
            check: Fail the test when the command exits unsuccessfully.

        Returns:
            Exit status, stdout, and stderr.
        """
        with mock.patch.dict(os.environ, self.environment, clear=False):
            os.environ.pop(CONFIG_ENV_VAR, None)
            result = invoke(*arguments)
        if check and result.returncode != 0:
            raise AssertionError(
                f"command failed ({result.returncode}): {result.stderr}"
            )
        return result.returncode, result.stdout, result.stderr

    def run_json(self, *arguments: str) -> dict[str, object]:
        """
        Run a successful repos command in JSON mode.

        Args:
            *arguments: Arguments excluding the executable name.

        Returns:
            Parsed success document.
        """
        _code, stdout, _stderr = self.run_cli("--json", *arguments)
        document: dict[str, object] = json.loads(stdout)
        return document

    def run_json_error(self, *arguments: str) -> dict[str, object]:
        """
        Run a failing command in JSON mode.

        Args:
            *arguments: Arguments excluding the executable name.

        Returns:
            Parsed error object.
        """
        code, stdout, stderr = self.run_cli("--json", *arguments, check=False)
        if code == 0:
            raise AssertionError("command unexpectedly succeeded")
        if stdout:
            raise AssertionError(f"failure wrote stdout: {stdout!r}")
        document: dict[str, object] = json.loads(stderr)
        error: dict[str, object] = document["error"]  # type: ignore[assignment]
        return error


class ReposPathTests(ReposCliTestCase):
    """Cover repos path against missing and present configuration files."""

    def test_path_reports_the_default_even_when_missing(self) -> None:
        document = self.run_json("repos", "path")
        data = document["data"]
        assert isinstance(data, dict)

        self.assertEqual(document["command"], "repos")
        self.assertEqual(data["operation"], "path")
        self.assertEqual(data["config_path"], str(self.config_path))
        self.assertFalse(self.config_path.exists())

    def test_path_accepts_an_explicit_config(self) -> None:
        explicit = self.directory / "custom.toml"

        result = invoke("--json", "--config", str(explicit), "repos", "path")
        data = json.loads(result.stdout)["data"]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(data["config_path"], str(explicit.resolve()))
        self.assertEqual(data["operation"], "path")


class ReposListTests(ReposCliTestCase):
    """Cover repos list for empty and populated collections."""

    def test_an_empty_default_list_succeeds(self) -> None:
        document = self.run_json("repos", "list")
        data = document["data"]
        assert isinstance(data, dict)

        self.assertEqual(document["command"], "repos")
        self.assertEqual(data["operation"], "list")
        self.assertEqual(data["config_path"], str(self.config_path))
        self.assertEqual(data["repositories"], [])

    def test_an_empty_human_list_prints_nothing(self) -> None:
        _code, stdout, stderr = self.run_cli("repos", "list")

        self.assertEqual(stdout, "")
        self.assertEqual(stderr, "")

    def test_list_includes_entries_in_configuration_order(self) -> None:
        first = self.directory / "first"
        second = self.directory / "second"
        first.mkdir()
        second.mkdir()
        self.run_cli("repos", "add", str(first))
        self.run_cli("repos", "add", str(second))

        data = self.run_json("repos", "list")["data"]
        assert isinstance(data, dict)
        repositories = data["repositories"]
        assert isinstance(repositories, list)

        self.assertEqual(
            [(row["name"], row["path"]) for row in repositories],
            [("first", str(first)), ("second", str(second))],
        )


class ReposAddTests(ReposCliTestCase):
    """Cover repos add JSON, human output, and default path."""

    def test_add_defaults_to_the_current_directory(self) -> None:
        repo = self.directory / "cwd-repo"
        repo.mkdir()
        original = Path.cwd()
        os.chdir(repo)
        self.addCleanup(os.chdir, original)

        document = self.run_json("repos", "add")
        data = document["data"]
        assert isinstance(data, dict)
        entry = data["entry"]
        assert isinstance(entry, dict)

        self.assertEqual(document["command"], "repos")
        self.assertEqual(data["operation"], "add")
        self.assertEqual(data["config_path"], str(self.config_path))
        self.assertEqual(entry["name"], "cwd-repo")
        self.assertEqual(entry["path"], str(repo))
        self.assertTrue(self.config_path.is_file())

    def test_human_add_prints_a_confirmation(self) -> None:
        repo = self.directory / "human-repo"
        repo.mkdir()

        _code, stdout, _stderr = self.run_cli("repos", "add", str(repo))

        self.assertIn("added", stdout)
        self.assertIn("human-repo", stdout)

    def test_name_flag_overrides_the_basename(self) -> None:
        repo = self.directory / "My Project"
        repo.mkdir()

        data = self.run_json("repos", "add", str(repo), "--name", "ledger")["data"]
        assert isinstance(data, dict)
        entry = data["entry"]
        assert isinstance(entry, dict)

        self.assertEqual(entry["name"], "ledger")
        self.assertEqual(entry["path"], str(repo))


class ReposRemoveTests(ReposCliTestCase):
    """Cover repos remove by name and by path."""

    def test_remove_by_name_emits_the_removed_entry(self) -> None:
        repo = self.directory / "drop-me"
        repo.mkdir()
        self.run_cli("repos", "add", str(repo))

        document = self.run_json("repos", "remove", "drop-me")
        data = document["data"]
        assert isinstance(data, dict)
        entry = data["entry"]
        assert isinstance(entry, dict)

        self.assertEqual(data["operation"], "remove")
        self.assertEqual(entry["name"], "drop-me")
        self.assertEqual(entry["path"], str(repo))
        remaining = self.run_json("repos", "list")["data"]
        assert isinstance(remaining, dict)
        self.assertEqual(remaining["repositories"], [])

    def test_human_remove_prints_a_confirmation(self) -> None:
        repo = self.directory / "drop-me"
        repo.mkdir()
        self.run_cli("repos", "add", str(repo))

        _code, stdout, _stderr = self.run_cli("repos", "remove", "drop-me")

        self.assertIn("removed", stdout)
        self.assertIn("drop-me", stdout)


class ReposSelectorTests(ReposCliTestCase):
    """Cover selector combinations the repos group accepts and rejects."""

    def test_root_repo_and_all_are_usage_errors(self) -> None:
        selectors = (
            ("--root", str(self.directory)),
            ("--repo", "demo"),
            ("--all",),
        )
        for selector in selectors:
            with self.subTest(selector=selector[0]):
                error = self.run_json_error(*selector, "repos", "list")
                self.assertEqual(error["code"], "usage")

    def test_config_is_accepted_with_repos(self) -> None:
        explicit = self.directory / "custom.toml"
        explicit.write_text("schema_version = 1\n", encoding="utf-8")

        result = invoke("--json", "--config", str(explicit), "repos", "list")
        data = json.loads(result.stdout)["data"]

        self.assertEqual(result.returncode, 0)
        self.assertEqual(data["config_path"], str(explicit.resolve()))
        self.assertEqual(data["repositories"], [])


if __name__ == "__main__":
    unittest.main()
