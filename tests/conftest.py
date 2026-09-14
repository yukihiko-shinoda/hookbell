# Copyright (c) 2026 Yukihiko Shinoda
"""Configuration of pytest."""

from __future__ import annotations

import pytest

from hookbell.notifiers.slack import SlackNotifier


@pytest.fixture(autouse=True)
def _isolate_slack_webhook_secret_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path_factory: pytest.TempPathFactory,
) -> None:
    """Point the Docker secret path at a location tests control instead of a real host file."""
    unused_path = tmp_path_factory.mktemp("run-secrets") / "slack_webhook_url"
    monkeypatch.setattr(SlackNotifier, "WEBHOOK_URL_SECRET_PATH", unused_path)
