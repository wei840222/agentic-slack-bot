from functools import cache

from emoji_sentiment import EmojiSentiment
from langchain_core.callbacks import BaseCallbackHandler, StdOutCallbackHandler

from common import get_logger
from .base import BaseTracker


class StdoutTracker(BaseTracker):
    emoji_sentiment = EmojiSentiment(round_to=4)

    def __init__(self):
        self.logger = get_logger()

    @cache
    def get_langchain_callbackk_handler(self) -> BaseCallbackHandler:
        return StdOutCallbackHandler()

    def collect_emoji_feedback(self, message_id: str, message: str, reply_message: str, emoji_name: str):
        if (emoji := self.emoji_sentiment.get(emoji_name)) is None:
            self.logger.warning("no sentiment score found for emoji",
                                message_id=message_id, message=message, reply_message=reply_message, emoji_name=emoji_name)
            return

        if emoji.score >= 0:
            self.logger.info("received user positive feedback",
                             message_id=message_id, message=message, reply_message=reply_message, emoji=emoji)
        else:
            self.logger.info("received user negative feedback",
                             message_id=message_id, message=message, reply_message=reply_message, emoji=emoji)
