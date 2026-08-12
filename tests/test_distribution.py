"""Verify that a built wheel installs and runs outside this checkout."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

#: Repository checkout holding the build inputs.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
#: Resolved ``uv`` executable, or ``None`` when it is unavailable.
UV = shutil.which("uv")


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
            self._run(
                [
                    str(executable),
                    "--root",
                    str(repository),
                    "init",
                    "--name",
                    "Demo",
                ]
            )
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

            self.assertIn("bot-todo", version)
            self.assertIn("Installed task", listed)
            self.assertTrue((repository / "TODO.md").exists())

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
