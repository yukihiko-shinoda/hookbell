# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.notifiers.factory."""

from __future__ import annotations

import pytest

from hookbell.notifiers.factory import NotifierFactory
from hookbell.notifiers.slack import SlackNotifier
from hookbell.notifiers.sns import SnsNotifier


class TestNotifierFactoryFromEnvironment:
    """Tests for NotifierFactory.from_environment."""

    def test_returns_a_slack_notifier_when_only_slack_is_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T000/B000/XXX")
        monkeypatch.delenv("HOOKBELL_SNS_TOPIC_ARN", raising=False)

        notifier = NotifierFactory.from_environment()

        assert isinstance(notifier, SlackNotifier)

    def test_returns_an_sns_notifier_when_only_sns_is_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        monkeypatch.setenv("HOOKBELL_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:hookbell")

        notifier = NotifierFactory.from_environment()

        assert isinstance(notifier, SnsNotifier)

    def test_raises_when_both_slack_and_sns_are_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/services/T000/B000/XXX")
        monkeypatch.setenv("HOOKBELL_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:hookbell")

        with pytest.raises(ValueError, match="exactly one destination"):
            NotifierFactory.from_environment()

    def test_raises_when_neither_is_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        monkeypatch.delenv("HOOKBELL_SNS_TOPIC_ARN", raising=False)

        with pytest.raises(KeyError):
            NotifierFactory.from_environment()
