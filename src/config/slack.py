from typing import List
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings


class SlackEmoji(BaseModel):
    name: str
    emoji: str


class SlackEmojiConfig(YamlBaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="./resources/slack.yaml",
        secrets_dir="./resources",
        extra="ignore",
    )

    emojis: List[SlackEmoji] = Field(default_factory=list)


class SlackMessage(BaseModel):
    name: str
    text: str


class SlackMessageConfig(YamlBaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="./resources/slack.yaml",
        secrets_dir="./resources",
        extra="ignore",
    )

    messages: List[SlackMessage] = Field(default_factory=list)


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

    emojis: SlackEmojiConfig = Field(default_factory=SlackEmojiConfig)
    messages: SlackMessageConfig = Field(default_factory=SlackMessageConfig)

    def get_emoji(self, name: str) -> SlackEmoji:
        for emoji in self.emojis.emojis:
            if emoji.name == name:
                return emoji
        raise ValueError(f"Emoji with name {name} not found")

    def get_message(self, name: str) -> SlackMessage:
        for message in self.messages.messages:
            if message.name == name:
                return message
        raise ValueError(f"Message with name {name} not found")
