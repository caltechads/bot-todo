"""End-to-end tests for the bot-todo command-line interface."""

from __future__ import annotations

import contextlib
import json
import re
import tempfile
import unittest
from pathlib import Path

from tests.support import TodoCliTestCase, invoke


class InitializationAndIdentityTests(TodoCliTestCase):
    """Verify initialization, allocation, and task identity rules."""

    def test_init_add_read_and_validate(self) -> None:
        task_id = self.run_cli(
            "add",
            "Fix authentication",
            "--priority",
            "P1",
            "--type",
            "bug",
            "--tag",
            "auth",
            "--acceptance",
            "Invalid tokens are rejected",
        ).stdout.strip()

        self.assertEqual(task_id, "T001")
        self.assertIn("T001", self.run_cli("list").stdout)
        self.assertIn("Fix authentication", self.run_cli("show", "T001").stdout)
        self.assertEqual(self.run_cli("actionable").stdout.split()[0], "T001")
        self.assertEqual(self.run_cli("validate").stdout.strip(), "valid")

        todo = (self.root / "TODO.md").read_text()
        self.assertIn("<!-- todo-format: 1; next-id: 2 -->", todo)
        self.assertIn("#bug #auth", todo)
        self.assertIn("Acceptance: Invalid tokens are rejected", todo)

    def test_add_requires_acceptance_or_simple_marker(self) -> None:
        result = self.run_cli(
            "add",
            "Ambiguous task",
            "--priority",
            "P2",
            "--type",
            "feature",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--acceptance or --simple", result.stderr)
        self.assertNotIn("Ambiguous task", (self.root / "TODO.md").read_text())

    def test_add_rejects_hashtag_like_title_tokens(self) -> None:
        original = (self.root / "TODO.md").read_text()

        result = self.run_cli(
            "add",
            "Fix issue #123",
            "--priority",
            "P2",
            "--type",
            "bug",
            "--simple",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("use --tag", result.stderr)
        self.assertEqual((self.root / "TODO.md").read_text(), original)

    def test_ids_expand_past_three_digits(self) -> None:
        todo_path = self.root / "TODO.md"
        todo_path.write_text(
            todo_path.read_text().replace("next-id: 1", "next-id: 999")
        )

        self.assertEqual(self.add_simple("Task 999"), "T999")
        self.assertEqual(self.add_simple("Task 1000"), "T1000")
        self.assertIn("next-id: 1001", todo_path.read_text())

    def test_validate_rejects_counter_at_or_below_used_id(self) -> None:
        self.add_simple("Existing task")
        todo_path = self.root / "TODO.md"
        todo_path.write_text(todo_path.read_text().replace("next-id: 2", "next-id: 1"))

        result = self.run_cli("validate", check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("next-id must be greater than 1", result.stderr)

    def test_init_rejects_multiline_project_without_creating_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            result = invoke("--root", str(root), "init", "--name", "Bad\nProject")

            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((root / "TODO.md").exists())
            self.assertFalse((root / "TODO.archive.md").exists())

    def test_init_reports_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = invoke("--root", directory, "init", "--name", "Example")

            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout.strip(), "initialized")

    def test_init_rejects_an_initialized_repository(self) -> None:
        result = self.run_cli("init", "--name", "Example", check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)


class LifecycleTests(TodoCliTestCase):
    """Verify task state transitions, dependencies, and archive retention."""

    def test_claim_release_edit_and_complete(self) -> None:
        dependency_id = self.add_simple("Dependency", "P1")
        dependent_id = self.run_cli(
            "add",
            "Dependent",
            "--priority",
            "P1",
            "--type",
            "feature",
            "--simple",
            "--blocked-by",
            dependency_id,
        ).stdout.strip()

        self.assertEqual(self.run_cli("actionable").stdout.split()[0], dependency_id)
        self.run_cli(
            "claim", dependency_id, "--actor", "codex", "--branch", "feature/todo"
        )
        self.assertEqual(
            self.run_cli("actionable").stdout.strip(), "no actionable task"
        )
        self.assertIn("Claimed: codex |", self.run_cli("show", dependency_id).stdout)
        self.run_cli("release", dependency_id)
        self.run_cli(
            "edit",
            dependent_id,
            "--priority",
            "P0",
            "--add-tag",
            "workflow",
            "--acceptance",
            "Dependency is integrated",
        )
        self.run_cli("complete", dependency_id)

        self.assertEqual(self.run_cli("actionable").stdout.split()[0], dependent_id)
        self.assertIn("#workflow", self.run_cli("show", dependent_id).stdout)
        completed = self.run_cli("show", dependency_id).stdout
        self.assertIn("Outcome: completed", completed)
        self.assertRegex(completed, r"Closed: \d{4}-\d{2}-\d{2}")

    def test_cancelled_blocker_does_not_unblock_dependent_task(self) -> None:
        blocker_id = self.add_simple("Optional prerequisite", "P1")
        dependent_id = self.run_cli(
            "add",
            "Still needs a decision",
            "--priority",
            "P1",
            "--type",
            "feature",
            "--simple",
            "--blocked-by",
            blocker_id,
        ).stdout.strip()

        self.run_cli("cancel", blocker_id, "--reason", "Superseded")

        self.assertEqual(
            self.run_cli("actionable").stdout.strip(), "no actionable task"
        )
        self.assertIn(dependent_id, self.run_cli("list").stdout)
        self.assertIn("Outcome: cancelled", self.run_cli("show", blocker_id).stdout)
        self.assertIn("Reason: Superseded", self.run_cli("show", blocker_id).stdout)

    def test_edit_clears_blockers(self) -> None:
        blocker_id = self.add_simple("Blocker", "P1")
        dependent_id = self.run_cli(
            "add",
            "Dependent",
            "--priority",
            "P1",
            "--type",
            "feature",
            "--simple",
            "--blocked-by",
            blocker_id,
        ).stdout.strip()

        self.run_cli("edit", dependent_id, "--clear-blockers")

        self.assertNotIn("Blocked by", self.run_cli("show", dependent_id).stdout)

    def test_edit_rejects_removing_a_type_tag(self) -> None:
        task_id = self.add_simple("Typed task")

        result = self.run_cli("edit", task_id, "--remove-tag", "chore", check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("use --type", result.stderr)

    def test_archive_keeps_twenty_most_recent_closed_tasks(self) -> None:
        for number in range(21):
            task_id = self.add_simple(f"Task {number:02d}")
            self.run_cli("complete", task_id)

        todo = (self.root / "TODO.md").read_text()
        archive = (self.root / "TODO.archive.md").read_text()

        self.assertEqual(
            len(re.findall(r"^- \[x\] \*\*T\d+\*\*", todo, re.MULTILINE)), 20
        )
        self.assertNotIn("**T001**", todo)
        self.assertIn("**T001**", archive)
        self.assertEqual(self.run_cli("validate").stdout.strip(), "valid")

    def test_failed_mutation_preserves_invalid_original(self) -> None:
        todo_path = self.root / "TODO.md"
        invalid = todo_path.read_text().replace("## P1 — High Priority", "## Wrong")
        todo_path.write_text(invalid)

        result = self.run_cli(
            "add",
            "Must not be written",
            "--priority",
            "P2",
            "--type",
            "bug",
            "--simple",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(todo_path.read_text(), invalid)

    def test_unstructured_content_before_sections_is_not_silently_lost(self) -> None:
        todo_path = self.root / "TODO.md"
        invalid = todo_path.read_text().replace(
            "\n## P0", "\nDo not discard this note\n\n## P0"
        )
        todo_path.write_text(invalid)

        result = self.run_cli(
            "add",
            "Must not be written",
            "--priority",
            "P2",
            "--type",
            "bug",
            "--simple",
            check=False,
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(todo_path.read_text(), invalid)

    def test_validate_rejects_invalid_close_date(self) -> None:
        task_id = self.add_simple("Close me")
        self.run_cli("complete", task_id)
        todo_path = self.root / "TODO.md"
        todo_path.write_text(
            re.sub(
                r"Closed: \d{4}-\d{2}-\d{2}", "Closed: someday", todo_path.read_text()
            )
        )

        result = self.run_cli("validate", check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid Closed date", result.stderr)

    def test_validate_rejects_blank_field_and_malformed_claim(self) -> None:
        task_id = self.run_cli(
            "add",
            "Validate fields",
            "--priority",
            "P1",
            "--type",
            "bug",
            "--acceptance",
            "A real result",
        ).stdout.strip()
        todo_path = self.root / "TODO.md"
        malformed = todo_path.read_text().replace(
            "  - Acceptance: A real result",
            "  - Acceptance:   \n  - Claimed: nobody",
        )
        todo_path.write_text(malformed)

        result = self.run_cli("validate", check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(task_id, result.stderr)


class SelectionTests(TodoCliTestCase):
    """Verify repository selection, discovery, and process contract."""

    def test_discovery_finds_the_nearest_ancestor_repository(self) -> None:
        nested = self.root / "nested" / "deeper"
        nested.mkdir(parents=True)
        self.add_simple("Discoverable")

        with contextlib.chdir(nested):
            result = invoke("list")

        self.assertEqual(result.returncode, 0)
        self.assertIn("Discoverable", result.stdout)

    def test_discovery_stops_at_the_first_invalid_repository(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()
        (nested / "TODO.md").write_text("not a task file\n")

        with contextlib.chdir(nested):
            result = invoke("list")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TODO.md:1", result.stderr)

    def test_missing_repository_reports_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory, contextlib.chdir(directory):
            result = invoke("list")

        self.assertEqual(result.returncode, 1)
        self.assertIn("no task repository", result.stderr)

    def test_init_targets_the_exact_working_directory(self) -> None:
        nested = self.root / "nested"
        nested.mkdir()

        with contextlib.chdir(nested):
            result = invoke("init", "--name", "Nested")

        self.assertEqual(result.returncode, 0)
        self.assertTrue((nested / "TODO.md").exists())

    def test_long_option_abbreviation_is_rejected(self) -> None:
        result = invoke("--roo", str(self.root), "list")

        self.assertEqual(result.returncode, 2)

    def test_unknown_option_reports_a_usage_failure(self) -> None:
        result = invoke("--root", str(self.root), "list", "--nope")

        self.assertEqual(result.returncode, 2)

    def test_help_and_version_succeed(self) -> None:
        self.assertEqual(invoke("--help").returncode, 0)
        self.assertEqual(invoke("--version").returncode, 0)

    def test_domain_failure_exits_one(self) -> None:
        result = self.run_cli("show", "T999", check=False)

        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown task ID T999", result.stderr)

    def test_results_and_diagnostics_use_separate_streams(self) -> None:
        failure = self.run_cli("show", "T999", check=False)

        self.assertEqual(failure.stdout, "")
        self.assertNotEqual(failure.stderr, "")


class QueryTests(TodoCliTestCase):
    """Cover the settled critical and actionable query semantics."""

    def test_critical_returns_a_blocked_task_that_actionable_skips(self) -> None:
        dependency = self.add_simple("Groundwork", "P1")
        blocked = self.add_simple("Blocked work", "P0")
        self.run_cli("edit", blocked, "--blocked-by", dependency)

        self.assertEqual(self.run_json("critical")["data"]["task"]["id"], blocked)
        self.assertEqual(self.run_json("actionable")["data"]["task"]["id"], dependency)

    def test_critical_returns_a_claimed_task_that_actionable_skips(self) -> None:
        claimed = self.add_simple("Claimed work", "P0")
        later = self.add_simple("Later work", "P1")
        self.run_cli("claim", claimed, "--actor", "agent", "--branch", "topic")

        self.assertEqual(self.run_json("critical")["data"]["task"]["id"], claimed)
        self.assertEqual(self.run_json("actionable")["data"]["task"]["id"], later)

    def test_an_empty_list_prints_nothing_and_succeeds(self) -> None:
        result = self.run_cli("list")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(self.run_json("list")["data"]["tasks"], [])

    def test_an_empty_singular_query_explains_itself_and_succeeds(self) -> None:
        for command in ("critical", "actionable"):
            result = self.run_cli(command)

            self.assertEqual(result.returncode, 0)
            self.assertNotEqual(result.stdout.strip(), "")
            self.assertIsNone(self.run_json(command)["data"]["task"])


class JsonDocumentTests(TodoCliTestCase):
    """Cover JSON Schema Version 1 success and error documents."""

    #: Every key a Task object must carry.
    TASK_KEYS = frozenset(
        {
            "repository",
            "id",
            "title",
            "state",
            "priority",
            "type",
            "tags",
            "simple",
            "acceptance",
            "context",
            "related",
            "blocked_by",
            "claim",
            "actionable",
            "closed_on",
            "reason",
        }
    )

    def test_the_success_envelope_names_its_command_and_version(self) -> None:
        document = self.run_json("list")

        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["command"], "list")
        self.assertEqual(document["data"], {"tasks": []})

    def test_a_task_carries_every_documented_key(self) -> None:
        task_id = self.run_cli(
            "add",
            "Fix authentication",
            "--priority",
            "P1",
            "--type",
            "bug",
            "--tag",
            "auth",
            "--acceptance",
            "Invalid tokens are rejected",
            "--context",
            "docs/auth.md",
            "--related",
            "T000",
        ).stdout.strip()

        task = self.run_json("show", task_id)["data"]["task"]

        self.assertEqual(set(task), self.TASK_KEYS)
        self.assertEqual(task["id"], task_id)
        self.assertEqual(task["state"], "open")
        self.assertEqual(task["priority"], "P1")
        self.assertEqual(task["type"], "bug")
        self.assertEqual(task["tags"], ["auth"])
        self.assertFalse(task["simple"])
        self.assertEqual(task["acceptance"], "Invalid tokens are rejected")
        self.assertEqual(task["context"], "docs/auth.md")
        self.assertEqual(task["related"], "T000")
        self.assertEqual(task["blocked_by"], [])
        self.assertIsNone(task["claim"])
        self.assertTrue(task["actionable"])
        self.assertIsNone(task["closed_on"])
        self.assertIsNone(task["reason"])

    def test_repository_provenance_is_absolute_and_unnamed_without_configuration(
        self,
    ) -> None:
        task_id = self.add_simple("Work")

        repository = self.run_json("show", task_id)["data"]["task"]["repository"]

        self.assertIsNone(repository["name"])
        self.assertEqual(repository["path"], str(self.root))

    def test_a_simple_task_reports_no_acceptance_criteria(self) -> None:
        task_id = self.add_simple("Simple work")

        task = self.run_json("show", task_id)["data"]["task"]

        self.assertTrue(task["simple"])
        self.assertIsNone(task["acceptance"])
        self.assertEqual(task["tags"], [])

    def test_a_completed_task_reports_its_closing_date_and_no_reason(self) -> None:
        task_id = self.add_simple("Work")
        self.run_cli("complete", task_id)

        task = self.run_json("show", task_id)["data"]["task"]

        self.assertEqual(task["state"], "completed")
        self.assertIsNone(task["priority"])
        self.assertIsNotNone(task["closed_on"])
        self.assertIsNone(task["reason"])
        self.assertFalse(task["actionable"])

    def test_a_cancelled_task_reports_its_reason(self) -> None:
        task_id = self.add_simple("Work")
        self.run_cli("cancel", task_id, "--reason", "superseded")

        task = self.run_json("show", task_id)["data"]["task"]

        self.assertEqual(task["state"], "cancelled")
        self.assertEqual(task["reason"], "superseded")
        self.assertFalse(task["actionable"])

    def test_a_claimed_task_reports_its_claim(self) -> None:
        task_id = self.add_simple("Work")
        self.run_cli("claim", task_id, "--actor", "agent", "--branch", "topic")

        task = self.run_json("show", task_id)["data"]["task"]

        self.assertEqual(task["claim"]["actor"], "agent")
        self.assertEqual(task["claim"]["branch"], "topic")
        self.assertRegex(task["claim"]["claimed_on"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertFalse(task["actionable"])

    def test_a_blocked_task_lists_its_blockers(self) -> None:
        dependency = self.add_simple("Groundwork")
        blocked = self.add_simple("Blocked work")
        self.run_cli("edit", blocked, "--blocked-by", dependency)

        task = self.run_json("show", blocked)["data"]["task"]

        self.assertEqual(task["blocked_by"], [dependency])
        self.assertFalse(task["actionable"])

    def test_every_mutation_returns_the_resulting_task(self) -> None:
        task_id = self.add_simple("Work")

        for arguments in (
            ("claim", task_id, "--actor", "agent"),
            ("release", task_id),
            ("edit", task_id, "--title", "Renamed"),
            ("complete", task_id),
        ):
            document = self.run_json(*arguments)

            self.assertEqual(document["data"]["task"]["id"], task_id)

    def test_add_returns_the_added_task(self) -> None:
        document = self.run_json("add", "New work", "--type", "chore", "--simple")

        self.assertEqual(document["data"]["task"]["title"], "New work")

    def test_command_specific_results_carry_their_own_shapes(self) -> None:
        self.assertEqual(
            self.run_json("validate")["data"],
            {"repository": {"name": None, "path": str(self.root)}},
        )
        self.assertEqual(self.run_json("archive")["data"], {"archived": 0})

    def test_init_reports_repository_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = invoke("--json", "--root", directory, "init", "--name", "Fresh")

        document = json.loads(result.stdout)

        self.assertEqual(document["command"], "init")
        self.assertEqual(document["data"]["repository"]["name"], None)

    def test_an_expected_failure_writes_one_error_document_to_stderr(self) -> None:
        error = self.run_json_error("show", "T999")

        self.assertEqual(error["code"], "unknown_task")
        self.assertIn("T999", error["message"])

    def test_an_unsupported_format_version_reports_its_versions(self) -> None:
        path = self.root / "TODO.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "todo-format: 1", "todo-format: 2"
            ),
            encoding="utf-8",
        )

        error = self.run_json_error("validate")

        self.assertEqual(error["code"], "unsupported_format_version")
        self.assertEqual(error["encountered"], 2)
        self.assertEqual(error["supported"], [1])

    def test_exactly_one_document_is_written(self) -> None:
        self.add_simple("Work")

        stdout = self.run_cli("--json", "list").stdout

        self.assertEqual(stdout.count("\n"), 1)
        self.assertTrue(stdout.endswith("\n"))


class GrammarTests(TodoCliTestCase):
    """Cover the settled option grammar and usage failures."""

    def test_a_usage_failure_under_json_emits_an_error_document(self) -> None:
        result = invoke("--json", "--root", str(self.root), "bogus")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, "")
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "usage")

    def test_an_abbreviated_json_option_is_not_honored(self) -> None:
        result = invoke("--js", "--root", str(self.root), "list")

        self.assertEqual(result.returncode, 2)
        self.assertNotIn("schema_version", result.stderr)

    def test_abbreviation_is_rejected_at_the_subcommand_level(self) -> None:
        task_id = self.add_simple("Work")

        result = self.run_cli("edit", task_id, "--tit", "Renamed", check=False)

        self.assertEqual(result.returncode, 2)

    def test_help_and_version_succeed_under_json(self) -> None:
        for option in ("--help", "--version"):
            result = invoke("--json", option)

            self.assertEqual(result.returncode, 0)
            self.assertNotIn("schema_version", result.stdout)

    def test_config_requires_the_repo_selector(self) -> None:
        result = invoke("--config", "/nowhere.toml", "--root", str(self.root), "list")

        self.assertEqual(result.returncode, 2)

    def test_root_and_repo_are_mutually_exclusive(self) -> None:
        result = invoke("--root", str(self.root), "--repo", "name", "list")

        self.assertEqual(result.returncode, 2)

    def test_an_edit_requesting_no_change_is_a_usage_failure(self) -> None:
        task_id = self.add_simple("Work")

        result = self.run_cli("edit", task_id, check=False)

        self.assertEqual(result.returncode, 2)

    def test_edit_clears_optional_fields(self) -> None:
        task_id = self.run_cli(
            "add",
            "Work",
            "--type",
            "chore",
            "--acceptance",
            "It works",
            "--context",
            "docs/a.md",
            "--related",
            "T000",
        ).stdout.strip()

        self.run_cli("edit", task_id, "--simple", "--clear-context", "--clear-related")
        task = self.run_json("show", task_id)["data"]["task"]

        self.assertTrue(task["simple"])
        self.assertIsNone(task["acceptance"])
        self.assertIsNone(task["context"])
        self.assertIsNone(task["related"])

    def test_edit_rejects_setting_and_clearing_the_same_field(self) -> None:
        task_id = self.add_simple("Work")

        result = self.run_cli(
            "edit", task_id, "--context", "docs/a.md", "--clear-context", check=False
        )

        self.assertEqual(result.returncode, 2)


class ConfiguredSelectionTests(TodoCliTestCase):
    """Cover the --repo selector against a temporary configuration."""

    def setUp(self) -> None:
        """
        Configure the isolated repository under a Repository Name.

        Side Effects:
            Writes a configuration file beside the repository.
        """
        super().setUp()
        self.config = self.root / "config.toml"
        self.config.write_text(
            "schema_version = 1\n\n"
            f'[[repositories]]\nname = "demo"\npath = "{self.root}"\n\n'
            '[[repositories]]\nname = "fresh"\npath = "created-by-init"\n',
            encoding="utf-8",
        )

    def test_repo_resolves_a_configured_repository_and_names_it(self) -> None:
        self.add_simple("Work")

        result = invoke(
            "--json", "--config", str(self.config), "--repo", "demo", "critical"
        )
        task = json.loads(result.stdout)["data"]["task"]

        self.assertEqual(task["repository"]["name"], "demo")
        self.assertEqual(task["repository"]["path"], str(self.root))

    def test_init_creates_a_configured_path_that_does_not_exist(self) -> None:
        result = invoke(
            "--config", str(self.config), "--repo", "fresh", "init", "--name", "Fresh"
        )

        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.root / "created-by-init" / "TODO.md").is_file())

    def test_an_unknown_repository_name_is_reported(self) -> None:
        result = invoke(
            "--json", "--config", str(self.config), "--repo", "absent", "list"
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(result.stderr)["error"]["code"], "repository_not_found"
        )


if __name__ == "__main__":
    unittest.main()
