"""Report application errors and present messages to the user."""

from __future__ import annotations

import logging
from pathlib import Path
from types import TracebackType

from PySide6.QtCore import QCoreApplication, QObject, Qt, Signal
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from starflight.app.crash_reporting import CrashReport, CrashReporter
from starflight.views.dialogs.crash_report_dialog import (
    CrashReportDialog,
    RecoveredCrashReportDialog,
)


class ErrorService(QObject):
    """central service for exception reporting and user dialogs."""

    _crash_report_requested = Signal(object, bool)

    def __init__(self, logger: logging.Logger, crash_reporter: CrashReporter) -> None:
        super().__init__()
        self._logger = logger
        self._crash_reporter = crash_reporter
        self._presenting_crash_report = False
        self._crash_report_requested.connect(
            self._present_queued_crash_report,
            Qt.ConnectionType.QueuedConnection,
        )

    @staticmethod
    def tr(text: str) -> str:
        """Translate a message owned by the error service."""

        return QCoreApplication.translate("ErrorService", text)

    def report_exception(self, context: str, exc: BaseException) -> CrashReport:
        """persist an exception for compatibility with non-UI callers."""

        return self._crash_reporter.capture_exception(context, exc)

    def show_crash_report(
        self,
        context: str,
        exc: BaseException,
        parent: QWidget | None = None,
        *,
        fatal: bool = False,
    ) -> CrashReport:
        """persist and immediately present a safely contained runtime failure."""

        report = self._crash_reporter.capture_exception(context, exc)
        self.present_crash_report(report, parent, fatal=fatal)
        return report

    def queue_crash_report(
        self,
        context: str,
        exc: BaseException,
        tb: TracebackType | None = None,
        *,
        fatal: bool,
    ) -> CrashReport:
        """persist a failure and queue its dialog on the Qt UI thread."""

        report = self._crash_reporter.capture_exception(context, exc, tb)
        if QApplication.instance() is not None:
            self._crash_report_requested.emit(report, fatal)
        return report

    def present_pending_crash_reports(self) -> None:
        """show only the newest pending report and acknowledge the complete backlog."""

        report, pending_paths = self._crash_reporter.latest_pending_report()
        if report is None:
            if pending_paths:
                self._crash_reporter.mark_pending_reports_presented(pending_paths)
            return
        app = QApplication.instance()
        parent = app.activeWindow() if app is not None else None
        self._present_report_dialog(
            report,
            RecoveredCrashReportDialog,
            parent,
            pending_paths,
            fatal=False,
            pending_count=len(pending_paths),
        )

    def present_crash_report(
        self,
        report: CrashReport,
        parent: QWidget | None = None,
        *,
        fatal: bool = False,
    ) -> None:
        """show a copyable crash report and mark it as presented."""

        self._present_report_dialog(
            report,
            CrashReportDialog,
            parent,
            [report.path],
            fatal=fatal,
        )
        app = QApplication.instance()
        if fatal and app is not None:
            app.exit(1)

    def _present_report_dialog(
        self,
        report: CrashReport,
        dialog_type: type[CrashReportDialog],
        parent: QWidget | None,
        paths_to_acknowledge: list[Path],
        *,
        fatal: bool,
        pending_count: int = 1,
    ) -> None:
        """show one crash-report dialog while preventing nested reports."""

        if QApplication.instance() is None or self._presenting_crash_report:
            return
        self._presenting_crash_report = True
        try:
            if dialog_type is RecoveredCrashReportDialog:
                dialog = RecoveredCrashReportDialog(
                    report,
                    self._crash_reporter.log_path.parent,
                    parent,
                    fatal=fatal,
                    pending_count=pending_count,
                )
            else:
                dialog = dialog_type(
                    report,
                    self._crash_reporter.log_path.parent,
                    parent,
                    fatal=fatal,
                )
            dialog.exec()
            self._crash_reporter.mark_pending_reports_presented(paths_to_acknowledge)
        except Exception:
            self._logger.exception("crash report dialog failed")
        finally:
            self._presenting_crash_report = False

    def _present_queued_crash_report(self, report: CrashReport, fatal: bool) -> None:
        """present a queued report after the failing Qt callback has unwound."""

        app = QApplication.instance()
        if app is None:
            return
        active_window = app.activeWindow()
        self.present_crash_report(report, active_window, fatal=fatal)

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
