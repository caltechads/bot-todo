"""Install the packaged todo skill into one Skill Target's Skill Root."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from bot_todo import package_version
from bot_todo.repository import TodoError

#: Package directory holding the canonical skill tree.
ASSET_DIRECTORY = "skill_assets"
#: Installed skill directory name under any Skill Root.
SKILL_DIRECTORY = "todo"
#: Ownership manifest filename inside a Managed Skill Installation.
MANIFEST_NAME = ".bot-todo-install.json"
#: Manifest schema version this release writes and accepts.
MANIFEST_SCHEMA_VERSION = 1
#: Default Skill Root per Skill Target.
TARGET_ROOTS = {
    "codex": "~/.agents/skills",
    "claude": "~/.claude/skills",
    "cursor": "~/.cursor/skills",
    "grok": "~/.grok/skills",
}
#: Packaged asset paths each Skill Target receives.
TARGET_ASSETS = {
    "codex": ("SKILL.md", "agents/openai.yaml"),
    "claude": ("SKILL.md",),
    "cursor": ("SKILL.md",),
    "grok": ("SKILL.md",),
}


def _digest(data: bytes) -> str:
    """
    Digest one asset's bytes.

    Args:
        data: Asset content.

    Returns:
        Hexadecimal SHA-256 digest.

    """
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class InstallationResult:
    """
    Report what one ``install-skill`` invocation classified and performed.

    Args:
        target: Selected Skill Target.
        skill_root: Resolved Skill Root.
        skill_path: Resolved installed skill path.
        action: Reconciliation Action that was classified.
        dry_run: Whether the filesystem was deliberately left untouched.
        backup_path: Retained forced-replacement backup, or ``None``.

    """

    #: Selected Skill Target.
    target: str
    #: Resolved Skill Root.
    skill_root: Path
    #: Resolved installed skill path.
    skill_path: Path
    #: Reconciliation Action that was classified.
    action: str
    #: Whether the filesystem was deliberately left untouched.
    dry_run: bool
    #: Retained forced-replacement backup, or ``None``.
    backup_path: Path | None


class SkillAssets:
    """
    Read the packaged todo skill as bytes for one Skill Target.

    Assets are located through ``importlib.resources`` so an installed wheel
    works without a source checkout, and are read eagerly because whole
    directory materialization is unavailable before Python 3.12.

    """

    def view(self, target: str) -> dict[str, bytes]:
        """
        Read the asset view one Skill Target receives.

        Side Effects:
            Reads the packaged skill assets.

        Args:
            target: Skill Target selecting the view.

        Returns:
            Each relative asset path mapped to its exact bytes.

        """
        root = files("bot_todo").joinpath(ASSET_DIRECTORY).joinpath(SKILL_DIRECTORY)
        view = {}
        for name in TARGET_ASSETS[target]:
            resource = root
            for part in name.split("/"):
                resource = resource.joinpath(part)
            view[name] = resource.read_bytes()
        return view


class SkillInstaller:
    """
    Reconcile one Skill Root with the packaged todo skill.

    Every invocation classifies exactly one Reconciliation Action and either
    performs it through a staged sibling tree or reports a ``conflict``.

    Args:
        target: Skill Target to install.
        destination: Skill Root replacing the target default, if any.

    Keyword Args:
        dry_run: Whether to classify without touching the filesystem.
        force: Whether a conflict may be replaced from a retained backup.

    """

    def __init__(
        self,
        target: str,
        destination: Path | None,
        *,
        dry_run: bool,
        force: bool,
    ) -> None:
        """
        Initialize an installer over one requested installation.

        Args:
            target: Skill Target to install.
            destination: Skill Root replacing the target default, if any.

        Keyword Args:
            dry_run: Whether to classify without touching the filesystem.
            force: Whether a conflict may be replaced from a retained backup.

        """
        #: Skill Target to install.
        self.target = target
        #: Skill Root replacing the target default, if any.
        self.destination = destination
        #: Whether to classify without touching the filesystem.
        self.dry_run = dry_run
        #: Whether a conflict may be replaced from a retained backup.
        self.force = force

    def run(self) -> InstallationResult:
        """
        Classify and, unless this is a dry run, perform the installation.

        Side Effects:
            Creates, updates, replaces, or backs up an installed skill tree.

        Returns:
            Classified action and the paths it applied to.

        Raises:
            TodoError: If the Skill Root is unusable or an unforced conflict
                exists.

        """
        view = SkillAssets().view(self.target)
        root = self._root()
        skill_path = root / SKILL_DIRECTORY
        action = self._classify(skill_path, view)
        backup = None
        if not self.dry_run:
            backup = self._commit(root, skill_path, view, action)
        return InstallationResult(
            target=self.target,
            skill_root=root,
            skill_path=skill_path,
            action=action,
            dry_run=self.dry_run,
            backup_path=backup,
        )

    def _root(self) -> Path:
        """
        Resolve the Skill Root without creating it.

        Returns:
            Absolute Skill Root path, which need not exist yet.

        Raises:
            TodoError: If the Skill Root exists but is not a directory.

        """
        requested = self.destination or Path(TARGET_ROOTS[self.target])
        root = requested.expanduser().resolve()
        if os.path.lexists(root) and not root.is_dir():
            raise TodoError(f"skill root {root} is not a directory", "io_error")
        return root

    def _classify(self, skill_path: Path, view: dict[str, bytes]) -> str:
        """
        Decide the single Reconciliation Action this invocation performs.

        Side Effects:
            Reads the existing installed tree.

        Args:
            skill_path: Installed skill path.
            view: Packaged asset view for the selected target.

        Returns:
            One of ``install``, ``adopt``, ``update``, ``noop``, ``replace``.

        Raises:
            TodoError: If the path conflicts and ``--force`` was not given.

        """
        if not os.path.lexists(skill_path):
            return "install"
        tree = self._scan(skill_path)
        action = None if tree is None else self._reconcile(skill_path, tree, view)
        if action is not None:
            return action
        if self.force:
            return "replace"
        raise TodoError(
            f"{skill_path} is not a clean managed todo skill installation",
            "conflict",
        )

    def _scan(self, tree: Path) -> dict[str, str] | None:
        """
        Digest every regular file in a tree without following links.

        Side Effects:
            Reads the tree's files.

        Args:
            tree: Directory to inspect.

        Returns:
            Relative paths mapped to digests, or ``None`` when the tree is not
            a plain directory of regular files.

        """
        if os.path.islink(tree) or not os.path.isdir(tree):
            return None
        found: dict[str, str] = {}
        pending = [(tree, "")]
        while pending:
            directory, prefix = pending.pop()
            with os.scandir(directory) as entries:
                for entry in entries:
                    relative = f"{prefix}{entry.name}"
                    if entry.is_symlink():
                        return None
                    if entry.is_dir(follow_symlinks=False):
                        pending.append((Path(entry.path), f"{relative}/"))
                    elif entry.is_file(follow_symlinks=False):
                        found[relative] = _digest(Path(entry.path).read_bytes())
                    else:
                        return None
        return found

    def _reconcile(
        self, skill_path: Path, tree: dict[str, str], view: dict[str, bytes]
    ) -> str | None:
        """
        Compare a scanned tree against its manifest and the packaged view.

        Side Effects:
            Reads the ownership manifest.

        Args:
            skill_path: Installed skill path.
            tree: Scanned digests including any manifest.
            view: Packaged asset view for the selected target.

        Returns:
            ``adopt``, ``noop``, or ``update``, or ``None`` when the tree
            conflicts.

        """
        wanted = {name: _digest(data) for name, data in view.items()}
        managed = {name: value for name, value in tree.items() if name != MANIFEST_NAME}
        if MANIFEST_NAME not in tree:
            return "adopt" if managed == wanted else None
        recorded = self._recorded(skill_path / MANIFEST_NAME)
        if recorded is None or managed != recorded:
            return None
        return "noop" if recorded == wanted else "update"

    def _recorded(self, manifest: Path) -> dict[str, str] | None:
        """
        Read the managed asset digests one manifest records.

        Side Effects:
            Reads the manifest file.

        Args:
            manifest: Manifest path.

        Returns:
            Recorded relative paths mapped to digests, or ``None`` when the
            manifest is malformed, versioned differently, or written for
            another Skill Target.

        """
        try:
            document = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(document, dict):
            return None
        if document.get("schema_version") != MANIFEST_SCHEMA_VERSION:
            return None
        if document.get("target") != self.target:
            return None
        assets = document.get("assets")
        if not isinstance(assets, dict):
            return None
        if not all(
            isinstance(name, str) and isinstance(value, str)
            for name, value in assets.items()
        ):
            return None
        return dict(assets)

    def _manifest(self, view: dict[str, bytes]) -> bytes:
        """
        Render the ownership manifest for one asset view.

        Args:
            view: Packaged asset view for the selected target.

        Returns:
            Manifest bytes, which never record the manifest itself.

        """
        document = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "target": self.target,
            "package_version": package_version(),
            "assets": {name: _digest(data) for name, data in view.items()},
        }
        return json.dumps(document, indent=2, sort_keys=True).encode("utf-8") + b"\n"

    def _commit(
        self, root: Path, skill_path: Path, view: dict[str, bytes], action: str
    ) -> Path | None:
        """
        Perform one classified action through a staged sibling tree.

        Side Effects:
            Creates the Skill Root and writes, moves, or backs up trees.

        Args:
            root: Resolved Skill Root.
            skill_path: Installed skill path.
            view: Packaged asset view for the selected target.
            action: Classified Reconciliation Action.

        Returns:
            Retained forced-replacement backup path, or ``None``.

        Raises:
            TodoError: If staging fails validation or the commit races.

        """
        if action == "noop":
            return None
        if action == "adopt":
            self._adopt(skill_path, view)
            return None
        root.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix="todo.staging-", dir=root))
        try:
            self._materialize(staging, view)
            if action == "replace":
                return self._replace(root, skill_path, staging)
            if action == "update":
                self._update(root, skill_path, staging)
            else:
                self._install(skill_path, staging)
            return None
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _materialize(self, staging: Path, view: dict[str, bytes]) -> None:
        """
        Write and validate the complete new tree in the staging path.

        Side Effects:
            Writes the asset view and manifest into the staging path.

        Args:
            staging: Unique staging sibling.
            view: Packaged asset view for the selected target.

        Raises:
            TodoError: If the staged tree does not match the asset view.

        """
        staging.chmod(0o755)
        for name, data in view.items():
            asset = staging.joinpath(*name.split("/"))
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_bytes(data)
        manifest = self._manifest(view)
        (staging / MANIFEST_NAME).write_bytes(manifest)
        wanted = {name: _digest(data) for name, data in view.items()}
        wanted[MANIFEST_NAME] = _digest(manifest)
        if self._scan(staging) != wanted:
            raise TodoError("staged skill tree failed validation", "io_error")

    def _install(self, skill_path: Path, staging: Path) -> None:
        """
        Commit a staged tree where no skill directory exists.

        Side Effects:
            Renames the staged tree into place.

        Args:
            skill_path: Installed skill path.
            staging: Validated staging sibling.

        Raises:
            TodoError: If something occupied the path during staging.

        """
        if os.path.lexists(skill_path):
            raise TodoError(f"{skill_path} appeared during installation", "conflict")
        os.rename(staging, skill_path)

    def _update(self, root: Path, skill_path: Path, staging: Path) -> None:
        """
        Replace a clean Managed Skill Installation, restoring it on failure.

        Side Effects:
            Moves the existing tree aside and the staged tree into place.

        Args:
            root: Resolved Skill Root.
            skill_path: Installed skill path.
            staging: Validated staging sibling.

        Raises:
            TodoError: If the commit fails after the old tree moved aside.

        """
        rollback = Path(tempfile.mkdtemp(prefix=".todo.rollback-", dir=root))
        previous = rollback / SKILL_DIRECTORY
        os.rename(skill_path, previous)
        try:
            os.rename(staging, skill_path)
        except OSError as error:
            os.rename(previous, skill_path)
            raise TodoError(
                f"could not update {skill_path}: {error}", "io_error"
            ) from error
        shutil.rmtree(rollback, ignore_errors=True)

    def _replace(self, root: Path, skill_path: Path, staging: Path) -> Path:
        """
        Replace a conflicting entry, retaining it as a timestamped backup.

        The existing entry itself is moved, so a symlink is preserved as a
        symlink and its target is never traversed or modified.

        Side Effects:
            Moves the existing entry to a backup and commits the staged tree.

        Args:
            root: Resolved Skill Root.
            skill_path: Installed skill path.
            staging: Validated staging sibling.

        Returns:
            Retained backup path.

        Raises:
            TodoError: If the commit fails after the backup was taken.

        """
        stamp = datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S")
        backup = Path(
            tempfile.mkdtemp(prefix=f"{SKILL_DIRECTORY}.backup-{stamp}-", dir=root)
        )
        backup.rmdir()
        os.rename(skill_path, backup)
        try:
            os.rename(staging, skill_path)
        except OSError as error:
            os.rename(backup, skill_path)
            raise TodoError(
                f"could not replace {skill_path}: {error}", "io_error"
            ) from error
        return backup

    def _adopt(self, skill_path: Path, view: dict[str, bytes]) -> None:
        """
        Mark an unmanaged but identical tree as managed.

        Side Effects:
            Writes the ownership manifest into the existing tree.

        Args:
            skill_path: Installed skill path.
            view: Packaged asset view for the selected target.

        Raises:
            TodoError: If the tree changed after classification.

        """
        wanted = {name: _digest(data) for name, data in view.items()}
        if self._scan(skill_path) != wanted:
            raise TodoError(f"{skill_path} changed during adoption", "conflict")
        handle, temporary = tempfile.mkstemp(
            prefix=".bot-todo-install-", dir=skill_path
        )
        with os.fdopen(handle, "wb") as stream:
            stream.write(self._manifest(view))
        os.chmod(temporary, 0o644)
        os.replace(temporary, skill_path / MANIFEST_NAME)
