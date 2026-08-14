"""Verify CollectionStore mutations of the Repository Collection file."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bot_todo.config import CollectionStore, RepositoryCollection
from bot_todo.repository import TodoError


class CollectionStoreTestCase(unittest.TestCase):
    """Exercise CollectionStore against an isolated configuration root."""

    def setUp(self) -> None:
        """
        Create an isolated directory for configuration and repositories.

        Side Effects:
            Creates a temporary directory.
        """
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._temporary_directory.name).resolve()
        self.config_path = self.directory / "bot-todo" / "config.toml"

    def tearDown(self) -> None:
        """
        Remove the isolated directory.

        Side Effects:
            Deletes the temporary directory and its contents.
        """
        self._temporary_directory.cleanup()

    def store(self, explicit: Path | None = None) -> CollectionStore:
        """
        Build a store over the isolated explicit configuration path.

        Args:
            explicit: Configuration path, or ``None`` for the default in this
                test's XDG root.

        Returns:
            CollectionStore bound to that path.
        """
        if explicit is not None:
            return CollectionStore(explicit)
        environment = {"XDG_CONFIG_HOME": str(self.directory)}
        with mock.patch.dict(os.environ, environment, clear=False):
            os.environ.pop("BOT_TODO_CONFIG", None)
            return CollectionStore(None)

    def add_repo(self, name: str) -> Path:
        """
        Create one repository directory under the isolated root.

        Args:
            name: Directory basename, also used as the inferred name when valid.

        Returns:
            Resolved repository path.
        """
        path = self.directory / name
        path.mkdir()
        return path


class ResolvePathTests(CollectionStoreTestCase):
    """Cover active configuration path resolution."""

    def test_the_default_path_follows_xdg_config_home(self) -> None:
        environment = {"XDG_CONFIG_HOME": str(self.directory)}

        with mock.patch.dict(os.environ, environment, clear=False):
            os.environ.pop("BOT_TODO_CONFIG", None)
            path = RepositoryCollection.resolve_path(None)

        self.assertEqual(path, self.config_path)

    def test_an_explicit_path_is_resolved(self) -> None:
        relative = Path("config.toml")

        path = RepositoryCollection.resolve_path(self.directory / relative)

        self.assertEqual(path, self.directory / "config.toml")


class MissingFileTests(CollectionStoreTestCase):
    """Cover the missing-default versus missing-explicit contract."""

    def test_a_missing_default_loads_as_empty(self) -> None:
        collection = self.store().load()

        self.assertEqual(len(collection), 0)
        self.assertFalse(self.config_path.exists())

    def test_a_missing_explicit_file_is_reported(self) -> None:
        missing = self.directory / "missing.toml"

        with self.assertRaises(TodoError) as caught:
            CollectionStore(missing).load()

        self.assertEqual(caught.exception.code, "config_not_found")
        self.assertFalse(missing.exists())

    def test_add_creates_the_default_file_and_parents(self) -> None:
        repo = self.add_repo("sample-repo")

        entry = self.store().add(str(repo))

        self.assertEqual(entry.name, "sample-repo")
        self.assertEqual(entry.path, repo)
        self.assertTrue(self.config_path.is_file())
        loaded = RepositoryCollection.load(self.config_path)
        self.assertEqual([item.name for item in loaded], ["sample-repo"])

    def test_add_does_not_create_a_missing_explicit_file(self) -> None:
        missing = self.directory / "missing.toml"
        repo = self.add_repo("sample-repo")

        with self.assertRaises(TodoError) as caught:
            CollectionStore(missing).add(str(repo))

        self.assertEqual(caught.exception.code, "config_not_found")
        self.assertFalse(missing.exists())

    def test_remove_from_a_missing_default_is_not_found(self) -> None:
        with self.assertRaises(TodoError) as caught:
            self.store().remove("sample-repo")

        self.assertEqual(caught.exception.code, "repository_not_found")
        self.assertFalse(self.config_path.exists())


class AddTests(CollectionStoreTestCase):
    """Cover add path grammar, name inference, and canonical writes."""

    def test_a_bare_slug_path_is_usage(self) -> None:
        with self.assertRaises(TodoError) as caught:
            self.store().add("ledger")

        self.assertEqual(caught.exception.code, "usage")
        self.assertFalse(self.config_path.exists())

    def test_dot_adds_the_current_directory(self) -> None:
        repo = self.add_repo("cwd-repo")
        original = Path.cwd()
        os.chdir(repo)
        self.addCleanup(os.chdir, original)

        entry = self.store().add(".")

        self.assertEqual(entry.name, "cwd-repo")
        self.assertEqual(entry.path, repo)

    def test_an_invalid_basename_requires_name(self) -> None:
        repo = self.add_repo("My Project")

        with self.assertRaises(TodoError) as caught:
            self.store().add(str(repo))

        self.assertEqual(caught.exception.code, "usage")

    def test_name_overrides_the_inferred_basename(self) -> None:
        repo = self.add_repo("My Project")

        entry = self.store().add(str(repo), name="ledger")

        self.assertEqual(entry.name, "ledger")
        self.assertEqual(entry.path, repo)

    def test_a_basename_is_lowercased_before_matching(self) -> None:
        repo = self.add_repo("Bot-Todo")

        entry = self.store().add(str(repo))

        self.assertEqual(entry.name, "bot-todo")

    def test_a_path_need_not_exist(self) -> None:
        prospective = self.directory / "future-repo"

        entry = self.store().add(str(prospective))

        self.assertEqual(entry.name, "future-repo")
        self.assertEqual(entry.path, prospective)
        self.assertFalse(prospective.exists())

    def test_home_relative_paths_are_stored_with_a_tilde(self) -> None:
        repo = self.add_repo("under-home")

        with mock.patch.object(Path, "home", return_value=self.directory):
            self.store().add(str(repo))

        text = self.config_path.read_text(encoding="utf-8")
        self.assertIn('path = "~/under-home"', text)

    def test_paths_outside_home_are_stored_absolute(self) -> None:
        outside = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(lambda: outside.rmdir() if outside.is_dir() else None)
        repo = outside / "external-repo"
        repo.mkdir()
        self.addCleanup(lambda: repo.rmdir() if repo.is_dir() else None)

        with mock.patch.object(Path, "home", return_value=self.directory):
            self.store().add(str(repo))

        text = self.config_path.read_text(encoding="utf-8")
        self.assertIn(f'path = "{repo}"', text)

    def test_quotes_in_paths_are_escaped(self) -> None:
        repo = self.directory / 'quote"repo'
        repo.mkdir()

        self.store().add(str(repo), name="quoted")

        loaded = RepositoryCollection.load(self.config_path)
        self.assertEqual(loaded.entry("quoted").path, repo)

    def test_entries_append_in_configuration_order(self) -> None:
        first = self.add_repo("first")
        second = self.add_repo("second")
        store = self.store()

        store.add(str(first))
        store.add(str(second))

        loaded = RepositoryCollection.load(self.config_path)
        self.assertEqual([entry.name for entry in loaded], ["first", "second"])

    def test_a_duplicate_name_is_reported(self) -> None:
        first = self.add_repo("first")
        second = self.add_repo("second")
        store = self.store()
        store.add(str(first))

        with self.assertRaises(TodoError) as caught:
            store.add(str(second), name="first")

        self.assertEqual(caught.exception.code, "duplicate_repository")
        loaded = RepositoryCollection.load(self.config_path)
        self.assertEqual([entry.name for entry in loaded], ["first"])

    def test_a_duplicate_resolved_path_is_reported(self) -> None:
        repo = self.add_repo("shared")
        store = self.store()
        store.add(str(repo))

        with self.assertRaises(TodoError) as caught:
            store.add(str(repo / "."), name="other")

        self.assertEqual(caught.exception.code, "duplicate_repository")

    def test_an_invalid_file_is_not_rewritten(self) -> None:
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text("schema_version = 1\nextra = true\n", encoding="utf-8")
        original = self.config_path.read_bytes()
        repo = self.add_repo("sample-repo")

        with self.assertRaises(TodoError) as caught:
            CollectionStore(self.config_path).add(str(repo))

        self.assertEqual(caught.exception.code, "invalid_config")
        self.assertEqual(self.config_path.read_bytes(), original)

    def test_an_unsupported_version_is_not_rewritten(self) -> None:
        self.config_path.parent.mkdir(parents=True)
        self.config_path.write_text("schema_version = 2\n", encoding="utf-8")
        original = self.config_path.read_bytes()
        repo = self.add_repo("sample-repo")

        with self.assertRaises(TodoError) as caught:
            CollectionStore(self.config_path).add(str(repo))

        self.assertEqual(caught.exception.code, "unsupported_config_version")
        self.assertEqual(self.config_path.read_bytes(), original)


class RemoveTests(CollectionStoreTestCase):
    """Cover remove-by-name, remove-by-path, and name-wins collisions."""

    def configure(self, *names: str) -> CollectionStore:
        """
        Add named repositories and return the store.

        Side Effects:
            Writes the configuration file.

        Args:
            *names: Directory basenames to add in order.

        Returns:
            Store bound to the written file.
        """
        store = self.store()
        for name in names:
            store.add(str(self.add_repo(name)))
        return store

    def test_remove_by_name(self) -> None:
        store = self.configure("keep", "drop")

        entry = store.remove("drop")

        self.assertEqual(entry.name, "drop")
        loaded = RepositoryCollection.load(self.config_path)
        self.assertEqual([item.name for item in loaded], ["keep"])

    def test_remove_by_path(self) -> None:
        store = self.configure("keep", "drop")
        target = self.directory / "drop"

        entry = store.remove(str(target))

        self.assertEqual(entry.name, "drop")
        loaded = RepositoryCollection.load(self.config_path)
        self.assertEqual([item.name for item in loaded], ["keep"])

    def test_remove_dot_uses_the_current_directory(self) -> None:
        store = self.configure("keep", "cwd-repo")
        original = Path.cwd()
        os.chdir(self.directory / "cwd-repo")
        self.addCleanup(os.chdir, original)

        entry = store.remove(".")

        self.assertEqual(entry.name, "cwd-repo")

    def test_name_wins_when_a_slug_matches_a_name(self) -> None:
        store = self.store()
        named = self.add_repo("shared")
        other = self.directory / "other"
        other.mkdir()
        store.add(str(named), name="shared")
        store.add(str(other), name="other")

        entry = store.remove("shared")

        self.assertEqual(entry.path, named)
        loaded = RepositoryCollection.load(self.config_path)
        self.assertEqual([item.name for item in loaded], ["other"])

    def test_an_unknown_target_is_not_found(self) -> None:
        store = self.configure("keep")

        with self.assertRaises(TodoError) as caught:
            store.remove("missing")

        self.assertEqual(caught.exception.code, "repository_not_found")
        loaded = RepositoryCollection.load(self.config_path)
        self.assertEqual([item.name for item in loaded], ["keep"])

    def test_removing_the_last_entry_leaves_a_valid_empty_file(self) -> None:
        store = self.configure("only")

        store.remove("only")

        collection = RepositoryCollection.load(self.config_path)
        self.assertEqual(len(collection), 0)


if __name__ == "__main__":
    unittest.main()
