import httpx

from enum import Enum
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse
from langfuse.client import DatasetStatus
from langfuse.callback import CallbackHandler

from common import get_logger
from config import LangfuseConfig
from .base import BaseTracker


class LangfuseDataset(Enum):
    EMOJI_FEEDBACK = "emoji_feedback"
    EMOJI_UNSCORED = "emoji_unscored"


class LangfuseTracker(BaseTracker):
    def __init__(self, config: LangfuseConfig):
        self.logger = get_logger()

        httpx_client = httpx.Client(verify=not config.skip_ssl_verify)

        self.langfuse = Langfuse(
            host=config.url,
            public_key=config.public_key,
            secret_key=config.secret_key,
            environment=config.environment,
            release=config.release,
            httpx_client=httpx_client,
        )
        assert self.langfuse.auth_check()
        self.langfuse.create_dataset(
            name=LangfuseDataset.EMOJI_FEEDBACK.value,
            description="Emoji feedback records",
        )
        self.langfuse.create_dataset(
            name=LangfuseDataset.EMOJI_UNSCORED.value,
            description="Emoji unscored records",
        )

        self.langfuse_callback_handler = CallbackHandler(
            host=config.url,
            public_key=config.public_key,
            secret_key=config.secret_key,
            environment=config.environment,
            release=config.release,
            version=config.version,
            httpx_client=httpx_client,
        )
        assert self.langfuse_callback_handler.auth_check()

    def inject_runnable_config(self, config: RunnableConfig) -> RunnableConfig:
        config = super().inject_runnable_config(config)
        config["callbacks"].append(self.langfuse_callback_handler)
        if "user_id" in config["metadata"]:
            config["metadata"]["langfuse_user_id"] = config["metadata"]["user_id"]
        if "session_id" in config["metadata"]:
            config["metadata"]["langfuse_session_id"] = config["metadata"]["session_id"]
        return config

    def collect_emoji_feedback(self, message_id: str, user_id: str,  message: str, reply_message: str, emoji_name: str) -> None:
        if (emoji := self.emoji_sentiment.get(emoji_name)) is None:
            self.logger.warning("no sentiment score found for emoji",
                                message_id=message_id, message=message, reply_message=reply_message, emoji_name=emoji_name)
            self.langfuse.create_dataset_item(
                dataset_name=LangfuseDataset.EMOJI_UNSCORED.value,
                id=emoji_name,
                source_trace_id=message_id,
                status=DatasetStatus.ACTIVE,
            )
            return

        self.langfuse.score(
            id=f"{message_id}:{user_id}:{emoji_name}",
            name=LangfuseDataset.EMOJI_FEEDBACK.value,
            data_type="NUMERIC",
            value=emoji.score,
            trace_id=message_id
        )

        self.logger.info(f"received user {"positive" if emoji.score >= 0 else "negative"} feedback",
                         message_id=message_id, user_id=user_id, message=message, reply_message=reply_message, emoji=emoji)

        self.langfuse.create_dataset_item(
            dataset_name=LangfuseDataset.EMOJI_FEEDBACK.value,
            id=f"{message_id}:{user_id}:{emoji_name}",
            input=message,
            expected_output=reply_message,
            source_trace_id=message_id,
            metadata={"emoji": emoji.model_dump(
            ), "feedback": "positive" if emoji.score >= 0 else "negative"},
            status=DatasetStatus.ACTIVE,
        )

    def flush(self) -> None:
        self.langfuse.shutdown()
        self.langfuse_callback_handler.flush()
