# Hookbell

[![Test](https://github.com/yukihiko-shinoda/hookbell/workflows/Test/badge.svg)](https://github.com/yukihiko-shinoda/hookbell/actions?query=workflow%3ATest)
[![CodeQL](https://github.com/yukihiko-shinoda/hookbell/workflows/CodeQL/badge.svg)](https://github.com/yukihiko-shinoda/hookbell/actions?query=workflow%3ACodeQL)
[![Code Coverage](https://qlty.sh/gh/yukihiko-shinoda/projects/hookbell/coverage.svg)](https://qlty.sh/gh/yukihiko-shinoda/projects/hookbell)
[![Maintainability](https://qlty.sh/gh/yukihiko-shinoda/projects/hookbell/maintainability.svg)](https://qlty.sh/gh/yukihiko-shinoda/projects/hookbell)
[![Dependabot](https://flat.badgen.net/github/dependabot/yukihiko-shinoda/hookbell?icon=dependabot)](https://github.com/yukihiko-shinoda/hookbell/security/dependabot)
[![Python versions](https://img.shields.io/pypi/pyversions/hookbell)](https://pypi.org/project/hookbell/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/hookbell)](https://pypi.org/project/hookbell/)
[![X URL](https://img.shields.io/twitter/url?style=social&url=https%3A%2F%2Fgithub.com%2Fyukihiko-shinoda%2Fhookbell)](https://x.com/intent/post?text=Hookbell&url=https%3A%2F%2Fpypi.org%2Fproject%2Fhookbell%2F&hashtags=python)

Notifies Slack — as a Claude Code hook, or as a general "notify me when this finishes" command for
any piped output.

## Advantage

A Claude Code hook script that only understands its own hook JSON payload
(`transcript_path`, `hook_event_name`, ...) can't double as a general-purpose notification command
for anything else you run — and a general-purpose command built without Claude Code in mind knows
nothing about its transcripts, so it can't report what the assistant actually said or which
permission it's waiting on. Maintaining one script per use case means duplicating the Slack-posting
logic each time.

Hookbell covers both with a single command: it inspects stdin and automatically picks the right
behavior. A Claude Code hook payload gets reported through its referenced transcript; anything else
is treated as free-form piped text and posted as-is.

## Quickstart

```bash
uv tool install hookbell
```

Set the webhook URL from a Slack [Incoming Webhook](https://api.slack.com/messaging/webhooks):

```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T000/B000/XXXX"
```

Pipe any text into hookbell to post it to Slack:

```bash
echo 'Hello world' | uvx hookbell
```

That posts this single Slack message:

````text
Finished!
```
Hello world
```
````

Since any piped input gets wrapped the same way, piping a long-running command's own output into
hookbell delivers that output to Slack the moment the command is done, without having to watch the
terminal for it — redirecting stderr into stdout matters here, since build tools like
`docker compose build` write their progress there:

```bash
docker compose build 2>&1 | uvx hookbell
```

When the command's output isn't worth forwarding and only knowing it ended matters, chaining with
`;` instead leaves hookbell's stdin empty, so it just posts `Finished!` on its own:

```bash
docker compose build; uvx hookbell
```

<!-- markdownlint-disable no-trailing-punctuation -->
## How do I...
<!-- markdownlint-enable no-trailing-punctuation -->

### How do I use hookbell as a Claude Code hook?

Point Claude Code's `Notification`, `PermissionRequest`, and `Stop` hooks at hookbell in
`settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [{ "type": "command", "command": "uvx hookbell" }]
      }
    ]
  }
}
```

Hookbell recognizes a Claude Code hook payload by its `transcript_path` field and posts a message
built from that transcript: the assistant's own last message when there is one, or a description of
the pending permission request otherwise. A failed notification here is swallowed rather than raised,
so a flaky network never turns into hook-failure noise; turn on logging (below) to see why it failed.

### How do I answer Claude from Slack?

Add `--wait-reply` to the `Stop` and `PermissionRequest` hooks. Hookbell then posts the message
through a Slack bot and waits for your reply in its thread:

| Event | Your reply | What Claude Code does |
| --- | --- | --- |
| `Stop` | Any text | Keeps working, with your reply as its next instruction |
| `Stop` | Exactly `stop`, `quit`, or `q` | Stops as usual |
| `PermissionRequest` | Exactly `ok`, `yes`, or `y` | Allows the tool call |
| `PermissionRequest` | Anything else | Denies the tool call, and Claude reads your reply as the reason |
| Either | No reply before the timeout | Waits for you at the terminal as usual |

Keywords match only exactly, so a speech-to-text slip such as `ok!` or `yes.` denies rather than
allows. Matching ignores only the following all differences:

- Letter case
- Surrounding spaces
- Full-width letters (`ＯＫ` matches `ok`)

Before Claude Code acts on your reply, hookbell reacts to it with the emoji for what the reply did, so you
can tell in Slack that it was received and how it was read:

| Reaction | Meaning |
| --- | --- |
| 👀 | Claude keeps working on your `Stop` reply |
| 💤 | Claude stops on your stop keyword |
| ⚡ | The tool call is allowed |
| ♻️ | The tool call is denied |

Whenever anything goes wrong,
hookbell prints nothing and the decision stays with you at the terminal.

When Claude keeps working on your `Stop` reply, Claude Code shows that reply under a
`Stop hook error:` label. This label is how Claude Code displays a `Stop` hook's reason to continue;
nothing has failed.

The terminal stays usable while hookbell waits, as follows:

| What you do at the terminal | What happens |
| --- | --- |
| Answer a `PermissionRequest` dialog | Your terminal answer wins. Hookbell keeps waiting until the timeout and posts its timeout notice, so a later reply in that thread is ignored |
| Send a message while `Stop` waits | Hookbell notices it within 5 seconds, stops waiting, and says so in the thread. Claude Code then sends your message, and a later reply in that thread is ignored |
| Press Esc while `Stop` waits | The wait stops and Claude Code returns to the prompt. No timeout notice is posted, and a later reply in that thread is ignored |

Set the hook's `timeout` above `--reply-timeout` (540 seconds by default), so Claude Code doesn't
cancel hookbell before it can print the decision:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          { "type": "command", "command": "uvx hookbell --wait-reply", "timeout": 600 }
        ]
      }
    ]
  }
}
```

This needs a Slack app of your own, installed to your workspace and invited to the channel:

| Setting | Docker secret | Environment variable |
| --- | --- | --- |
| Bot token (`xoxb-`) with `chat:write` and `channels:history` (`groups:history` for a private channel), plus the optional `reactions:write` for the reactions | `/run/secrets/slack_bot_token` | `SLACK_BOT_TOKEN` |
| Channel ID to post in | `/run/secrets/hookbell_slack_channel_id` | `HOOKBELL_SLACK_CHANNEL_ID` |
| Your Slack member ID; replies from anyone else are ignored | `/run/secrets/hookbell_slack_allowed_user_id` | `HOOKBELL_SLACK_ALLOWED_USER_ID` |

Hookbell checks the thread every 5 seconds and doesn't use Socket Mode, so several sessions can wait
at once without taking each other's replies. Without these settings, or with SNS configured,
`--wait-reply` falls back to the usual one-way notification. `Notification` events never wait.

[Setting up `--wait-reply`](https://github.com/yukihiko-shinoda/hookbell/blob/main/docs/setup-wait-reply.md) walks through the whole setup step by step, from
adding the bot token to your Slack app to trying each kind of reply.

### How do I see why a notification failed?

Hookbell writes no log by default. Add `--log-level` to the command (or set `HOOKBELL_LOG_LEVEL`) to
write hookbell's own logs to `$XDG_CACHE_HOME/hookbell/slack.log` (`~/.cache/hookbell/slack.log` when
`XDG_CACHE_HOME` is unset):

```json
{ "type": "command", "command": "uvx hookbell --log-level warning" }
```

The log file lives outside your project, so it never ends up in a commit, and only you can read it.
At `debug`, the log includes the raw hook payload, which carries your conversation and tool inputs.

Other libraries stay at WARNING whatever `--log-level` you choose, because their DEBUG output can
contain credentials — the AWS SDK logs request headers and response bodies verbatim. When you really
need it, `--dangerously-debug-all-loggers` sets every logger to DEBUG. It is accepted only on the
command line, never from an environment variable, and prints a warning on every run; remove it as
soon as you finish debugging.

### How do I use hookbell in a Docker container?

Hookbell checks `/run/secrets/slack_webhook_url` before falling back to `SLACK_WEBHOOK_URL`, so a
[Docker secret] keeps the webhook URL out of the container's environment and image layers entirely.
With Compose, write the URL to a local file Compose reads at build/run time, and mount it as a
secret named `slack_webhook_url` so Docker places it at that exact path:

```yaml
services:
  app:
    secrets:
      - slack_webhook_url

secrets:
  slack_webhook_url:
    file: ./slack_webhook_url.txt
```

[Docker secret]: https://docs.docker.com/compose/how-tos/use-secrets/

## Credits

This package was created with [Cookiecutter] and the [yukihiko-shinoda/cookiecutter-pypackage] project template.

[Cookiecutter]: https://github.com/audreyr/cookiecutter
[yukihiko-shinoda/cookiecutter-pypackage]: https://github.com/audreyr/cookiecutter-pypackage
