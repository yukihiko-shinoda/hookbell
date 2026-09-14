# Copyright (c) 2026 Yukihiko Shinoda
"""Notifier interface shared by every notification backend."""

from abc import ABC
from abc import abstractmethod


class Notifier(ABC):
    """A destination hookbell can send a notification text to."""

    @abstractmethod
    def notify(self, text: str) -> None:
        """Send text as a notification."""
