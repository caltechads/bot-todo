"""Load and validate the Repository Collection configuration file."""

from __future__ import annotations

import os
import re
import stat
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from bot_todo.repository import LOCK_TIMEOUT_SECONDS, RepositoryLock, TodoError

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

#: Configuration schema versions this release understands.
SUPPORTED_CONFIG_VERSIONS = (1,)
#: Environment variable naming an explicit configuration file.
CONFIG_ENV_VAR = "BOT_TODO_CONFIG"
#: Directory holding the configuration file under a platform config root.
CONFIG_DIRECTORY = "bot-todo"
#: Configuration filename within that directory.
CONFIG_FILENAME = "config.toml"
#: Only top-level keys a valid configuration may declare.
TOP_LEVEL_KEYS = frozenset({"schema_version", "repositories"})
#: Only keys one Repository Entry may declare.
ENTRY_KEYS = frozenset({"name", "path"})
#: Valid Repository Name grammar.
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True)
class RepositoryEntry:
    """
    Name one prospective or existing Task Repository.

    Args:
        name: Unique lowercase Repository Name.
        path: Resolved repository path, which need not exist yet.

    """

    #: Unique lowercase Repository Name.
    name: str
    #: Resolved repository path, which need not exist yet.
    path: Path


class RepositoryCollection:
    """
    Hold the ordered Repository Entries loaded from one configuration file.

    Configuration order is preserved because it breaks ties in aggregate
    queries.

    Args:
        entries: Repository Entries in configuration order.

    """

    def __init__(self, entries: tuple[RepositoryEntry, ...]) -> None:
        """
        Initialize a collection over already validated entries.

        Args:
            entries: Repository Entries in configuration order.

        """
        #: Repository Entries in configuration order.
        self.entries = entries

    def __iter__(self) -> Iterator[RepositoryEntry]:
        """
        Iterate the entries in configuration order.

        Yields:
            Each Repository Entry.

        """
        return iter(self.entries)

    def __len__(self) -> int:
        """
        Report how many Repository Entries are configured.

        Returns:
            Number of entries.

        """
        return len(self.entries)

    def entry(self, name: str) -> RepositoryEntry:
        """
        Look up one Repository Entry by name.

        Args:
            name: Repository Name to find.

        Returns:
            Matching Repository Entry.

        Raises:
            TodoError: If no configured entry carries that name.

        """
        for entry in self.entries:
            if entry.name == name:
                return entry
        raise TodoError(f"unknown repository {name}", "repository_not_found")

    @classmethod
    def default_path(cls) -> Path:
        """
        Report the platform default configuration path.

        Returns:
            Default configuration file path.

        """
        if os.name == "nt":
            base = Path(os.environ.get("APPDATA", "~")).expanduser()
        else:
            base = Path(os.environ.get("XDG_CONFIG_HOME") or "~/.config").expanduser()
        return base / CONFIG_DIRECTORY / CONFIG_FILENAME

    @classmethod
    def resolve_path(cls, explicit: Path | None) -> Path:
        """
        Resolve the active configuration path without requiring the file.

        Args:
            explicit: Path named by ``--config`` or the environment, or
                ``None`` to use the platform default.

        Returns:
            Resolved configuration file path.

        """
        if explicit is not None:
            return explicit.expanduser().resolve()
        return cls.default_path().resolve()

    @classmethod
    def load(cls, explicit: Path | None) -> RepositoryCollection:
        """
        Load and fully validate a Repository Collection.

        An explicit path must exist, while an absent platform default simply
        means no repositories are configured.

        Side Effects:
            Reads the configuration file from disk.

        Args:
            explicit: Path named by ``--config`` or the environment, or
                ``None`` to use the platform default.

        Returns:
            Validated Repository Collection.

        Raises:
            TodoError: If the configuration is missing, malformed, or declares
                an unsupported schema version.

        """
        path = cls.resolve_path(explicit)
        if not path.is_file():
            if explicit is not None:
                raise TodoError(
                    f"configuration file not found: {path}", "config_not_found"
                )
            return cls(())
        return cls(_parse(path))


def _parse(path: Path) -> tuple[RepositoryEntry, ...]:
    """
    Read one configuration file into validated Repository Entries.

    Side Effects:
        Reads the configuration file from disk.

    Args:
        path: Configuration file to read.

    Returns:
        Repository Entries in configuration order.

    Raises:
        TodoError: If the file is unreadable, malformed, or unsupported.

    """
    try:
        with path.open("rb") as handle:
            document = tomllib.load(handle)
    except OSError as error:
        raise TodoError(f"cannot read {path}: {error}", "io_error") from error
    except tomllib.TOMLDecodeError as error:
        raise TodoError(
            f"{path} is not valid TOML: {error}", "invalid_config"
        ) from error
    return _document_entries(path, document)


def _require_supported_version(path: Path, document: dict[str, object]) -> None:
    """
    Reject an unsupported schema version before any other validation.

    Args:
        path: Configuration file being read.
        document: Parsed TOML document.

    Raises:
        TodoError: If the declared version is absent, malformed, or
            unsupported.

    """
    version = document.get("schema_version")
    if not isinstance(version, int) or isinstance(version, bool):
        raise TodoError(
            f"{path} must declare an integer schema_version", "invalid_config"
        )
    if version not in SUPPORTED_CONFIG_VERSIONS:
        raise TodoError(
            f"unsupported configuration schema version {version}",
            "unsupported_config_version",
            {"encountered": version, "supported": list(SUPPORTED_CONFIG_VERSIONS)},
        )


def _parse_entries(path: Path, repositories: object) -> tuple[RepositoryEntry, ...]:
    """
    Validate the repository table array into Repository Entries.

    Any invalid entry invalidates the whole configuration, so names and
    resolved paths are both checked for duplicates.

    Args:
        path: Configuration file being read.
        repositories: Raw ``repositories`` value from the document.

    Returns:
        Repository Entries in configuration order.

    Raises:
        TodoError: If any entry is malformed or duplicated.

    """
    if not isinstance(repositories, list):
        raise TodoError(f"{path} repositories must be an array", "invalid_config")
    entries: list[RepositoryEntry] = []
    names: set[str] = set()
    paths: set[Path] = set()
    for index, raw in enumerate(repositories):
        entry = _parse_entry(path, index, raw)
        if entry.name in names:
            raise TodoError(
                f"{path} repeats repository name {entry.name}", "invalid_config"
            )
        if entry.path in paths:
            raise TodoError(
                f"{path} repeats repository path {entry.path}", "invalid_config"
            )
        names.add(entry.name)
        paths.add(entry.path)
        entries.append(entry)
    return tuple(entries)


def _parse_entry(path: Path, index: int, raw: object) -> RepositoryEntry:
    """
    Validate one repository table into a Repository Entry.

    Args:
        path: Configuration file being read.
        index: Zero-based position of the entry.
        raw: Raw entry value from the document.

    Returns:
        Validated Repository Entry.

    Raises:
        TodoError: If the entry is not a table with exactly a valid name and
            path.

    """
    location = f"{path} repositories[{index}]"
    if not isinstance(raw, dict):
        raise TodoError(f"{location} must be a table", "invalid_config")
    if set(raw) != ENTRY_KEYS:
        raise TodoError(
            f"{location} must declare exactly name and path", "invalid_config"
        )
    name = raw["name"]
    value = raw["path"]
    if not isinstance(name, str) or not NAME_RE.fullmatch(name):
        raise TodoError(f"{location} has an invalid name", "invalid_config")
    if not isinstance(value, str) or not value.strip():
        raise TodoError(f"{location} has an invalid path", "invalid_config")
    return RepositoryEntry(name, _resolve(path, value))


def _resolve(config_path: Path, value: str) -> Path:
    """
    Resolve one entry path without expanding environment variables.

    A relative entry path is anchored to the configuration file's directory so
    a collection stays portable alongside its configuration.

    Args:
        config_path: Configuration file declaring the entry.
        value: Raw path value.

    Returns:
        Resolved path, which need not exist.

    """
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = config_path.parent / candidate
    return candidate.resolve()


class CollectionStore:
    """
    Mutate one Repository Collection configuration file.

    Args:
        explicit: Path named by ``--config`` or the environment, or ``None``
            to use the platform default.

    Keyword Args:
        timeout: Seconds to wait for the configuration lock.

    """

    def __init__(
        self, explicit: Path | None, *, timeout: float = LOCK_TIMEOUT_SECONDS
    ) -> None:
        """
        Bind one store to the resolved configuration path.

        Args:
            explicit: Path named by ``--config`` or the environment, or
                ``None`` to use the platform default.

        Keyword Args:
            timeout: Seconds to wait for the configuration lock.

        """
        #: Whether this store targets an explicit configuration path.
        self.explicit = explicit is not None
        #: Resolved configuration file path.
        self.path = RepositoryCollection.resolve_path(explicit)
        #: Exclusive and shared lock for the configuration file.
        self._lock = RepositoryLock(Path(str(self.path) + ".lock"), timeout=timeout)

    def load(self) -> RepositoryCollection:
        """
        Load and fully validate this store's Repository Collection.

        Side Effects:
            Reads the configuration file from disk.

        Returns:
            Validated Repository Collection.

        Raises:
            TodoError: If the configuration is missing, malformed, or declares
                an unsupported schema version.

        """
        if not self.path.is_file():
            return self._read()
        with self._lock.shared():
            return self._read()

    def add(self, path: str, name: str | None = None) -> RepositoryEntry:
        """
        Append one Repository Entry and write the canonical configuration.

        Side Effects:
            Creates parent directories for a missing default file, locks the
            configuration, and atomically replaces it.

        Args:
            path: Exact repository path as typed on the command line.

        Keyword Args:
            name: Repository Name override, or ``None`` to infer from the
                directory basename.

        Returns:
            The appended Repository Entry.

        Raises:
            TodoError: If the path or name is unusable, the file is missing or
                invalid, or the entry duplicates a name or resolved path.

        """
        resolved = _resolve_add_path(path)
        chosen = _choose_name(resolved, name)
        if not self.path.is_file() and self.explicit:
            raise TodoError(
                f"configuration file not found: {self.path}", "config_not_found"
            )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock.exclusive():
            current = self._read()
            _reject_duplicate(current.entries, chosen, resolved)
            entry = RepositoryEntry(chosen, resolved)
            self._replace((*current.entries, entry))
            return entry

    def remove(self, target: str) -> RepositoryEntry:
        """
        Remove one Repository Entry by name or resolved path.

        Side Effects:
            Locks the configuration and atomically replaces it when the file
            exists.

        Args:
            target: Repository Name, or a path including ``.``.

        Returns:
            The removed Repository Entry.

        Raises:
            TodoError: If the configuration is missing or invalid, or no entry
                matches the target.

        """
        if not self.path.is_file():
            self._read()
            raise TodoError(f"unknown repository {target}", "repository_not_found")
        with self._lock.exclusive():
            current = self._read()
            remaining, removed = _without_target(current.entries, target)
            self._replace(remaining)
            return removed

    def _read(self) -> RepositoryCollection:
        """
        Load this store's collection without acquiring the lock.

        Side Effects:
            Reads the configuration file from disk when it exists.

        Returns:
            Validated Repository Collection.

        Raises:
            TodoError: If an explicit file is missing or the file is invalid.

        """
        if not self.path.is_file():
            if self.explicit:
                raise TodoError(
                    f"configuration file not found: {self.path}", "config_not_found"
                )
            return RepositoryCollection(())
        return RepositoryCollection(_parse(self.path))

    def _replace(self, entries: tuple[RepositoryEntry, ...]) -> None:
        """
        Validate, atomically replace, and re-validate the configuration file.

        Side Effects:
            Replaces the configuration file.

        Args:
            entries: Repository Entries to persist in configuration order.

        Raises:
            TodoError: If the rendered document is invalid.

        """
        text = _render(entries)
        _document_entries(self.path, tomllib.loads(text))
        _replace_text(self.path, text)
        _parse(self.path)


def _allowed_add_path(value: str) -> bool:
    """
    Report whether an add path uses an allowed form.

    Args:
        value: Path as typed on the command line.

    Returns:
        ``True`` when the value is ``.``, home-relative, absolute, or contains
        a separator.

    """
    if value == "." or value.startswith("~"):
        return True
    candidate = Path(value)
    if candidate.is_absolute():
        return True
    return "/" in value or "\\" in value


def _resolve_add_path(value: str) -> Path:
    """
    Resolve one add path against the current directory.

    Args:
        value: Path as typed on the command line.

    Returns:
        Resolved repository path, which need not exist.

    Raises:
        TodoError: If the typed path is a bare slug.

    """
    if not _allowed_add_path(value):
        raise TodoError(
            "path must be '.', start with '~', be absolute, or contain a separator",
            "usage",
        )
    return _resolve_user_path(value)


def _resolve_user_path(value: str) -> Path:
    """
    Resolve one typed path against the current directory.

    Args:
        value: Path as typed on the command line.

    Returns:
        Resolved path, which need not exist.

    """
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    return candidate.resolve()


def _choose_name(resolved: Path, name: str | None) -> str:
    """
    Choose a Repository Name from an override or the directory basename.

    Args:
        resolved: Resolved repository path.
        name: Explicit Repository Name, or ``None`` to infer.

    Returns:
        Valid Repository Name.

    Raises:
        TodoError: If the inferred or explicit name is not a valid slug.

    """
    if name is None:
        inferred = resolved.name.lower()
        if not NAME_RE.fullmatch(inferred):
            raise TodoError(
                f"cannot infer a repository name from {resolved.name!r}; pass --name",
                "usage",
            )
        return inferred
    if not NAME_RE.fullmatch(name):
        raise TodoError(f"invalid repository name {name}", "usage")
    return name


def _reject_duplicate(
    entries: tuple[RepositoryEntry, ...], name: str, path: Path
) -> None:
    """
    Reject a name or resolved path already present in the collection.

    Args:
        entries: Existing Repository Entries.
        name: Candidate Repository Name.
        path: Candidate resolved path.

    Raises:
        TodoError: If the name or path is already configured.

    """
    for entry in entries:
        if entry.name == name:
            raise TodoError(
                f"repository {name} is already configured", "duplicate_repository"
            )
        if entry.path == path:
            raise TodoError(
                f"repository path {path} is already configured",
                "duplicate_repository",
            )


def _without_target(
    entries: tuple[RepositoryEntry, ...], target: str
) -> tuple[tuple[RepositoryEntry, ...], RepositoryEntry]:
    """
    Remove the entry identified by name or resolved path.

    A matching Repository Name wins over a path that resolves to a different
    entry.

    Args:
        entries: Existing Repository Entries.
        target: Repository Name, or a path including ``.``.

    Returns:
        Remaining entries and the removed entry.

    Raises:
        TodoError: If no entry matches the target.

    """
    for index, entry in enumerate(entries):
        if entry.name == target:
            return (*entries[:index], *entries[index + 1 :]), entry
    resolved = _resolve_user_path(target)
    for index, entry in enumerate(entries):
        if entry.path == resolved:
            return (*entries[:index], *entries[index + 1 :]), entry
    raise TodoError(f"unknown repository {target}", "repository_not_found")


def _stored_path(resolved: Path) -> str:
    """
    Render one resolved path for canonical configuration storage.

    Args:
        resolved: Resolved repository path.

    Returns:
        Home-relative ``~/...`` form when the path is under the home
        directory, otherwise the absolute path.

    """
    try:
        relative = resolved.relative_to(Path.home().resolve())
    except ValueError:
        return str(resolved)
    return "~/" + relative.as_posix()


def _toml_string(value: str) -> str:
    """
    Quote one TOML basic string.

    Args:
        value: Raw string to emit.

    Returns:
        Quoted TOML basic string.

    """
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )
    return f'"{escaped}"'


def _render(entries: Sequence[RepositoryEntry]) -> str:
    """
    Render a canonical Configuration Schema Version 1 document.

    Args:
        entries: Repository Entries in configuration order.

    Returns:
        Canonical TOML text ending in a newline.

    """
    lines = ["schema_version = 1"]
    if entries:
        lines.append("")
    for entry in entries:
        lines.append("[[repositories]]")
        lines.append(f"name = {_toml_string(entry.name)}")
        lines.append(f"path = {_toml_string(_stored_path(entry.path))}")
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


def _replace_text(path: Path, content: str) -> None:
    """
    Atomically replace one UTF-8 text file, preserving its permissions.

    Side Effects:
        Creates a temporary sibling file and replaces the target path.

    Args:
        path: Target file path.
        content: Complete replacement content.

    """
    mode: int | None = None
    try:
        mode = stat.S_IMODE(os.lstat(path).st_mode)
    except FileNotFoundError:
        pass
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}."
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        if mode is not None:
            temporary_path.chmod(mode)
        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def _document_entries(path: Path, document: dict[str, object]) -> tuple[RepositoryEntry, ...]:
    """
    Validate a parsed TOML document into Repository Entries.

    Args:
        path: Configuration file the document belongs to.
        document: Parsed TOML document.

    Returns:
        Repository Entries in configuration order.

    Raises:
        TodoError: If the document is malformed or unsupported.

    """
    _require_supported_version(path, document)
    unknown = sorted(set(document) - TOP_LEVEL_KEYS)
    if unknown:
        raise TodoError(f"{path} declares unknown key {unknown[0]}", "invalid_config")
    return _parse_entries(path, document.get("repositories", []))
