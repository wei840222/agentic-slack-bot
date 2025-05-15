from enum import Enum
from typing import Annotated, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pymongo import AsyncMongoClient, MongoClient
from langchain_core.runnables import Runnable, RunnableConfig, ensure_config
from langchain.chat_models import init_chat_model
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_google_vertexai import VertexAIEmbeddings
from langgraph.types import Checkpointer
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.mongodb.aio import AsyncMongoDBSaver
from langgraph.checkpoint.mongodb import MongoDBSaver

from tracking import BaseTracker, StdoutTracker, LangfuseTracker, LangSmithTracker
from .logger import LoggerMixin
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


class AgentConfig(BaseSettings, LoggerMixin, PromptMixin, EmojiMixin, MessageMixin):
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

    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = Field(
        # default="google_vertexai/gemini-2.0-flash",
        default="google_genai/gemini-2.0-flash",
        description="The name of the language model to use for the agent's main interactions."
        "Should be in the form: provider/model-name."
    )

    embeddings_model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = Field(
        # default="google_vertexai/text-embedding-large-exp-03-07",
        default="google_genai/gemini-embedding-exp-03-07",
        description="The name of the language model to use for the agent's embeddings."
        "Should be in the form: provider/model-name."
    )

    google_api_key: str = Field(description="The API key for the Google API.")
    google_cse_id: str = Field(description="The CSE ID for the Google API.")
    google_search_default_num_results: int = Field(
        default=3,
        description="The number of search results to return for each search query."
    )

    slack_search_default_num_results: int = Field(
        default=3,
        description="The number of search results to return for each search query."
    )

    slack_search_score_threshold: float = Field(
        default=0.6,
        description="The score threshold for the search results."
    )

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "AgentConfig":
        """Create a AgentConfig instance from a RunnableConfig object."""
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        return cls(**{k: v for k, v in configurable.items() if k in cls.model_fields})

    def load_chat_model(self) -> Runnable:
        provider, model = self.model.split("/", maxsplit=1)
        kwargs = {}
        if provider == "google_genai":
            kwargs["google_api_key"] = self.google_api_key
        return init_chat_model(model, model_provider=provider, **kwargs)

    def load_embeddings_model(self) -> Runnable:
        provider, model = self.embeddings_model.split("/", maxsplit=1)
        if provider == "google_genai":
            return GoogleGenerativeAIEmbeddings(model=f"models/{model}", task_type="semantic_similarity", google_api_key=self.google_api_key)
        if provider == "google_vertexai":
            return VertexAIEmbeddings(model)
        raise ValueError(
            f"Invalid embeddings model provider: {provider}")

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
