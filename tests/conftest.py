# Copyright (c) 2026 Yukihiko Shinoda
"""Configuration of pytest."""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING
from typing import Any
from urllib import parse

import pytest

from hookbell.notifiers.slack import SlackNotifier
from hookbell.notifiers.sns import SnsNotifier
from hookbell.replies.slack_credentials import SlackCredentials

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Iterator
    from pathlib import Path
    from unittest.mock import MagicMock
    from urllib import request

    from pytest_mock import MockerFixture

SETTING_ENVIRONMENT_VARIABLE = "HOOKBELL_TEST_SETTING"


class FakeSlackWebApi:
    """Answers urlopen() calls to the Slack Web API from responses queued per method, recording every call."""

    def __init__(self, mocker: MockerFixture) -> None:
        self.mocker = mocker
        self.responses: dict[str, list[dict[str, Any] | Exception]] = {}
        self.calls: list[tuple[str, dict[str, str]]] = []
        self.authorization_headers: list[str | None] = []

    def queue(self, method: str, *responses: dict[str, Any] | Exception) -> None:
        """Queue responses for method in order; the last one keeps answering once the others are used up."""
        self.responses.setdefault(method, []).extend(responses)

    def params_of(self, method: str) -> list[dict[str, str]]:
        return [params for called_method, params in self.calls if called_method == method]

    def urlopen(self, req: request.Request, **_kwargs: object) -> MagicMock:
        """Return a context manager whose response body is the next queued response for the requested method."""
        method = req.full_url.rsplit("/", 1)[-1]
        data = req.data if isinstance(req.data, bytes) else b""
        self.calls.append((method, dict(parse.parse_qsl(data.decode("utf-8")))))
        self.authorization_headers.append(req.get_header("Authorization"))
        queued = self.responses[method]
        response = queued.pop(0) if len(queued) > 1 else queued[0]
        if isinstance(response, Exception):
            raise response
        context_manager: MagicMock = self.mocker.MagicMock()
        context_manager.__enter__.return_value.read.return_value = json.dumps(response).encode("utf-8")
        return context_manager


class FakeClock:
    """A monotonic clock that only advances when sleep() is called.

    Callbacks added to during_next_sleep run once in the next sleep(), standing in for what happens elsewhere while the
    code under test waits.
    """

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []
        self.during_next_sleep: list[Callable[[], None]] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds
        callbacks, self.during_next_sleep = self.during_next_sleep, []
        for callback in callbacks:
            callback()


@pytest.fixture(autouse=True)
def _isolate_cache_home(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Point XDG_CACHE_HOME at a location tests control so hookbell's log file never lands in the real ~/.cache."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path_factory.mktemp("cache")))


@pytest.fixture(autouse=True)
def _restore_hookbell_logger_level() -> Iterator[None]:
    """Undo the level main()'s --log-level sets on the hookbell logger, which would otherwise leak across tests."""
    logger = logging.getLogger("hookbell")
    level = logger.level
    yield
    logger.setLevel(level)


@pytest.fixture(autouse=True)
def _isolate_slack_webhook_secret_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Point the Docker secret path at a location tests control instead of a real host file."""
    unused_path = tmp_path_factory.mktemp("run-secrets") / "slack_webhook_url"
    monkeypatch.setattr(SlackNotifier, "WEBHOOK_URL_SECRET_PATH", unused_path)


@pytest.fixture(autouse=True)
def _isolate_sns_secret_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Point the Docker secret paths at locations tests control instead of real host files."""
    run_secrets = tmp_path_factory.mktemp("run-secrets")
    monkeypatch.setattr(SnsNotifier, "TOPIC_ARN_SECRET_PATH", run_secrets / "hookbell_sns_topic_arn")
    monkeypatch.setattr(SnsNotifier, "AWS_PROFILE_SECRET_PATH", run_secrets / "hookbell_aws_profile")


@pytest.fixture(autouse=True)
def _isolate_slack_bot_settings(monkeypatch: pytest.MonkeyPatch, tmp_path_factory: pytest.TempPathFactory) -> None:
    """Start every test with no Slack bot settings, whatever the host's secret files and environment hold."""
    run_secrets = tmp_path_factory.mktemp("run-secrets")
    for setting in (SlackCredentials.BOT_TOKEN, SlackCredentials.CHANNEL_ID, SlackCredentials.ALLOWED_USER_ID):
        monkeypatch.setattr(setting, "secret_path", run_secrets / setting.environment_variable.lower())
        monkeypatch.delenv(setting.environment_variable, raising=False)


@pytest.fixture
def slack_bot_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test-token")
    monkeypatch.setenv("HOOKBELL_SLACK_CHANNEL_ID", "C0123")
    monkeypatch.setenv("HOOKBELL_SLACK_ALLOWED_USER_ID", "U0ALLOWED")


@pytest.fixture
def fake_slack_web_api(mocker: MockerFixture) -> FakeSlackWebApi:
    fake = FakeSlackWebApi(mocker)
    mocker.patch("hookbell.replies.slack_web_api.request.urlopen", side_effect=fake.urlopen)
    return fake


@pytest.fixture
def fake_clock(mocker: MockerFixture) -> FakeClock:
    clock = FakeClock()
    mocker.patch("hookbell.replies.slack.monotonic", side_effect=clock.monotonic)
    mocker.patch("hookbell.replies.slack.sleep", side_effect=clock.sleep)
    return clock


@pytest.fixture(autouse=True)
def _unset_setting_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(SETTING_ENVIRONMENT_VARIABLE, raising=False)


@pytest.fixture
def setting_secret_path(tmp_path: Path) -> Path:
    path = tmp_path / "hookbell_test_setting"
    path.write_text("from-secret\n", encoding="utf-8")
    return path


@pytest.fixture
def setting_environment_variable(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setenv(SETTING_ENVIRONMENT_VARIABLE, "from-environment")
    return SETTING_ENVIRONMENT_VARIABLE
