from abc import ABC, abstractmethod

from langchain_core.callbacks import BaseCallbackHandler


class BaseTracker(ABC):
    @abstractmethod
    def get_langchain_callbackk_handler(self) -> BaseCallbackHandler:
        return NotImplemented

    @abstractmethod
    def collect_emoji_feedback(self, message_id: str, message: str, reply_message: str, emoji_name: str):
        return NotImplemented
