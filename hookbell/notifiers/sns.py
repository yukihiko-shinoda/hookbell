# Copyright (c) 2026 Yukihiko Shinoda
"""Amazon SNS notification backend."""

from __future__ import annotations

import json
import os
from logging import getLogger
from pathlib import Path

import boto3

from hookbell.notifiers.base import Notifier


class SnsNotifier(Notifier):
    """Publishes a notification to an Amazon SNS topic as an AWS Chatbot custom notification.

    See the event schema AWS Chatbot requires of a custom notification published to SNS:
    https://docs.aws.amazon.com/chatbot/latest/adminguide/custom-notifs.html#event-schema
    """

    TOPIC_ARN_SECRET_PATH = Path("/run/secrets/hookbell_sns_topic_arn")
    AWS_PROFILE_SECRET_PATH = Path("/run/secrets/hookbell_aws_profile")
    TOPIC_ARN_ENVIRONMENT_VARIABLE = "HOOKBELL_SNS_TOPIC_ARN"
    AWS_PROFILE_ENVIRONMENT_VARIABLE = "HOOKBELL_AWS_PROFILE"

    def __init__(self, topic_arn: str, profile_name: str | None = None) -> None:
        self.topic_arn = topic_arn
        self.profile_name = profile_name
        self.logger = getLogger(__name__)

    @classmethod
    def is_configured(cls) -> bool:
        """Return whether an SNS topic ARN is available from either the secret file or the environment."""
        return cls.TOPIC_ARN_SECRET_PATH.exists() or cls.TOPIC_ARN_ENVIRONMENT_VARIABLE in os.environ

    @classmethod
    def from_environment(cls) -> SnsNotifier:
        """Build an SnsNotifier from the Docker secrets, falling back to the environment variables."""
        return cls(topic_arn=cls._read_topic_arn(), profile_name=cls._read_profile_name())

    @classmethod
    def _read_topic_arn(cls) -> str:
        if cls.TOPIC_ARN_SECRET_PATH.exists():
            return cls.TOPIC_ARN_SECRET_PATH.read_text(encoding="utf-8").strip()
        return os.environ[cls.TOPIC_ARN_ENVIRONMENT_VARIABLE]

    @classmethod
    def _read_profile_name(cls) -> str | None:
        if cls.AWS_PROFILE_SECRET_PATH.exists():
            return cls.AWS_PROFILE_SECRET_PATH.read_text(encoding="utf-8").strip()
        return os.environ.get(cls.AWS_PROFILE_ENVIRONMENT_VARIABLE)

    def notify(self, text: str) -> None:
        """Publish text to the SNS topic as an AWS Chatbot custom notification."""
        payload = {
            "version": "1.0",
            "source": "custom",
            "content": {"textType": "client-markdown", "description": text},
        }
        client = boto3.Session(profile_name=self.profile_name).client("sns")
        response = client.publish(TopicArn=self.topic_arn, Message=json.dumps(payload))
        self.logger.debug("response: %s", response)
