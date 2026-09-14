# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.cli."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from click.testing import CliRunner

from hookbell import cli

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture


@pytest.fixture(autouse=True)
def _slack_webhook_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T000/B000/XXX")


@pytest.fixture(name="urlopen")
def _urlopen_fixture(mocker: MockerFixture) -> MagicMock:
    mock = mocker.patch("hookbell.notifiers.slack.request.urlopen")
    mock.return_value.__enter__.return_value.read.return_value = b"ok"
    return mock


class TestMainHelp:
    def test_shows_usage(self) -> None:
        result = CliRunner().invoke(cli.main, ["--help"])

        assert result.exit_code == 0
        assert "--help  Show this message and exit." in result.output


class TestMainPlainTextMode:
    """Tests for main() when stdin is not a Claude Code hook payload."""

    def test_notifies_the_default_text_when_stdin_was_not_piped(self, urlopen: MagicMock) -> None:
        result = CliRunner().invoke(cli.main, input=None)

        assert result.exit_code == 0
        posted = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        assert posted["blocks"][0]["text"]["text"] == "Finished!"

    def test_notifies_the_piped_plain_text(self, urlopen: MagicMock) -> None:
        result = CliRunner().invoke(cli.main, input="Hello world\n")

        assert result.exit_code == 0
        posted = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        assert "Hello world" in posted["blocks"][0]["text"]["text"]

    def test_reports_notification_failures_as_a_clean_error_and_exits_1(self, mocker: MockerFixture) -> None:
        mocker.patch("hookbell.notifiers.slack.request.urlopen", side_effect=OSError("boom"))

        result = CliRunner().invoke(cli.main, input="Hello world\n")

        assert result.exit_code == 1
        assert "Error: boom" in result.output


class TestMainClaudeCodeHookMode:
    """Tests for main() when stdin is a Claude Code hook payload."""

    def test_notifies_through_the_referenced_transcript(self, tmp_path: Path, urlopen: MagicMock) -> None:
        """Notify with text composed from the payload's referenced transcript."""
        entry = {"message": {"content": [{"type": "text", "text": "Hello from assistant"}]}}
        transcript_path = tmp_path / "transcript.jsonl"
        transcript_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        payload = json.dumps({"hook_event_name": "Stop", "transcript_path": str(transcript_path)})

        result = CliRunner().invoke(cli.main, input=payload)

        assert result.exit_code == 0
        posted = json.loads(urlopen.call_args.args[0].data.decode("utf-8"))
        assert "Hello from assistant" in posted["blocks"][0]["text"]["text"]

    def test_swallows_notification_failures_and_still_exits_0(self, tmp_path: Path) -> None:
        payload = json.dumps({"hook_event_name": "Stop", "transcript_path": str(tmp_path / "missing.jsonl")})

        result = CliRunner().invoke(cli.main, input=payload)

        assert result.exit_code == 0
