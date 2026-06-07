"""Runtime logging sink backed by stdlib logging."""

from __future__ import annotations

import logging
import sys


LOGGER_NAME = "stock_agent.runtime"


def get_runtime_logger() -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


def log_runtime_message(message: str, *, level: str = "info") -> None:
    logger = get_runtime_logger()
    log_method = getattr(logger, str(level or "info").lower(), logger.info)
    log_method(str(message)[:500])
