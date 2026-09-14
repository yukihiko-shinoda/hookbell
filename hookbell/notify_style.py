# Copyright (c) 2026 Yukihiko Shinoda
"""Composes a plain-text notification from captured stdin.

A bare invocation notifies "Finished!", and piped stdin gets wrapped into a code block beneath it, truncated to Slack's
message character limit.
"""


class PlainTextNotification:
    """A plain-text notification built from optional piped stdin."""

    DEFAULT_TEXT = "Finished!"
    # Following the character length limit on Slack messages:
    # https://api.slack.com/changelog/2018-04-truncating-really-long-messages
    STDIN_CHARACTER_LIMIT = 39900

    def __init__(self, captured_stdin: str) -> None:
        self.captured_stdin = captured_stdin

    @property
    def text(self) -> str:
        """Return the notification text."""
        if not self.captured_stdin:
            return self.DEFAULT_TEXT
        truncated = self.captured_stdin[-self.STDIN_CHARACTER_LIMIT :]
        return f"{self.DEFAULT_TEXT}\n```\n{truncated}\n```"
