from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TrackingConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TRACKING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    enabled: bool = Field(
        default=False, description="Whether to enable tracking.")
