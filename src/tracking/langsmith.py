import os
from langchain_core.runnables import RunnableConfig
from langsmith.utils import LangSmithConflictError

from config.client import LangSmithConfig
from .base import BaseTracker, Score, Dataset


class LangSmithTracker(BaseTracker):
    def __init__(self, config: LangSmithConfig):
        self.logger = config.get_logger()
        self.config = config
        self.langsmith = config.get_langsmith_client()

        try:
            self.langsmith.create_dataset(
                dataset_name=Dataset.EMOJI_FEEDBACK_POSITIVE.value,
                description="Emoji feedback positive records",
            )
        except LangSmithConflictError as e:
            pass
        try:
            self.langsmith.create_dataset(
                dataset_name=Dataset.EMOJI_FEEDBACK_NEGATIVE.value,
                description="Emoji feedback negative records",
            )
        except LangSmithConflictError as e:
            pass
        try:
            self.langsmith.create_dataset(
                dataset_name=Dataset.EMOJI_UNSCORED.value,
                description="Emoji unscored records",
            )
        except LangSmithConflictError as e:
            pass

    def inject_runnable_config(self, config: RunnableConfig) -> RunnableConfig:
        config = super().inject_runnable_config(config)
        config["metadata"]["environment"] = self.config.environment
        config["metadata"]["release"] = self.config.release
        config["metadata"]["version"] = self.config.version
        return config

    def collect_emoji_feedback(self, message_id: str, user_id: str,  message: str, reply_message: str, emoji_name: str) -> None:
        if (emoji := self.emoji_sentiment.get(emoji_name)) is None:
            self.logger.warning("no sentiment score found for emoji",
                                message_id=message_id, message=message, reply_message=reply_message, emoji_name=emoji_name)
            self.langsmith.create_example(
                dataset_name=Dataset.EMOJI_UNSCORED.value,
                inputs={"message": message},
                outputs={"reply_message": reply_message},
                source_run_id=message_id,
                metadata={"user_id": user_id, "emoji_name": emoji_name}
            )
            return

        self.langsmith.create_feedback(
            message_id,
            key=Score.EMOJI_FEEDBACK.value,
            score=emoji.score,
            extra={"user_id": user_id, "emoji": emoji.model_dump()}
        )

        self.logger.info(f"received user {"positive" if emoji.score >= 0 else "negative"} feedback",
                         message_id=message_id, user_id=user_id, message=message, reply_message=reply_message, emoji=emoji)

        self.langsmith.create_example(
            dataset_name=Dataset.EMOJI_FEEDBACK_POSITIVE.value if emoji.score >= 0 else Dataset.EMOJI_FEEDBACK_NEGATIVE.value,
            inputs={"message": message},
            outputs={"reply_message": reply_message},
            source_run_id=message_id,
            metadata={"user_id": user_id, "emoji": emoji.model_dump()}
        )

    def flush(self) -> None:
        self.langsmith.flush()
        self.langsmith.cleanup()
