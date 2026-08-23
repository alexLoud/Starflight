"""Route Qt diagnostic messages into the application log."""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QMessageLogContext, QtMsgType, qInstallMessageHandler

QtMessageHandler = Callable[[QtMsgType, QMessageLogContext, str], None]


def install_qt_message_logging(logger: logging.Logger) -> QtMessageHandler | None:
    """install a process-wide Qt message handler backed by the application logger."""

    levels = {
        QtMsgType.QtDebugMsg: logging.DEBUG,
        QtMsgType.QtInfoMsg: logging.INFO,
        QtMsgType.QtWarningMsg: logging.WARNING,
        QtMsgType.QtCriticalMsg: logging.ERROR,
        QtMsgType.QtFatalMsg: logging.CRITICAL,
    }

    def handle_message(
        message_type: QtMsgType,
        context: QMessageLogContext,
        message: str,
    ) -> None:
        category = context.category or "default"
        location = ""
        if context.file:
            location = f" ({context.file}:{context.line})"
        logger.log(
            levels.get(message_type, logging.INFO),
            "Qt[%s]%s: %s",
            category,
            location,
            message,
        )

    return qInstallMessageHandler(handle_message)


def restore_qt_message_logging(previous_handler: QtMessageHandler | None) -> None:
    """restore the Qt message handler that preceded application logging."""

    qInstallMessageHandler(previous_handler)


__all__ = ["install_qt_message_logging", "restore_qt_message_logging"]
