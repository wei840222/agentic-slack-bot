from typing import Optional

from config import TrackingConfig
from .base import BaseTracker
from .stdout_tracker import StdoutTracker
from .langfuse_tracker import LangfuseTracker


def create_tracker(config: TrackingConfig) -> Optional[BaseTracker]:
    if config.enabled:
        if config.langfuse.public_key is not None and config.langfuse.secret_key is not None:
            return LangfuseTracker(config.langfuse)
        else:
            return StdoutTracker()
    else:
        return None


__all__ = ["create_tracker"]
