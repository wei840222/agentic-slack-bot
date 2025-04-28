import logging
import structlog
from functools import cache
from config import LoggerConfig


@cache
def get_logger() -> logging.Logger:
    config = LoggerConfig()

    structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, config.level.upper())))

    return structlog.stdlib.get_logger()
