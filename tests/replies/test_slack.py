# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.replies.slack."""

from __future__ import annotations

from email.message import Message
from typing import TYPE_CHECKING
from typing import Any
from urllib.error import HTTPError

import pytest

from hookbell.replies.slack import SlackReplyChannel
from hookbell.replies.slack_credentials import SlackCredentials

if TYPE_CHECKING:
    from tests.conftest import FakeClock
    from tests.conftest import FakeSlackWebApi

PARENT_TS = "1700000000.000100"
POSTED = {"ok": True, "ts": PARENT_TS}
PARENT_MESSAGE: dict[str, Any] = {"ts": PARENT_TS, "bot_id": "B0HOOKBELL", "text": "Claude stopped"}


def replies(*messages: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "messages": [PARENT_MESSAGE, *messages]}


def human_reply(text: str, ts: str = "1700000000.000200", user: str = "U0ALLOWED") -> dict[str, Any]:
    return {"ts": ts, "user": user, "text": text}


def rate_limited(retry_after: str) -> HTTPError:
    headers = Message()
    headers["Retry-After"] = retry_after
    return HTTPError("https://slack.com/api/conversations.replies", 429, "Too Many Requests", headers, None)


@pytest.fixture(name="channel")
def _channel_fixture() -> SlackReplyChannel:
    return SlackReplyChannel(SlackCredentials("xoxb-test-token", "C0123", "U0ALLOWED"))


class TestSlackReplyChannel:
    """Tests for SlackReplyChannel."""

    @pytest.mark.usefixtures("fake_clock")
    def test_ask_posts_the_text_and_returns_the_allowed_users_reply(
        self,
        channel: SlackReplyChannel,
        fake_slack_web_api: FakeSlackWebApi,
    ) -> None:
        """Post the text to the channel, then return the allowed user's reply from its thread."""
        fake_slack_web_api.queue("chat.postMessage", POSTED)
        fake_slack_web_api.queue("conversations.replies", replies(human_reply("Run the tests too")))

        reply = channel.ask("Claude stopped", timeout=60)

        assert reply is not None
        assert reply.text == "Run the tests too"
        assert fake_slack_web_api.params_of("chat.postMessage") == [{"channel": "C0123", "text": "Claude stopped"}]
        assert fake_slack_web_api.params_of("conversations.replies") == [{"channel": "C0123", "ts": PARENT_TS}]

    @pytest.mark.usefixtures("fake_clock")
    def test_ask_skips_replies_the_filter_rejects(
        self,
        channel: SlackReplyChannel,
        fake_slack_web_api: FakeSlackWebApi,
    ) -> None:
        """Skip replies the filter rejects and return the first one it accepts."""
        fake_slack_web_api.queue("chat.postMessage", POSTED)
        fake_slack_web_api.queue(
            "conversations.replies",
            replies(
                human_reply("from someone else", ts="1700000000.000150", user="U0OTHER"),
                human_reply("ok"),
            ),
        )

        reply = channel.ask("Claude stopped", timeout=60)

        assert reply is not None
        assert reply.text == "ok"

    def test_ask_polls_every_interval_until_a_reply_arrives(
        self,
        channel: SlackReplyChannel,
        fake_slack_web_api: FakeSlackWebApi,
        fake_clock: FakeClock,
    ) -> None:
        """Sleep one poll interval before every conversations.replies call until a reply arrives."""
        fake_slack_web_api.queue("chat.postMessage", POSTED)
        fake_slack_web_api.queue("conversations.replies", replies(), replies(), replies(human_reply("ok")))

        reply = channel.ask("Claude stopped", timeout=60)

        assert reply is not None
        assert fake_clock.sleeps == [SlackReplyChannel.POLL_INTERVAL_SECONDS] * 3

    def test_ask_returns_none_and_posts_a_notice_in_the_thread_on_timeout(
        self,
        channel: SlackReplyChannel,
        fake_slack_web_api: FakeSlackWebApi,
        fake_clock: FakeClock,
    ) -> None:
        """Return None at the deadline, cutting the last sleep short, and post the timeout notice in the thread."""
        fake_slack_web_api.queue("chat.postMessage", POSTED)
        fake_slack_web_api.queue("conversations.replies", replies())

        reply = channel.ask("Claude stopped", timeout=12)

        assert reply is None
        assert fake_clock.now == 12  # noqa: PLR2004
        assert fake_clock.sleeps == [5.0, 5.0, 2.0]
        assert fake_slack_web_api.params_of("chat.postMessage")[-1] == {
            "channel": "C0123",
            "text": SlackReplyChannel.TIMEOUT_NOTICE,
            "thread_ts": PARENT_TS,
        }

    def test_ask_returns_none_and_posts_a_notice_once_answered_elsewhere(
        self,
        channel: SlackReplyChannel,
        fake_slack_web_api: FakeSlackWebApi,
        fake_clock: FakeClock,
    ) -> None:
        """Stop waiting at the first poll after answered_elsewhere() turns True, and say so in the thread."""
        fake_slack_web_api.queue("chat.postMessage", POSTED)
        fake_slack_web_api.queue("conversations.replies", replies())
        answers = iter([False, True])

        reply = channel.ask("Claude stopped", timeout=60, answered_elsewhere=lambda: next(answers))

        assert reply is None
        assert fake_clock.sleeps == [5.0, 5.0]
        assert len(fake_slack_web_api.params_of("conversations.replies")) == 1
        assert fake_slack_web_api.params_of("chat.postMessage")[-1] == {
            "channel": "C0123",
            "text": SlackReplyChannel.ANSWERED_ELSEWHERE_NOTICE,
            "thread_ts": PARENT_TS,
        }

    def test_ask_waits_for_retry_after_when_rate_limited(
        self,
        channel: SlackReplyChannel,
        fake_slack_web_api: FakeSlackWebApi,
        fake_clock: FakeClock,
    ) -> None:
        """Wait for Slack's Retry-After before the next poll after an HTTP 429."""
        fake_slack_web_api.queue("chat.postMessage", POSTED)
        fake_slack_web_api.queue("conversations.replies", rate_limited("20"), replies(human_reply("ok")))

        reply = channel.ask("Claude stopped", timeout=60)

        assert reply is not None
        assert fake_clock.sleeps == [5.0, 20.0]

    @pytest.mark.usefixtures("fake_clock")
    def test_ask_unescapes_slack_message_text(
        self,
        channel: SlackReplyChannel,
        fake_slack_web_api: FakeSlackWebApi,
    ) -> None:
        """Undo Slack's &lt; &gt; &amp; escapes in the reply text."""
        fake_slack_web_api.queue("chat.postMessage", POSTED)
        fake_slack_web_api.queue("conversations.replies", replies(human_reply("use a &lt;b&gt; tag &amp; retry")))

        reply = channel.ask("Claude stopped", timeout=60)

        assert reply is not None
        assert reply.text == "use a <b> tag & retry"

    @pytest.mark.usefixtures("slack_bot_settings")
    def test_from_environment_reads_the_credentials(self) -> None:
        assert SlackReplyChannel.from_environment().credentials.channel_id == "C0123"
