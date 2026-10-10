# Copyright (c) 2026 Yukihiko Shinoda
"""Composes a notification text from a Claude Code hook event."""

from logging import getLogger

from hookbell.claude_code.stdin import ClaudeCodeStdin
from hookbell.claude_code.transcript import Transcript


class ClaudeCodeHookEvent:
    """A Claude Code hook event, combining its stdin payload and referenced transcript."""

    def __init__(self, stdin: ClaudeCodeStdin) -> None:
        self.stdin = stdin
        self.transcript = Transcript(stdin.transcript_path)
        self.logger = getLogger(__name__)

    @property
    def text(self) -> str:
        """Return the notification text for this hook event.

        The raw transcript entry goes to the debug log rather than the message: it is long enough to make Slack split
        the post, and a reply in any part but the one hookbell watches is never picked up.
        """
        self.logger.debug("transcript entry: %s", self.transcript.report())
        content = self.transcript.text_content or self.stdin.fallback_text
        return f"{content}\n\nMessage type: {self.stdin.message}"
