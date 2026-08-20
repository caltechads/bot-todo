"""Verify that a built wheel installs and runs outside this checkout."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path

#: Repository checkout holding the build inputs.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
#: Resolved ``uv`` executable, or ``None`` when it is unavailable.
UV = shutil.which("uv")
#: Canonical skill assets every distribution must carry.
SKILL_ASSETS = {"SKILL.md", "agents/openai.yaml"}


@unittest.skipUnless(UV, "requires the uv build front end")
class WheelSmokeTests(unittest.TestCase):
    """Build, install, and exercise the distribution in a disposable venv."""

    def test_the_installed_executable_runs_outside_the_checkout(self) -> None:
        assert UV is not None
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            wheel = self._build(workspace / "dist")
            executable = self._install(UV, wheel, workspace / "venv")
            repository = workspace / "demo"
            repository.mkdir()

            version = self._run([str(executable), "--version"])
            web_help = self._run([str(executable), "web", "--help"])
            self._run([str(executable), "--root", str(repository), "init"])
            self._run(
                [
                    str(executable),
                    "--root",
                    str(repository),
                    "add",
                    "Installed task",
                    "--type",
                    "chore",
                    "--simple",
                ]
            )
            listed = self._run([str(executable), "--root", str(repository), "list"])
            config = workspace / "config.toml"
            config.write_text(
                "schema_version = 1\n\n"
                f'[[repositories]]\nname = "demo"\npath = "{repository}"\n',
                encoding="utf-8",
            )
            aggregated = self._run(
                [str(executable), "--config", str(config), "--all", "list"]
            )

            self.assertIn("bot-todo", version)
            self.assertIn("--port", web_help)
            self.assertIn("--no-open", web_help)
            self.assertIn("Installed task", listed)
            self.assertEqual(aggregated.strip(), "demo\nT001 P2 Installed task #chore")
            self.assertTrue((repository / "TODO.md").exists())

    def test_the_packaged_skill_ships_and_installs_from_a_wheel(self) -> None:
        assert UV is not None
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            wheel, sdist = self._build_both(workspace / "dist")
            executable = self._install(UV, wheel, workspace / "venv")
            root = workspace / "skills"

            reported = self._run(
                [
                    str(executable),
                    "install-skill",
                    "--target",
                    "codex",
                    "--destination",
                    str(root),
                ]
            )

            self.assertEqual(self._skill_assets(wheel), SKILL_ASSETS)
            self.assertEqual(self._skill_assets(sdist), SKILL_ASSETS)
            self.assertIn("install", reported)
            for name in SKILL_ASSETS:
                packaged = PROJECT_ROOT / "src" / "bot_todo" / "skill_assets" / "todo"
                self.assertEqual(
                    (root / "todo" / name).read_bytes(),
                    (packaged / name).read_bytes(),
                )
            self.assertTrue((root / "todo" / ".bot-todo-install.json").exists())

    def _build_both(self, destination: Path) -> tuple[Path, Path]:
        """
        Build a wheel and a source distribution from this checkout.

        Side Effects:
            Writes distribution artifacts into ``destination``.

        Args:
            destination: Directory receiving the built artifacts.

        Returns:
            Paths to the built wheel and source distribution.

        """
        assert UV is not None
        self._run([UV, "build", "--out-dir", str(destination)], cwd=PROJECT_ROOT)
        wheels = sorted(destination.glob("bot_todo-*.whl"))
        archives = sorted(destination.glob("bot_todo-*.tar.gz"))
        self.assertEqual(len(wheels), 1)
        self.assertEqual(len(archives), 1)
        return wheels[0], archives[0]

    def _skill_assets(self, archive: Path) -> set[str]:
        """
        List the packaged skill assets one distribution carries.

        Side Effects:
            Reads the archive.

        Args:
            archive: Wheel or source distribution to inspect.

        Returns:
            Relative asset paths below the canonical skill directory.

        """
        if archive.suffix == ".whl":
            with zipfile.ZipFile(archive) as wheel:
                names = [
                    item.filename for item in wheel.infolist() if not item.is_dir()
                ]
        else:
            with tarfile.open(archive) as source:
                names = [item.name for item in source.getmembers() if item.isfile()]
        marker = "bot_todo/skill_assets/todo/"
        return {name.split(marker, 1)[1] for name in names if marker in name}

    def _build(self, destination: Path) -> Path:
        """
        Build a wheel from this checkout.

        Side Effects:
            Writes distribution artifacts into ``destination``.

        Args:
            destination: Directory receiving the built wheel.

        Returns:
            Path to the built wheel.

        """
        assert UV is not None
        self._run(
            [UV, "build", "--wheel", "--out-dir", str(destination)], cwd=PROJECT_ROOT
        )
        wheels = sorted(destination.glob("bot_todo-*.whl"))
        self.assertEqual(len(wheels), 1)
        return wheels[0]

    def _install(self, uv: str, wheel: Path, venv: Path) -> Path:
        """
        Install one wheel into a disposable virtual environment.

        Side Effects:
            Creates a virtual environment and installs the wheel into it.

        Args:
            uv: Path to the ``uv`` executable.
            wheel: Wheel to install.
            venv: Directory receiving the virtual environment.

        Returns:
            Path to the installed console script.

        """
        self._run([uv, "venv", "--python", sys.executable, str(venv)])
        self._run([uv, "pip", "install", "--python", str(venv), str(wheel)])
        scripts = "Scripts" if sys.platform == "win32" else "bin"
        suffix = ".exe" if sys.platform == "win32" else ""
        executable = venv / scripts / f"bot-todo{suffix}"
        self.assertTrue(executable.exists())
        return executable

    def _run(self, command: list[str], cwd: Path | None = None) -> str:
        """
        Run one command and return its standard output.

        Side Effects:
            Executes an external process.

        Args:
            command: Command and arguments.
            cwd: Working directory for the process.

        Returns:
            Captured standard output.

        """
        result = subprocess.run(
            command, cwd=cwd, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            message = f"{command} failed ({result.returncode}): {result.stderr}"
            raise AssertionError(message)
        return result.stdout


if __name__ == "__main__":
    unittest.main()
