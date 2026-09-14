# Copyright (c) 2026 Yukihiko Shinoda
"""Slack notification backend."""

from __future__ import annotations

import json
import os
import ssl
from logging import getLogger
from pathlib import Path
from typing import ClassVar
from urllib import request

import certifi

from hookbell.notifiers.base import Notifier


class SlackNotifier(Notifier):
    """Posts a notification to Slack via an incoming webhook."""

    HEADERS: ClassVar[dict[str, str]] = {"Content-Type": "application/json"}
    WEBHOOK_URL_SECRET_PATH = Path("/run/secrets/slack_webhook_url")
    WEBHOOK_URL_ENVIRONMENT_VARIABLE = "SLACK_WEBHOOK_URL"

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self.logger = getLogger(__name__)

    @classmethod
    def is_configured(cls) -> bool:
        """Return whether a webhook URL is available from either the secret file or the environment."""
        return cls.WEBHOOK_URL_SECRET_PATH.exists() or cls.WEBHOOK_URL_ENVIRONMENT_VARIABLE in os.environ

    @classmethod
    def from_environment(cls) -> SlackNotifier:
        """Build a SlackNotifier from the Docker secret, falling back to the environment variable."""
        if cls.WEBHOOK_URL_SECRET_PATH.exists():
            return cls(webhook_url=cls.WEBHOOK_URL_SECRET_PATH.read_text(encoding="utf-8").strip())
        return cls(webhook_url=os.environ[cls.WEBHOOK_URL_ENVIRONMENT_VARIABLE])

    def notify(self, text: str) -> None:
        """Post text to Slack as a single section block."""
        if not self.webhook_url.startswith("https://"):
            message = f"Slack webhook URL must use https://, got: {self.webhook_url!r}"
            raise ValueError(message)
        data = {"blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": text}}]}
        # Reason: self.webhook_url is only ever populated by from_environment() above, from an
        # operator-configured Docker secret file or the SLACK_WEBHOOK_URL environment variable --
        # never from untrusted external input -- and the https:// scheme check right above rules
        # out the file:/custom-scheme risk this rule targets. Ruff still flags the call even with
        # that check in place, since it does no control-flow analysis:
        # - Ruff Rule S310: suspicious-url-open-usage
        #   https://docs.astral.sh/ruff/rules/suspicious-url-open-usage/
        # - Bandit B310: urllib urlopen
        #   https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_calls.html#b310-urllib-urlopen
        # - Issue: Avoid raising S310 if user explicitly checks for URL scheme
        #   https://github.com/astral-sh/ruff/issues/7918
        req = request.Request(  # noqa: S310
            self.webhook_url,
            data=json.dumps(data).encode("utf-8"),
            headers=self.HEADERS,
        )
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        with request.urlopen(req, context=ssl_context) as response:  # noqa: S310  # nosec B310
            response_data = response.read().decode("utf-8")
            self.logger.debug("response_data: %s", response_data)
