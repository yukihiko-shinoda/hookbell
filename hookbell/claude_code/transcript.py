# Copyright (c) 2026 Yukihiko Shinoda
"""Reads and sanitizes a Claude Code transcript's last entry."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    import io
    from pathlib import Path


class FileLastLineGetter:
    """Gets the last line of a file without reading the whole file into memory."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    def get_last_line(self) -> str:
        """Return the last line of the file."""
        with self.file_path.open("rb") as file_pointer:
            return self._get_last_line(file_pointer)

    @staticmethod
    def _get_last_line(file_pointer: io.BufferedIOBase) -> str:
        try:
            FileLastLineGetter._seek_to_last_new_line(file_pointer)
        except OSError:
            # In case of a one line file
            file_pointer.seek(0)
        return file_pointer.readline().decode("utf-8").strip()

    @staticmethod
    def _seek_to_last_new_line(file_pointer: io.BufferedIOBase) -> None:
        file_pointer.seek(-2, os.SEEK_END)
        while file_pointer.read(1) != b"\n":
            file_pointer.seek(-2, os.SEEK_CUR)


class Transcript:
    """A Claude Code transcript.

    The transcript's last line is not always a plain assistant text message: it may be a tool call, a sub-
    agent/sidechain entry, or a compaction summary entry, each with a different shape. Every accessor here must
    tolerate keys being absent rather than assume the full schema.
    """

    UNREADABLE_KEYS = ("parentUuid", "isSidechain", "sessionId", "version", "requestId", "uuid", "timestamp")

    def __init__(self, path: Path) -> None:
        transcript_json_string = FileLastLineGetter(path).get_last_line()
        self.data: Any = json.loads(transcript_json_string)

    def report(self) -> str:
        """Return the last transcript entry as pretty-printed, sanitized JSON."""
        return json.dumps(self._remove_unreadable_keys(), indent=2, ensure_ascii=False)

    def _remove_unreadable_keys(self) -> dict[str, Any]:
        if not isinstance(self.data, dict):
            return {"raw": self.data}
        data = self.data.copy()
        for key in self.UNREADABLE_KEYS:
            data.pop(key, None)
        message = data.get("message")
        if isinstance(message, dict):
            self._remove_unreadable_message_keys(message)
        return data

    @staticmethod
    def _remove_unreadable_message_keys(message: dict[str, Any]) -> None:
        message.pop("id", None)
        for message_content in message.get("content") or []:
            if isinstance(message_content, dict):
                message_content.pop("id", None)

    @property
    def text_content(self) -> str:
        """Return the concatenated assistant text blocks of the last transcript entry."""
        if not isinstance(self.data, dict):
            return ""
        contents = self.data.get("message", {}).get("content") or []
        if not isinstance(contents, list):
            return ""
        texts = [item["text"] for item in contents if isinstance(item, dict) and item.get("type") == "text"]
        return "\n".join(texts)
