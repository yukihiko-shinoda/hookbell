# Copyright (c) 2026 Yukihiko Shinoda
"""Converts a reply into the JSON a Claude Code hook writes to stdout.

Every path that cannot clearly honor the reply returns None, so hookbell prints nothing and Claude Code falls back to
the user at the terminal. Output formats follow
https://code.claude.com/docs/en/hooks.
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from typing import TYPE_CHECKING
from typing import Any
from typing import ClassVar

if TYPE_CHECKING:
    from hookbell.replies.base import Reply


class HookDecision(ABC):
    """The decision a hook event's reply turns into."""

    @classmethod
    def for_event(cls, hook_event_name: str) -> HookDecision | None:
        """Return the decision for hook_event_name, or None for an event that cannot take a reply."""
        decision_classes: dict[str, type[HookDecision]] = {
            "Stop": StopDecision,
            "PermissionRequest": PermissionDecision,
        }
        decision_class = decision_classes.get(hook_event_name)
        return None if decision_class is None else decision_class()

    @property
    @abstractmethod
    def hint(self) -> str:
        """Return the instruction appended to the posted message, telling the user how to reply."""

    @abstractmethod
    def to_output(self, reply: Reply) -> dict[str, Any] | None:
        """Return the hook output for reply, or None to print nothing."""


class StopDecision(HookDecision):
    """Continues Claude with the reply as its next instruction, unless the reply is a stop keyword."""

    STOP_KEYWORDS: ClassVar[frozenset[str]] = frozenset({"stop", "quit", "q"})

    @property
    def hint(self) -> str:
        return (
            "Reply in this thread to give Claude its next instruction, or reply `stop` / `quit` / `q` to let it stop."
        )

    def to_output(self, reply: Reply) -> dict[str, Any] | None:
        if reply.normalized in self.STOP_KEYWORDS:
            return None
        return {"decision": "block", "reason": reply.text}


class PermissionDecision(HookDecision):
    """Allows the tool call only on an exact allow keyword, and denies it on anything else.

    Exact matching keeps a speech-to-text mistake (e.g. "ok!" or "yes.") from granting a permission by accident.
    """

    ALLOW_KEYWORDS: ClassVar[frozenset[str]] = frozenset({"ok", "yes", "y"})

    @property
    def hint(self) -> str:
        return "Reply exactly `ok` / `yes` / `y` to allow. Any other reply denies, and Claude reads it as the reason."

    def to_output(self, reply: Reply) -> dict[str, Any] | None:
        if reply.normalized in self.ALLOW_KEYWORDS:
            decision: dict[str, Any] = {"behavior": "allow"}
        else:
            # interrupt: False lets Claude keep working with the denial and reply text, instead of halting the turn.
            decision = {"behavior": "deny", "message": reply.text, "interrupt": False}
        return {"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": decision}}
