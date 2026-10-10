# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.cli."""

from __future__ import annotations

import json
import logging
import os
import stat

# Reason: Bandit flags any import of subprocess, but its only use here runs a constant argv without a shell, which
# TestLoggingConfiguration needs to observe the logging configuration in a fresh interpreter:
# - Blacklist Imports - B404: import_subprocess — Bandit documentation
#   https://bandit.readthedocs.io/en/latest/blacklists/blacklist_imports.html#b404-import-subprocess
import subprocess  # nosec B404
import sys
from typing import TYPE_CHECKING

import click
import pytest
from click.testing import CliRunner

from hookbell import cli

if TYPE_CHECKING:
    from pathlib import Path
    from unittest.mock import MagicMock

    from pytest_mock import MockerFixture

    from tests.conftest import FakeClock
    from tests.conftest import FakeSlackWebApi

PARENT_TS = "1700000000.000100"
WEBHOOK_URL = "https://hooks.slack.com/services/T000/B000/XXX"


@pytest.fixture(autouse=True)
def _slack_webhook_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", WEBHOOK_URL)


@pytest.fixture(name="urlopen")
def _urlopen_fixture(mocker: MockerFixture) -> MagicMock:
    mock = mocker.patch("hookbell.notifiers.slack.request.urlopen")
    mock.return_value.__enter__.return_value.read.return_value = b"ok"
    return mock


class TestMainHelp:
    def test_shows_usage(self) -> None:
        result = CliRunner().invoke(cli.main, ["--help"])

        assert result.exit_code == 0
        assert "Show this message and exit." in result.output


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

    def test_reports_both_destinations_configured_as_a_clean_error_and_exits_1(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Report the NotifierFactory conflict error the same way as any other notification failure."""
        monkeypatch.setenv("HOOKBELL_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:hookbell")

        result = CliRunner().invoke(cli.main, input="Hello world\n")

        assert result.exit_code == 1
        assert "exactly one destination" in result.output


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

    def test_swallows_both_destinations_configured_and_still_exits_0(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Swallow the NotifierFactory conflict error the same way as any other notification failure."""
        monkeypatch.setenv("HOOKBELL_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:hookbell")
        entry = {"message": {"content": [{"type": "text", "text": "Hello from assistant"}]}}
        transcript_path = tmp_path / "transcript.jsonl"
        transcript_path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        payload = json.dumps({"hook_event_name": "Stop", "transcript_path": str(transcript_path)})

        result = CliRunner().invoke(cli.main, input=payload)

        assert result.exit_code == 0


@pytest.fixture(name="transcript_path")
def _transcript_path_fixture(tmp_path: Path) -> Path:
    entry = {"message": {"content": [{"type": "text", "text": "Hello from assistant"}]}}
    path = tmp_path / "transcript.jsonl"
    path.write_text(json.dumps(entry) + "\n", encoding="utf-8")
    return path


def hook_payload(transcript_path: Path, hook_event_name: str) -> str:
    return json.dumps({"hook_event_name": hook_event_name, "transcript_path": str(transcript_path)})


def queue_reply(fake_slack_web_api: FakeSlackWebApi, text: str) -> None:
    fake_slack_web_api.queue("chat.postMessage", {"ok": True, "ts": PARENT_TS})
    fake_slack_web_api.queue(
        "conversations.replies",
        {"ok": True, "messages": [{"ts": "1700000000.000200", "user": "U0ALLOWED", "text": text}]},
    )


@pytest.mark.usefixtures("slack_bot_settings", "fake_clock")
class TestMainWaitReply:
    """Tests for main() with --wait-reply."""

    def test_stop_continues_claude_with_the_reply(
        self,
        transcript_path: Path,
        fake_slack_web_api: FakeSlackWebApi,
    ) -> None:
        """Print a block decision carrying the reply, posting only through the bot and never the webhook."""
        queue_reply(fake_slack_web_api, "Run the tests too")

        result = CliRunner().invoke(cli.main, ["--wait-reply"], input=hook_payload(transcript_path, "Stop"))

        assert result.exit_code == 0
        assert json.loads(result.output) == {"decision": "block", "reason": "Run the tests too"}
        posted_text = fake_slack_web_api.params_of("chat.postMessage")[0]["text"]
        assert "Hello from assistant" in posted_text
        assert "`stop`" in posted_text
        # The fake answers every urlopen() call, so a webhook POST would show up here too.
        assert [method for method, _ in fake_slack_web_api.calls] == ["chat.postMessage", "conversations.replies"]

    def test_stop_prints_nothing_for_a_stop_keyword(
        self,
        transcript_path: Path,
        fake_slack_web_api: FakeSlackWebApi,
    ) -> None:
        """Print nothing for a stop keyword, so Claude stops as it would without hookbell."""
        queue_reply(fake_slack_web_api, "quit")

        result = CliRunner().invoke(cli.main, ["--wait-reply"], input=hook_payload(transcript_path, "Stop"))

        assert result.exit_code == 0
        assert result.output == ""

    def test_permission_request_allows_on_an_allow_keyword(
        self,
        transcript_path: Path,
        fake_slack_web_api: FakeSlackWebApi,
    ) -> None:
        """Print an allow decision for an exact allow keyword."""
        queue_reply(fake_slack_web_api, "ok")

        result = CliRunner().invoke(
            cli.main,
            ["--wait-reply"],
            input=hook_payload(transcript_path, "PermissionRequest"),
        )

        assert result.exit_code == 0
        assert json.loads(result.output)["hookSpecificOutput"]["decision"] == {"behavior": "allow"}

    def test_permission_request_denies_a_near_miss_of_an_allow_keyword(
        self,
        transcript_path: Path,
        fake_slack_web_api: FakeSlackWebApi,
    ) -> None:
        """Deny a reply that only nearly matches an allow keyword, such as "ok!"."""
        queue_reply(fake_slack_web_api, "ok!")

        result = CliRunner().invoke(
            cli.main,
            ["--wait-reply"],
            input=hook_payload(transcript_path, "PermissionRequest"),
        )

        assert result.exit_code == 0
        assert json.loads(result.output)["hookSpecificOutput"]["decision"]["behavior"] == "deny"

    def test_prints_nothing_on_timeout(self, transcript_path: Path, fake_slack_web_api: FakeSlackWebApi) -> None:
        """Print nothing once the reply timeout passes, leaving the decision to the terminal."""
        fake_slack_web_api.queue("chat.postMessage", {"ok": True, "ts": PARENT_TS})
        fake_slack_web_api.queue("conversations.replies", {"ok": True, "messages": []})

        result = CliRunner().invoke(
            cli.main,
            ["--wait-reply", "--reply-timeout", "10"],
            input=hook_payload(transcript_path, "PermissionRequest"),
        )

        assert result.exit_code == 0
        assert result.output == ""

    def test_stop_prints_nothing_once_a_message_is_queued_at_the_terminal(
        self,
        transcript_path: Path,
        fake_slack_web_api: FakeSlackWebApi,
        fake_clock: FakeClock,
    ) -> None:
        """Stop waiting and print nothing once the user sends a message at the terminal, so Claude Code handles it."""
        fake_slack_web_api.queue("chat.postMessage", {"ok": True, "ts": PARENT_TS})
        fake_slack_web_api.queue("conversations.replies", {"ok": True, "messages": []})
        enqueue = {"type": "queue-operation", "operation": "enqueue", "content": "Run the tests too"}

        def send_message_at_terminal() -> None:
            with transcript_path.open("a", encoding="utf-8") as file:
                file.write(json.dumps(enqueue) + "\n")

        fake_clock.during_next_sleep.append(send_message_at_terminal)

        result = CliRunner().invoke(cli.main, ["--wait-reply"], input=hook_payload(transcript_path, "Stop"))

        assert result.exit_code == 0
        assert result.output == ""
        assert fake_clock.sleeps == [5.0]
        assert fake_slack_web_api.params_of("conversations.replies") == []

    def test_prints_nothing_and_exits_0_on_failure(
        self,
        transcript_path: Path,
        fake_slack_web_api: FakeSlackWebApi,
    ) -> None:
        """Print nothing and still exit 0 when Slack fails, never falling back to an allow."""
        fake_slack_web_api.queue("chat.postMessage", {"ok": False, "error": "channel_not_found"})

        result = CliRunner().invoke(
            cli.main,
            ["--wait-reply"],
            input=hook_payload(transcript_path, "PermissionRequest"),
        )

        assert result.exit_code == 0
        assert result.output == ""

    def test_notifies_other_events_through_the_webhook_without_waiting(
        self,
        transcript_path: Path,
        urlopen: MagicMock,
    ) -> None:
        """Notify events that take no reply through the webhook, without waiting."""
        result = CliRunner().invoke(cli.main, ["--wait-reply"], input=hook_payload(transcript_path, "Notification"))

        assert result.exit_code == 0
        assert result.output == ""
        assert [call.args[0].full_url for call in urlopen.call_args_list] == [WEBHOOK_URL]

    def test_notifies_without_waiting_when_sns_is_configured(
        self,
        transcript_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        mocker: MockerFixture,
        urlopen: MagicMock,
    ) -> None:
        """Leave the SNS-configured setup on its usual one-way path, since SNS has no way to receive a reply."""
        monkeypatch.setenv("HOOKBELL_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:hookbell")
        monkeypatch.delenv("SLACK_WEBHOOK_URL")
        session = mocker.patch("hookbell.notifiers.sns.boto3.Session")

        result = CliRunner().invoke(cli.main, ["--wait-reply"], input=hook_payload(transcript_path, "Stop"))

        assert result.exit_code == 0
        assert result.output == ""
        session.return_value.client.return_value.publish.assert_called_once()
        urlopen.assert_not_called()

    def test_notifies_through_the_webhook_without_the_option(
        self,
        transcript_path: Path,
        urlopen: MagicMock,
    ) -> None:
        """Keep notifying through the webhook without waiting when --wait-reply isn't given."""
        result = CliRunner().invoke(cli.main, input=hook_payload(transcript_path, "Stop"))

        assert result.exit_code == 0
        assert result.output == ""
        assert [call.args[0].full_url for call in urlopen.call_args_list] == [WEBHOOK_URL]


class TestMainWaitReplyWithoutBotSettings:
    """Tests for main() with --wait-reply when the Slack bot isn't configured."""

    def test_falls_back_to_the_webhook(self, transcript_path: Path, urlopen: MagicMock) -> None:
        result = CliRunner().invoke(cli.main, ["--wait-reply"], input=hook_payload(transcript_path, "Stop"))

        assert result.exit_code == 0
        assert result.output == ""
        assert [call.args[0].full_url for call in urlopen.call_args_list] == [WEBHOOK_URL]


class TestMainLogging:
    """Tests for how main() hands its logging options to configure_logging()."""

    @pytest.mark.usefixtures("urlopen")
    def test_writes_no_log_file_by_default(self) -> None:
        result = CliRunner().invoke(cli.main, input="Hello world\n")

        assert result.exit_code == 0
        assert not cli.log_file_path().exists()

    @pytest.mark.usefixtures("urlopen")
    def test_log_level_option_enables_the_log_file(self) -> None:
        result = CliRunner().invoke(cli.main, ["--log-level", "debug"], input="Hello world\n")

        assert result.exit_code == 0
        assert cli.log_file_path().is_file()

    @pytest.mark.usefixtures("urlopen")
    def test_log_level_is_read_from_the_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Accept HOOKBELL_LOG_LEVEL so the level can be set without editing the hook command."""
        monkeypatch.setenv("HOOKBELL_LOG_LEVEL", "info")

        result = CliRunner().invoke(cli.main, input="Hello world\n")

        assert result.exit_code == 0
        assert cli.log_file_path().is_file()

    def test_rejects_an_unknown_log_level(self) -> None:
        result = CliRunner().invoke(cli.main, ["--log-level", "verbose"], input="Hello world\n")

        assert result.exit_code == click.UsageError.exit_code

    @pytest.mark.usefixtures("urlopen")
    def test_dangerously_debug_all_loggers_warns_on_stderr(self) -> None:
        # result.output includes stderr both on Click < 8.2 (mixed by default) and on Click >= 8.2 (interleaved).
        result = CliRunner().invoke(cli.main, ["--dangerously-debug-all-loggers"], input="Hello world\n")

        assert result.exit_code == 0
        assert "Warning: --dangerously-debug-all-loggers" in result.output


class TestConfigureLogging:
    """Tests for configure_logging(), observed in a fresh interpreter per test."""

    # Loggers whose DEBUG output contains wire traces: request/response bodies, headers, and URLs that can carry
    # credentials (e.g. botocore.endpoint's Authorization header, botocore.parsers' STS/SSO response bodies).
    WIRE_TRACE_LOGGERS = ("botocore", "boto3", "urllib3", "httpx", "httpcore")

    # Reason: The configuration must be observed in a fresh interpreter. Under pytest, the root logger already
    # has pytest's own handlers, so logging.basicConfig() silently does nothing and an in-process check would pass
    # regardless of what hookbell configures.
    PROBE_SCRIPT = """
import json
import logging
import sys

from hookbell.cli import configure_logging

configure_logging(**json.loads(sys.argv[1]))
print(json.dumps({name: logging.getLogger(name).getEffectiveLevel() for name in sys.argv[2:]}))
"""

    def test_wire_trace_loggers_not_debug(self, tmp_path: Path) -> None:
        """Keep third-party wire trace loggers above DEBUG even when hookbell's own logs are at DEBUG."""
        effective_levels = self._probe(tmp_path, tmp_path / "cache", level="DEBUG")

        assert effective_levels.pop("hookbell") == logging.DEBUG
        assert {name: level for name, level in effective_levels.items() if level <= logging.DEBUG} == {}

    def test_dangerously_debug_all_loggers_sets_wire_trace_loggers_to_debug(self, tmp_path: Path) -> None:
        effective_levels = self._probe(tmp_path, tmp_path / "cache", level=None, dangerously_debug_all_loggers=True)

        assert set(effective_levels.values()) == {logging.DEBUG}

    def test_writes_no_log_file_when_level_is_none(self, tmp_path: Path) -> None:
        cache_home = tmp_path / "cache"

        self._probe(tmp_path, cache_home, level=None)

        assert not cache_home.exists()

    def test_writes_log_file_under_cache_home_not_working_directory(self, tmp_path: Path) -> None:
        """Keep the log file out of the working tree of whichever project Claude Code runs the hook in."""
        working_directory = tmp_path / "project"
        working_directory.mkdir()
        cache_home = tmp_path / "cache"

        self._probe(working_directory, cache_home, level="DEBUG")

        assert (cache_home / "hookbell" / "slack.log").is_file()
        assert not list(working_directory.iterdir())

    @pytest.mark.skipif(sys.platform == "win32", reason="Windows doesn't support POSIX permission bits.")
    def test_log_file_is_readable_only_by_its_owner(self, tmp_path: Path) -> None:
        cache_home = tmp_path / "cache"

        self._probe(tmp_path, cache_home, level="DEBUG")

        assert stat.S_IMODE((cache_home / "hookbell" / "slack.log").stat().st_mode) == 0o600  # noqa: PLR2004

    def _probe(self, cwd: Path, cache_home: Path, **kwargs: str | bool | None) -> dict[str, int]:
        """Run configure_logging(**kwargs) in a fresh interpreter and return the effective level of each logger.

        XDG_CACHE_HOME points at a test-owned directory so the probe never writes into the real user's ~/.cache.
        """
        # Reason: Every argv element is sys.executable, a constant of this class, or JSON-encoded test arguments, and
        # no shell is used, but Ruff can't trace the attribute references back to their constant values, and Bandit
        # flags every shell-less call regardless of the input:
        # - Ruff rules - subprocess-without-shell-equals-true (S603)
        #   https://docs.astral.sh/ruff/rules/subprocess-without-shell-equals-true/
        # - B603: Test for use of subprocess without shell equals true — Bandit documentation
        #   https://bandit.readthedocs.io/en/latest/plugins/b603_subprocess_without_shell_equals_true.html
        completed = subprocess.run(  # noqa: S603  # nosec B603
            [sys.executable, "-c", self.PROBE_SCRIPT, json.dumps(kwargs), "hookbell", *self.WIRE_TRACE_LOGGERS],
            capture_output=True,
            check=True,
            cwd=cwd,
            env={**os.environ, "XDG_CACHE_HOME": str(cache_home)},
            text=True,
        )
        effective_levels: dict[str, int] = json.loads(completed.stdout)
        return effective_levels
