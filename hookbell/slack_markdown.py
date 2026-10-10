# Copyright (c) 2026 Yukihiko Shinoda
"""Wraps standard Markdown into a Slack Block Kit markdown block.

Slack translates a markdown block's text itself, so Claude Code's Markdown (headings, tables, fenced code with a
language) renders as structured text instead of mrkdwn showing its raw syntax. See:
https://docs.slack.dev/reference/block-kit/blocks/markdown-block/
"""

from __future__ import annotations

FENCE = "```"


class SlackMarkdown:
    """Markdown text cut to fit a single Slack markdown block."""

    # Slack's cumulative limit for every markdown block in a single payload.
    CHARACTER_LIMIT = 12000
    CLOSING_FENCE = f"\n{FENCE}"
    TRUNCATION_NOTICE = "\n\n(truncated)"

    def __init__(self, text: str) -> None:
        self.text = text

    @property
    def truncated_text(self) -> str:
        """Return the text, cut to the limit with a notice, closing a code block the cut leaves open."""
        if len(self.text) <= self.CHARACTER_LIMIT:
            return self.text
        head = self.text[: self.CHARACTER_LIMIT - len(self.CLOSING_FENCE) - len(self.TRUNCATION_NOTICE)]
        if head.count(FENCE) % 2 == 1:
            head += self.CLOSING_FENCE
        return head + self.TRUNCATION_NOTICE

    @property
    def blocks(self) -> list[dict[str, str]]:
        """Return the Block Kit blocks carrying the text."""
        return [{"type": "markdown", "text": self.truncated_text}]
