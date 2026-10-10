# Copyright (c) 2026 Yukihiko Shinoda
"""Minimal Slack Web API client authenticated with a bot token."""

from __future__ import annotations

import json
import ssl
from typing import Any
from urllib import parse
from urllib import request
from urllib.error import HTTPError

import certifi

HTTP_TOO_MANY_REQUESTS = 429


class SlackApiError(Exception):
    """Slack answered a Web API call with "ok": false."""


class SlackRateLimitedError(Exception):
    """Slack rejected a Web API call with HTTP 429."""

    def __init__(self, retry_after: float) -> None:
        super().__init__(f"Rate limited by Slack; retry after {retry_after} seconds")
        self.retry_after = retry_after


class SlackWebApi:
    """Calls Slack Web API methods with a bot token."""

    BASE_URL = "https://slack.com/api/"
    REQUEST_TIMEOUT_SECONDS = 30

    def __init__(self, bot_token: str) -> None:
        self.bot_token = bot_token

    def call(self, method: str, **params: str) -> dict[str, Any]:
        """Call a Web API method with form-encoded params and return its JSON response.

        Raises:
            SlackRateLimitedError: Slack responded with HTTP 429.
            SlackApiError: Slack responded with "ok": false.
        """
        # Reason: The URL is always the BASE_URL constant (https://slack.com/api/) followed by a method name hard-coded
        # by this package's callers -- never untrusted external input -- so the file:/custom-scheme risk this rule
        # targets can't occur. Ruff and Bandit still flag every call, since they do no data-flow analysis:
        # - Ruff Rule S310: suspicious-url-open-usage
        #   https://docs.astral.sh/ruff/rules/suspicious-url-open-usage/
        # - Bandit B310: urllib urlopen
        #   https://bandit.readthedocs.io/en/1.9.4/blacklists/blacklist_calls.html#b310-urllib-urlopen
        # - Issue: Avoid raising S310 if user explicitly checks for URL scheme
        #   https://github.com/astral-sh/ruff/issues/7918
        req = request.Request(  # noqa: S310
            self.BASE_URL + method,
            data=parse.urlencode(params).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.bot_token}",
                "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            },
        )
        body = self._send(req)
        if not body.get("ok"):
            # The error code (e.g. "channel_not_found") never contains the token.
            message = f"Slack {method} failed: {body.get('error', 'unknown_error')}"
            raise SlackApiError(message)
        return body

    def _send(self, req: request.Request) -> dict[str, Any]:
        ssl_context = ssl.create_default_context(cafile=certifi.where())
        try:
            # Reason: same constant https:// URL as the request.Request() call in call() above.
            with request.urlopen(  # noqa: S310  # nosec B310
                req,
                context=ssl_context,
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            ) as response:
                body: dict[str, Any] = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == HTTP_TOO_MANY_REQUESTS:
                raise SlackRateLimitedError(float(error.headers.get("Retry-After", "1"))) from error
            raise
        return body
