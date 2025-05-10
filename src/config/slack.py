from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .agent import AgentConfig
from .logger import LoggerMixin
from .prompt import PromptMixin
from .message import EmojiMixin, MessageMixin


class SlackConfig(BaseSettings, LoggerMixin, PromptMixin, EmojiMixin, MessageMixin):
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

    agent_config: AgentConfig = Field(default_factory=AgentConfig)
