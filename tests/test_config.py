"""Verify Configuration Schema Version 1 discovery, precedence, and validation."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bot_todo.config import CONFIG_ENV_VAR, RepositoryCollection
from bot_todo.repository import TodoError
from tests.support import invoke


class ConfigurationTestCase(unittest.TestCase):
    """Exercise configuration loading against isolated temporary files."""

    def setUp(self) -> None:
        """
        Create an isolated directory for configuration files.

        Side Effects:
            Creates a temporary directory.
        """
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._temporary_directory.name).resolve()

    def tearDown(self) -> None:
        """
        Remove the isolated directory.

        Side Effects:
            Deletes the temporary directory and its contents.
        """
        self._temporary_directory.cleanup()

    def write(self, text: str, name: str = "config.toml") -> Path:
        """
        Write one configuration file.

        Side Effects:
            Creates a file in the isolated directory.

        Args:
            text: Configuration file contents.

        Keyword Args:
            name: Filename within the isolated directory.

        Returns:
            Path to the written file.
        """
        path = self.directory / name
        path.write_text(text, encoding="utf-8")
        return path

    def load_failure(self, text: str) -> TodoError:
        """
        Load an invalid configuration and return the raised failure.

        Side Effects:
            Writes and reads a configuration file.

        Args:
            text: Configuration file contents.

        Returns:
            The raised domain failure.
        """
        with self.assertRaises(TodoError) as caught:
            RepositoryCollection.load(self.write(text))
        return caught.exception


class DiscoveryTests(ConfigurationTestCase):
    """Cover configuration location, precedence, and absence."""

    def test_an_absent_default_is_an_empty_collection(self) -> None:
        environment = {"XDG_CONFIG_HOME": str(self.directory / "absent")}

        with mock.patch.dict(os.environ, environment, clear=False):
            collection = RepositoryCollection.load(None)

        self.assertEqual(len(collection), 0)

    def test_the_default_path_follows_xdg_config_home(self) -> None:
        environment = {"XDG_CONFIG_HOME": str(self.directory)}

        with mock.patch.dict(os.environ, environment, clear=False):
            path = RepositoryCollection.default_path()

        self.assertEqual(path, self.directory / "bot-todo" / "config.toml")

    def test_a_missing_explicit_configuration_is_reported(self) -> None:
        with self.assertRaises(TodoError) as caught:
            RepositoryCollection.load(self.directory / "missing.toml")

        self.assertEqual(caught.exception.code, "config_not_found")

    def test_the_default_is_used_when_no_explicit_path_is_given(self) -> None:
        root = self.directory / "bot-todo"
        root.mkdir()
        (root / "config.toml").write_text(
            'schema_version = 1\n\n[[repositories]]\nname = "one"\npath = "/tmp/one"\n',
            encoding="utf-8",
        )
        environment = {"XDG_CONFIG_HOME": str(self.directory)}

        with mock.patch.dict(os.environ, environment, clear=False):
            collection = RepositoryCollection.load(None)

        self.assertEqual([entry.name for entry in collection], ["one"])


class PrecedenceTests(ConfigurationTestCase):
    """Cover the settled --config over BOT_TODO_CONFIG over default order."""

    def setUp(self) -> None:
        """
        Write one configuration file per precedence level.

        Side Effects:
            Creates three configuration files.
        """
        super().setUp()
        for name in ("flag", "environment", "default"):
            (self.directory / name).mkdir()
            self.write(
                f'schema_version = 1\n\n[[repositories]]\nname = "{name}"\n'
                f'path = "{self.directory}/{name}"\n',
                f"{name}.toml",
            )
        self.default_root = self.directory / "bot-todo"
        self.default_root.mkdir()
        (self.default_root / "config.toml").write_bytes(
            (self.directory / "default.toml").read_bytes()
        )

    def selected_name(self, *arguments: str) -> str:
        """
        Report which configuration a ``--repo`` lookup resolved against.

        The winning file names its only repository after itself, so a
        successful lookup identifies the file that was loaded.

        Side Effects:
            Runs the CLI in this process.

        Args:
            *arguments: Global options preceding the command.

        Returns:
            The resolved Repository Name.
        """
        result = invoke(*arguments, "--json", "validate")
        document = json.loads(result.stderr or result.stdout)
        if "error" in document:
            code: str = document["error"]["code"]
            return code
        name: str = document["data"]["repository"]["name"]
        return name

    def test_the_flag_overrides_the_environment(self) -> None:
        environment = {
            CONFIG_ENV_VAR: str(self.directory / "environment.toml"),
            "XDG_CONFIG_HOME": str(self.directory),
        }

        with mock.patch.dict(os.environ, environment, clear=False):
            name = self.selected_name(
                "--config", str(self.directory / "flag.toml"), "--repo", "flag"
            )

        self.assertEqual(name, "not_initialized")

    def test_the_environment_overrides_the_default(self) -> None:
        environment = {
            CONFIG_ENV_VAR: str(self.directory / "environment.toml"),
            "XDG_CONFIG_HOME": str(self.directory),
        }

        with mock.patch.dict(os.environ, environment, clear=False):
            found = self.selected_name("--repo", "environment")
            missing = self.selected_name("--repo", "default")

        self.assertEqual(found, "not_initialized")
        self.assertEqual(missing, "repository_not_found")

    def test_the_default_applies_without_an_override(self) -> None:
        environment = {"XDG_CONFIG_HOME": str(self.directory)}

        with mock.patch.dict(os.environ, environment, clear=False):
            os.environ.pop(CONFIG_ENV_VAR, None)
            name = self.selected_name("--repo", "default")

        self.assertEqual(name, "not_initialized")


class ValidationTests(ConfigurationTestCase):
    """Cover strict structural validation of a supported configuration."""

    def test_a_valid_collection_preserves_configuration_order(self) -> None:
        collection = RepositoryCollection.load(
            self.write(
                "schema_version = 1\n\n"
                '[[repositories]]\nname = "second"\npath = "/tmp/b"\n\n'
                '[[repositories]]\nname = "first"\npath = "/tmp/a"\n'
            )
        )

        self.assertEqual([entry.name for entry in collection], ["second", "first"])

    def test_an_empty_file_is_invalid(self) -> None:
        self.assertEqual(self.load_failure("").code, "invalid_config")

    def test_malformed_toml_is_invalid(self) -> None:
        self.assertEqual(self.load_failure("schema_version = ").code, "invalid_config")

    def test_an_unknown_top_level_key_invalidates_the_file(self) -> None:
        self.assertEqual(
            self.load_failure("schema_version = 1\nextra = true\n").code,
            "invalid_config",
        )

    def test_an_unknown_entry_key_invalidates_the_file(self) -> None:
        text = (
            "schema_version = 1\n\n[[repositories]]\n"
            'name = "one"\npath = "/tmp/one"\nextra = 1\n'
        )

        self.assertEqual(self.load_failure(text).code, "invalid_config")

    def test_a_missing_entry_key_invalidates_the_file(self) -> None:
        text = 'schema_version = 1\n\n[[repositories]]\nname = "one"\n'

        self.assertEqual(self.load_failure(text).code, "invalid_config")

    def test_an_invalid_name_invalidates_the_file(self) -> None:
        for name in ("Upper", "-leading", "has space", ""):
            text = (
                f'schema_version = 1\n\n[[repositories]]\nname = "{name}"\n'
                'path = "/tmp/one"\n'
            )

            self.assertEqual(self.load_failure(text).code, "invalid_config")

    def test_a_duplicate_name_invalidates_the_file(self) -> None:
        text = (
            "schema_version = 1\n\n"
            '[[repositories]]\nname = "one"\npath = "/tmp/a"\n\n'
            '[[repositories]]\nname = "one"\npath = "/tmp/b"\n'
        )

        self.assertEqual(self.load_failure(text).code, "invalid_config")

    def test_a_duplicate_resolved_path_invalidates_the_file(self) -> None:
        text = (
            "schema_version = 1\n\n"
            '[[repositories]]\nname = "one"\npath = "/tmp/shared"\n\n'
            '[[repositories]]\nname = "two"\npath = "/tmp/./shared"\n'
        )

        self.assertEqual(self.load_failure(text).code, "invalid_config")

    def test_an_unknown_repository_name_is_reported(self) -> None:
        collection = RepositoryCollection.load(
            self.write(
                'schema_version = 1\n\n[[repositories]]\nname = "one"\npath = "/tmp/a"\n'
            )
        )

        with self.assertRaises(TodoError) as caught:
            collection.entry("other")

        self.assertEqual(caught.exception.code, "repository_not_found")


class EntryPathTests(ConfigurationTestCase):
    """Cover Repository Entry path semantics."""

    def entry_path(self, value: str) -> Path:
        """
        Resolve one configured entry path.

        Side Effects:
            Writes and reads a configuration file.

        Args:
            value: Raw path value to configure.

        Returns:
            The resolved entry path.
        """
        collection = RepositoryCollection.load(
            self.write(
                f'schema_version = 1\n\n[[repositories]]\nname = "one"\npath = "{value}"\n'
            )
        )
        return collection.entry("one").path

    def test_a_relative_path_resolves_against_the_configuration_file(self) -> None:
        self.assertEqual(self.entry_path("nested/repo"), self.directory / "nested/repo")

    def test_an_absolute_path_is_preserved(self) -> None:
        absolute = self.directory / "absolute"

        self.assertEqual(self.entry_path(str(absolute)), absolute)

    def test_a_home_relative_path_expands(self) -> None:
        self.assertEqual(self.entry_path("~/repo"), Path.home() / "repo")

    def test_environment_variables_are_not_expanded(self) -> None:
        with mock.patch.dict(os.environ, {"BOT_TODO_TEST_VAR": "expanded"}):
            resolved = self.entry_path("$BOT_TODO_TEST_VAR")

        self.assertEqual(resolved, self.directory / "$BOT_TODO_TEST_VAR")

    def test_a_missing_entry_path_remains_valid_configuration(self) -> None:
        resolved = self.entry_path("does/not/exist")

        self.assertFalse(resolved.exists())


class SchemaVersionTests(ConfigurationTestCase):
    """Cover the closed Configuration Schema Version 1 contract."""

    def test_an_unsupported_version_reports_encountered_and_supported(self) -> None:
        error = self.load_failure("schema_version = 2\n")

        self.assertEqual(error.code, "unsupported_config_version")
        self.assertEqual(error.details, {"encountered": 2, "supported": [1]})

    def test_a_missing_version_is_invalid_rather_than_unsupported(self) -> None:
        text = 'repositories = [{ name = "one", path = "/tmp/a" }]\n'

        self.assertEqual(self.load_failure(text).code, "invalid_config")

    def test_a_non_integer_version_is_invalid(self) -> None:
        self.assertEqual(
            self.load_failure('schema_version = "1"\n').code, "invalid_config"
        )

    def test_a_boolean_version_is_invalid(self) -> None:
        self.assertEqual(
            self.load_failure("schema_version = true\n").code, "invalid_config"
        )

    def test_an_unsupported_version_is_rejected_before_structure(self) -> None:
        text = "schema_version = 99\nunknown_key = 1\nrepositories = 5\n"

        self.assertEqual(self.load_failure(text).code, "unsupported_config_version")

    def test_an_unsupported_version_is_rejected_before_repository_access(self) -> None:
        broken = self.directory / "broken"
        broken.mkdir()
        (broken / "TODO.md").write_text("not a task file", encoding="utf-8")
        config = self.write(
            f'schema_version = 7\n\n[[repositories]]\nname = "one"\npath = "{broken}"\n'
        )

        result = invoke("--json", "--config", str(config), "--repo", "one", "validate")

        self.assertEqual(result.stdout, "")
        self.assertEqual(
            json.loads(result.stderr)["error"]["code"], "unsupported_config_version"
        )


if __name__ == "__main__":
    unittest.main()
