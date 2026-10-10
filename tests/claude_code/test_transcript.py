# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.claude_code.transcript."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from hookbell.claude_code.transcript import FileLastLineGetter
from hookbell.claude_code.transcript import QueuedMessageWatcher
from hookbell.claude_code.transcript import Transcript

if TYPE_CHECKING:
    from pathlib import Path


class TestFileLastLineGetter:
    """Tests for FileLastLineGetter."""

    def test_returns_the_final_line_of_a_multiline_file(self, tmp_path: Path) -> None:
        path = tmp_path / "transcript.jsonl"
        path.write_text('{"line": 1}\n{"line": 2}\n', encoding="utf-8")

        assert FileLastLineGetter(path).get_last_line() == '{"line": 2}'

    def test_returns_the_only_line_of_a_single_line_file(self, tmp_path: Path) -> None:
        path = tmp_path / "transcript.jsonl"
        path.write_text('{"line": 1}\n', encoding="utf-8")

        assert FileLastLineGetter(path).get_last_line() == '{"line": 1}'


ENQUEUE = {"type": "queue-operation", "operation": "enqueue", "content": "Run the tests too"}


def append_lines(path: Path, *lines: str) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write("".join(lines))


class TestQueuedMessageWatcher:
    """Tests for QueuedMessageWatcher."""

    def test_detects_an_enqueue_entry_appended_after_creation(self, tmp_path: Path) -> None:
        """Detect the entry Claude Code appends when the user sends a message while a hook runs."""
        path = tmp_path / "transcript.jsonl"
        path.write_text('{"type": "assistant"}\n', encoding="utf-8")
        watcher = QueuedMessageWatcher(path)

        append_lines(path, json.dumps(ENQUEUE) + "\n")

        assert watcher.has_queued_message()

    def test_ignores_an_enqueue_entry_written_before_creation(self, tmp_path: Path) -> None:
        path = tmp_path / "transcript.jsonl"
        path.write_text(json.dumps(ENQUEUE) + "\n", encoding="utf-8")

        assert not QueuedMessageWatcher(path).has_queued_message()

    def test_ignores_other_appended_entries(self, tmp_path: Path) -> None:
        """Ignore metadata, dequeue entries, and lines that aren't JSON objects."""
        path = tmp_path / "transcript.jsonl"
        path.write_text("", encoding="utf-8")
        watcher = QueuedMessageWatcher(path)

        append_lines(
            path,
            '{"type": "ai-title", "aiTitle": "title"}\n',
            '{"type": "queue-operation", "operation": "dequeue"}\n',
            '["queue-operation"]\n',
            "not json\n",
        )

        assert not watcher.has_queued_message()

    def test_reports_each_enqueue_entry_only_once(self, tmp_path: Path) -> None:
        """Report an entry already checked no more, since each check reads only what was appended since the last."""
        path = tmp_path / "transcript.jsonl"
        path.write_text("", encoding="utf-8")
        watcher = QueuedMessageWatcher(path)
        append_lines(path, json.dumps(ENQUEUE) + "\n")

        assert watcher.has_queued_message()
        assert not watcher.has_queued_message()

    def test_waits_for_a_line_still_being_written(self, tmp_path: Path) -> None:
        """Leave a line without its trailing newline for the next check instead of misreading it."""
        path = tmp_path / "transcript.jsonl"
        path.write_text("", encoding="utf-8")
        watcher = QueuedMessageWatcher(path)
        line = json.dumps(ENQUEUE)

        append_lines(path, line[:10])
        assert not watcher.has_queued_message()

        append_lines(path, line[10:] + "\n")
        assert watcher.has_queued_message()


class TestTranscriptReport:
    """Tests for Transcript.report."""

    def test_removes_unreadable_keys_from_the_entry_and_its_message(self, tmp_path: Path) -> None:
        """Strip internal bookkeeping keys before reporting a transcript entry."""
        entry = {
            "parentUuid": "parent",
            "isSidechain": False,
            "sessionId": "session",
            "version": "1.0",
            "requestId": "request",
            "uuid": "uuid",
            "timestamp": "2026-09-14T00:00:00Z",
            "message": {
                "id": "message-id",
                "content": [{"id": "content-id", "type": "text", "text": "Hello"}],
            },
        }
        path = tmp_path / "transcript.jsonl"
        path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        reported = json.loads(Transcript(path).report())

        assert "parentUuid" not in reported
        assert "id" not in reported["message"]
        assert "id" not in reported["message"]["content"][0]
        assert reported["message"]["content"][0]["text"] == "Hello"

    def test_wraps_a_non_dict_last_line_as_raw(self, tmp_path: Path) -> None:
        path = tmp_path / "transcript.jsonl"
        path.write_text("[1, 2, 3]\n", encoding="utf-8")

        assert json.loads(Transcript(path).report()) == {"raw": [1, 2, 3]}


class TestTranscriptTextContent:
    """Tests for Transcript.text_content."""

    def test_joins_assistant_text_blocks(self, tmp_path: Path) -> None:
        entry = {"message": {"content": [{"type": "text", "text": "Hello"}, {"type": "text", "text": "World"}]}}
        path = tmp_path / "transcript.jsonl"
        path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        assert Transcript(path).text_content == "Hello\nWorld"

    def test_ignores_non_text_content_blocks(self, tmp_path: Path) -> None:
        entry = {"message": {"content": [{"type": "tool_use", "name": "Bash"}]}}
        path = tmp_path / "transcript.jsonl"
        path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        assert Transcript(path).text_content == ""

    def test_returns_empty_string_for_a_non_dict_last_line(self, tmp_path: Path) -> None:
        path = tmp_path / "transcript.jsonl"
        path.write_text("[1, 2, 3]\n", encoding="utf-8")

        assert Transcript(path).text_content == ""

    def test_returns_empty_string_when_message_content_is_not_a_list(self, tmp_path: Path) -> None:
        entry = {"message": {"content": "not a list"}}
        path = tmp_path / "transcript.jsonl"
        path.write_text(json.dumps(entry) + "\n", encoding="utf-8")

        assert Transcript(path).text_content == ""
