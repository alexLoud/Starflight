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
            _emit_startup_failure(reporter, exc, report)
            _present_startup_report(reporter, report)
        except Exception:
            reporter.logger.exception("application startup and crash reporting failed")
            _print_startup_failure(
                f"Starflight failed to start: {exc}",
                getattr(reporter, "log_path", None),
            )
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


def _emit_startup_failure(
    reporter: CrashReporter,
    exc: BaseException,
    report: CrashReport,
) -> None:
    """
    log and print a clear startup failure when the gui cannot be shown.

    reporter
        active crash reporter with log path
    exc
        exception that stopped startup
    report
        persisted crash report
    """

    hint = _startup_failure_hint(exc)
    message = f"Starflight failed to start: {exc}"
    if hint:
        message = f"{message}\n{hint}"
    reporter.logger.error(
        "%s | log=%s | report=%s",
        message.replace("\n", " | "),
        reporter.log_path,
        report.path,
    )
    _print_startup_failure(message, reporter.log_path, report.path)


def _startup_failure_hint(exc: BaseException) -> str:
    """
    return a short hint for common qt/display library startup failures.

    exc
        exception raised during startup
    """

    text = f"{type(exc).__name__}: {exc}".lower()
    if "libegl" in text or "libgl.so" in text or "libgldispatch" in text:
        return (
            "A required OpenGL/EGL library could not be loaded. "
            "The Linux package should bundle libEGL; if this persists, install "
            "libegl1 (Debian/Ubuntu) or mesa-libEGL (Fedora/RHEL)."
        )
    if "xcb-cursor" in text or ("xcb" in text and "platform plugin" in text):
        return (
            "The Qt xcb platform plugin failed to load. "
            "The Linux package should bundle libxcb-cursor; if this persists, install "
            "libxcb-cursor0 (Debian/Ubuntu) or xcb-util-cursor (Fedora/RHEL/Arch)."
        )
    if isinstance(exc, ImportError) and ("pyside" in text or "qt" in text or "lib" in text):
        return (
            "Qt/PySide6 failed to import. See the application log for the missing "
            "library name."
        )
    return ""


def _print_startup_failure(
    message: str,
    log_path: object | None = None,
    report_path: object | None = None,
) -> None:
    """
    write a user-visible startup error to stderr (even without a console gui).

    message
        primary failure text
    log_path
        application log path when available
    report_path
        crash report path when available
    """

    lines = [message.rstrip(), ""]
    if log_path is not None:
        lines.append(f"Log file: {log_path}")
    if report_path is not None:
        lines.append(f"Crash report: {report_path}")
    print("\n".join(lines).rstrip() + "\n", file=sys.stderr)


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
