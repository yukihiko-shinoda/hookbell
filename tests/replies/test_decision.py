# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.replies.decision."""

from __future__ import annotations

import pytest

from hookbell.replies.base import Reply
from hookbell.replies.decision import HookDecision
from hookbell.replies.decision import PermissionDecision
from hookbell.replies.decision import StopDecision
from tests.replies.test_base import FULL_WIDTH_OK


class TestHookDecision:
    """Tests for HookDecision."""

    def test_for_event_returns_stop_decision_for_stop(self) -> None:
        assert isinstance(HookDecision.for_event("Stop"), StopDecision)

    def test_for_event_returns_permission_decision_for_permission_request(self) -> None:
        assert isinstance(HookDecision.for_event("PermissionRequest"), PermissionDecision)

    @pytest.mark.parametrize("hook_event_name", ["Notification", "SubagentStop", ""])
    def test_for_event_returns_none_for_events_that_take_no_reply(self, hook_event_name: str) -> None:
        assert HookDecision.for_event(hook_event_name) is None


class TestStopDecision:
    """Tests for StopDecision."""

    def test_to_output_blocks_the_stop_with_the_reply_as_reason(self) -> None:
        output = StopDecision().to_output(Reply("Run the tests too"))

        assert output == {"decision": "block", "reason": "Run the tests too"}

    @pytest.mark.parametrize("text", ["stop", "STOP", "quit", "q", "Q", " q\n"])
    def test_to_output_prints_nothing_for_a_stop_keyword(self, text: str) -> None:
        assert StopDecision().to_output(Reply(text)) is None

    @pytest.mark.parametrize("text", ["stop.", "q!", "終了"])
    def test_to_output_blocks_the_stop_for_a_near_miss_of_a_stop_keyword(self, text: str) -> None:
        """Keep Claude working on a reply that only nearly matches a stop keyword, passing it on as the instruction."""
        assert StopDecision().to_output(Reply(text)) == {"decision": "block", "reason": text}

    def test_hint_names_the_stop_keywords(self) -> None:
        assert all(f"`{keyword}`" in StopDecision().hint for keyword in StopDecision.STOP_KEYWORDS)


class TestPermissionDecision:
    """Tests for PermissionDecision."""

    @pytest.mark.parametrize("text", ["ok", "OK", FULL_WIDTH_OK, "yes", "y", "Y", " y\n"])
    def test_to_output_allows_on_an_exact_allow_keyword(self, text: str) -> None:
        output = PermissionDecision().to_output(Reply(text))

        assert output == {
            "hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}},
        }

    @pytest.mark.parametrize("text", ["ok!", "yes.", "はい", "okay", "ok, but use --dry-run", "no"])
    def test_to_output_denies_anything_else_with_the_reply_as_message(self, text: str) -> None:
        """Deny near-misses too, so a speech-to-text slip like "ok!" never grants the permission."""
        output = PermissionDecision().to_output(Reply(text))

        assert output == {
            "hookSpecificOutput": {
                "hookEventName": "PermissionRequest",
                "decision": {"behavior": "deny", "message": text, "interrupt": False},
            },
        }

    def test_hint_names_the_allow_keywords(self) -> None:
        assert all(keyword in PermissionDecision().hint for keyword in PermissionDecision.ALLOW_KEYWORDS)
