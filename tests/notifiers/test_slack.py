# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.notifiers.slack."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from hookbell.notifiers.slack import SlackNotifier

if TYPE_CHECKING:
    from pathlib import Path

    from pytest_mock import MockerFixture


class TestSlackNotifierFromEnvironment:
    """Tests for SlackNotifier.from_environment."""

    def test_uses_environment_variable_when_secret_file_is_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T000/B000/XXX")

        notifier = SlackNotifier.from_environment()

        assert notifier.webhook_url == "https://hooks.slack.com/services/T000/B000/XXX"

    def test_prefers_the_docker_secret_file_over_the_environment_variable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Read the Docker secret file when it exists, ignoring the environment variable."""
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T000/B000/XXX")
        secret_path = tmp_path / "slack_webhook_url"
        secret_path.write_text("https://hooks.slack.com/services/T111/B111/YYY\n", encoding="utf-8")
        monkeypatch.setattr(SlackNotifier, "WEBHOOK_URL_SECRET_PATH", secret_path)

        notifier = SlackNotifier.from_environment()

        assert notifier.webhook_url == "https://hooks.slack.com/services/T111/B111/YYY"


class TestSlackNotifierIsConfigured:
    """Tests for SlackNotifier.is_configured."""

    def test_returns_false_when_neither_secret_nor_variable_is_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

        assert SlackNotifier.is_configured() is False

    def test_returns_true_when_the_environment_variable_is_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T000/B000/XXX")

        assert SlackNotifier.is_configured() is True


class TestSlackNotifierNotify:
    """Tests for SlackNotifier.notify."""

    def test_posts_text_as_a_single_slack_section_block(self, mocker: MockerFixture) -> None:
        """Post the given text as a single Slack Block Kit section."""
        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/services/T000/B000/XXX")
        urlopen = mocker.patch("hookbell.notifiers.slack.request.urlopen")
        urlopen.return_value.__enter__.return_value.read.return_value = b"ok"

        notifier.notify("Hello world")

        posted_request = urlopen.call_args.args[0]
        assert posted_request.full_url == "https://hooks.slack.com/services/T000/B000/XXX"
        posted_data = json.loads(posted_request.data.decode("utf-8"))
        assert posted_data == {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "Hello world"}}]}

    def test_rejects_a_non_https_webhook_url(self) -> None:
        notifier = SlackNotifier(webhook_url="file:///etc/passwd")

        with pytest.raises(ValueError, match="https://"):
            notifier.notify("Hello world")
