from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .logger import LoggerConfig, LoggerMixin
from .slack import SlackConfig
from .agent import AgentConfig


class BaseConfig(BaseSettings, LoggerMixin):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    slack_config: SlackConfig = Field(default_factory=SlackConfig)
    agent_config: AgentConfig = Field(default_factory=AgentConfig)

    @property
    def logger_config(self) -> LoggerConfig:
        if self._logger_config is None:
            self._logger_config = LoggerConfig()
        return self._logger_config


_config: Optional[BaseConfig] = None


def get_config() -> BaseConfig:
    global _config
    if _config is None:
        _config = BaseConfig()
    return _config
