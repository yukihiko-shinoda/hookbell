# Copyright (c) 2026 Yukihiko Shinoda
"""Configuration of pytest."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pytest

from hookbell.notifiers.slack import SlackNotifier
from hookbell.notifiers.sns import SnsNotifier

if TYPE_CHECKING:
    from collections.abc import Iterator


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
