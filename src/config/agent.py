from enum import Enum
from typing import Annotated, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import AsyncMongoClient, MongoClient
from langchain_core.runnables import RunnableConfig, ensure_config
from langgraph.types import Checkpointer
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver
from langgraph.checkpoint.mongodb import MongoDBSaver

from tracking import BaseTracker, LangfuseTracker, StdoutTracker
from .prompt import Prompt, PromptConfig
from .client import LangfuseConfig

_checkpointer: Optional[Checkpointer] = None
_tracker: Optional[BaseTracker] = None


class PromptProvider(Enum):
    YAML = "yaml"
    LANGFUSE = "langfuse"


class CheckpointerProvider(Enum):
    MEMORY = "memory"
    MONGODB = "mongodb"


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

    checkpointer_provider: CheckpointerProvider = Field(
        default=CheckpointerProvider.MEMORY,
        description="The provider to use for the agent's checkpointer."
    )

    checkpointer_mongodb_uri: Optional[str] = Field(
        default=None,
        description="The URI for the MongoDB database."
    )

    checkpointer_mongodb_async: bool = Field(
        default=True,
        description="Whether to use the async MongoDB checkpointer."
    )

    checkpointer_max_tokens: int = Field(
        default=65536*4,
        description="The maximum number of tokens to use for the agent's checkpointer aka the number of tokens to keep in the memory."
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
        default=3,
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

    def get_checkpointer(self, async_mongodb: bool = True) -> Checkpointer:
        global _checkpointer
        if _checkpointer is None:
            match self.checkpointer_provider:
                case CheckpointerProvider.MEMORY:
                    _checkpointer = MemorySaver()
                case CheckpointerProvider.MONGODB:
                    if async_mongodb:
                        _checkpointer = AsyncMongoDBSaver(
                            AsyncMongoClient(self.checkpointer_mongodb_uri))
                    else:
                        _checkpointer = MongoDBSaver(
                            MongoClient(self.checkpointer_mongodb_uri))
                case _:
                    raise ValueError(
                        f"Invalid checkpointer provider: {self.checkpointer_provider}")
        return _checkpointer

    def get_tracker(self) -> Optional[BaseTracker]:
        global _tracker
        if _tracker is None:
            match self.tracking_provider:
                case TrackingProvider.LANGFUSE:
                    _tracker = LangfuseTracker(self._get_langfuse_config())
                case TrackingProvider.STDOUT:
                    _tracker = StdoutTracker()
                case TrackingProvider.NONE:
                    _tracker = None
                case _:
                    raise ValueError(
                        f"Invalid tracking provider: {self.tracking_provider}")
        return _tracker
