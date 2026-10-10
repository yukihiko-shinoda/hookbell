# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.slack_markdown."""

from __future__ import annotations

from hookbell.slack_markdown import SlackMarkdown


class TestSlackMarkdown:
    """Tests for SlackMarkdown."""

    def test_blocks_wraps_the_text_in_a_single_markdown_block(self) -> None:
        assert SlackMarkdown("## Done\n\n| a | b |\n| - | - |").blocks == [
            {"type": "markdown", "text": "## Done\n\n| a | b |\n| - | - |"},
        ]

    def test_truncated_text_keeps_text_within_the_limit_as_is(self) -> None:
        text = "x" * SlackMarkdown.CHARACTER_LIMIT

        assert SlackMarkdown(text).truncated_text == text

    def test_truncated_text_cuts_long_text_to_the_limit_with_a_notice(self) -> None:
        truncated = SlackMarkdown("x" * (SlackMarkdown.CHARACTER_LIMIT + 1)).truncated_text

        assert len(truncated) <= SlackMarkdown.CHARACTER_LIMIT
        assert truncated.endswith("x" + SlackMarkdown.TRUNCATION_NOTICE)

    def test_truncated_text_closes_a_code_block_the_cut_leaves_open(self) -> None:
        """Close a fenced code block cut in the middle, so the notice doesn't render as code."""
        truncated = SlackMarkdown("Summary\n```json\n" + "x" * SlackMarkdown.CHARACTER_LIMIT + "\n```").truncated_text

        assert len(truncated) <= SlackMarkdown.CHARACTER_LIMIT
        assert truncated.endswith("x\n```" + SlackMarkdown.TRUNCATION_NOTICE)
