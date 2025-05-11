from enum import Enum
from abc import ABC, abstractmethod

from emoji_sentiment import EmojiSentiment
from langchain_core.runnables import RunnableConfig


class Score(Enum):
    EMOJI_FEEDBACK = "emoji_feedback"


class Dataset(Enum):
    EMOJI_FEEDBACK_POSITIVE = "emoji_feedback_positive"
    EMOJI_FEEDBACK_NEGATIVE = "emoji_feedback_negative"
    EMOJI_UNSCORED = "emoji_unscored"


class BaseTracker(ABC):
    emoji_sentiment = EmojiSentiment(round_to=4)

    def inject_runnable_config(self, config: RunnableConfig) -> RunnableConfig:
        if "callbacks" not in config:
            config["callbacks"] = []
        if "metadata" not in config:
            config["metadata"] = {}
        return config

    @abstractmethod
    def collect_emoji_feedback(self, message_id: str, user_id: str, message: str, reply_message: str, emoji_name: str) -> None:
        return NotImplemented

    def flush() -> None:
        pass
