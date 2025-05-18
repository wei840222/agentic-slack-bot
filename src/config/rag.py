from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from langchain_core.runnables import RunnableConfig, ensure_config

from .logger import LoggerMixin
from .model import ModelMixin
from .prompt import PromptMixin
from .client import QdrantConfig


class RagConfig(BaseSettings, LoggerMixin, ModelMixin, PromptMixin):
    model_config = SettingsConfigDict(
        env_prefix="RAG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_api_key: str = Field(description="The API key for the Google API.")
    google_cse_id: str = Field(description="The CSE ID for the Google API.")
    google_search_default_top_n: int = Field(
        default=3,
        description="The number of search results to return for each search query."
    )

    slack_search_default_top_n: int = Field(
        default=3,
        description="The number of search results to return for each search query."
    )

    slack_search_top_p: float = Field(
        default=0.6,
        description="The score threshold for the search results."
    )
    slack_search_rerank_top_n_multiplier: float = Field(
        default=5.0,
        description="The multiplier for the number of search results to fetch before reranking. For example, if num_results=10 and multiplier=3, we'll fetch 30 results then rerank to get the top 10."
    )

    _qdrant_config: Optional[QdrantConfig] = None

    @classmethod
    def from_runnable_config(
        cls, config: Optional[RunnableConfig] = None
    ) -> "RagConfig":
        """Create a RagConfig instance from a RunnableConfig object."""
        config = ensure_config(config)
        configurable = config.get("configurable") or {}
        return cls(**{k: v for k, v in configurable.items() if k in cls.model_fields})

    def get_qdrant_config(self) -> QdrantConfig:
        if self._qdrant_config is None:
            self._qdrant_config = QdrantConfig()
        return self._qdrant_config
