# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for `hookbell` package."""

from __future__ import annotations

from typing import Any

from click.testing import CliRunner

from hookbell import cli


def test_content(response: dict[Any, Any] | None) -> None:
    """Sample pytest test function with the pytest fixture as an argument."""
    # from bs4 import BeautifulSoup  # noqa: ERA001
    # assert 'GitHub' in BeautifulSoup(response.content).title.string  # noqa: ERA001
    del response


def test_command_line_interface() -> None:
    """Test the CLI."""
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0
    assert "hookbell.cli.main" in result.output
    help_result = runner.invoke(cli.main, ["--help"])
    assert help_result.exit_code == 0
    assert "--help  Show this message and exit." in help_result.output
