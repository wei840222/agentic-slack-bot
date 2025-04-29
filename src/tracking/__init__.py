from typing import Optional

from config import TrackingConfig
from .base import BaseTracker
from .stdout import StdoutTracker


def create_tracker(config: TrackingConfig) -> Optional[BaseTracker]:
    if config.enabled:
        return StdoutTracker()
    else:
        return None


__all__ = ["create_tracker"]
