from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .logger import LoggerMixin
from .message import EmojiMixin, MessageMixin


class SlackConfig(BaseSettings, LoggerMixin, EmojiMixin, MessageMixin):
    model_config = SettingsConfigDict(
        env_prefix="SLACK_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_token: str
    bot_token: str
    bot_id: str
    assistant: bool = False
    workspace_url: str
