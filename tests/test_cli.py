"""End-to-end tests for the bot-todo command-line interface."""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from bot_todo.config import CONFIG_ENV_VAR
from tests.support import CliResult, TodoCliTestCase, invoke, task_id_from_confirmation
from tests.test_task_management_snippet import EXPECTED


class InitializationAndIdentityTests(TodoCliTestCase):
    """Verify initialization, allocation, and task identity rules."""

    def test_init_add_read_and_validate(self) -> None:
        task_id = self.added_id(
            "Fix authentication",
            "--priority",
            "P1",
            "--type",
            "bug",
            "--tag",
            "auth",
            "--acceptance",
            "Invalid tokens are rejected",
        )

        self.assertEqual(task_id, "T001")
        self.assertIn("T001", self.run_cli("list").stdout)
        self.assertIn("Fix authentication", self.run_cli("show", "T001").stdout)
        self.assertEqual(self.run_cli("actionable").stdout.split()[0], "T001")
        self.assertEqual(self.run_cli("validate").stdout.strip(), "valid")

        todo = (self.root / "TODO.md").read_text()
        self.assertIn("<!-- todo-format: 2; next-id: 2 -->", todo)
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
            self.assertEqual(
                result.stdout,
                "initialized\n\n"
                "Add the following to your AGENTS.md/CLAUDE.md:\n\n"
                f"{EXPECTED}",
            )

    def test_init_defaults_name_to_root_basename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "My_App"
            root.mkdir()

            result = invoke("--root", str(root), "init")

            self.assertEqual(result.returncode, 0)
            self.assertIn("# TODO — My_App\n", (root / "TODO.md").read_text())

    def test_init_name_overrides_basename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "My_App"
            root.mkdir()

            result = invoke("--root", str(root), "init", "--name", "Custom")

            self.assertEqual(result.returncode, 0)
            self.assertIn("# TODO — Custom\n", (root / "TODO.md").read_text())

    def test_init_rejects_an_initialized_repository(self) -> None:
        result = self.run_cli("init", "--name", "Example", check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)


class LifecycleTests(TodoCliTestCase):
    """Verify task state transitions, dependencies, and archive retention."""

    def test_claim_release_edit_and_complete(self) -> None:
        dependency_id = self.add_simple("Dependency", "P1")
        dependent_id = self.added_id(
            "Dependent",
            "--priority",
            "P1",
            "--type",
            "feature",
            "--simple",
            "--blocked-by",
            dependency_id,
        )

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
        dependent_id = self.added_id(
            "Still needs a decision",
            "--priority",
            "P1",
            "--type",
            "feature",
            "--simple",
            "--blocked-by",
            blocker_id,
        )

        self.run_cli("cancel", blocker_id, "--reason", "Superseded")

        self.assertEqual(
            self.run_cli("actionable").stdout.strip(), "no actionable task"
        )
        self.assertIn(dependent_id, self.run_cli("list").stdout)
        self.assertIn("Outcome: cancelled", self.run_cli("show", blocker_id).stdout)
        self.assertIn("Reason: Superseded", self.run_cli("show", blocker_id).stdout)

    def test_edit_clears_blockers(self) -> None:
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
        task_id = self.added_id(
            "Validate fields",
            "--priority",
            "P1",
            "--type",
            "bug",
            "--acceptance",
            "A real result",
        )
        todo_path = self.root / "TODO.md"
        malformed = todo_path.read_text().replace(
            "  - Acceptance: A real result",
            "  - Acceptance:   \n  - Claimed: nobody",
        )
        todo_path.write_text(malformed)

        result = self.run_cli("validate", check=False)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn(task_id, result.stderr)


class ReviewStateTests(TodoCliTestCase):
    """Cover Review transitions, selectors, and JSON."""

    def test_review_clears_claim_and_stays_in_priority_section(self) -> None:
        task_id = self.add_simple("Needs a look", "P1")
        self.run_cli(
            "claim", task_id, "--actor", "codex", "--branch", "feature/review"
        )
        result = self.run_cli("review", task_id)
        self.assertEqual(result.stdout.strip(), f"reviewed {task_id} Needs a look")

        shown = self.run_cli("show", task_id).stdout
        self.assertIn("Review:", shown)
        self.assertNotIn("Claimed:", shown)
        self.assertNotIn("Outcome:", shown)
        todo = (self.root / "TODO.md").read_text(encoding="utf-8")
        p1 = todo.index("## P1")
        done = todo.index("## Done")
        self.assertLess(p1, todo.index(task_id))
        self.assertLess(todo.index(task_id), done)

        task = self.run_json("show", task_id)["data"]["task"]
        self.assertEqual(task["state"], "review")
        self.assertEqual(task["priority"], "P1")
        self.assertIsNone(task["claim"])
        self.assertFalse(task["actionable"])
        self.assertRegex(task["reviewed_on"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertIsNone(task["closed_on"])

    def test_unclaimed_open_task_can_enter_review(self) -> None:
        task_id = self.add_simple("Unclaimed work", "P2")
        self.run_cli("review", task_id)
        self.assertEqual(
            self.run_json("show", task_id)["data"]["task"]["state"], "review"
        )

    def test_list_includes_review_with_state_word(self) -> None:
        open_id = self.add_simple("Still open", "P1")
        review_id = self.add_simple("Waiting", "P1")
        self.run_cli("review", review_id)
        lines = self.run_cli("list").stdout.splitlines()
        self.assertIn(f"{open_id} P1 Still open #chore", lines)
        self.assertIn(f"{review_id} P1 review Waiting #chore", lines)

    def test_critical_and_actionable_skip_review(self) -> None:
        first = self.add_simple("In review", "P0")
        second = self.add_simple("Still open", "P1")
        self.run_cli("review", first)
        self.assertEqual(self.run_cli("critical").stdout.split()[0], second)
        self.assertEqual(self.run_cli("actionable").stdout.split()[0], second)

    def test_review_does_not_satisfy_blockers(self) -> None:
        blocker = self.add_simple("Blocker", "P1")
        dependent = self.added_id(
            "Dependent",
            "--priority",
            "P1",
            "--type",
            "feature",
            "--simple",
            "--blocked-by",
            blocker,
        )
        self.run_cli("review", blocker)
        self.assertEqual(
            self.run_cli("actionable").stdout.strip(), "no actionable task"
        )
        self.assertIn(dependent, self.run_cli("list").stdout)

    def test_complete_from_review_and_from_open(self) -> None:
        reviewed = self.add_simple("Reviewed work", "P2")
        opened = self.add_simple("Direct complete", "P2")
        self.run_cli("review", reviewed)
        self.run_cli("complete", reviewed)
        self.run_cli("complete", opened)
        self.assertEqual(
            self.run_json("show", reviewed)["data"]["task"]["state"], "completed"
        )
        self.assertIsNone(
            self.run_json("show", reviewed)["data"]["task"]["reviewed_on"]
        )
        self.assertEqual(
            self.run_json("show", opened)["data"]["task"]["state"], "completed"
        )

    def test_cancel_from_review(self) -> None:
        task_id = self.add_simple("Abandoned in review", "P2")
        self.run_cli("review", task_id)
        self.run_cli("cancel", task_id, "--reason", "Not shipping")
        task = self.run_json("show", task_id)["data"]["task"]
        self.assertEqual(task["state"], "cancelled")
        self.assertEqual(task["reason"], "Not shipping")
        self.assertIsNone(task["reviewed_on"])

    def test_reopen_returns_to_open_and_is_actionable(self) -> None:
        task_id = self.add_simple("Send back", "P1")
        self.run_cli("review", task_id)
        result = self.run_cli("reopen", task_id)
        self.assertEqual(result.stdout.strip(), f"reopened {task_id} Send back")
        task = self.run_json("show", task_id)["data"]["task"]
        self.assertEqual(task["state"], "open")
        self.assertIsNone(task["reviewed_on"])
        self.assertTrue(task["actionable"])
        self.assertIn(f"{task_id} P1 Send back #chore", self.run_cli("list").stdout)

    def test_reopen_rejects_open_and_completed(self) -> None:
        opened = self.add_simple("Never reviewed", "P2")
        closed = self.add_simple("Already done", "P2")
        self.run_cli("complete", closed)
        self.assertEqual(
            self.run_json_error("reopen", opened)["code"], "invalid_transition"
        )
        self.assertEqual(
            self.run_json_error("reopen", closed)["code"], "invalid_transition"
        )

    def test_claim_and_second_review_are_invalid_in_review(self) -> None:
        task_id = self.add_simple("Locked", "P2")
        self.run_cli("review", task_id)
        self.assertEqual(
            self.run_json_error(
                "claim", task_id, "--actor", "codex", "--branch", "x"
            )["code"],
            "invalid_transition",
        )
        self.assertEqual(
            self.run_json_error("review", task_id)["code"], "invalid_transition"
        )

    def test_edit_is_legal_in_review(self) -> None:
        task_id = self.add_simple("Editable", "P2")
        self.run_cli("review", task_id)
        self.run_cli("edit", task_id, "--title", "Still editable")
        self.assertEqual(
            self.run_json("show", task_id)["data"]["task"]["title"],
            "Still editable",
        )
        self.assertEqual(
            self.run_json("show", task_id)["data"]["task"]["state"], "review"
        )


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

    def test_init_without_selector_uses_cwd_basename(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "My_Cwd_App"
            root.mkdir()

            with contextlib.chdir(root):
                result = invoke("init")

            self.assertEqual(result.returncode, 0)
            self.assertTrue((root / "TODO.md").exists())
            self.assertIn("# TODO — My_Cwd_App\n", (root / "TODO.md").read_text())

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


class WebCommandTests(TodoCliTestCase):
    """Verify the human-only single-repository web command contract."""

    def test_web_rejects_aggregate_and_json_modes(self) -> None:
        """Catch web accidentally entering aggregate or machine-output flows."""
        aggregate = invoke("--all", "web", "--no-open")
        machine = invoke(
            "--json", "--root", str(self.root), "web", "--no-open"
        )

        self.assertEqual(aggregate.returncode, 2)
        self.assertIn("--all does not support web", aggregate.stderr)
        self.assertEqual(machine.returncode, 2)
        self.assertEqual(json.loads(machine.stderr)["error"]["code"], "usage")
        self.assertIn("web does not support --json", machine.stderr)

    @mock.patch("bot_todo.cli.run_web")
    def test_web_selects_one_repository_and_passes_launch_options(
        self, run_web: mock.Mock
    ) -> None:
        """Catch CLI dispatch that loses repository, port, or browser options."""
        result = self.run_cli("web", "--port", "0", "--no-open")

        self.assertEqual(result.returncode, 0)
        store = run_web.call_args.args[0]
        self.assertEqual(store.root, self.root)
        self.assertEqual(
            run_web.call_args.kwargs,
            {"name": None, "port": 0, "open_browser": False},
        )

    def test_web_rejects_a_port_outside_the_tcp_range(self) -> None:
        """Catch invalid numeric ports reaching socket binding."""
        for port in ("-1", "65536"):
            with self.subTest(port=port):
                result = self.run_cli("web", "--port", port, "--no-open", check=False)
                self.assertEqual(result.returncode, 2)
                self.assertIn("port must be between 0 and 65535", result.stderr)


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


class HumanMutationConfirmationTests(TodoCliTestCase):
    """Verify human mutation stdout names the operation, ID, and title."""

    def test_every_mutation_confirms_the_verb_id_and_title(self) -> None:
        added = self.run_cli("add", "Work item", "--type", "chore", "--simple")
        self.assertEqual(added.stdout.strip(), "added T001 Work item")

        claimed = self.run_cli("claim", "T001", "--actor", "codex")
        self.assertEqual(claimed.stdout.strip(), "claimed T001 Work item")

        released = self.run_cli("release", "T001")
        self.assertEqual(released.stdout.strip(), "released T001 Work item")

        edited = self.run_cli("edit", "T001", "--title", "Renamed work")
        self.assertEqual(edited.stdout.strip(), "edited T001 Renamed work")

        completed = self.run_cli("complete", "T001")
        self.assertEqual(completed.stdout.strip(), "completed T001 Renamed work")

        self.run_cli("add", "Drop me", "--type", "chore", "--simple")
        cancelled = self.run_cli("cancel", "T002", "--reason", "Superseded")
        self.assertEqual(cancelled.stdout.strip(), "cancelled T002 Drop me")


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
            "reviewed_on",
            "reason",
        }
    )

    def test_the_success_envelope_names_its_command_and_version(self) -> None:
        document = self.run_json("list")

        self.assertEqual(document["schema_version"], 2)
        self.assertEqual(document["command"], "list")
        self.assertEqual(document["data"], {"tasks": []})

    def test_a_task_carries_every_documented_key(self) -> None:
        task_id = self.added_id(
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
        )

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
        self.assertIsNone(task["reviewed_on"])
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
        self.assertEqual(document["data"]["snippet"], EXPECTED.rstrip("\n"))

    def test_an_expected_failure_writes_one_error_document_to_stderr(self) -> None:
        error = self.run_json_error("show", "T999")

        self.assertEqual(error["code"], "unknown_task")
        self.assertIn("T999", error["message"])

    def test_an_unsupported_format_version_reports_its_versions(self) -> None:
        path = self.root / "TODO.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "todo-format: 2", "todo-format: 3"
            ),
            encoding="utf-8",
        )

        error = self.run_json_error("validate")

        self.assertEqual(error["code"], "unsupported_format_version")
        self.assertEqual(error["encountered"], 3)
        self.assertEqual(error["supported"], [1, 2])

    def test_exactly_one_document_is_written(self) -> None:
        self.add_simple("Work")

        stdout = self.run_cli("--json", "list").stdout

        self.assertEqual(stdout.count("\n"), 1)
        self.assertTrue(stdout.endswith("\n"))


class MigrationTests(TodoCliTestCase):
    """Cover Task Data Format 1 dual-read and opt-in migrate."""

    def test_format_1_remains_readable(self) -> None:
        path = self.root / "TODO.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("todo-format: 2", "todo-format: 1"),
            encoding="utf-8",
        )
        result = self.run_cli("validate")
        self.assertEqual(result.stdout.strip(), "valid")

    def test_mutating_format_1_requires_migrate(self) -> None:
        path = self.root / "TODO.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("todo-format: 2", "todo-format: 1"),
            encoding="utf-8",
        )
        error = self.run_json_error("add", "Work", "--type", "chore", "--simple")
        self.assertEqual(error["code"], "migration_required")
        self.assertEqual(error["encountered"], 1)
        self.assertEqual(error["required"], 2)
        self.assertIn("todo-format: 1", path.read_text(encoding="utf-8"))

    def test_migrate_rewrites_format_1_to_2(self) -> None:
        path = self.root / "TODO.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace("todo-format: 2", "todo-format: 1"),
            encoding="utf-8",
        )
        document = self.run_json("migrate")
        self.assertEqual(document["command"], "migrate")
        self.assertEqual(document["data"]["from"], 1)
        self.assertEqual(document["data"]["to"], 2)
        self.assertIn("todo-format: 2", path.read_text(encoding="utf-8"))
        self.run_cli("add", "Work", "--type", "chore", "--simple")

    def test_migrate_on_format_2_is_a_successful_noop(self) -> None:
        document = self.run_json("migrate")
        self.assertEqual(document["data"]["from"], 2)
        self.assertEqual(document["data"]["to"], 2)

    def test_format_1_rejects_a_review_field(self) -> None:
        path = self.root / "TODO.md"
        body = path.read_text(encoding="utf-8").replace(
            "todo-format: 2", "todo-format: 1"
        )
        body = body.replace(
            "next-id: 1",
            "next-id: 2",
        )
        body = body.replace(
            "## P2 — Backlog\n",
            "## P2 — Backlog\n\n"
            "- [ ] **T001** Hand edited #chore #simple\n"
            "  - Review: 2026-08-17\n",
        )
        path.write_text(body, encoding="utf-8")
        error = self.run_json_error("validate")
        self.assertEqual(error["code"], "invalid_document")


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
        task_id = self.added_id(
            "Work",
            "--type",
            "chore",
            "--acceptance",
            "It works",
            "--context",
            "docs/a.md",
            "--related",
            "T000",
        )

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


class AggregateTestCase(unittest.TestCase):
    """Build an ordered two-repository collection for the --all selector."""

    def setUp(self) -> None:
        """
        Initialize the repositories alpha and beta and configure them in order.

        Side Effects:
            Creates a temporary directory holding both repositories and the
            configuration file naming them.
        """
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.directory = Path(self._temporary_directory.name).resolve()
        for name in ("alpha", "beta"):
            (self.directory / name).mkdir()
            self.run_in(name, "init", "--name", name)
        self.config = self.directory / "config.toml"
        self.write_config("alpha", "beta")

    def tearDown(self) -> None:
        """
        Remove both repositories and the configuration.

        Side Effects:
            Deletes the temporary directory and its contents.
        """
        self._temporary_directory.cleanup()

    def write_config(self, *names: str) -> None:
        """
        Rewrite the configuration over the named repositories, in order.

        Side Effects:
            Overwrites the configuration file.

        Args:
            *names: Directory names to configure, which need not exist.
        """
        entries = "".join(
            f'\n[[repositories]]\nname = "{name}"\npath = "{self.directory / name}"\n'
            for name in names
        )
        self.config.write_text(f"schema_version = 1\n{entries}", encoding="utf-8")

    def run_in(self, repo: str, *arguments: str) -> CliResult:
        """
        Run one command against a single repository by path.

        Side Effects:
            May update that repository's canonical task file.

        Args:
            repo: Directory name of the repository.
            *arguments: Command and command-specific arguments.

        Returns:
            Captured exit status and output.
        """
        result = invoke("--root", str(self.directory / repo), *arguments)
        if result.returncode != 0:
            raise AssertionError(f"setup failed ({result.returncode}): {result.stderr}")
        return result

    def add(self, repo: str, title: str, priority: str, *extra: str) -> str:
        """
        Add one simple chore to a repository and return its allocated ID.

        Side Effects:
            Updates that repository's canonical task file.

        Args:
            repo: Directory name of the repository.
            title: Task title.
            priority: Priority section for the task.
            *extra: Additional options for the add command.

        Returns:
            The allocated task ID.
        """
        result = self.run_in(
            repo,
            "add",
            title,
            "--priority",
            priority,
            "--type",
            "chore",
            "--simple",
            *extra,
        )
        return task_id_from_confirmation(result.stdout)

    def aggregate(self, *arguments: str) -> CliResult:
        """
        Run one aggregate query in human mode.

        Side Effects:
            Reads every configured repository.

        Args:
            *arguments: Command and command-specific arguments.

        Returns:
            Captured exit status and output.
        """
        return invoke("--config", str(self.config), "--all", *arguments)

    def aggregate_json(self, *arguments: str) -> dict[str, Any]:
        """
        Run one successful aggregate query and parse its data object.

        Side Effects:
            Reads every configured repository.

        Args:
            *arguments: Command and command-specific arguments.

        Returns:
            The parsed ``data`` object.
        """
        result = invoke("--json", "--config", str(self.config), "--all", *arguments)
        if result.returncode != 0:
            raise AssertionError(f"query failed ({result.returncode}): {result.stderr}")
        data: dict[str, Any] = json.loads(result.stdout)["data"]
        return data

    def provenance(self, tasks: list[dict[str, Any]]) -> list[tuple[str, str]]:
        """
        Reduce tasks to their Repository Name and task ID, in order.

        Args:
            tasks: JSON Task objects.

        Returns:
            One name and ID pair per task.
        """
        return [(task["repository"]["name"], task["id"]) for task in tasks]


class AggregateQueryTests(AggregateTestCase):
    """Cover --all ordering, provenance, and the two singular queries."""

    def test_list_orders_by_priority_then_collection_then_file(self) -> None:
        self.add("alpha", "alpha late", "P2")
        self.add("alpha", "alpha first", "P0")
        self.add("beta", "beta first", "P0")
        self.add("beta", "beta second", "P0")
        self.add("beta", "beta middle", "P1")

        tasks = self.aggregate_json("list")["tasks"]

        self.assertEqual(
            self.provenance(tasks),
            [
                ("alpha", "T002"),
                ("beta", "T001"),
                ("beta", "T002"),
                ("beta", "T003"),
                ("alpha", "T001"),
            ],
        )

    def test_every_task_carries_its_own_repository_provenance(self) -> None:
        self.add("alpha", "alpha work", "P0")
        self.add("beta", "beta work", "P0")

        tasks = self.aggregate_json("list")["tasks"]

        self.assertEqual(
            [task["repository"] for task in tasks],
            [
                {"name": "alpha", "path": str(self.directory / "alpha")},
                {"name": "beta", "path": str(self.directory / "beta")},
            ],
        )

    def test_human_rows_name_their_repository(self) -> None:
        self.add("alpha", "alpha work", "P0")
        self.add("beta", "beta work", "P1")

        result = self.aggregate("list")

        self.assertEqual(
            result.stdout.splitlines(),
            [
                "alpha",
                "T001 P0 alpha work #chore",
                "",
                "beta",
                "T001 P1 beta work #chore",
            ],
        )

    def test_human_list_groups_by_repository_while_json_stays_priority_first(
        self,
    ) -> None:
        self.add("alpha", "alpha late", "P2")
        self.add("beta", "beta first", "P0")

        result = self.aggregate("list")
        tasks = self.aggregate_json("list")["tasks"]

        self.assertEqual(self.provenance(tasks), [("beta", "T001"), ("alpha", "T001")])
        self.assertEqual(
            result.stdout.splitlines(),
            [
                "alpha",
                "T001 P2 alpha late #chore",
                "",
                "beta",
                "T001 P0 beta first #chore",
            ],
        )

    def test_all_list_prints_a_header_for_a_single_populated_repository(self) -> None:
        self.add("alpha", "alpha work", "P0")

        result = self.aggregate("list")

        self.assertEqual(
            result.stdout.splitlines(), ["alpha", "T001 P0 alpha work #chore"]
        )

    def test_all_list_omits_repositories_with_no_open_tasks(self) -> None:
        self.add("alpha", "alpha work", "P0")

        result = self.aggregate("list")

        self.assertEqual(
            result.stdout.splitlines(), ["alpha", "T001 P0 alpha work #chore"]
        )
        self.assertNotIn("beta", result.stdout.splitlines())

    def test_human_list_appends_user_tags(self) -> None:
        self.add("alpha", "alpha work", "P0", "--tag", "auth")

        listed = invoke("--config", str(self.config), "--repo", "alpha", "list")
        aggregated = self.aggregate("list")

        self.assertEqual(
            listed.stdout.splitlines(), ["T001 P0 alpha work #chore #auth"]
        )
        self.assertEqual(
            aggregated.stdout.splitlines(),
            ["alpha", "T001 P0 alpha work #chore #auth"],
        )
        self.assertNotIn("#simple", listed.stdout)

    def test_all_critical_keeps_a_prefixed_line_without_tags(self) -> None:
        self.add("alpha", "alpha work", "P0", "--tag", "auth")

        result = self.aggregate("critical")

        self.assertEqual(result.stdout.strip(), "alpha T001 P0 alpha work")
        self.assertNotIn("#auth", result.stdout)

    def test_all_critical_skips_review_tasks(self) -> None:
        self.add("alpha", "in review", "P0")
        self.add("beta", "still open", "P1")
        self.run_in("alpha", "review", "T001")

        result = self.aggregate("critical")

        self.assertEqual(result.stdout.strip(), "beta T001 P1 still open")

    def test_a_single_repository_row_keeps_no_provenance_prefix(self) -> None:
        self.add("alpha", "alpha work", "P0")

        result = invoke("--config", str(self.config), "--repo", "alpha", "list")

        self.assertEqual(result.stdout.splitlines(), ["T001 P0 alpha work #chore"])

    def test_critical_returns_a_claimed_task_that_actionable_skips(self) -> None:
        self.add("alpha", "alpha work", "P0")
        self.add("beta", "beta work", "P0")
        self.run_in("alpha", "claim", "T001", "--actor", "someone")

        critical = self.aggregate_json("critical")["task"]
        actionable = self.aggregate_json("actionable")["task"]

        self.assertEqual(self.provenance([critical]), [("alpha", "T001")])
        self.assertEqual(self.provenance([actionable]), [("beta", "T001")])

    def test_a_cancelled_blocker_still_blocks_across_the_collection(self) -> None:
        blocker = self.add("alpha", "alpha blocker", "P1")
        self.add("alpha", "alpha blocked", "P0", "--blocked-by", blocker)
        self.add("beta", "beta work", "P0")
        self.run_in("alpha", "cancel", blocker, "--reason", "obsolete")

        actionable = self.aggregate_json("actionable")["task"]

        self.assertEqual(self.provenance([actionable]), [("beta", "T001")])

    def test_empty_singular_queries_still_succeed(self) -> None:
        critical = self.aggregate_json("critical")
        result = self.aggregate("actionable")

        self.assertEqual(critical, {"task": None})
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "no actionable task")

    def test_an_empty_collection_succeeds_with_no_tasks(self) -> None:
        environment = {"XDG_CONFIG_HOME": str(self.directory / "absent")}

        with mock.patch.dict(os.environ, environment, clear=False):
            os.environ.pop(CONFIG_ENV_VAR, None)
            listed = invoke("--json", "--all", "list")
            critical = invoke("--json", "--all", "critical")
            human = invoke("--all", "list")

        self.assertEqual(json.loads(listed.stdout)["data"], {"tasks": []})
        self.assertEqual(json.loads(critical.stdout)["data"], {"task": None})
        self.assertEqual((human.returncode, human.stdout), (0, ""))


class AggregateFailureTests(AggregateTestCase):
    """Cover strict aggregate partial failure and its exit status."""

    def test_one_failed_repository_fails_the_whole_query(self) -> None:
        self.add("alpha", "alpha work", "P0")
        self.write_config("alpha", "gone")

        result = invoke("--json", "--config", str(self.config), "--all", "list")
        failures = json.loads(result.stderr)["error"]["failures"]

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "")
        self.assertEqual(
            json.loads(result.stderr)["error"]["code"], "aggregate_partial_failure"
        )
        self.assertEqual(
            [(one["name"], one["path"], one["code"]) for one in failures],
            [("gone", str(self.directory / "gone"), "repository_not_found")],
        )
        self.assertTrue(failures[0]["message"])

    def test_every_failure_is_listed_in_configuration_order(self) -> None:
        (self.directory / "bare").mkdir()
        self.write_config("gone", "alpha", "bare")

        result = invoke("--json", "--config", str(self.config), "--all", "critical")
        failures = json.loads(result.stderr)["error"]["failures"]

        self.assertEqual(result.returncode, 3)
        self.assertEqual(
            [(one["name"], one["code"]) for one in failures],
            [("gone", "repository_not_found"), ("bare", "not_initialized")],
        )

    def test_a_human_failure_names_the_failed_repositories(self) -> None:
        self.write_config("alpha", "gone")

        result = self.aggregate("list")

        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, "")
        self.assertIn("gone", result.stderr)

    def test_an_invalid_configuration_fails_before_any_repository_is_read(self) -> None:
        self.config.write_text("schema_version = 2\n", encoding="utf-8")

        result = invoke("--json", "--config", str(self.config), "--all", "list")

        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(result.stderr)["error"]["code"], "unsupported_config_version"
        )


class AggregateSelectorTests(AggregateTestCase):
    """Cover which commands and selector combinations --all accepts."""

    #: Commands the aggregate selector must reject.
    REJECTED = (
        ("add", "New", "--type", "chore", "--simple"),
        ("edit", "T001", "--title", "New"),
        ("claim", "T001", "--actor", "someone"),
        ("complete", "T001"),
        ("cancel", "T001", "--reason", "obsolete"),
        ("archive",),
        ("init", "--name", "Nope"),
        ("validate",),
        ("show", "T001"),
    )

    def test_all_rejects_every_command_outside_the_read_queries(self) -> None:
        for command in self.REJECTED:
            with self.subTest(command=command[0]):
                result = invoke(
                    "--json", "--config", str(self.config), "--all", *command
                )

                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)["error"]["code"], "usage")

    def test_all_conflicts_with_the_single_repository_selectors(self) -> None:
        conflicts = (("--root", str(self.directory / "alpha")), ("--repo", "alpha"))

        for selector in conflicts:
            with self.subTest(selector=selector[0]):
                result = invoke(
                    "--json", "--config", str(self.config), "--all", *selector, "list"
                )

                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)["error"]["code"], "usage")

    def test_config_is_accepted_alongside_all(self) -> None:
        self.add("alpha", "alpha work", "P0")

        tasks = self.aggregate_json("list")["tasks"]

        self.assertEqual(self.provenance(tasks), [("alpha", "T001")])

    def test_config_without_repo_or_all_is_still_a_usage_failure(self) -> None:
        result = invoke("--json", "--config", str(self.config), "list")

        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stderr)["error"]["code"], "usage")

    def test_the_environment_configuration_is_honored_for_all(self) -> None:
        self.add("beta", "beta work", "P1")
        environment = {CONFIG_ENV_VAR: str(self.config)}

        with mock.patch.dict(os.environ, environment, clear=False):
            result = invoke("--json", "--all", "list")

        tasks = json.loads(result.stdout)["data"]["tasks"]
        self.assertEqual(self.provenance(tasks), [("beta", "T001")])


if __name__ == "__main__":
    unittest.main()
