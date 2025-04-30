import httpx
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from langfuse import Langfuse
from langfuse.callback import CallbackHandler


_httpx_client: Optional[httpx.Client] = None
_langfuse_client: Optional[Langfuse] = None
_langfuse_callback_handler: Optional[CallbackHandler] = None


class LangfuseConfig(BaseSettings):
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
