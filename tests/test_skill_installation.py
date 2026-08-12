"""Exercise bundled skill installation through the public command line."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from bot_todo.skill_installation import (
    MANIFEST_NAME,
    TARGET_ASSETS,
    TARGET_ROOTS,
    SkillAssets,
)
from tests.support import invoke


class SkillInstallationTestCase(unittest.TestCase):
    """Install the packaged skill into disposable roots only."""

    def setUp(self) -> None:
        """
        Create an isolated Skill Root for each test.

        Side Effects:
            Creates a temporary directory.
        """
        self._temporary_directory = tempfile.TemporaryDirectory()
        self.base = Path(self._temporary_directory.name).resolve()
        self.root = self.base / "skills"
        self.skill = self.root / "todo"

    def tearDown(self) -> None:
        """
        Remove the isolated Skill Root.

        Side Effects:
            Deletes the temporary directory and its contents.
        """
        self._temporary_directory.cleanup()

    def install(self, *arguments: str, target: str = "codex") -> dict[str, Any]:
        """
        Install one target successfully and return its ``data`` object.

        Args:
            *arguments: Extra ``install-skill`` options.

        Keyword Args:
            target: Skill Target to install.

        Returns:
            The parsed success ``data`` object.
        """
        result = invoke(
            "--json",
            "install-skill",
            "--target",
            target,
            "--destination",
            str(self.root),
            *arguments,
        )
        if result.returncode != 0:
            raise AssertionError(f"install failed: {result.stderr}")
        document: dict[str, Any] = json.loads(result.stdout)
        data: dict[str, Any] = document["data"]
        return data

    def failure(self, *arguments: str, target: str = "codex") -> dict[str, Any]:
        """
        Run a failing installation and return its exit status and error.

        Args:
            *arguments: Extra ``install-skill`` options.

        Keyword Args:
            target: Skill Target to install.

        Returns:
            The parsed error object with its ``exit`` status added.
        """
        result = invoke(
            "--json",
            "install-skill",
            "--target",
            target,
            "--destination",
            str(self.root),
            *arguments,
        )
        if result.returncode == 0:
            raise AssertionError("installation unexpectedly succeeded")
        if result.stdout:
            raise AssertionError(f"failure wrote stdout: {result.stdout!r}")
        error: dict[str, Any] = json.loads(result.stderr)["error"]
        error["exit"] = result.returncode
        return error

    def view(self, target: str = "codex") -> dict[str, bytes]:
        """
        Read the packaged asset view for one target.

        Args:
            target: Skill Target selecting the view.

        Returns:
            Each relative asset path mapped to its bytes.
        """
        return SkillAssets().view(target)

    def snapshot(self, tree: Path) -> dict[str, bytes]:
        """
        Capture every regular file under a tree.

        Args:
            tree: Directory to capture.

        Returns:
            Relative POSIX paths mapped to file bytes.
        """
        return {
            str(path.relative_to(tree).as_posix()): path.read_bytes()
            for path in sorted(tree.rglob("*"))
            if path.is_file()
        }

    def manifest(self) -> dict[str, Any]:
        """
        Read the installed ownership manifest.

        Returns:
            The parsed manifest document.
        """
        document: dict[str, Any] = json.loads(
            (self.skill / MANIFEST_NAME).read_text(encoding="utf-8")
        )
        return document

    def write_manifest(self, document: dict[str, Any]) -> None:
        """
        Overwrite the installed ownership manifest.

        Side Effects:
            Rewrites the manifest file.

        Args:
            document: Manifest document to write.
        """
        (self.skill / MANIFEST_NAME).write_text(json.dumps(document), encoding="utf-8")


class TargetViewTests(SkillInstallationTestCase):
    """Install exactly the assets each Skill Target receives."""

    def test_codex_receives_both_assets_byte_for_byte(self) -> None:
        data = self.install(target="codex")

        self.assertEqual(data["action"], "install")
        self.assertEqual(
            self.snapshot(self.skill),
            {
                **self.view("codex"),
                MANIFEST_NAME: (self.skill / MANIFEST_NAME).read_bytes(),
            },
        )

    def test_other_targets_receive_only_the_portable_skill(self) -> None:
        for target in ("claude", "cursor", "grok"):
            with self.subTest(target=target):
                self.root = self.base / target
                self.skill = self.root / "todo"

                self.install(target=target)

                self.assertEqual(
                    (self.skill / "SKILL.md").read_bytes(),
                    self.view(target)["SKILL.md"],
                )
                self.assertFalse((self.skill / "agents").exists())

    def test_the_manifest_records_every_managed_asset(self) -> None:
        self.install()

        document = self.manifest()
        self.assertEqual(document["schema_version"], 1)
        self.assertEqual(document["target"], "codex")
        self.assertEqual(sorted(document["assets"]), sorted(TARGET_ASSETS["codex"]))
        self.assertNotIn(MANIFEST_NAME, document["assets"])
        self.assertIn("package_version", document)


class ReconciliationActionTests(SkillInstallationTestCase):
    """Classify exactly one action per invocation."""

    def test_installation_creates_missing_root_parents(self) -> None:
        self.root = self.base / "nested" / "deeper" / "skills"
        self.skill = self.root / "todo"

        data = self.install()

        self.assertEqual(data["action"], "install")
        self.assertEqual(data["skill_path"], str(self.skill))
        self.assertTrue(self.skill.is_dir())

    def test_a_second_run_is_a_noop(self) -> None:
        self.install()
        before = self.snapshot(self.skill)

        data = self.install()

        self.assertEqual(data["action"], "noop")
        self.assertEqual(self.snapshot(self.skill), before)

    def test_a_stale_managed_tree_updates(self) -> None:
        self.install()
        stale = b"stale skill content\n"
        (self.skill / "SKILL.md").write_bytes(stale)
        document = self.manifest()
        document["assets"]["SKILL.md"] = hashlib.sha256(stale).hexdigest()
        self.write_manifest(document)

        data = self.install()

        self.assertEqual(data["action"], "update")
        self.assertEqual(
            (self.skill / "SKILL.md").read_bytes(), self.view()["SKILL.md"]
        )

    def test_an_identical_unmarked_tree_is_adopted(self) -> None:
        for name, content in self.view().items():
            asset = self.skill.joinpath(*name.split("/"))
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(content)

        data = self.install()

        self.assertEqual(data["action"], "adopt")
        self.assertEqual(self.manifest()["target"], "codex")
        self.assertEqual(
            (self.skill / "SKILL.md").read_bytes(), self.view()["SKILL.md"]
        )


class ConflictTests(SkillInstallationTestCase):
    """Refuse to touch anything this installer does not own."""

    def corrupt(self, kind: str) -> None:
        """
        Put the Skill Root into one conflicting state.

        Side Effects:
            Creates or modifies the installed tree.

        Args:
            kind: Conflict to create.
        """
        if kind == "symlink":
            self.root.mkdir(parents=True)
            (self.base / "elsewhere").mkdir()
            (self.base / "elsewhere" / "keep.md").write_bytes(b"keep\n")
            os.symlink(self.base / "elsewhere", self.skill)
            return
        if kind == "regular_file":
            self.root.mkdir(parents=True)
            self.skill.write_bytes(b"not a directory\n")
            return
        if kind == "unmanaged":
            self.skill.mkdir(parents=True)
            (self.skill / "SKILL.md").write_bytes(b"someone else's skill\n")
            return
        self.install()
        if kind == "extra_file":
            (self.skill / "notes.md").write_bytes(b"extra\n")
        elif kind == "missing_file":
            (self.skill / "agents" / "openai.yaml").unlink()
        elif kind == "modified_file":
            (self.skill / "SKILL.md").write_bytes(b"edited\n")
        elif kind == "malformed_manifest":
            (self.skill / MANIFEST_NAME).write_bytes(b"{not json")
        elif kind == "unknown_manifest_schema":
            document = self.manifest()
            document["schema_version"] = 2
            self.write_manifest(document)
        elif kind == "target_mismatch":
            document = self.manifest()
            document["target"] = "grok"
            self.write_manifest(document)
        else:
            raise AssertionError(f"unknown conflict {kind}")

    def test_every_conflict_fails_without_changing_anything(self) -> None:
        kinds = (
            "symlink",
            "regular_file",
            "unmanaged",
            "extra_file",
            "missing_file",
            "modified_file",
            "malformed_manifest",
            "unknown_manifest_schema",
            "target_mismatch",
        )
        for kind in kinds:
            with self.subTest(conflict=kind):
                self.root = self.base / kind
                self.skill = self.root / "todo"
                self.corrupt(kind)
                before = self.snapshot(self.root)

                error = self.failure()

                self.assertEqual(error["code"], "conflict")
                self.assertEqual(error["exit"], 1)
                self.assertEqual(self.snapshot(self.root), before)
                self.assertEqual([path.name for path in self.root.iterdir()], ["todo"])

    def test_a_target_mismatch_conflicts_across_targets(self) -> None:
        self.install(target="claude")

        error = self.failure(target="cursor")

        self.assertEqual(error["code"], "conflict")

    def test_a_skill_root_that_is_a_file_is_an_io_error(self) -> None:
        self.root.write_bytes(b"occupied\n")

        error = self.failure()

        self.assertEqual(error["code"], "io_error")
        self.assertEqual(error["exit"], 1)


class ForcedReplacementTests(SkillInstallationTestCase):
    """Replace conflicts only when explicitly authorized."""

    def test_a_conflict_is_replaced_and_backed_up(self) -> None:
        self.install()
        (self.skill / "SKILL.md").write_bytes(b"edited\n")

        data = self.install("--force")

        self.assertEqual(data["action"], "replace")
        backup = Path(data["backup_path"])
        self.assertTrue(backup.name.startswith("todo.backup-"))
        self.assertEqual((backup / "SKILL.md").read_bytes(), b"edited\n")
        self.assertEqual(
            (self.skill / "SKILL.md").read_bytes(), self.view()["SKILL.md"]
        )

    def test_a_symlink_is_backed_up_without_touching_its_target(self) -> None:
        self.root.mkdir(parents=True)
        target = self.base / "elsewhere"
        target.mkdir()
        (target / "keep.md").write_bytes(b"keep\n")
        os.symlink(target, self.skill)

        data = self.install("--force")

        backup = Path(data["backup_path"])
        self.assertEqual(data["action"], "replace")
        self.assertTrue(backup.is_symlink())
        self.assertFalse(self.skill.is_symlink())
        self.assertEqual(sorted(path.name for path in target.iterdir()), ["keep.md"])
        self.assertEqual((target / "keep.md").read_bytes(), b"keep\n")

    def test_force_does_not_replace_a_clean_tree(self) -> None:
        self.install()

        data = self.install("--force")

        self.assertEqual(data["action"], "noop")
        self.assertIsNone(data["backup_path"])
        self.assertEqual([path.name for path in self.root.iterdir()], ["todo"])


class DryRunTests(SkillInstallationTestCase):
    """Classify without mutating the filesystem."""

    def test_a_dry_installation_creates_nothing(self) -> None:
        data = self.install("--dry-run")

        self.assertEqual(data["action"], "install")
        self.assertTrue(data["dry_run"])
        self.assertFalse(self.root.exists())

    def test_a_dry_run_still_fails_on_a_conflict(self) -> None:
        self.install()
        (self.skill / "SKILL.md").write_bytes(b"edited\n")

        error = self.failure("--dry-run")

        self.assertEqual(error["code"], "conflict")

    def test_a_dry_forced_replacement_reports_no_backup(self) -> None:
        self.install()
        (self.skill / "SKILL.md").write_bytes(b"edited\n")
        before = self.snapshot(self.root)

        data = self.install("--dry-run", "--force")

        self.assertEqual(data["action"], "replace")
        self.assertIsNone(data["backup_path"])
        self.assertEqual(self.snapshot(self.root), before)


class SkillRootTests(SkillInstallationTestCase):
    """Resolve Skill Roots per target and per override."""

    def test_each_target_defaults_to_its_own_user_root(self) -> None:
        home = self.base / "home"
        home.mkdir()
        environment = {"HOME": str(home), "USERPROFILE": str(home)}
        for target, default in TARGET_ROOTS.items():
            with self.subTest(target=target), mock.patch.dict(os.environ, environment):
                result = invoke(
                    "--json", "install-skill", "--target", target, "--dry-run"
                )

                self.assertEqual(result.returncode, 0)
                data = json.loads(result.stdout)["data"]
                expected = Path(default.replace("~", str(home))).resolve()
                self.assertEqual(data["skill_root"], str(expected))
                self.assertEqual(data["skill_path"], str(expected / "todo"))
                self.assertFalse(expected.exists())

    def test_the_destination_replaces_the_root_but_not_the_skill_name(self) -> None:
        data = self.install()

        self.assertEqual(data["skill_root"], str(self.root))
        self.assertEqual(data["skill_path"], str(self.root / "todo"))

    def test_the_success_document_carries_exactly_the_settled_keys(self) -> None:
        data = self.install()

        self.assertEqual(
            sorted(data),
            [
                "action",
                "backup_path",
                "dry_run",
                "skill_path",
                "skill_root",
                "target",
            ],
        )


class UsageTests(SkillInstallationTestCase):
    """Reject selector and target misuse before touching the filesystem."""

    def test_a_missing_or_unknown_target_is_a_usage_failure(self) -> None:
        for arguments in (("install-skill",), ("install-skill", "--target", "vim")):
            with self.subTest(arguments=arguments):
                result = invoke("--json", *arguments)

                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)["error"]["code"], "usage")

    def test_no_repository_selector_is_accepted(self) -> None:
        selectors = (
            ("--root", "."),
            ("--repo", "demo"),
            ("--all",),
            ("--config", "config.toml"),
        )
        for selector in selectors:
            with self.subTest(selector=selector):
                result = invoke(
                    "--json",
                    *selector,
                    "install-skill",
                    "--target",
                    "codex",
                    "--destination",
                    str(self.root),
                    "--dry-run",
                )

                self.assertEqual(result.returncode, 2)
                self.assertEqual(json.loads(result.stderr)["error"]["code"], "usage")
                self.assertFalse(self.root.exists())


if __name__ == "__main__":
    unittest.main()
