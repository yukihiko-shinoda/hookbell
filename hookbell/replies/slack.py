# Copyright (c) 2026 Yukihiko Shinoda
"""Slack reply channel: posts with a bot token and polls the thread for a reply."""

from __future__ import annotations

import json
from logging import getLogger
from time import monotonic
from time import sleep
from typing import TYPE_CHECKING

from hookbell.replies.base import Reply
from hookbell.replies.base import ReplyChannel
from hookbell.replies.base import never
from hookbell.replies.reply_filter import ReplyFilter
from hookbell.replies.slack_credentials import SlackCredentials
from hookbell.replies.slack_web_api import SlackApiError
from hookbell.replies.slack_web_api import SlackRateLimitedError
from hookbell.replies.slack_web_api import SlackWebApi
from hookbell.slack_markdown import SlackMarkdown

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any


class SlackReplyChannel(ReplyChannel):
    """Posts a message to a Slack channel and waits for the allowed user's reply in its thread.

    It polls conversations.replies instead of listening on Socket Mode: Socket Mode delivers each event to only one of
    the app's open connections, so a session waiting in parallel could receive, and lose, another session's reply.
    """

    # conversations.replies is a Tier 3 method (about 50 calls per minute), shared by every session waiting at once.
    POLL_INTERVAL_SECONDS = 5.0
    TIMEOUT_NOTICE = "Timed out waiting for a reply. Answer in the terminal instead."
    ANSWERED_ELSEWHERE_NOTICE = "Answered in the terminal, so this thread no longer takes a reply."
    # Slack's name for the 👍 emoji.
    ACKNOWLEDGEMENT_REACTION = "+1"

    def __init__(self, credentials: SlackCredentials, web_api: SlackWebApi | None = None) -> None:
        self.credentials = credentials
        self.web_api = web_api or SlackWebApi(credentials.bot_token)
        self.logger = getLogger(__name__)

    @classmethod
    def is_configured(cls) -> bool:
        """Return whether every setting this channel needs is available."""
        return SlackCredentials.is_configured()

    @classmethod
    def from_environment(cls) -> SlackReplyChannel:
        """Build a SlackReplyChannel from the Docker secret and the environment variables."""
        return cls(SlackCredentials.from_environment())

    def ask(self, text: str, timeout: float, answered_elsewhere: Callable[[], bool] = never) -> Reply | None:
        """Post text, then return the first accepted reply in its thread.

        Return None instead after timeout seconds, or once answered_elsewhere() returns True, posting a notice in the
        thread that says why it no longer takes a reply.
        """
        parent_ts = self._post(text)
        outcome = self._wait(ReplyFilter(parent_ts, self.credentials.allowed_user_id), timeout, answered_elsewhere)
        if isinstance(outcome, Reply):
            return outcome
        self._post(outcome, thread_ts=parent_ts)
        return None

    def _post(self, text: str, **params: str) -> str:
        response = self.web_api.call(
            "chat.postMessage",
            channel=self.credentials.channel_id,
            text=text,
            blocks=json.dumps(SlackMarkdown(text).blocks),
            **params,
        )
        return str(response["ts"])

    def _wait(self, reply_filter: ReplyFilter, timeout: float, answered_elsewhere: Callable[[], bool]) -> Reply | str:
        """Return the accepted reply, or the notice to post in the thread when the wait ends without one."""
        deadline = monotonic() + timeout
        delay = self.POLL_INTERVAL_SECONDS
        while self._sleep_before_poll(delay, deadline):
            if answered_elsewhere():
                return self.ANSWERED_ELSEWHERE_NOTICE
            try:
                reply = self._find_reply(reply_filter)
            except SlackRateLimitedError as error:
                self.logger.warning("%s", error)
                delay = max(error.retry_after, self.POLL_INTERVAL_SECONDS)
                continue
            if reply is not None:
                return reply
            delay = self.POLL_INTERVAL_SECONDS
        return self.TIMEOUT_NOTICE

    @staticmethod
    def _sleep_before_poll(delay: float, deadline: float) -> bool:
        """Sleep for delay, cut short at deadline, and return False once the deadline has already passed."""
        remaining = deadline - monotonic()
        if remaining <= 0:
            return False
        sleep(min(delay, remaining))
        return True

    def _find_reply(self, reply_filter: ReplyFilter) -> Reply | None:
        response = self.web_api.call(
            "conversations.replies",
            channel=self.credentials.channel_id,
            ts=reply_filter.parent_ts,
        )
        messages: list[dict[str, Any]] = response.get("messages", [])
        for message in messages:
            if reply_filter.matches(message):
                self.logger.debug("reply: %s", message.get("text"))
                self._acknowledge(str(message.get("ts", "")))
                return Reply(self._unescape(str(message.get("text", ""))))
        return None

    def _acknowledge(self, message_ts: str) -> None:
        """React to the accepted reply so the user sees in Slack that hookbell received it.

        The reaction is best-effort: a failure, such as a bot token without the reactions:write scope, is only logged, so
        it never costs the reply itself.
        """
        try:
            self.web_api.call(
                "reactions.add",
                channel=self.credentials.channel_id,
                timestamp=message_ts,
                name=self.ACKNOWLEDGEMENT_REACTION,
            )
        except (SlackApiError, SlackRateLimitedError, OSError):
            self.logger.warning("Failed to react to the reply", exc_info=True)

    @staticmethod
    def _unescape(text: str) -> str:
        """Undo the only three escapes Slack applies to message text.

        See: https://docs.slack.dev/messaging/formatting-message-text#escaping
        """
        return text.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
