"""Report application errors and present messages to the user."""

from __future__ import annotations

import logging

from PySide6.QtCore import QCoreApplication, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget


class ErrorService:
    """central service for exception reporting and user dialogs."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    @staticmethod
    def tr(text: str) -> str:
        """Translate a message owned by the error service."""

        return QCoreApplication.translate("ErrorService", text)

    def report_exception(self, context: str, exc: BaseException) -> None:
        """log exception with context."""

        self._logger.exception("%s", context, exc_info=exc)

    def show_user_error(self, title: str, message: str, parent: QWidget | None = None) -> None:
        """show non-blocking error dialog."""

        self._logger.error("%s: %s", title, message)
        if QApplication.instance() is None:
            return

        dialog = QMessageBox(parent)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.setIcon(QMessageBox.Icon.Critical)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.open()

    def show_user_warning(self, title: str, message: str, parent: QWidget | None = None) -> None:
        """show non-blocking warning dialog."""

        self._logger.warning("%s: %s", title, message)
        if QApplication.instance() is None:
            return

        dialog = QMessageBox(parent)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.setIcon(QMessageBox.Icon.Warning)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.open()

    def show_user_info(self, title: str, message: str, parent: QWidget | None = None) -> None:
        """show non-blocking info dialog."""

        self._logger.info("%s: %s", title, message)
        if QApplication.instance() is None:
            return

        dialog = QMessageBox(parent)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        dialog.setIcon(QMessageBox.Icon.Information)
        dialog.setWindowTitle(title)
        dialog.setText(message)
        dialog.open()

    def ask_save_discard_cancel(
        self,
        parent: QWidget,
        title: str,
        message: str,
    ) -> QMessageBox.StandardButton:
        """ask user to save, discard or cancel."""

        dialog = QMessageBox(parent)
        dialog.setIcon(QMessageBox.Icon.Question)
        dialog.setWindowTitle(title)
        dialog.setText(message)

        save_button = dialog.addButton(
            self.tr("Save"),
            QMessageBox.ButtonRole.AcceptRole,
        )
        discard_button = dialog.addButton(
            self.tr("Discard"),
            QMessageBox.ButtonRole.DestructiveRole,
        )
        cancel_button = dialog.addButton(
            self.tr("Cancel"),
            QMessageBox.ButtonRole.RejectRole,
        )
        dialog.setDefaultButton(save_button)
        dialog.exec()

        clicked = dialog.clickedButton()
        if clicked == save_button:
            return QMessageBox.StandardButton.Save
        if clicked == discard_button:
            return QMessageBox.StandardButton.Discard
        if clicked == cancel_button:
            return QMessageBox.StandardButton.Cancel
        return QMessageBox.StandardButton.Cancel


__all__ = ["ErrorService"]
