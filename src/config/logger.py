from pydantic_settings import BaseSettings, SettingsConfigDict


class LoggerConfig(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOG_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    level: str = "INFO"
