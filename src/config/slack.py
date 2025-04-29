from typing import List, Dict
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings


class SlackBotAssistantResources(BaseSettings):
    thinking_message: str
    greeting_message: str
    greeting_prompts: List[Dict[str, str]]


class SlackBotResources(YamlBaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="./assets/slack_bot_resources.yaml",
        secrets_dir="./assets",
        extra="ignore",
    )

    emoji: Dict[str, str]
    artifact_icon_emoji: Dict[str, str]
    content_disclaimer_message: str
    tool_reference_message: str
    assistant: SlackBotAssistantResources


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

    resources: SlackBotResources = Field(default_factory=SlackBotResources)
