from typing import Annotated

from pydantic import Field
from langchain_core.language_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain.chat_models import init_chat_model
from langchain_google_vertexai import VertexAIEmbeddings


class ModelMixin:
    model: Annotated[str, {"__template_metadata__": {"kind": "llm"}}] = Field(
        default="google_vertexai/gemini-2.5-flash-preview-04-17",
        description="The name of the language model to use for the agent's main interactions."
        "Should be in the form: provider/model-name."
    )

    embeddings_model: str = Field(
        default="google_vertexai/text-embedding-large-exp-03-07",
        description="The name of the language model to use for the agent's embeddings."
        "Should be in the form: provider/model-name."
    )

    rerank_model: str = Field(
        default="semantic-ranker-default-004",
        description="The name of the rerank model to use for the rag reranking."
    )

    def load_chat_model(self, **kwargs) -> BaseChatModel:
        provider, model = self.model.split("/", maxsplit=1)
        return init_chat_model(model, model_provider=provider, **kwargs)

    def load_embeddings_model(self) -> Embeddings:
        provider, model = self.embeddings_model.split("/", maxsplit=1)
        if provider == "google_vertexai":
            return VertexAIEmbeddings(model)
        raise ValueError(
            f"Invalid embeddings model provider: {provider}")
