import re
from collections import defaultdict
from typing import List, Dict
from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings


class Emoji(BaseModel):
    name: str
    emoji: str


class EmojiConfig(YamlBaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="./config/message.yaml",
        secrets_dir="./secret",
        extra="ignore",
    )

    emojis: List[Emoji] = Field(default_factory=list)

    def __getitem__(self, key: str) -> str:
        for emoji in self.emojis:
            if emoji.name == key:
                return emoji.emoji
        raise ValueError(f"Emoji with name {key} not found")


class Message(BaseModel):
    name: str
    text: str


class MessageConfig(YamlBaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="./config/message.yaml",
        secrets_dir="./secret",
        extra="ignore",
    )

    messages: List[Message] = Field(default_factory=list)

    def __getitem__(self, key: str) -> str:
        for message in self.messages:
            if message.name == key:
                return message.text
        raise ValueError(f"Message with name {key} not found")

    def get_message_dicts(self, key: str) -> List[Dict[str, str]]:
        pattern = re.compile(f"^{key}_(\\d+)_(.+)$")
        message_dicts = defaultdict(dict)
        for message in self.messages:
            if not pattern.fullmatch(message.name):
                continue
            idx, key = pattern.findall(message.name)[0]
            message_dicts[idx][key] = message.text
        return [
            message_dicts[idx]
            for idx in sorted(message_dicts.keys())
        ]
