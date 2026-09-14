# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.notifiers.sns."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import boto3
from botocore.stub import Stubber

from hookbell.notifiers.sns import SnsNotifier

if TYPE_CHECKING:
    from pathlib import Path

    import pytest
    from pytest_mock import MockerFixture

TOPIC_ARN = "arn:aws:sns:us-east-1:123456789012:hookbell"


class TestSnsNotifierFromEnvironment:
    """Tests for SnsNotifier.from_environment."""

    def test_uses_environment_variables_when_secret_files_are_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Read both the topic ARN and the profile name from the environment."""
        monkeypatch.setenv("HOOKBELL_SNS_TOPIC_ARN", TOPIC_ARN)
        monkeypatch.setenv("HOOKBELL_AWS_PROFILE", "hookbell-profile")

        notifier = SnsNotifier.from_environment()

        assert notifier.topic_arn == TOPIC_ARN
        assert notifier.profile_name == "hookbell-profile"

    def test_leaves_profile_name_none_when_no_profile_secret_or_variable_is_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Leave profile_name None so boto3 falls back to its own default credential resolution."""
        monkeypatch.setenv("HOOKBELL_SNS_TOPIC_ARN", TOPIC_ARN)
        monkeypatch.delenv("HOOKBELL_AWS_PROFILE", raising=False)

        notifier = SnsNotifier.from_environment()

        assert notifier.profile_name is None

    def test_prefers_the_docker_secret_files_over_the_environment_variables(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        """Read the Docker secret files when they exist, ignoring the environment variables."""
        monkeypatch.setenv("HOOKBELL_SNS_TOPIC_ARN", "arn:aws:sns:us-east-1:123456789012:env-topic")
        monkeypatch.setenv("HOOKBELL_AWS_PROFILE", "env-profile")
        topic_arn_path = tmp_path / "hookbell-sns-topic-arn"
        topic_arn_path.write_text(f"{TOPIC_ARN}\n", encoding="utf-8")
        profile_path = tmp_path / "hookbell-aws-profile"
        profile_path.write_text("secret-profile\n", encoding="utf-8")
        monkeypatch.setattr(SnsNotifier, "TOPIC_ARN_SECRET_PATH", topic_arn_path)
        monkeypatch.setattr(SnsNotifier, "AWS_PROFILE_SECRET_PATH", profile_path)

        notifier = SnsNotifier.from_environment()

        assert notifier.topic_arn == TOPIC_ARN
        assert notifier.profile_name == "secret-profile"


class TestSnsNotifierIsConfigured:
    """Tests for SnsNotifier.is_configured."""

    def test_returns_false_when_neither_secret_nor_variable_is_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("HOOKBELL_SNS_TOPIC_ARN", raising=False)

        assert SnsNotifier.is_configured() is False

    def test_returns_true_when_the_environment_variable_is_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOOKBELL_SNS_TOPIC_ARN", TOPIC_ARN)

        assert SnsNotifier.is_configured() is True


class TestSnsNotifierNotify:
    """Tests for SnsNotifier.notify."""

    def test_publishes_text_as_an_aws_chatbot_custom_notification(self, mocker: MockerFixture) -> None:
        """Publish text wrapped in the AWS Chatbot custom notification schema, using the configured profile."""
        notifier = SnsNotifier(topic_arn=TOPIC_ARN, profile_name="hookbell-profile")
        client = boto3.client("sns", region_name="us-east-1")
        stubber = Stubber(client)
        expected_message = json.dumps(
            {
                "version": "1.0",
                "source": "custom",
                "content": {"textType": "client-markdown", "description": "Hello world"},
            },
        )
        stubber.add_response(
            "publish",
            {"MessageId": "11111111-1111-1111-1111-111111111111"},
            {"TopicArn": TOPIC_ARN, "Message": expected_message},
        )
        stubber.activate()
        session = mocker.patch("hookbell.notifiers.sns.boto3.Session")
        session.return_value.client.return_value = client

        notifier.notify("Hello world")

        session.assert_called_once_with(profile_name="hookbell-profile")
        stubber.assert_no_pending_responses()
