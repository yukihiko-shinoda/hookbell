# Setting up `--wait-reply`

This guide sets up hookbell's `--wait-reply`, which lets you answer Claude Code from a Slack thread: give
Claude its next instruction when it stops, or allow or deny a pending permission request. It assumes you
already post to Slack through an Incoming Webhook and reuse that webhook's Slack app, and it walks through
every step from the Slack app settings to restarting Claude Code. For what each reply does once it is set
up, see [How do I answer Claude from Slack?](../README.md#how-do-i-answer-claude-from-slack) in the README.

## 1. Check that you can reuse your webhook's Slack app

You can add a bot token to the Slack app behind your webhook when it meets the following all conditions:

- The app is listed on [api.slack.com/apps](https://api.slack.com/apps)
  - If it isn't, the webhook was made as a legacy "Custom Integration", which can't carry a bot token.
    Create a new app instead
- **Manage Distribution** doesn't have Public Distribution turned on
  - An app limited to your own workspace is exempt from the 1-request-per-minute rate limit on
    `conversations.replies`
  - A publicly distributed app is subject to it, which rules out hookbell checking the thread every
    5 seconds

## 2. Add a bot token

On the app's settings pages, do the following all steps:

1. Under **OAuth & Permissions** → **Bot Token Scopes**, add the following all scopes:
   - `chat:write`
   - `channels:history` (`groups:history` for a private channel)
   - `reactions:write`
     - Optional. It lets hookbell react with 👍 to your reply once it receives it. Without it, your reply
       still works, just without the reaction
2. Click **Reinstall to Workspace** at the top of the page
   - New scopes take effect only after reinstalling
   - Your existing webhook URL normally keeps working
3. Copy the **Bot User OAuth Token** (starting with `xoxb-`) from the same page
4. In the channel to post in, run `/invite @<your app name>` to invite the bot
   - A webhook can post without joining the channel, but `chat.postMessage` and reading threads require
     the bot to be a member

## 3. Copy the channel ID and your member ID

Hookbell also needs the following both IDs:

| Value | Where to find it |
| --- | --- |
| Channel ID (starting with `C`) | At the bottom of the details dialog that opens when you click the channel name. It can be the same channel as your webhook's |
| Your member ID (starting with `U`) | Your profile → "⋮" → "Copy member ID". Replies from anyone else are ignored |

## 4. Pass the three values to hookbell

Hookbell reads each value from its Docker secret file first, and falls back to its environment variable:

| Value | Docker secret | Environment variable |
| --- | --- | --- |
| Bot token | `/run/secrets/slack_bot_token` | `SLACK_BOT_TOKEN` |
| Channel ID | `/run/secrets/hookbell_slack_channel_id` | `HOOKBELL_SLACK_CHANNEL_ID` |
| Allowed member ID | `/run/secrets/hookbell_slack_allowed_user_id` | `HOOKBELL_SLACK_ALLOWED_USER_ID` |

With Docker Compose, register them in your `compose.yml` the same way as `slack_webhook_url`:

```yaml
services:
  app:
    secrets:
      - slack_webhook_url
      - slack_bot_token
      - hookbell_slack_channel_id
      - hookbell_slack_allowed_user_id

secrets:
  slack_bot_token:
    file: ./slack_bot_token.txt
  hookbell_slack_channel_id:
    file: ./hookbell_slack_channel_id.txt
  hookbell_slack_allowed_user_id:
    file: ./hookbell_slack_allowed_user_id.txt
```

- Add the secret files, the bot token above all, to `.gitignore` so they are never committed
- Secrets are mounted when the container is created, so recreate the container after adding them
  ("Rebuild Container" for a Dev Container, `docker compose up -d` for Compose)

## 5. Configure the Claude Code hooks

In `~/.claude/settings.json`, add `--wait-reply` to the `Stop` and `PermissionRequest` hooks only:

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [{ "type": "command", "command": "uvx hookbell --wait-reply", "timeout": 600 }] }
    ],
    "PermissionRequest": [
      { "hooks": [{ "type": "command", "command": "uvx hookbell --wait-reply", "timeout": 600 }] }
    ],
    "Notification": [
      {
        "matcher": "idle_prompt|elicitation_dialog|auth_success",
        "hooks": [{ "type": "command", "command": "uvx hookbell" }]
      }
    ]
  }
}
```

Each setting has the following reason:

- `"timeout": 600` stays above how long hookbell waits for a reply (`--reply-timeout`, 540 seconds by
  default). With a shorter timeout, Claude Code cancels hookbell before it prints its decision, and the
  decision is lost
- The `Notification` matcher leaves out `permission_prompt`. Including it would send two messages for every
  permission request, one from `Notification` and one from `PermissionRequest`

## 6. Restart Claude Code

Claude Code reads hook settings at startup, so restart it after changing them.

## 7. Try it

Temporarily setting `--reply-timeout 120` and `"timeout": 180` shortens the waits while you try the
following all checks:

1. Ask Claude something that needs no permission, such as "Reply with just 'hello', without using any
   tools", and check that a message arrives in Slack once it answers
   - A request that needs a permission starts a `PermissionRequest` wait first, mixing it up with the
     `Stop` one
2. Reply with an instruction in the thread, and check that a 👍 reaction appears on your reply and
   Claude keeps working on it
   - Claude Code shows your reply under a `Stop hook error:` label. Nothing has failed
3. When Claude stops again, reply a stop keyword (`stop`, `quit`, or `q`), and check that Claude stops
4. While `running Stop hooks…` is shown, send a message at the terminal, and check that Claude handles it
   within about 5 seconds
5. Ask for something that always asks for permission, such as "Create `hookbell-test.txt` containing
   `test`" (a Write), and check the following all cases:
   - Replying with an allow keyword allows it. The allow keywords are the following all words, matched
     exactly apart from the few differences the README lists:
     - `ok`
     - `yes`
     - `y`
   - Replying with anything else denies it, and Claude reads your reply as the reason. There is no list
     of deny words: a reason such as `Write it under tmp/ instead` denies, and so does a near miss such
     as `ok!` or `yes.`, so a speech-to-text slip never allows by accident
   - Answering the dialog at the terminal first wins
6. Delete the test file, and set the timeouts back

A Bash command doesn't work for step 5 when Claude Code's sandbox is on: a sandboxed command runs without
asking for permission, so no `PermissionRequest` occurs. A network destination missing from the sandbox's
allow list stops at the sandbox's own prompt instead, which doesn't call the hook either.

If something doesn't work, add `--log-level debug` to the command to write logs to
`~/.cache/hookbell/slack.log`. At `debug`, the log includes your replies and the raw hook input, so remove
the option once you are done.
