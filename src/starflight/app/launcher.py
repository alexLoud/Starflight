"""Launch Starflight with diagnostics active before importing the Qt application."""

from __future__ import annotations

import sys

from starflight.app.crash_reporting import CrashReport, CrashReporter
from starflight.app.logging import configure_logging


def main() -> int:
    """run the application behind an early startup exception boundary."""

    reporter = CrashReporter(configure_logging())
    previous_qt_handler = None
    restore_qt_logging = None
    try:
        reporter.start_native_fault_capture()
        from starflight.app.qt_diagnostics import (
            install_qt_message_logging,
            restore_qt_message_logging,
        )

        restore_qt_logging = restore_qt_message_logging
        previous_qt_handler = install_qt_message_logging(reporter.logger)

        from starflight.app.bootstrap import main as run_application

        return run_application(reporter)
    except Exception as exc:
        try:
            report = reporter.capture_exception("application startup failed", exc)
            _present_startup_report(reporter, report)
        except Exception:
            reporter.logger.exception("application startup and crash reporting failed")
        return 1
    finally:
        if restore_qt_logging is not None:
            try:
                restore_qt_logging(previous_qt_handler)
            except Exception:
                reporter.logger.exception("Qt message handler could not be restored")
        try:
            reporter.shutdown()
        except Exception:
            reporter.logger.exception("diagnostic shutdown failed")


def _present_startup_report(reporter: CrashReporter, report: CrashReport) -> None:
    """show a startup report when Qt is usable, otherwise leave it pending."""

    try:
        from PySide6.QtCore import QCoreApplication
        from PySide6.QtWidgets import QApplication

        from starflight.app.constants import (
            APP_DISPLAY_NAME,
            APP_ORGANIZATION,
            APP_ORGANIZATION_DOMAIN,
        )
        from starflight.views.dialogs.crash_report_dialog import CrashReportDialog

        app = QApplication.instance() or QApplication(sys.argv)
        QCoreApplication.setApplicationName(APP_DISPLAY_NAME)
        QApplication.setApplicationDisplayName(APP_DISPLAY_NAME)
        QCoreApplication.setOrganizationName(APP_ORGANIZATION)
        QCoreApplication.setOrganizationDomain(APP_ORGANIZATION_DOMAIN)
        _try_install_translations(app)
        _try_apply_startup_dialog_theme(app, reporter)

        dialog = CrashReportDialog(report, reporter.log_path.parent)
        dialog.exec()
        reporter.mark_presented(report)
    except Exception:
        reporter.logger.exception(
            "startup crash report dialog unavailable; report remains pending at %s",
            report.path,
        )


def _try_apply_startup_dialog_theme(app: object, reporter: CrashReporter) -> None:
    """best-effort styling when normal application setup failed early."""

    try:
        from starflight.app.constants import APP_ICON_FILE, APP_ICON_MACOS_FILE
        from starflight.views.icons import load_icon_asset
        from starflight.views.theme import apply_dark_theme

        icon_file = APP_ICON_MACOS_FILE if sys.platform == "darwin" else APP_ICON_FILE
        app.setWindowIcon(load_icon_asset(icon_file))
        apply_dark_theme(app)
    except Exception:
        reporter.logger.exception("startup crash report styling unavailable")


def _try_install_translations(app: object) -> None:
    """best-effort translation setup for failures during normal startup."""

    try:
        from starflight.app.constants import DEFAULT_LANGUAGE, SETTINGS_KEY_LANGUAGE
        from starflight.app.settings import create_settings
        from starflight.i18n import install_translators, normalize_language_code

        settings = create_settings()
        language = normalize_language_code(
            str(settings.value(SETTINGS_KEY_LANGUAGE, DEFAULT_LANGUAGE)),
        )
        install_translators(app, language)
    except Exception:
        return


__all__ = ["main"]
