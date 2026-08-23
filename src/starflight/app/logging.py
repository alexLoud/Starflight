"""Configure file and optional console logging for the application."""

from __future__ import annotations

import datetime as dt
import logging
import os
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

from starflight.app.constants import APP_DISPLAY_NAME, APP_ID

DEV_CONSOLE_LOG_ENV = "NA_DEV_CONSOLE_LOG"


class _IsoFormatter(logging.Formatter):
    """format timestamps with local timezone and millisecond precision."""

    def formatTime(  # noqa: N802
        self,
        record: logging.LogRecord,
        datefmt: str | None = None,
    ) -> str:
        del datefmt
        timestamp = dt.datetime.fromtimestamp(record.created).astimezone()
        return timestamp.isoformat(timespec="milliseconds")


def get_log_directory() -> Path:
    """return the platform-specific application log directory."""

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / APP_DISPLAY_NAME
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA")
        root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return root / APP_DISPLAY_NAME / "Logs"

    state_home = os.getenv("XDG_STATE_HOME")
    root = Path(state_home) if state_home else Path.home() / ".local" / "state"
    return root / APP_ID


def _writable_log_directory() -> Path:
    """create the normal log directory or fall back to the system temp directory."""

    candidates = (get_log_directory(), Path(tempfile.gettempdir()) / APP_ID / "logs")
    for directory in candidates:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=directory):
                pass
            return directory
        except OSError:
            continue
    return candidates[-1]


def get_log_file_path() -> Path:
    """return application log file path."""

    return _writable_log_directory() / f"{APP_ID}.log"


def configure_logging() -> logging.Logger:
    """configure application logger once."""

    logger = logging.getLogger(APP_ID)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    formatter = _IsoFormatter(
        fmt=(
            "%(asctime)s | %(levelname)s | pid=%(process)d | "
            "thread=%(threadName)s(%(thread)d) | %(name)s | %(message)s"
        ),
    )

    try:
        file_handler = RotatingFileHandler(
            get_log_file_path(),
            maxBytes=2 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        logger.addHandler(logging.NullHandler())

    if os.getenv(DEV_CONSOLE_LOG_ENV) == "1":
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(formatter)
        logger.addHandler(stream_handler)

    logger.info("logger initialized | log_path=%s", get_log_file_path())
    return logger


__all__ = [
    "DEV_CONSOLE_LOG_ENV",
    "configure_logging",
    "get_log_directory",
    "get_log_file_path",
]
