"""Crash-report persistence, diagnostics, and hook regression tests."""

from __future__ import annotations

import logging
import os
import re
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication, QTimer, qWarning
from PySide6.QtWidgets import QApplication

from starflight.app import logging as app_logging
from starflight.app.bootstrap import _install_global_exception_hooks
from starflight.app.crash_reporting import CrashReport, CrashReporter
from starflight.app.launcher import main as launch_application
from starflight.app.qt_diagnostics import (
    install_qt_message_logging,
    restore_qt_message_logging,
)
from starflight.services.error_service import ErrorService
from starflight.views.dialogs.crash_report_dialog import (
    CrashReportDialog,
    RecoveredCrashReportDialog,
)


class CrashReporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_directory.name)
        self.log_path = self.root / "starflight.log"
        self.logger = logging.getLogger(f"starflight-test-{id(self)}")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        self.handler = logging.FileHandler(self.log_path, encoding="utf-8")
        self.logger.addHandler(self.handler)
        self.reporter = CrashReporter(
            self.logger,
            log_path=self.log_path,
            report_directory=self.root / "reports",
        )

    def tearDown(self) -> None:
        self.reporter.shutdown()
        self.handler.close()
        self.logger.handlers.clear()
        self.temp_directory.cleanup()

    def test_exception_report_contains_runtime_os_traceback_and_log(self) -> None:
        self.logger.info("diagnostic log marker")
        try:
            raise RuntimeError("render pipeline failed")
        except RuntimeError as exc:
            report = self.reporter.capture_exception("preview rendering failed", exc)

        self.assertTrue(report.path.is_file())
        self.assertTrue(report.path.name.endswith(".pending.txt"))
        self.assertIn("Operating system:", report.text)
        self.assertIn("OS version:", report.text)
        self.assertIn("Architecture:", report.text)
        self.assertIn("Python version:", report.text)
        self.assertIn("PySide version:", report.text)
        self.assertIn("Qt version:", report.text)
        self.assertIn(f"Crash report directory: {self.reporter.report_directory}", report.text)
        self.assertIn(f"Application log: {self.log_path}", report.text)
        self.assertIn("preview rendering failed", report.text)
        self.assertIn("RuntimeError: render pipeline failed", report.text)
        self.assertIn("diagnostic log marker", report.text)

    def test_presented_report_is_retained_but_no_longer_pending(self) -> None:
        report = self.reporter.capture_exception("test failure", ValueError("broken"))

        acknowledged = self.reporter.mark_presented(report)

        self.assertTrue(acknowledged.path.is_file())
        self.assertFalse(acknowledged.path.name.endswith(".pending.txt"))
        self.assertEqual(self.reporter.pending_reports(), [])

    def test_only_nonempty_native_fault_trace_creates_pending_report(self) -> None:
        native_directory = self.reporter.native_fault_directory
        native_directory.mkdir(parents=True)
        (native_directory / "native-fault-empty.log").write_text("", encoding="utf-8")
        (native_directory / "native-fault-crashed.log").write_text(
            "Fatal Python error: Aborted\nCurrent thread traceback",
            encoding="utf-8",
        )

        self.reporter.start_native_fault_capture()
        pending = self.reporter.pending_reports()

        self.assertEqual(len(pending), 1)
        self.assertIn("NativeProcessFault", pending[0].text)
        self.assertIn("Fatal Python error: Aborted", pending[0].text)
        self.assertFalse((native_directory / "native-fault-empty.log").exists())
        self.assertFalse((native_directory / "native-fault-crashed.log").exists())

    def test_native_fault_trace_is_retained_if_report_cannot_be_persisted(self) -> None:
        native_directory = self.reporter.native_fault_directory
        native_directory.mkdir(parents=True)
        fault_path = native_directory / "native-fault-crashed.log"
        fault_path.write_text("Fatal Python error: Aborted", encoding="utf-8")
        missing_report = CrashReport(
            report_id="missing",
            text="report",
            path=self.root / "missing.pending.txt",
        )

        with patch.object(self.reporter, "_write_report", return_value=missing_report):
            self.reporter.start_native_fault_capture()

        self.assertTrue(fault_path.is_file())

    def test_unreadable_pending_report_is_acknowledged_without_a_dialog(self) -> None:
        self.reporter.report_directory.mkdir(parents=True)
        corrupt = self.reporter.report_directory / "starflight-crash-corrupt.pending.txt"
        corrupt.write_bytes(b"\xff\xfe")
        service = ErrorService(self.logger, self.reporter)

        with patch("starflight.services.error_service.RecoveredCrashReportDialog") as dialog_type:
            service.present_pending_crash_reports()

        dialog_type.assert_not_called()
        self.assertEqual(self.reporter.pending_reports(), [])
        self.assertTrue((self.reporter.report_directory / "starflight-crash-corrupt.txt").is_file())

    def test_unwritable_report_directory_uses_log_fallback_location(self) -> None:
        fallback_root = self.root / "temp"
        writable_probe = MagicMock()
        with (
            patch(
                "starflight.app.crash_reporting.tempfile.gettempdir",
                return_value=str(fallback_root),
            ),
            patch(
                "starflight.app.crash_reporting.tempfile.NamedTemporaryFile",
                side_effect=[PermissionError, writable_probe, writable_probe],
            ),
        ):
            self.reporter.pending_reports()

        self.assertEqual(
            self.reporter.report_directory,
            fallback_root / "starflight" / "logs" / "Crash Reports",
        )


class ApplicationLoggingTests(unittest.TestCase):
    def test_macos_log_path_uses_user_library_logs(self) -> None:
        with patch.object(app_logging.sys, "platform", "darwin"):
            self.assertEqual(
                app_logging.get_log_directory(),
                Path.home() / "Library" / "Logs" / "Starflight",
            )

    def test_linux_log_path_uses_xdg_state_directory(self) -> None:
        with (
            patch.object(app_logging.sys, "platform", "linux"),
            patch.dict(os.environ, {"XDG_STATE_HOME": "/state"}),
        ):
            self.assertEqual(app_logging.get_log_directory(), Path("/state/starflight"))

    def test_windows_log_path_uses_local_application_data(self) -> None:
        with (
            patch.object(app_logging.sys, "platform", "win32"),
            patch.dict(os.environ, {"LOCALAPPDATA": "C:/LocalData"}),
        ):
            self.assertEqual(
                app_logging.get_log_directory(),
                Path("C:/LocalData/Starflight/Logs"),
            )

    def test_log_timestamp_contains_milliseconds_and_timezone(self) -> None:
        formatter = app_logging._IsoFormatter("%(asctime)s | %(message)s")
        record = logging.LogRecord(
            "starflight",
            logging.ERROR,
            __file__,
            1,
            "failure",
            (),
            None,
        )

        formatted = formatter.format(record)

        self.assertRegex(
            formatted,
            re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}[+-]\d{2}:\d{2}"),
        )

    def test_unwritable_primary_log_directory_uses_temp_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            primary = root / "primary"
            fallback_root = root / "temp"
            writable_probe = MagicMock()
            with (
                patch.object(app_logging, "get_log_directory", return_value=primary),
                patch.object(app_logging.tempfile, "gettempdir", return_value=str(fallback_root)),
                patch.object(
                    app_logging.tempfile,
                    "NamedTemporaryFile",
                    side_effect=[PermissionError, writable_probe],
                ),
            ):
                result = app_logging._writable_log_directory()

        self.assertEqual(result, fallback_root / "starflight" / "logs")


class ExceptionHookTests(unittest.TestCase):
    def test_global_hooks_capture_main_thread_failures_as_fatal(self) -> None:
        error_service = Mock()
        context = Mock(error_service=error_service)
        original_hook = sys.excepthook
        restore = _install_global_exception_hooks(context)
        try:
            error = RuntimeError("slot failed")
            sys.excepthook(RuntimeError, error, error.__traceback__)
        finally:
            restore()

        error_service.queue_crash_report.assert_called_once_with(
            "unhandled exception in main thread",
            error,
            error.__traceback__,
            fatal=True,
        )
        self.assertIs(sys.excepthook, original_hook)

    def test_system_exit_does_not_queue_crash_report(self) -> None:
        error_service = Mock()
        context = Mock(error_service=error_service)
        restore = _install_global_exception_hooks(context)
        try:
            sys.excepthook(SystemExit, SystemExit(0), None)
        finally:
            restore()

        error_service.queue_crash_report.assert_not_called()

    def test_keyboard_interrupt_does_not_queue_crash_report(self) -> None:
        error_service = Mock()
        context = Mock(error_service=error_service)
        restore = _install_global_exception_hooks(context)
        try:
            sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
        finally:
            restore()

        error_service.queue_crash_report.assert_not_called()


class StartupBoundaryTests(unittest.TestCase):
    def test_startup_exception_is_persisted_and_presented(self) -> None:
        logger = Mock()
        reporter = Mock(logger=logger)
        report = CrashReport("startup", "startup failed", Path("startup.pending.txt"))
        reporter.capture_exception.return_value = report
        error = RuntimeError("Qt component missing")

        with (
            patch("starflight.app.launcher.configure_logging", return_value=logger),
            patch("starflight.app.launcher.CrashReporter", return_value=reporter),
            patch(
                "starflight.app.qt_diagnostics.install_qt_message_logging",
                return_value=None,
            ),
            patch("starflight.app.qt_diagnostics.restore_qt_message_logging"),
            patch("starflight.app.bootstrap.main", side_effect=error),
            patch("starflight.app.launcher._present_startup_report") as present,
        ):
            result = launch_application()

        self.assertEqual(result, 1)
        reporter.start_native_fault_capture.assert_called_once_with()
        reporter.capture_exception.assert_called_once_with("application startup failed", error)
        present.assert_called_once_with(reporter, report)
        reporter.shutdown.assert_called_once_with()


class QtMessageLoggingTests(unittest.TestCase):
    def test_qt_warning_is_written_to_application_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            log_path = Path(directory) / "qt.log"
            logger = logging.getLogger(f"qt-message-test-{id(self)}")
            logger.setLevel(logging.INFO)
            logger.propagate = False
            handler = logging.FileHandler(log_path, encoding="utf-8")
            logger.addHandler(handler)
            previous = install_qt_message_logging(logger)
            try:
                qWarning("Qt diagnostic marker")
            finally:
                restore_qt_message_logging(previous)
                handler.close()
                logger.handlers.clear()

            self.assertIn("Qt diagnostic marker", log_path.read_text(encoding="utf-8"))


class CrashReportDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_dialog_exposes_complete_report_and_copy_action(self) -> None:
        report = CrashReport(
            report_id="report-1",
            text="Operating system: Test OS\nTraceback: failure",
            path=Path("report.pending.txt"),
        )
        dialog = CrashReportDialog(report, Path(tempfile.gettempdir()))

        self.assertEqual(dialog.report_edit.toPlainText(), report.text)
        dialog.copy_button.click()
        self.assertEqual(QApplication.clipboard().text(), report.text)

    def test_dialog_keeps_technical_details_collapsed_until_requested(self) -> None:
        report = CrashReport(
            report_id="report-1",
            text="Operating system: Test OS\nTraceback: failure",
            path=Path("report.pending.txt"),
        )
        dialog = CrashReportDialog(report, Path(tempfile.gettempdir()))

        self.assertTrue(dialog.report_edit.isHidden())
        dialog.details_button.setChecked(True)
        self.assertFalse(dialog.report_edit.isHidden())
        dialog.details_button.setChecked(False)
        self.assertTrue(dialog.report_edit.isHidden())

    def test_nonfatal_dialog_allows_the_current_session_to_continue(self) -> None:
        report = CrashReport(
            report_id="report-1",
            text="Operating system: Test OS\nTraceback: failure",
            path=Path("report.pending.txt"),
        )
        dialog = CrashReportDialog(
            report,
            Path(tempfile.gettempdir()),
            fatal=False,
        )

        self.assertIn("continue using Starflight", dialog._summary_label.text())
        self.assertEqual(
            dialog.close_button.text(),
            QCoreApplication.translate("CrashReportDialog", "Close message"),
        )

    def test_pending_report_is_acknowledged_after_dialog_is_shown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logger = logging.getLogger(f"pending-dialog-test-{id(self)}")
            logger.addHandler(logging.NullHandler())
            reporter = CrashReporter(
                logger,
                log_path=root / "starflight.log",
                report_directory=root / "reports",
            )
            report = reporter.capture_exception("previous native failure", RuntimeError("boom"))
            service = ErrorService(logger, reporter)

            with patch.object(RecoveredCrashReportDialog, "exec", return_value=0):
                service.present_pending_crash_reports()

            self.assertEqual(reporter.pending_reports(), [])
            acknowledged = report.path.with_name(
                f"{report.path.name.removesuffix('.pending.txt')}.txt"
            )
            self.assertTrue(acknowledged.is_file())
            logger.handlers.clear()

    def test_only_newest_pending_report_is_shown_and_complete_backlog_is_acknowledged(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logger = logging.getLogger(f"pending-backlog-test-{id(self)}")
            logger.addHandler(logging.NullHandler())
            reporter = CrashReporter(
                logger,
                log_path=root / "starflight.log",
                report_directory=root / "reports",
            )
            reports = [
                reporter.capture_exception(f"failure {index}", RuntimeError(str(index)))
                for index in range(3)
            ]
            for index, report in enumerate(reports, start=1):
                os.utime(report.path, ns=(index, index))
            service = ErrorService(logger, reporter)

            with patch(
                "starflight.services.error_service.RecoveredCrashReportDialog"
            ) as dialog_type:
                dialog_type.return_value.exec.return_value = 0
                service.present_pending_crash_reports()

            dialog_type.assert_called_once()
            shown_report = dialog_type.call_args.args[0]
            self.assertEqual(shown_report.report_id, reports[-1].report_id)
            self.assertEqual(dialog_type.call_args.kwargs["pending_count"], 3)
            self.assertEqual(reporter.pending_reports(), [])
            acknowledged = list((root / "reports").glob("starflight-crash-*.txt"))
            self.assertEqual(len(acknowledged), 3)
            logger.handlers.clear()

    def test_large_pending_backlog_is_read_once_and_pruned_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logger = logging.getLogger(f"pending-large-backlog-test-{id(self)}")
            logger.addHandler(logging.NullHandler())
            reporter = CrashReporter(
                logger,
                log_path=root / "starflight.log",
                report_directory=root / "reports",
            )
            reports = [
                reporter.capture_exception(f"failure {index}", RuntimeError(str(index)))
                for index in range(100)
            ]
            service = ErrorService(logger, reporter)

            with (
                patch.object(
                    reporter,
                    "_read_pending_report",
                    wraps=reporter._read_pending_report,
                ) as read,
                patch.object(
                    reporter,
                    "_prune_acknowledged_reports",
                    wraps=reporter._prune_acknowledged_reports,
                ) as prune,
                patch(
                    "starflight.services.error_service.RecoveredCrashReportDialog"
                ) as dialog_type,
            ):
                dialog_type.return_value.exec.return_value = 0
                service.present_pending_crash_reports()

            self.assertEqual(read.call_count, 1)
            self.assertEqual(prune.call_count, 1)
            shown_report = dialog_type.call_args.args[0]
            self.assertEqual(shown_report.report_id, reports[-1].report_id)
            self.assertEqual(reporter.pending_reports(), [])
            self.assertEqual(len(list((root / "reports").glob("*.txt"))), 10)
            logger.handlers.clear()

    def test_recovered_report_shows_backlog_count(self) -> None:
        report = CrashReport(
            report_id="report-1",
            text="Operating system: Test OS\nTraceback: failure",
            path=Path("report.pending.txt"),
        )
        dialog = RecoveredCrashReportDialog(
            report,
            Path(tempfile.gettempdir()),
            pending_count=3,
        )

        self.assertIn("3", dialog._summary_label.text())
        self.assertIn("log folder", dialog._summary_label.text())

    def test_recovered_report_allows_the_new_session_to_continue(self) -> None:
        report = CrashReport(
            report_id="report-1",
            text="Operating system: Test OS\nTraceback: failure",
            path=Path("report.pending.txt"),
        )
        dialog = RecoveredCrashReportDialog(report, Path(tempfile.gettempdir()))

        self.assertEqual(
            dialog.windowTitle(),
            QCoreApplication.translate(
                "RecoveredCrashReportDialog",
                "Previous Starflight Crash",
            ),
        )
        self.assertEqual(
            dialog.close_button.text(),
            QCoreApplication.translate("CrashReportDialog", "Close message"),
        )

    def test_recovered_report_uses_shared_translations_for_details_and_copy(self) -> None:
        report = CrashReport(
            report_id="report-1",
            text="Operating system: Test OS\nTraceback: failure",
            path=Path("report.pending.txt"),
        )
        dialog = RecoveredCrashReportDialog(report, Path(tempfile.gettempdir()))

        self.assertEqual(
            dialog.details_button.text(),
            QCoreApplication.translate("CrashReportDialog", "Show technical details"),
        )
        dialog.copy_button.click()
        self.assertEqual(
            dialog.copy_button.text(),
            QCoreApplication.translate("CrashReportDialog", "Report copied"),
        )

    def test_unhandled_qt_callback_shows_report_and_exits_event_loop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logger = logging.getLogger(f"fatal-callback-test-{id(self)}")
            logger.addHandler(logging.NullHandler())
            reporter = CrashReporter(
                logger,
                log_path=root / "starflight.log",
                report_directory=root / "reports",
            )
            service = ErrorService(logger, reporter)
            restore = _install_global_exception_hooks(Mock(error_service=service))
            timeout = QTimer()
            timeout.setSingleShot(True)
            timeout.timeout.connect(lambda: self.app.exit(99))

            def fail_in_qt_callback() -> None:
                raise RuntimeError("unhandled Qt callback failure")

            try:
                with patch.object(CrashReportDialog, "exec", return_value=0):
                    QTimer.singleShot(0, fail_in_qt_callback)
                    timeout.start(2_000)
                    result = self.app.exec()
            finally:
                timeout.stop()
                restore()

            self.assertEqual(result, 1)
            self.assertEqual(reporter.pending_reports(), [])
            reports = list((root / "reports").glob("starflight-crash-*.txt"))
            self.assertEqual(len(reports), 1)
            self.assertIn(
                "RuntimeError: unhandled Qt callback failure",
                reports[0].read_text(encoding="utf-8"),
            )
            logger.handlers.clear()

    def test_unhandled_worker_failure_shows_report_without_fatal_exit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            logger = logging.getLogger(f"worker-callback-test-{id(self)}")
            logger.addHandler(logging.NullHandler())
            reporter = CrashReporter(
                logger,
                log_path=root / "starflight.log",
                report_directory=root / "reports",
            )
            service = ErrorService(logger, reporter)
            restore = _install_global_exception_hooks(Mock(error_service=service))

            def fail_in_worker() -> None:
                raise RuntimeError("isolated worker failure")

            try:
                with patch.object(CrashReportDialog, "exec", return_value=0):
                    worker = threading.Thread(target=fail_in_worker, name="test-worker")
                    worker.start()
                    worker.join()
                    QTimer.singleShot(50, self.app.quit)
                    result = self.app.exec()
            finally:
                restore()

            self.assertEqual(result, 0)
            self.assertEqual(reporter.pending_reports(), [])
            reports = list((root / "reports").glob("starflight-crash-*.txt"))
            self.assertEqual(len(reports), 1)
            self.assertIn(
                "unhandled exception in worker thread 'test-worker'",
                reports[0].read_text(encoding="utf-8"),
            )
            logger.handlers.clear()


if __name__ == "__main__":
    unittest.main()
