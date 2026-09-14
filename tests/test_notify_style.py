# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.notify_style."""

from __future__ import annotations

from hookbell.notify_style import PlainTextNotification


class TestPlainTextNotificationText:
    """Tests for PlainTextNotification.text."""

    def test_defaults_to_finished_when_no_stdin_was_captured(self) -> None:
        assert PlainTextNotification("").text == "Finished!"

    def test_wraps_captured_stdin_in_a_code_block(self) -> None:
        assert PlainTextNotification("Hello world").text == "Finished!\n```\nHello world\n```"

    def test_truncates_captured_stdin_to_the_slack_character_limit(self) -> None:
        captured = "x" * (PlainTextNotification.STDIN_CHARACTER_LIMIT + 100)

        text = PlainTextNotification(captured).text

        truncated = captured[-PlainTextNotification.STDIN_CHARACTER_LIMIT :]
        assert text == f"Finished!\n```\n{truncated}\n```"
