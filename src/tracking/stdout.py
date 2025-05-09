from langchain_core.callbacks import StdOutCallbackHandler
from langchain_core.runnables import RunnableConfig

from config.logger import LoggerConfig
from .base import BaseTracker


class StdoutTracker(BaseTracker):
    def __init__(self, config: LoggerConfig):
        self.logger = config.logger

    def inject_runnable_config(self, config: RunnableConfig) -> RunnableConfig:
        config = super().inject_runnable_config(config)
        config["callbacks"].append(StdOutCallbackHandler())
        return config

    def collect_emoji_feedback(self, message_id: str, user_id: str, message: str, reply_message: str, emoji_name: str) -> None:
        if (emoji := self.emoji_sentiment.get(emoji_name)) is None:
            self.logger.warning("no sentiment score found for emoji",
                                message_id=message_id, user_id=user_id, message=message, reply_message=reply_message, emoji_name=emoji_name)
            return

        self.logger.info(f"received user {"positive" if emoji.score >= 0 else "negative"} feedback",
                         message_id=message_id, user_id=user_id, message=message, reply_message=reply_message, emoji=emoji)
