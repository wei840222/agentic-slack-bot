from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .message import EmojiConfig, MessageConfig


class SlackConfig(BaseSettings):
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

    emojis: EmojiConfig = Field(default_factory=EmojiConfig)
    messages: MessageConfig = Field(default_factory=MessageConfig)
