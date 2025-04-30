
from enum import Enum
from typing import Dict, Annotated, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_settings_yaml import YamlBaseSettings
from langchain_core.runnables import RunnableConfig, ensure_config

from tracking import BaseTracker, LangfuseTracker, StdoutTracker
from .client import LangfuseConfig


class Prompt(YamlBaseSettings):
    model_config = SettingsConfigDict(
        yaml_file="./assets/agent_prompt.yaml",
        secrets_dir="./assets",
        extra="ignore",
    )

    system: str = Field(
        default="You are a helpful assistant.",
        description="The system prompt to use for the agent's interactions."
        "This prompt sets the context and behavior for the agent."
    )
    tool: Dict[str, str]
    chain: Dict[str, str]


class TrackingProvider(Enum):
    LANGFUSE = "langfuse"
    STDOUT = "stdout"
    NONE = "none"


class AgentConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    prompt: Prompt = Field(default_factory=Prompt)

    tracking_provider: TrackingProvider = Field(
        default=TrackingProvider.NONE,
        description="The provider to use for tracking the agent's interactions."
    )

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = Field(
        default="google_genai/gemini-2.0-flash",
        description="The name of the language model to use for the agent's main interactions."
        "Should be in the form: provider/model-name."
    )

    google_api_key: str = Field(description="The API key for the Google API.")
    google_cse_id: str = Field(description="The CSE ID for the Google API.")
    google_search_num_results: int = Field(
        default=5,
        description="The number of search results to return for each search query."
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "AgentConfig":
        """Create a AgentConfig instance from a RunnableConfig object."""
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        return cls(**{k: v for k, v in configurable.items() if k in cls.model_fields})

    def create_tracker(self) -> Optional[BaseTracker]:
        match self.tracking_provider:
            case TrackingProvider.LANGFUSE:
                return LangfuseTracker(LangfuseConfig())
            case TrackingProvider.STDOUT:
                return StdoutTracker()
            case TrackingProvider.NONE:
                return None

        raise ValueError(
            f"Invalid tracking provider: {self.tracking_provider}")
