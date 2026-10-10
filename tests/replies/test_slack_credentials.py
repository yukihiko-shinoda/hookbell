# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.replies.slack_credentials."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from hookbell.replies.slack_credentials import SlackCredentials

if TYPE_CHECKING:
    from pathlib import Path


class TestSlackCredentials:
    """Tests for SlackCredentials."""

    @pytest.mark.usefixtures("slack_bot_settings")
    def test_from_environment_reads_the_environment_variables(self) -> None:
        credentials = SlackCredentials.from_environment()

        assert credentials.bot_token == os.environ["SLACK_BOT_TOKEN"]
        assert credentials.channel_id == "C0123"
        assert credentials.allowed_user_id == "U0ALLOWED"

    @pytest.mark.usefixtures("slack_bot_settings")
    def test_from_environment_prefers_the_docker_secret_over_the_environment_variable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Read the Docker secret file when it exists, ignoring the environment variable."""
        secret_path = tmp_path / "slack_bot_token"
        secret_path.write_text("xoxb-from-secret\n", encoding="utf-8")
        monkeypatch.setattr(SlackCredentials.BOT_TOKEN, "secret_path", secret_path)

        assert SlackCredentials.from_environment().bot_token == secret_path.read_text(encoding="utf-8").strip()

    @pytest.mark.usefixtures("slack_bot_settings")
    def test_from_environment_reads_the_channel_and_user_from_docker_secrets(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Read the channel ID and the allowed user ID from Docker secrets over environment variables."""
        for setting, value in (
            (SlackCredentials.CHANNEL_ID, "C9SECRET"),
            (SlackCredentials.ALLOWED_USER_ID, "U9SECRET"),
        ):
            secret_path = tmp_path / setting.environment_variable.lower()
            secret_path.write_text(f"{value}\n", encoding="utf-8")
            monkeypatch.setattr(setting, "secret_path", secret_path)

        credentials = SlackCredentials.from_environment()

        assert credentials.channel_id == "C9SECRET"
        assert credentials.allowed_user_id == "U9SECRET"

    @pytest.mark.usefixtures("slack_bot_settings")
    def test_is_configured_when_every_setting_is_available(self) -> None:
        assert SlackCredentials.is_configured() is True

    @pytest.mark.usefixtures("slack_bot_settings")
    @pytest.mark.parametrize(
        "missing",
        ["SLACK_BOT_TOKEN", "HOOKBELL_SLACK_CHANNEL_ID", "HOOKBELL_SLACK_ALLOWED_USER_ID"],
    )
    def test_is_not_configured_when_a_setting_is_missing(self, monkeypatch: pytest.MonkeyPatch, missing: str) -> None:
        """Report unconfigured when any one of the three settings is missing."""
        monkeypatch.delenv(missing)

        assert SlackCredentials.is_configured() is False

    def test_repr_hides_the_bot_token(self) -> None:
        assert "xoxb" not in repr(SlackCredentials("xoxb-secret", "C0123", "U0ALLOWED"))
