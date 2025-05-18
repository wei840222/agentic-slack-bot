from enum import Enum
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import AsyncMongoClient, MongoClient
from langchain_core.runnables import RunnableConfig, ensure_config
from langgraph.types import Checkpointer
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver
from langgraph.checkpoint.mongodb import MongoDBSaver

from tracking import BaseTracker, StdoutTracker, LangfuseTracker, LangSmithTracker
from .logger import LoggerMixin
from .model import ModelMixin
from .prompt import PromptMixin
from .message import EmojiMixin, MessageMixin

_checkpointer: Optional[Checkpointer] = None
_tracker: Optional[BaseTracker] = None


class CheckpointerProvider(Enum):
    MEMORY = "memory"
    MONGODB = "mongodb"


class TrackingProvider(Enum):
    NONE = "none"
    STDOUT = "stdout"
    LANGSMITH = "langsmith"
    LANGFUSE = "langfuse"


class AgentConfig(BaseSettings, LoggerMixin, ModelMixin, PromptMixin, EmojiMixin, MessageMixin):
    model_config = SettingsConfigDict(
        env_prefix="AGENT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
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

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "AgentConfig":
        """Create a AgentConfig instance from a RunnableConfig object."""
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        return cls(**{k: v for k, v in configurable.items() if k in cls.model_fields})

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
                case TrackingProvider.NONE:
                    _tracker = None
                case TrackingProvider.STDOUT:
                    _tracker = StdoutTracker()
                case TrackingProvider.LANGSMITH:
                    _tracker = LangSmithTracker(self._get_langsmith_config())
                case TrackingProvider.LANGFUSE:
                    _tracker = LangfuseTracker(self._get_langfuse_config())
                case _:
                    raise ValueError(
                        f"Invalid tracking provider: {self.tracking_provider}")
        return _tracker
