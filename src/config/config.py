from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from .logger import LoggerConfig
from .slack import SlackConfig
from .agent import AgentConfig
from .tracking import TrackingConfig


class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    logger: LoggerConfig = Field(default_factory=LoggerConfig)
    slack: SlackConfig = Field(default_factory=SlackConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    tracking: TrackingConfig = Field(default_factory=TrackingConfig)
