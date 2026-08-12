"""Load and validate the Repository Collection configuration file."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from bot_todo.repository import TodoError

if TYPE_CHECKING:
    from collections.abc import Iterator

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
        path = explicit if explicit is not None else cls.default_path()
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
    _require_supported_version(path, document)
    unknown = sorted(set(document) - TOP_LEVEL_KEYS)
    if unknown:
        raise TodoError(f"{path} declares unknown key {unknown[0]}", "invalid_config")
    return _parse_entries(path, document.get("repositories", []))


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
