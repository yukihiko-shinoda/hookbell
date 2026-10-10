# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Hookbell is a Python CLI (`hookbell` console script) that posts notifications to Slack via an incoming
webhook. It serves two purposes through one entry point: acting as a Claude Code hook (`Notification`,
`PermissionRequest`, `Stop`) that reports what the assistant said or which permission it is waiting on, and
acting as a general `notify`-style command that wraps any piped stdin into a Slack message. See
[README.md](README.md) for the user-facing usage and Docker secret setup.

## Commands

```bash
# Setup
uv sync

# Testing
uv run pytest                                    # all tests
uv run pytest tests/path/to/test_file.py::TestClass::test_method  # single test
uv run inv test                                  # fast tests (excludes @pytest.mark.slow)
uv run inv test.all                              # all tests via invoke-lint
uv run inv test.coverage                         # with coverage report

# Linting
uv run inv lint                                  # fast linters (xenon, ruff, bandit, dodgy, flake8, pydocstyle)
uv run inv lint.deep                             # deep linters (mypy, pylint, semgrep)
uv run inv lint.<tool>                           # individual tool

# Formatting
uv run inv style                                 # format code
uv run inv style --check                         # check without changes

uv run inv --list                                # list all available tasks
```

Per [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md), a full pre-PR check also re-runs the test suite under the
oldest supported interpreter (the project's floor is Python 3.8):

```bash
uv run inv style --check
uv run pytest
uv python install 3.8
uv run pytest --python 3.8
```

## Architecture

### Mode dispatch (`hookbell/cli.py`)

`main()` is the single entry point for both usage modes. It reads stdin (unless it is a TTY) and branches on
whether `ClaudeCodeStdin.parse()` recognizes the payload as a Claude Code hook event — a JSON object carrying a
`transcript_path` key:

- **Claude Code hook mode** (`_notify_claude_code_hook`): builds a `ClaudeCodeHookEvent` and notifies Slack.
  Failures are caught, logged to `slack.log`, and swallowed rather than raised — a hook script must not turn a
  transient failure (flaky network, unreachable webhook, malformed transcript line) into Claude Code
  hook-failure noise.
- **Plain-text mode** (`_notify_plain_text`): wraps any other stdin (including empty/TTY input) in a
  `PlainTextNotification` and notifies Slack. Failures are re-raised as `click.ClickException` so a direct,
  interactive invocation surfaces the error on stderr with exit code 1.

Before either mode runs, `main()` calls `configure_logging()`, driven by two options:

- **No option (default)**: logging is off. The root logger gets a `NullHandler` so even the logging module's
  last-resort stderr handler stays quiet.
- **`--log-level` / `HOOKBELL_LOG_LEVEL`**: writes to `log_file_path()` — `$XDG_CACHE_HOME/hookbell/slack.log`
  (`~/.cache/hookbell/slack.log` when `XDG_CACHE_HOME` is unset, empty, or relative). The level is applied to the
  `hookbell` logger only; the root logger stays at WARNING, so third-party wire traces (botocore's
  `Authorization` headers and STS/SSO response bodies) never reach the file. Never set the root logger to DEBUG in
  this path — that is how AWS credentials leaked into a committed `slack.log` before.
- **`--dangerously-debug-all-loggers`**: sets the root logger to DEBUG and warns on stderr every run. It is
  deliberately CLI-only (no `envvar`) so it can't silently persist in a shell profile or container setting.

The log path is absolute on purpose: Claude Code runs hooks with the user's project as the current directory, so a
relative path would drop the log into that project's working tree, where it could be committed. The file is created
with mode `0600`. Logging is configured inside `main()` rather than at import time so importing `hookbell.cli` has no
filesystem side effects. Tests isolate `XDG_CACHE_HOME` and restore the `hookbell` logger level with autouse
fixtures in `tests/conftest.py`; `TestConfigureLogging` checks effective levels in a fresh interpreter because under
pytest the root logger already has handlers, which turns `basicConfig()` into a no-op.

### Waiting for a Slack reply (`hookbell/replies/`, `--wait-reply`)

With `--wait-reply`, `_handle_claude_code_hook` sends `Stop` and `PermissionRequest` events (the only ones whose
hook output can carry a decision) to `_ask_claude_code_hook` instead of the one-way notifier. It falls back to the
one-way path when `SlackCredentials` isn't fully configured, or when SNS is configured (SNS can't receive replies).
The one design rule: whenever hookbell can't clearly honor a reply, it prints **nothing**, so Claude Code falls back
to the user at the terminal — never `allow`. That covers the following all cases:

- Any exception
- A timeout with no reply
- A `Stop` reply that is a stop keyword

- `base.py`: `ReplyChannel` ABC (`ask(text, timeout) -> Reply | None`), kept separate from `Notifier` so SNS isn't
  affected. `Reply.normalized` applies NFKC + `strip()` + `casefold()` but keeps punctuation, so `ok!` never matches.
- `slack.py` (`SlackReplyChannel`): posts with `chat.postMessage`, then polls `conversations.replies` every 5 s until
  `--reply-timeout`, honoring `Retry-After` on HTTP 429, and posts a timeout notice in the thread. It deliberately
  doesn't use Socket Mode: Socket Mode delivers each event to only one of the app's connections, so sessions waiting
  in parallel would steal each other's replies.
- Terminal input ends the wait early: Claude Code queues a message the user sends while a hook runs and appends a
  `queue-operation` entry with `operation: "enqueue"` to the transcript right away. `QueuedMessageWatcher`
  (`hookbell/claude_code/transcript.py`) reads only what was appended since hookbell started, and
  `SlackReplyChannel` checks it before every poll; on a hit it posts a notice in the thread and returns `None`, so
  hookbell prints nothing and Claude Code sends the queued message. This entry type is not a documented Claude Code
  interface, so a format change silently degrades to waiting until the timeout.
- `reply_filter.py` (`ReplyFilter`): accepts a message newer than the parent (`Decimal` ts compare), from the allowed
  user, with no `bot_id` or `subtype`.
- `decision.py` (`HookDecision` → `StopDecision` / `PermissionDecision`): reply → hook output JSON per
  https://code.claude.com/docs/en/hooks. Only an exact allow keyword allows; anything else denies with
  `interrupt: false` so Claude continues with the reply as the reason.
- `slack_web_api.py` (`SlackWebApi`): bot-token Web API client on `urllib` + `certifi`, like the webhook notifier —
  no `slack_sdk` dependency.
- `slack_credentials.py`: built on `hookbell/setting.py`'s `Setting` (Docker secret file first, then environment
  variable). Its `__repr__`s never include the token.

Tests mock only `urlopen` (`FakeSlackWebApi` in `tests/conftest.py`) and the module's `monotonic`/`sleep`
(`FakeClock`). Both `hookbell.notifiers.slack.request` and `hookbell.replies.slack_web_api.request` are the same
`urllib.request` module, so a test must use either `FakeSlackWebApi` or the webhook `urlopen` fixture, not both.

### Claude Code hook event composition (`hookbell/claude_code/`)

- `stdin.py` (`ClaudeCodeStdin`): parses the raw hook JSON. `message` falls back to `hook_event_name`;
  `fallback_text` covers the cases where the transcript's last line has no readable assistant text —
  `PermissionRequest` payloads carry the pending tool call instead, and some `Stop` payloads carry a ready-made
  `last_assistant_message`.
- `transcript.py` (`Transcript` / `FileLastLineGetter`): reads only the *last line* of the (potentially large,
  append-only JSONL) transcript file, seeking backward from EOF rather than reading the whole file.
  `_remove_unreadable_keys` strips internal bookkeeping fields (`parentUuid`, `uuid`, `sessionId`, etc.) before
  the entry is written to the debug log as pretty-printed JSON. Every accessor tolerates missing keys, since
  the last line can be a plain assistant message, a tool call, a sub-agent/sidechain entry, or a compaction
  summary — each with a different shape.
- `event.py` (`ClaudeCodeHookEvent`): combines a `ClaudeCodeStdin` and its referenced `Transcript` into the final
  notification text — `transcript.text_content` when present, else `stdin.fallback_text`, followed by the message
  type. The sanitized transcript entry goes to the debug log, never the message: it once made Slack split a
  `--wait-reply` post into several messages, and a reply in a part other than the one whose `ts` hookbell polls is
  never seen.

### Plain-text composition (`hookbell/notify_style.py`)

`PlainTextNotification` produces `"Finished!"` on its own for empty stdin, or `"Finished!"` plus the captured
stdin in a code block otherwise, keeping only the tail that fits `STDIN_CHARACTER_LIMIT` (sized so the whole text fits
one Slack markdown block).

### Slack Markdown (`hookbell/slack_markdown.py`)

Both Slack paths (`SlackNotifier` and `SlackReplyChannel`) post the text as a Block Kit `markdown` block, not a
`mrkdwn` section, so Claude Code's standard Markdown (headings, tables, fenced code) renders as structured text;
the raw text also goes in the top-level `text` as the notification fallback. `SlackMarkdown` cuts text to Slack's
12,000-character cumulative limit for markdown blocks, closing a fenced code block the cut leaves open.

### Notification backend (`hookbell/notifiers/`)

`base.py` defines the `Notifier` ABC (single `notify(text: str)` method) as the extension point for future
backends; `slack.py`'s `SlackNotifier` is the only implementation today. `SlackNotifier.from_environment()`
resolves the webhook URL from the Docker secret path `/run/secrets/slack_webhook_url` first, falling back to the
`SLACK_WEBHOOK_URL` environment variable — this is what lets the same code run either in a container with the
URL mounted as a secret or directly from a shell environment variable. `notify()` rejects non-`https://` URLs
before POSTing, and builds its own SSL context from `certifi`'s CA bundle rather than relying on the platform
store (kept reliable on minimal/slim container images).

## Release process

Version bumps use `bump-my-version` (`[tool.bumpversion]` in [pyproject.toml](pyproject.toml)), which keeps
`pyproject.toml` and `hookbell/__init__.py`'s `__version__` in sync and creates a commit + tag.
