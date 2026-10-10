# Copyright (c) 2026 Yukihiko Shinoda
"""Decides which messages in a Slack thread count as the awaited reply."""

from __future__ import annotations

from decimal import Decimal
from typing import Any


class ReplyFilter:
    """Accepts only a human reply from the allowed user, posted after the thread's parent message."""

    def __init__(self, parent_ts: str, allowed_user_id: str) -> None:
        self.parent_ts = parent_ts
        self.allowed_user_id = allowed_user_id

    def matches(self, message: dict[str, Any]) -> bool:
        """Return whether message is a reply this filter accepts.

        conversations.replies also returns the parent message itself, so the ts comparison excludes it. A bot_id marks
        a bot's post (including hookbell's own), and any subtype marks an edit, a join, a file share, or another non-
        plain message.
        """
        return (
            # Decimal keeps ts values such as "1700000000.000100" exact, which float would round.
            Decimal(str(message.get("ts", "0"))) > Decimal(self.parent_ts)
            and message.get("user") == self.allowed_user_id
            and "bot_id" not in message
            and "subtype" not in message
        )
