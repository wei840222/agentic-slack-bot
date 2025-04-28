from typing import List, Dict
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings


class SlackAssistantI18N(BaseSettings):
    thinking_message: str
    greeting_message: str
    greeting_prompts: List[Dict[str, str]]


class SlackI18N(YamlBaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="./assets/slack_i18n.yaml",
        extra="ignore",
    )

    loading_emoji: str
    content_disclaimer_message: str
    assistant: SlackAssistantI18N


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

    i18n: SlackI18N = Field(default_factory=SlackI18N)
