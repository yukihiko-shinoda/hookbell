# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.setting."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from hookbell.setting import Setting
from tests.conftest import SETTING_ENVIRONMENT_VARIABLE

if TYPE_CHECKING:
    from pathlib import Path


class TestSetting:
    """Tests for Setting."""

    def test_read_prefers_the_secret_file_over_the_environment_variable(
        self,
        setting_secret_path: Path,
        setting_environment_variable: str,
    ) -> None:
        assert Setting(setting_environment_variable, secret_path=setting_secret_path).read() == "from-secret"

    def test_read_falls_back_to_the_environment_variable(
        self,
        tmp_path: Path,
        setting_environment_variable: str,
    ) -> None:
        assert Setting(setting_environment_variable, secret_path=tmp_path / "missing").read() == "from-environment"

    def test_read_uses_the_environment_variable_when_there_is_no_secret_path(
        self,
        setting_environment_variable: str,
    ) -> None:
        assert Setting(setting_environment_variable).read() == "from-environment"

    def test_read_raises_key_error_when_neither_is_set(self, tmp_path: Path) -> None:
        with pytest.raises(KeyError):
            Setting(SETTING_ENVIRONMENT_VARIABLE, secret_path=tmp_path / "missing").read()

    def test_is_set_with_only_the_secret_file(self, setting_secret_path: Path) -> None:
        assert Setting(SETTING_ENVIRONMENT_VARIABLE, secret_path=setting_secret_path).is_set() is True

    def test_is_set_with_only_the_environment_variable(self, setting_environment_variable: str) -> None:
        assert Setting(setting_environment_variable).is_set() is True

    def test_is_not_set_when_neither_is_available(self, tmp_path: Path) -> None:
        assert Setting(SETTING_ENVIRONMENT_VARIABLE, secret_path=tmp_path / "missing").is_set() is False

    def test_repr_hides_the_value(self, setting_secret_path: Path) -> None:
        assert "from-secret" not in repr(Setting(SETTING_ENVIRONMENT_VARIABLE, secret_path=setting_secret_path))
