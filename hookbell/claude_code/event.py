# Copyright (c) 2026 Yukihiko Shinoda
"""Composes a notification text from a Claude Code hook event."""

from hookbell.claude_code.stdin import ClaudeCodeStdin
from hookbell.claude_code.transcript import Transcript


class ClaudeCodeHookEvent:
    """A Claude Code hook event, combining its stdin payload and referenced transcript."""

    def __init__(self, stdin: ClaudeCodeStdin) -> None:
        self.stdin = stdin
        self.transcript = Transcript(stdin.transcript_path)

    @property
    def text(self) -> str:
        """Return the notification text for this hook event."""
        content = self.transcript.text_content or self.stdin.fallback_text
        return f"{content}\n\nMessage type: {self.stdin.message}\n\n```{self.transcript.report()}```"
