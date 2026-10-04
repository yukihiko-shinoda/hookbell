# Copyright (c) 2026 Yukihiko Shinoda
"""Console script for hookbell."""

from __future__ import annotations

import os
import sys
from logging import DEBUG
from logging import WARNING
from logging import NullHandler
from logging import basicConfig
from logging import getLogger
from pathlib import Path

import click

from hookbell.claude_code.event import ClaudeCodeHookEvent
from hookbell.claude_code.stdin import ClaudeCodeStdin
from hookbell.notifiers.factory import NotifierFactory
from hookbell.notify_style import PlainTextNotification

LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def _cache_home() -> Path:
    """Return the XDG base directory for user-specific cache files.

    Per the XDG Base Directory Specification, an unset, empty, or relative $XDG_CACHE_HOME is ignored in favor of
    ~/.cache.
    """
    xdg_cache_home = Path(os.environ.get("XDG_CACHE_HOME", ""))
    return xdg_cache_home if xdg_cache_home.is_absolute() else Path.home() / ".cache"


def log_file_path() -> Path:
    """Return hookbell's log file path under the user's cache directory.

    The path is absolute on purpose: Claude Code runs hooks with the user's project as the current directory, so a
    relative path would land in that project's working tree, where it could be committed.
    """
    return _cache_home() / "hookbell" / "slack.log"


def _write_root_logger_to_log_file(root_level: int) -> None:
    log_file = log_file_path()
    log_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    # The log file can hold sensitive data (raw hook payloads, or credentials when every logger is at DEBUG), so
    # only the owner may read it. touch()'s mode applies only on creation, so chmod() covers a pre-existing file.
    log_file.touch(mode=0o600)
    log_file.chmod(0o600)
    basicConfig(filename=log_file, level=root_level)


def configure_logging(level: str | None, *, dangerously_debug_all_loggers: bool = False) -> None:
    """Configure where and how verbosely hookbell logs.

    Args:
        level: Level for hookbell's own loggers. Third-party loggers stay at WARNING regardless, since their DEBUG
            output (e.g. botocore's wire traces) can contain credentials. None disables logging entirely.
        dangerously_debug_all_loggers: Set the root logger, and so every third-party logger, to DEBUG. Overrides
            level.
    """
    if dangerously_debug_all_loggers:
        click.echo(
            f"Warning: --dangerously-debug-all-loggers writes DEBUG logs of every library to {log_file_path()}. "
            "They can include credentials (e.g. AWS SDK wire traces). Remove the option once you finish debugging.",
            err=True,
        )
        _write_root_logger_to_log_file(DEBUG)
        return
    if level is None:
        # Without any handler, the logging module's last-resort handler would still print WARNING and above to
        # stderr.
        basicConfig(handlers=[NullHandler()])
        return
    _write_root_logger_to_log_file(WARNING)
    getLogger("hookbell").setLevel(level.upper())


@click.command()
@click.option(
    "--log-level",
    envvar="HOOKBELL_LOG_LEVEL",
    type=click.Choice(LOG_LEVELS, case_sensitive=False),
    default=None,
    help="Write hookbell's logs at this level to $XDG_CACHE_HOME/hookbell/slack.log. Logging is off when omitted.",
)
# Reason for no envvar: an environment variable silently persists in shell profiles and container settings, so this
# option is accepted only on the command line, where it stays visible in the hook command itself.
@click.option(
    "--dangerously-debug-all-loggers",
    is_flag=True,
    help="Write DEBUG logs of every library, including credentials in AWS SDK wire traces, to the log file.",
)
def main(log_level: str | None, *, dangerously_debug_all_loggers: bool) -> int:
    """Notify Slack, either as a Claude Code hook or from any piped input.

    Reads stdin (unless it is a TTY) and decides which mode applies: a Claude Code hook payload (JSON carrying
    "transcript_path") is reported through its referenced transcript; anything else is posted as free-form text.
    """
    configure_logging(log_level, dangerously_debug_all_loggers=dangerously_debug_all_loggers)
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
    # briefly down, an unreachable webhook, or both destinations being configured at once) from
    # producing hook-failure feedback for a non-critical path. The failure surface spans stdlib
    # json, pathlib and urllib, boto3, plus future code, so narrowing to specific exception types
    # would leave gaps:
    # - Pylint broad-exception-caught (W0718): no narrower alternative fits an evolving surface
    #   https://pylint.readthedocs.io/en/latest/user_guide/messages/warning/broad-exception-caught.html
    try:
        NotifierFactory.from_environment().notify(ClaudeCodeHookEvent(claude_code_stdin).text)
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
        NotifierFactory.from_environment().notify(PlainTextNotification(raw_stdin).text)
    except Exception as error:  # pylint: disable=broad-exception-caught
        raise click.ClickException(str(error)) from error


if __name__ == "__main__":
    # Command.main() rather than the equivalent main(): Pylint checks main() against the undecorated signature, not
    # the click.Command the decorators return, so it reports the options Click parses from sys.argv as missing.
    sys.exit(main.main())  # pragma: no cover
