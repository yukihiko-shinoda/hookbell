# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.replies.reply_filter."""

from __future__ import annotations

from typing import Any

import pytest

from hookbell.replies.reply_filter import ReplyFilter

PARENT_TS = "1700000000.000100"
HUMAN_REPLY: dict[str, Any] = {"ts": "1700000000.000200", "user": "U0ALLOWED", "text": "ok"}


class TestReplyFilter:
    """Tests for ReplyFilter."""

    def test_matches_a_reply_from_the_allowed_user(self) -> None:
        assert ReplyFilter(PARENT_TS, "U0ALLOWED").matches(HUMAN_REPLY) is True

    @pytest.mark.parametrize(
        "message",
        [
            pytest.param({**HUMAN_REPLY, "ts": PARENT_TS}, id="parent message itself"),
            pytest.param({**HUMAN_REPLY, "ts": "1700000000.000099"}, id="older than the parent"),
            pytest.param({**HUMAN_REPLY, "user": "U0OTHER"}, id="another user"),
            pytest.param({k: v for k, v in HUMAN_REPLY.items() if k != "user"}, id="no user"),
            pytest.param({**HUMAN_REPLY, "bot_id": "B0123"}, id="bot post"),
            pytest.param({**HUMAN_REPLY, "subtype": "thread_broadcast"}, id="message with subtype"),
        ],
    )
    def test_rejects(self, message: dict[str, Any]) -> None:
        """Reject every message that isn't a human reply from the allowed user after the parent."""
        assert ReplyFilter(PARENT_TS, "U0ALLOWED").matches(message) is False

    def test_compares_ts_exactly_beyond_float_precision(self) -> None:
        """Tell apart ts values that differ only in the last microsecond digit, which a float can't hold exactly."""
        reply_filter = ReplyFilter("1700000000.000001", "U0ALLOWED")

        assert reply_filter.matches({**HUMAN_REPLY, "ts": "1700000000.000002"}) is True
