# Copyright (c) 2026 Yukihiko Shinoda
"""Reply channel interface shared by every backend that can wait for a reply."""

from __future__ import annotations

import unicodedata
from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable


class Reply:
    """A human's reply received through a ReplyChannel."""

    def __init__(self, text: str) -> None:
        self.text = text

    @property
    def normalized(self) -> str:
        """Return the text for matching against keywords.

        NFKC folds full-width forms (e.g. U+FF2F U+FF2B) into their ASCII equivalents and casefold() ignores case, but
        punctuation is kept as is, so "ok!" never matches "ok".
        """
        return unicodedata.normalize("NFKC", self.text).strip().casefold()


def never() -> bool:
    """Return False, for a ReplyChannel.ask() caller with no other place the user can answer."""
    return False


class ReplyChannel(ABC):
    """A destination hookbell can post a message to and receive a reply from."""

    @abstractmethod
    def ask(self, text: str, timeout: float, answered_elsewhere: Callable[[], bool] = never) -> Reply | None:
        """Post text, then return the first reply to it.

        Return None instead when timeout seconds pass without one, or once answered_elsewhere() returns True, which
        means the user went on at the terminal and a reply could no longer be honored.
        """
