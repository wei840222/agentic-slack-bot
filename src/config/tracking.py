from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class LangfuseConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LANGFUSE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    url: Optional[str] = None
    skip_ssl_verify: bool = False
    public_key: str = ""
    secret_key: str = ""
    environment: str = ""
    release: str = ""
    version: str = ""


class TrackingConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRACKING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(
        default=False, description="Whether to enable tracking.")

    langfuse: LangfuseConfig = Field(default_factory=LangfuseConfig)
