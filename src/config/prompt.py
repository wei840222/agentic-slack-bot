from enum import Enum
from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings

from .client import LangfuseConfig


class PromptProvider(Enum):
    YAML = "yaml"
    LANGFUSE = "langfuse"


class Prompt(BaseModel):
    name: str
    text: str
    metadata: Optional[Dict[str, Any]] = None


class PromptConfig(YamlBaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="./config/agent.yaml",
        secrets_dir="./secret",
        extra="ignore",
    )

    prompts: List[Prompt] = Field(default_factory=list)

    def __getitem__(self, key: str) -> Prompt:
        for prompt in self.prompts:
            if prompt.name == key:
                return prompt
        raise ValueError(f"Prompt with name {key} not found")


class PromptMixin:
    _prompt_config: Optional[PromptConfig] = None
    _langfuse_config: Optional[LangfuseConfig] = None

    prompt_provider: PromptProvider = Field(
        default=PromptProvider.YAML,
        description="The provider to use for the agent's prompts."
    )

    def _get_langfuse_config(self) -> LangfuseConfig:
        if self._langfuse_config is None:
            self._langfuse_config = LangfuseConfig()
        return self._langfuse_config

    def get_prompt(self, name: str) -> Prompt:
        if self._prompt_config is None:
            self._prompt_config = PromptConfig()
        return self._prompt_config[name]

    def get_prompt(self, name: str) -> Prompt:
        match self.prompt_provider:
            case PromptProvider.YAML:
                if self._prompt_config is None:
                    self._prompt_config = PromptConfig()
                return self._prompt_config[name]
            case PromptProvider.LANGFUSE:
                client = self._get_langfuse_config().get_langfuse_client()
                langfuse_prompt = client.get_prompt(
                    name, label=client.environment)
                return Prompt(
                    name=langfuse_prompt.name,
                    text=langfuse_prompt.get_langchain_prompt(),
                    metadata=langfuse_prompt.config
                )
            case _:
                raise ValueError(
                    f"Invalid prompt provider: {self.prompt_provider}")
