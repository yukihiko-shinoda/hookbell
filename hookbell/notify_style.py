# Copyright (c) 2026 Yukihiko Shinoda
"""Composes a plain-text notification from captured stdin.

A bare invocation notifies "Finished!", and piped stdin gets wrapped into a code block beneath it, keeping only its
tail so the whole text fits a Slack markdown block.
"""

from hookbell.slack_markdown import SlackMarkdown


class PlainTextNotification:
    """A plain-text notification built from optional piped stdin."""

    DEFAULT_TEXT = "Finished!"
    CODE_BLOCK_START = "\n```\n"
    CODE_BLOCK_END = "\n```"
    STDIN_CHARACTER_LIMIT = (
        SlackMarkdown.CHARACTER_LIMIT - len(DEFAULT_TEXT) - len(CODE_BLOCK_START) - len(CODE_BLOCK_END)
    )

    def __init__(self, captured_stdin: str) -> None:
        self.captured_stdin = captured_stdin

    @property
    def text(self) -> str:
        """Return the notification text."""
        if not self.captured_stdin:
            return self.DEFAULT_TEXT
        truncated = self.captured_stdin[-self.STDIN_CHARACTER_LIMIT :]
        return f"{self.DEFAULT_TEXT}{self.CODE_BLOCK_START}{truncated}{self.CODE_BLOCK_END}"
