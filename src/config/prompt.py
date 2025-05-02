from typing import Optional, Dict, Any, List

from pydantic import BaseModel, Field
from pydantic_settings import SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings


class Prompt(BaseModel):
    name: str
    text: str
    metadata: Optional[Dict[str, Any]] = None


class PromptConfig(YamlBaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="./resources/agent.yaml",
        secrets_dir="./resources",
        extra="ignore",
    )

    prompts: List[Prompt] = Field(default_factory=list)

    def get_prompt(self, name: str) -> Prompt:
        for prompt in self.prompts:
            if prompt.name == name:
                return prompt
        raise ValueError(f"Prompt with name {name} not found")
