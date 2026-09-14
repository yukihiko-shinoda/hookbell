# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.claude_code.stdin."""

from __future__ import annotations

import json
from pathlib import Path

from hookbell.claude_code.stdin import ClaudeCodeStdin


class TestClaudeCodeStdinParse:
    """Tests for ClaudeCodeStdin.parse."""

    def test_returns_none_for_invalid_json(self) -> None:
        assert ClaudeCodeStdin.parse("not json") is None

    def test_returns_none_when_transcript_path_is_missing(self) -> None:
        assert ClaudeCodeStdin.parse(json.dumps({"hook_event_name": "Stop"})) is None

    def test_returns_none_for_a_json_array(self) -> None:
        assert ClaudeCodeStdin.parse(json.dumps(["not", "a", "dict"])) is None

    def test_returns_an_instance_when_transcript_path_is_present(self) -> None:
        stdin = ClaudeCodeStdin.parse(json.dumps({"transcript_path": "/path/to/transcript.jsonl"}))

        assert stdin is not None
        assert stdin.transcript_path == Path("/path/to/transcript.jsonl")


class TestClaudeCodeStdinMessage:
    """Tests for ClaudeCodeStdin.message."""

    def test_returns_the_message_field_when_present(self) -> None:
        stdin = ClaudeCodeStdin({"message": "Custom message", "hook_event_name": "Notification"})

        assert stdin.message == "Custom message"

    def test_falls_back_to_the_hook_event_name(self) -> None:
        stdin = ClaudeCodeStdin({"hook_event_name": "Stop"})

        assert stdin.message == "Stop"

    def test_falls_back_to_notification_by_default(self) -> None:
        stdin = ClaudeCodeStdin({})

        assert stdin.message == "Notification"


class TestClaudeCodeStdinFallbackText:
    """Tests for ClaudeCodeStdin.fallback_text."""

    def test_prefers_the_last_assistant_message(self) -> None:
        stdin = ClaudeCodeStdin({"last_assistant_message": "Done!", "tool_name": "Bash"})

        assert stdin.fallback_text == "Done!"

    def test_describes_a_pending_permission_request(self) -> None:
        stdin = ClaudeCodeStdin({"tool_name": "Bash", "tool_input": {"command": "ls"}})

        assert stdin.fallback_text == 'Waiting for permission: Bash({"command": "ls"})'

    def test_falls_back_to_message(self) -> None:
        stdin = ClaudeCodeStdin({"hook_event_name": "Stop"})

        assert stdin.fallback_text == "Stop"
