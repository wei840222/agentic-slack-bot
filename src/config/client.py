import os
import httpx
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from langsmith import Client as LangSmith
from langfuse import Langfuse
from langfuse.callback import CallbackHandler
from .logger import LoggerMixin


_httpx_client: Optional[httpx.Client] = None
_langfuse_client: Optional[Langfuse] = None
_langfuse_callback_handler: Optional[CallbackHandler] = None


class LangfuseConfig(BaseSettings, LoggerMixin):
    model_config = SettingsConfigDict(
        env_prefix="LANGFUSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: str = "https://cloud.langfuse.com"
    skip_ssl_verify: bool = False
    public_key: Optional[str] = None
    secret_key: Optional[str] = None
    environment: str = "local"
    release: str = "nightly"
    version: str = "0.0.0"

    @property
    def enabled(self) -> bool:
        return self.public_key is not None and self.secret_key is not None

    def _get_httpx_client(self) -> httpx.Client:
        global _httpx_client
        if _httpx_client is None:
            _httpx_client = httpx.Client(verify=not self.skip_ssl_verify)
        return _httpx_client

    def get_langfuse_client(self) -> Langfuse:
        if not self.enabled:
            raise RuntimeError("Langfuse is not enabled")

        global _langfuse_client
        if _langfuse_client is None:
            _langfuse_client = Langfuse(
                host=self.url,
                public_key=self.public_key,
                secret_key=self.secret_key,
                environment=self.environment,
                release=self.release,
                httpx_client=self._get_httpx_client(),
            )
            assert _langfuse_client.auth_check()

        return _langfuse_client

    def get_langfuse_callback_handler(self) -> CallbackHandler:
        if not self.enabled:
            raise RuntimeError("Langfuse is not enabled")

        global _langfuse_callback_handler
        if _langfuse_callback_handler is None:
            _langfuse_callback_handler = CallbackHandler(
                host=self.url,
                public_key=self.public_key,
                secret_key=self.secret_key,
                environment=self.environment,
                release=self.release,
                version=self.version,
                httpx_client=self._get_httpx_client(),
            )
            assert _langfuse_callback_handler.auth_check()

        return _langfuse_callback_handler


_langsmith_client: Optional[LangSmith] = None


class LangSmithConfig(BaseSettings, LoggerMixin):
    model_config = SettingsConfigDict(
        env_prefix="LANGSMITH_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    endpoint: str = "https://api.smith.langchain.com"
    project: Optional[str] = None
    api_key: Optional[str] = None
    environment: str = "local"
    release: str = "nightly"
    version: str = "0.0.0"

    @property
    def enabled(self) -> bool:
        return self.project is not None and self.api_key is not None

    def get_langsmith_client(self) -> LangSmith:
        if not self.enabled:
            raise RuntimeError("LangSmith is not enabled")

        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_ENDPOINT"] = self.endpoint
        os.environ["LANGSMITH_PROJECT"] = self.project
        os.environ["LANGSMITH_API_KEY"] = self.api_key

        global _langsmith_client
        if _langsmith_client is None:
            _langsmith_client = LangSmith(
                api_url=self.endpoint, api_key=self.api_key)

        return _langsmith_client
