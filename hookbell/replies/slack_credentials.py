# Copyright (c) 2026 Yukihiko Shinoda
"""Settings for posting to and reading replies from Slack with a bot token."""

from __future__ import annotations

from pathlib import Path

from hookbell.setting import Setting


class SlackCredentials:
    """The bot token, the channel to post in, and the only user whose replies count."""

    BOT_TOKEN = Setting("SLACK_BOT_TOKEN", secret_path=Path("/run/secrets/slack_bot_token"))
    CHANNEL_ID = Setting("HOOKBELL_SLACK_CHANNEL_ID", secret_path=Path("/run/secrets/hookbell_slack_channel_id"))
    ALLOWED_USER_ID = Setting(
        "HOOKBELL_SLACK_ALLOWED_USER_ID",
        secret_path=Path("/run/secrets/hookbell_slack_allowed_user_id"),
    )

    def __init__(self, bot_token: str, channel_id: str, allowed_user_id: str) -> None:
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.allowed_user_id = allowed_user_id

    def __repr__(self) -> str:
        # Keep the token out of tracebacks and logs that render this object.
        return f"SlackCredentials(channel_id={self.channel_id!r}, allowed_user_id={self.allowed_user_id!r})"

    @classmethod
    def is_configured(cls) -> bool:
        """Return whether the bot token, the channel ID, and the allowed user ID are all available."""
        return all(setting.is_set() for setting in (cls.BOT_TOKEN, cls.CHANNEL_ID, cls.ALLOWED_USER_ID))

    @classmethod
    def from_environment(cls) -> SlackCredentials:
        """Build SlackCredentials, reading each value from its Docker secret before its environment variable."""
        return cls(
            bot_token=cls.BOT_TOKEN.read(),
            channel_id=cls.CHANNEL_ID.read(),
            allowed_user_id=cls.ALLOWED_USER_ID.read(),
        )
