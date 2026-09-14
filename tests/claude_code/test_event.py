# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.claude_code.event."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from hookbell.claude_code.event import ClaudeCodeHookEvent
from hookbell.claude_code.stdin import ClaudeCodeStdin

if TYPE_CHECKING:
    from pathlib import Path


class TestClaudeCodeHookEventText:
    """Tests for ClaudeCodeHookEvent.text."""

    def test_uses_the_transcript_text_content_when_present(self, tmp_path: Path) -> None:
        """Use the transcript's own assistant text when the last entry has one."""
        entry = {"message": {"content": [{"type": "text", "text": "Hello from assistant"}]}}
        transcript_path = tmp_path / "transcript.jsonl"
        transcript_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        stdin = ClaudeCodeStdin({"hook_event_name": "Stop", "transcript_path": str(transcript_path)})

        text = ClaudeCodeHookEvent(stdin).text

        assert text.startswith("Hello from assistant\n\nMessage type: Stop\n\n```")
        assert '"text": "Hello from assistant"' in text

    def test_falls_back_to_the_stdin_fallback_text(self, tmp_path: Path) -> None:
        """Fall back to the stdin's own fallback text when the transcript has no assistant text."""
        entry = {"message": {"content": [{"type": "tool_use", "name": "Bash"}]}}
        transcript_path = tmp_path / "transcript.jsonl"
        transcript_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        stdin = ClaudeCodeStdin(
            {
                "hook_event_name": "PermissionRequest",
                "transcript_path": str(transcript_path),
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            },
        )

        text = ClaudeCodeHookEvent(stdin).text

        assert text.startswith('Waiting for permission: Bash({"command": "ls"})\n\nMessage type: PermissionRequest')
