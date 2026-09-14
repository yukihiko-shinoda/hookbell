# Copyright (c) 2026 Yukihiko Shinoda
"""Parses Claude Code hook stdin payloads."""

from __future__ import annotations

import json
from logging import getLogger
from pathlib import Path
from typing import Any


class ClaudeCodeStdin:
    """A Claude Code hook stdin payload."""

    TRANSCRIPT_PATH_KEY = "transcript_path"

    def __init__(self, data: dict[str, Any]) -> None:
        self.data = data

    @classmethod
    def parse(cls, raw_stdin: str) -> ClaudeCodeStdin | None:
        """Return a ClaudeCodeStdin when raw_stdin holds a Claude Code hook payload, else None."""
        try:
            data = json.loads(raw_stdin)
        except json.JSONDecodeError:
            return None
        if not isinstance(data, dict) or cls.TRANSCRIPT_PATH_KEY not in data:
            return None
        getLogger(__name__).debug("raw stdin: %s", raw_stdin)
        return cls(data)

    @property
    def message(self) -> str:
        """Return the hook's message, falling back to its event name."""
        return str(self.data.get("message") or self.data.get("hook_event_name", "Notification"))

    @property
    def transcript_path(self) -> Path:
        """Return the transcript file path this hook event refers to."""
        return Path(self.data[self.TRANSCRIPT_PATH_KEY])

    @property
    def fallback_text(self) -> str:
        """Return text to show when the transcript's last line has no readable text.

        PermissionRequest payloads carry the pending tool call directly instead of assistant text, and Stop payloads
        carry a ready-made last_assistant_message when the transcript's last line was something else (e.g. a sidechain
        or summary entry).
        """
        last_assistant_message = self.data.get("last_assistant_message")
        if last_assistant_message:
            return str(last_assistant_message)
        tool_name = self.data.get("tool_name")
        if tool_name:
            tool_input = json.dumps(self.data.get("tool_input", {}), ensure_ascii=False)
            return f"Waiting for permission: {tool_name}({tool_input})"
        return self.message
