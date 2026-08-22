"""Configure file and optional console logging for the application."""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from starflight.app.constants import APP_DISPLAY_NAME, APP_ID

DEV_CONSOLE_LOG_ENV = "NA_DEV_CONSOLE_LOG"


def get_log_file_path() -> Path:
    """return application log file path."""

    log_dir = Path.home() / "Library" / "Logs" / APP_DISPLAY_NAME
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{APP_ID}.log"


def configure_logging() -> logging.Logger:
    """configure application logger once."""

    logger = logging.getLogger(APP_ID)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        get_log_file_path(),
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if os.getenv(DEV_CONSOLE_LOG_ENV) == "1":
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.info("logger initialized")
    return logger


__all__ = ["DEV_CONSOLE_LOG_ENV", "configure_logging", "get_log_file_path"]
