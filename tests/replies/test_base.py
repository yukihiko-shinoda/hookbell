# Copyright (c) 2026 Yukihiko Shinoda
"""Tests for hookbell.replies.base."""

from __future__ import annotations

import pytest

from hookbell.replies.base import Reply

# Full-width "OK" (U+FF2F U+FF2B), spelled with escapes since Ruff flags full-width Latin letters as ambiguous.
FULL_WIDTH_OK = "\uff2f\uff2b"


class TestReply:
    """Tests for Reply."""

    @pytest.mark.parametrize("text", ["ok", "OK", "Ok", FULL_WIDTH_OK, " ok\n"])
    def test_normalized_folds_case_width_and_surrounding_whitespace(self, text: str) -> None:
        assert Reply(text).normalized == "ok"

    @pytest.mark.parametrize(("text", "expected"), [("ok!", "ok!"), ("はい。", "はい。"), ("o k", "o k")])
    def test_normalized_keeps_punctuation_and_inner_spaces(self, text: str, expected: str) -> None:
        assert Reply(text).normalized == expected

    def test_text_keeps_the_original_reply(self) -> None:
        assert Reply(f" Use {FULL_WIDTH_OK}\n").text == f" Use {FULL_WIDTH_OK}\n"
