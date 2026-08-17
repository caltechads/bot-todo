"""Load the packaged Task Management Snippet."""

from __future__ import annotations

from importlib.resources import files

#: Package directory holding packaged agent-facing assets.
ASSET_DIRECTORY = "skill_assets"
#: Filename of the consuming-repo Task Management Snippet.
SNIPPET_FILENAME = "task_management.md"


class TaskManagementSnippet:
    """
    Load the packaged Task Management Snippet.

    The text is packaged with ``bot-todo`` so an installed wheel can emit it
    from ``init`` and ``snippet`` without a source checkout.
    """

    def text(self) -> str:
        """
        Return the packaged markdown section without a trailing newline.

        Side Effects:
            Reads the packaged snippet asset.

        Returns:
            The consuming-repo Task Management section.

        """
        resource = (
            files("bot_todo").joinpath(ASSET_DIRECTORY).joinpath(SNIPPET_FILENAME)
        )
        return resource.read_text(encoding="utf-8").rstrip("\n")
