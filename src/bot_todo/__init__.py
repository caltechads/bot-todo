"""Installable task-repository CLI for agent and human backlogs."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version


def package_version() -> str:
    """
    Return the installed distribution version.

    Returns:
        Installed version, or ``unknown`` when running from an unbuilt tree.

    """
    try:
        return version("bot-todo")
    except PackageNotFoundError:
        return "unknown"
