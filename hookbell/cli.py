# Copyright (c) 2026 Yukihiko Shinoda
"""Console script for hookbell."""

import sys
from logging import DEBUG
from logging import basicConfig
from logging import getLogger
from pathlib import Path

import click

from hookbell.claude_code.event import ClaudeCodeHookEvent
from hookbell.claude_code.stdin import ClaudeCodeStdin
from hookbell.notifiers.slack import SlackNotifier
from hookbell.notify_style import PlainTextNotification

basicConfig(filename=Path("slack.log"), level=DEBUG)


@click.command()
def main() -> int:
    """Notify Slack, either as a Claude Code hook or from any piped input.

    Reads stdin (unless it is a TTY) and decides which mode applies: a Claude Code hook payload (JSON carrying
    "transcript_path") is reported through its referenced transcript; anything else is posted as free-form text.
    """
    raw_stdin = "" if sys.stdin.isatty() else sys.stdin.read()
    claude_code_stdin = ClaudeCodeStdin.parse(raw_stdin) if raw_stdin else None
    if claude_code_stdin is not None:
        _notify_claude_code_hook(claude_code_stdin)
    else:
        _notify_plain_text(raw_stdin)
    return 0


def _notify_claude_code_hook(claude_code_stdin: ClaudeCodeStdin) -> None:
    # Reason: This runs as a Claude Code hook, where a failed notification is best-effort side-
    # channel noise rather than something that should surface as this hook's own failure. Logging
    # and swallowing keeps a transient issue (a malformed transcript line, the network being
    # briefly down, an unreachable webhook) from producing hook-failure feedback for a non-critical
    # path. The failure surface spans stdlib json, pathlib and urllib plus future code, so
    # narrowing to specific exception types would leave gaps:
    # - Pylint broad-exception-caught (W0718): no narrower alternative fits an evolving surface
    #   https://pylint.readthedocs.io/en/latest/user_guide/messages/warning/broad-exception-caught.html
    try:
        SlackNotifier.from_environment().notify(ClaudeCodeHookEvent(claude_code_stdin).text)
    except Exception:  # pylint: disable=broad-exception-caught
        getLogger(__name__).exception("Failed to notify Claude Code hook event")


def _notify_plain_text(raw_stdin: str) -> None:
    # Reason: same broad failure surface as _notify_claude_code_hook above, but this branch is a
    # direct, interactive invocation, so the failure is surfaced to the caller by re-raising as
    # ClickException instead of only logged. Click's standalone mode ignores this
    # command callback's own return value for the process exit code (only a raised exception, or an
    # explicit ctx.exit(), controls it), and ClickException is the one exception type Click always
    # turns into a clean "Error: ..." message on stderr plus a guaranteed exit code of exactly 1:
    # - Pylint broad-exception-caught (W0718): no narrower alternative fits an evolving surface
    #   https://pylint.readthedocs.io/en/latest/user_guide/messages/warning/broad-exception-caught.html
    try:
        SlackNotifier.from_environment().notify(PlainTextNotification(raw_stdin).text)
    except Exception as error:  # pylint: disable=broad-exception-caught
        raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
