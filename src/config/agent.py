from enum import Enum
from typing import Annotated, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_core.runnables import RunnableConfig, ensure_config

from tracking import BaseTracker, LangfuseTracker, StdoutTracker
from .prompt import Prompt, PromptConfig
from .client import LangfuseConfig


class PromptProvider(Enum):
    YAML = "yaml"
    LANGFUSE = "langfuse"


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

    _langfuse_config: LangfuseConfig = None
    _prompt_config: PromptConfig = None

    prompt_provider: PromptProvider = Field(
        default=PromptProvider.YAML,
        description="The provider to use for the agent's prompts."
    )

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

    def _get_langfuse_config(self) -> LangfuseConfig:
        if self._langfuse_config is None:
            self._langfuse_config = LangfuseConfig()
        return self._langfuse_config

    def get_prompt(self, name: str) -> Prompt:
        match self.prompt_provider:
            case PromptProvider.YAML:
                if self._prompt_config is None:
                    self._prompt_config = PromptConfig()
                return self._prompt_config.get_prompt(name)
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

    def create_tracker(self) -> Optional[BaseTracker]:
        match self.tracking_provider:
            case TrackingProvider.LANGFUSE:
                return LangfuseTracker(self._get_langfuse_config())
            case TrackingProvider.STDOUT:
                return StdoutTracker()
            case TrackingProvider.NONE:
                return None
            case _:
                raise ValueError(
                    f"Invalid tracking provider: {self.tracking_provider}")
