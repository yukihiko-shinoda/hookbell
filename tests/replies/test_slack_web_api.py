# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.replies.slack_web_api."""

from __future__ import annotations

from email.message import Message
from typing import TYPE_CHECKING
from urllib.error import HTTPError

import pytest

from hookbell.replies.slack_web_api import SlackApiError
from hookbell.replies.slack_web_api import SlackRateLimitedError
from hookbell.replies.slack_web_api import SlackWebApi

if TYPE_CHECKING:
    from tests.conftest import FakeSlackWebApi


def http_error(code: int, headers: dict[str, str]) -> HTTPError:
    message = Message()
    for name, value in headers.items():
        message[name] = value
    return HTTPError("https://slack.com/api/chat.postMessage", code, "error", message, None)


class TestSlackWebApi:
    """Tests for SlackWebApi."""

    def test_call_posts_form_params_with_the_bot_token(self, fake_slack_web_api: FakeSlackWebApi) -> None:
        """Send params form-encoded with the bot token as a Bearer authorization header."""
        fake_slack_web_api.queue("chat.postMessage", {"ok": True, "ts": "1.2"})

        response = SlackWebApi("xoxb-test-token").call("chat.postMessage", channel="C0123", text="こんにちは")

        assert response == {"ok": True, "ts": "1.2"}
        assert fake_slack_web_api.calls == [("chat.postMessage", {"channel": "C0123", "text": "こんにちは"})]
        assert fake_slack_web_api.authorization_headers == ["Bearer xoxb-test-token"]

    def test_call_raises_slack_api_error_on_ok_false(self, fake_slack_web_api: FakeSlackWebApi) -> None:
        fake_slack_web_api.queue("chat.postMessage", {"ok": False, "error": "channel_not_found"})

        with pytest.raises(SlackApiError, match="channel_not_found") as error_info:
            SlackWebApi("xoxb-test-token").call("chat.postMessage", channel="C0123")

        assert "xoxb" not in str(error_info.value)

    def test_call_raises_rate_limited_error_with_retry_after_on_429(self, fake_slack_web_api: FakeSlackWebApi) -> None:
        fake_slack_web_api.queue("conversations.replies", http_error(429, {"Retry-After": "30"}))

        with pytest.raises(SlackRateLimitedError) as error_info:
            SlackWebApi("xoxb-test-token").call("conversations.replies", channel="C0123", ts="1.2")

        assert error_info.value.retry_after == 30.0  # noqa: PLR2004

    def test_call_reraises_other_http_errors(self, fake_slack_web_api: FakeSlackWebApi) -> None:
        fake_slack_web_api.queue("chat.postMessage", http_error(500, {}))

        with pytest.raises(HTTPError):
            SlackWebApi("xoxb-test-token").call("chat.postMessage", channel="C0123")
