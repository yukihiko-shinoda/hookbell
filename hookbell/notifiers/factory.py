# Copyright (c) 2026 Yukihiko Shinoda
"""Resolves which configured notifier backend to notify through."""

from __future__ import annotations

from typing import TYPE_CHECKING

from hookbell.notifiers.slack import SlackNotifier
from hookbell.notifiers.sns import SnsNotifier

if TYPE_CHECKING:
    from hookbell.notifiers.base import Notifier


class NotifierFactory:
    """Picks the one notifier backend configured in the environment."""

    @classmethod
    def from_environment(cls) -> Notifier:
        """Return the configured Notifier, raising when both or neither backend is configured."""
        if SlackNotifier.is_configured() and SnsNotifier.is_configured():
            message = (
                "Both a Slack webhook URL and an SNS topic ARN are configured; "
                "hookbell notifies through exactly one destination, so unset one of them."
            )
            raise ValueError(message)
        if SnsNotifier.is_configured():
            return SnsNotifier.from_environment()
        return SlackNotifier.from_environment()
