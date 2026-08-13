"""Storage-boundary tests for locking, durability, archiving, and file safety."""

from __future__ import annotations

import os
import re
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bot_todo import repository
from bot_todo.repository import TodoError, TodoStore
from tests.support import TodoCliTestCase


class LockingTests(TodoCliTestCase):
    """Verify shared reads, exclusive mutations, and the conflict timeout."""

    def test_a_held_mutation_blocks_a_concurrent_read(self) -> None:
        writer = TodoStore(self.root, lock_timeout=0.1)
        reader = TodoStore(self.root, lock_timeout=0.1)

        with writer.transaction(), self.assertRaises(TodoError) as caught:
            reader.snapshot()

        self.assertEqual(caught.exception.code, "conflict")

    def test_a_held_mutation_blocks_a_concurrent_mutation(self) -> None:
        first = TodoStore(self.root, lock_timeout=0.1)
        second = TodoStore(self.root, lock_timeout=0.1)

        with (
            first.transaction(),
            self.assertRaises(TodoError) as caught,
            second.transaction(),
        ):
            pass

        self.assertEqual(caught.exception.code, "conflict")

    def test_concurrent_reads_share_the_lock(self) -> None:
        first = TodoStore(self.root, lock_timeout=0.1)
        second = TodoStore(self.root, lock_timeout=0.1)

        with first.lock.shared(), second.lock.shared():
            pass

    def test_a_conflict_leaves_the_task_file_untouched(self) -> None:
        original = (self.root / "TODO.md").read_text()
        blocker = TodoStore(self.root, lock_timeout=0.1)
        writer = TodoStore(self.root, lock_timeout=0.1)

        with (
            blocker.lock.exclusive(),
            self.assertRaises(TodoError),
            writer.transaction() as transaction,
        ):
            transaction.add(title="Never", priority="P2", task_type="bug", simple=True)

        self.assertEqual((self.root / "TODO.md").read_text(), original)


class DurabilityTests(TodoCliTestCase):
    """Verify that failed writes never publish a partial task file."""

    def test_commit_failure_preserves_the_original_file(self) -> None:
        original = (self.root / "TODO.md").read_text()
        store = TodoStore(self.root)

        with (
            mock.patch.object(
                repository, "_write_document", side_effect=OSError("simulated")
            ),
            self.assertRaises(OSError),
            store.transaction() as transaction,
        ):
            transaction.add(
                title="Must not be written",
                priority="P2",
                task_type="bug",
                simple=True,
            )

        self.assertEqual((self.root / "TODO.md").read_text(), original)

    def test_failed_initialization_leaves_no_task_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = TodoStore(Path(directory))

            with (
                mock.patch.object(
                    repository, "_write_document", side_effect=OSError("simulated")
                ),
                self.assertRaises(OSError),
            ):
                store.initialize("Example")

            self.assertFalse(store.todo_path.exists())

    def test_mutation_preserves_existing_permissions(self) -> None:
        todo_path = self.root / "TODO.md"
        todo_path.chmod(0o600)

        self.add_simple("Permission check")

        self.assertEqual(stat.S_IMODE(todo_path.stat().st_mode), 0o600)

    def test_an_interrupted_overflow_keeps_the_task_file_authoritative(self) -> None:
        for number in range(21):
            self.run_cli("complete", self.add_simple(f"Task {number:02d}"))
        pending_id = self.add_simple("One more")
        original = (self.root / "TODO.md").read_text()
        archive_before = (self.root / "TODO.archive.md").read_text()
        store = TodoStore(self.root)

        with (
            mock.patch.object(
                repository, "_write_document", side_effect=OSError("simulated")
            ),
            self.assertRaises(OSError),
            store.transaction() as transaction,
        ):
            transaction.close(pending_id, "completed")

        self.assertEqual((self.root / "TODO.md").read_text(), original)
        self.assertTrue(
            (self.root / "TODO.archive.md").read_text().startswith(archive_before)
        )


class ArchiveTests(TodoCliTestCase):
    """Verify append-only archive behavior and blocker retention."""

    def test_the_archive_is_appended_and_never_rewritten(self) -> None:
        for number in range(21):
            self.run_cli("complete", self.add_simple(f"Task {number:02d}"))
        archive_path = self.root / "TODO.archive.md"
        first = archive_path.read_text()

        self.run_cli("complete", self.add_simple("Another task"))
        second = archive_path.read_text()

        self.assertTrue(second.startswith(first))
        self.assertGreater(len(second), len(first))
        self.assertEqual(second.count("# TODO Archive — Example"), 1)

    def test_a_referenced_blocker_is_retained_in_done(self) -> None:
        blocker_id = self.add_simple("Blocker", "P1")
        self.run_cli(
            "add",
            "Dependent",
            "--priority",
            "P1",
            "--type",
            "feature",
            "--simple",
            "--blocked-by",
            blocker_id,
        )
        self.run_cli("complete", blocker_id)
        for number in range(25):
            self.run_cli("complete", self.add_simple(f"Task {number:02d}"))

        todo = (self.root / "TODO.md").read_text()

        self.assertIn(f"**{blocker_id}**", todo)
        self.assertEqual(self.run_cli("validate").stdout.strip(), "valid")

    def test_a_cancelled_blocker_keeps_blocking_after_overflow(self) -> None:
        blocker_id = self.add_simple("Blocker", "P1")
        dependent_id = self.added_id(
            "Dependent",
            "--priority",
            "P1",
            "--type",
            "feature",
            "--simple",
            "--blocked-by",
            blocker_id,
        )
        self.run_cli("cancel", blocker_id, "--reason", "Superseded")
        for number in range(25):
            self.run_cli("complete", self.add_simple(f"Task {number:02d}"))

        self.assertEqual(
            self.run_cli("actionable").stdout.strip(), "no actionable task"
        )
        self.assertIn(dependent_id, self.run_cli("list").stdout)

    def test_show_finds_an_archived_task(self) -> None:
        for number in range(21):
            self.run_cli("complete", self.add_simple(f"Task {number:02d}"))
        self.assertNotIn("**T001**", (self.root / "TODO.md").read_text())

        result = self.run_cli("show", "T001")

        self.assertIn("**T001**", result.stdout)

    def test_archive_command_reports_the_number_retired(self) -> None:
        for number in range(21):
            self.run_cli("complete", self.add_simple(f"Task {number:02d}"))

        self.assertEqual(self.run_cli("archive").stdout.strip(), "0")

    def test_an_absent_archive_is_not_an_error(self) -> None:
        self.assertFalse((self.root / "TODO.archive.md").exists())

        self.assertEqual(self.run_cli("validate").stdout.strip(), "valid")


class FileSafetyTests(TodoCliTestCase):
    """Verify that unsafe canonical file types are rejected, never replaced."""

    def _expect_invalid_document(self) -> None:
        """
        Assert that reading the repository reports an unsafe canonical file.

        Raises:
            AssertionError: If the read succeeds or reports another code.

        """
        with self.assertRaises(TodoError) as caught:
            TodoStore(self.root).snapshot()
        self.assertEqual(caught.exception.code, "invalid_document")

    def test_a_symlinked_task_file_is_rejected(self) -> None:
        todo_path = self.root / "TODO.md"
        target = self.root / "elsewhere.md"
        target.write_text(todo_path.read_text())
        todo_path.unlink()
        try:
            todo_path.symlink_to(target)
        except OSError:  # pragma: no cover - platform without symlink rights
            self.skipTest("symlinks are unavailable")

        self._expect_invalid_document()
        self.assertTrue(todo_path.is_symlink())

    def test_a_directory_at_the_task_file_path_is_rejected(self) -> None:
        todo_path = self.root / "TODO.md"
        todo_path.unlink()
        todo_path.mkdir()

        self._expect_invalid_document()

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFOs")
    def test_a_fifo_at_the_task_file_path_is_rejected(self) -> None:
        todo_path = self.root / "TODO.md"
        todo_path.unlink()
        os.mkfifo(todo_path)

        self._expect_invalid_document()

    def test_an_unsafe_archive_is_rejected(self) -> None:
        (self.root / "TODO.archive.md").mkdir()

        self._expect_invalid_document()

    def test_a_symlinked_repository_directory_resolves_to_one_identity(self) -> None:
        alias = self.root.parent / f"{self.root.name}-alias"
        try:
            alias.symlink_to(self.root, target_is_directory=True)
        except OSError:  # pragma: no cover - platform without symlink rights
            self.skipTest("symlinks are unavailable")
        try:
            self.assertEqual(TodoStore(alias).root, TodoStore(self.root).root)
        finally:
            alias.unlink()


class FormatVersionTests(TodoCliTestCase):
    """Verify that unsupported task data formats fail before any write."""

    def test_an_unsupported_format_version_is_rejected(self) -> None:
        todo_path = self.root / "TODO.md"
        todo_path.write_text(
            todo_path.read_text().replace("todo-format: 1", "todo-format: 2")
        )

        with self.assertRaises(TodoError) as caught:
            TodoStore(self.root).snapshot()

        self.assertEqual(caught.exception.code, "unsupported_format_version")

    def test_an_unsupported_format_version_blocks_mutation(self) -> None:
        todo_path = self.root / "TODO.md"
        original = todo_path.read_text().replace("todo-format: 1", "todo-format: 2")
        todo_path.write_text(original)

        result = self.run_cli(
            "add", "Blocked", "--type", "bug", "--simple", check=False
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(todo_path.read_text(), original)


class CompatibilityTests(unittest.TestCase):
    """Verify that task data written before this release still loads."""

    #: A repository pair as written by the pre-package embedded CLI.
    LEGACY_TODO = (
        "# TODO — Legacy\n"
        "<!-- todo-format: 1; next-id: 3 -->\n"
        "\n"
        "## P0 — Critical / Blocking\n"
        "\n"
        "## P1 — High Priority\n"
        "\n"
        "- [ ] **T002** Still open #feature\n"
        "  - Acceptance: It ships\n"
        "  - Blocked by: T001\n"
        "\n"
        "## P2 — Backlog\n"
        "\n"
        "## Done (recent)\n"
        "\n"
        "- [x] **T001** Already closed #chore #simple\n"
        "  - Outcome: completed\n"
        "  - Closed: 2024-01-02\n"
    )

    def test_a_legacy_pair_loads_and_mutates_without_migration(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "TODO.md").write_text(self.LEGACY_TODO)
            (root / "TODO.archive.md").write_text("# TODO Archive — Legacy\n")
            store = TodoStore(root)

            actionable = store.snapshot().actionable()
            self.assertIsNotNone(actionable)
            assert actionable is not None
            self.assertEqual(actionable.task_id, "T002")

            with store.transaction() as transaction:
                added = transaction.add(
                    title="Newly added", priority="P2", task_type="bug", simple=True
                )

            self.assertEqual(added.task_id, "T003")
            self.assertIn("next-id: 4", (root / "TODO.md").read_text())

    def test_noncanonical_field_order_is_accepted_and_rewritten(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "TODO.md").write_text(
                self.LEGACY_TODO.replace(
                    "  - Acceptance: It ships\n  - Blocked by: T001\n",
                    "  - Blocked by: T001\n  - Acceptance: It ships\n",
                )
            )
            store = TodoStore(root)

            with store.transaction() as transaction:
                transaction.edit("T002", title="Renamed")

            rewritten = (root / "TODO.md").read_text()

            self.assertLess(
                rewritten.index("Acceptance: It ships"),
                rewritten.index("Blocked by: T001"),
            )

    def test_output_matches_the_documented_canonical_layout(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = TodoStore(root)
            store.initialize("Layout")

            with store.transaction() as transaction:
                transaction.add(
                    title="Canonical", priority="P1", task_type="docs", simple=True
                )

            self.assertRegex(
                (root / "TODO.md").read_text(),
                re.compile(
                    r"\A# TODO — Layout\n<!-- todo-format: 1; next-id: 2 -->\n\n"
                    r"## P0 — Critical / Blocking\n\n"
                    r"## P1 — High Priority\n\n"
                    r"- \[ \] \*\*T001\*\* Canonical #docs #simple\n\n"
                    r"## P2 — Backlog\n\n"
                    r"## Done \(recent\)\n\Z"
                ),
            )


if __name__ == "__main__":
    unittest.main()
