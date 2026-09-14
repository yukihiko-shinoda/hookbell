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
the pending permission request otherwise. A failed notification here is logged (see `slack.log`)
rather than raised, so a flaky network never turns into hook-failure noise.

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
