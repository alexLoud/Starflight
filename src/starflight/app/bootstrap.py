"""Create the Qt application and start the main window."""

from __future__ import annotations

import sys
import threading
import traceback
from collections.abc import Callable
from types import TracebackType

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtWidgets import QApplication

from starflight.app.command_setup import register_core_commands
from starflight.app.constants import (
    APP_DISPLAY_NAME,
    APP_ICON_FILE,
    APP_ICON_MACOS_FILE,
    APP_ID,
    APP_ORGANIZATION,
    APP_ORGANIZATION_DOMAIN,
    DEFAULT_LANGUAGE,
    SETTINGS_KEY_LANGUAGE,
)
from starflight.app.context import AppContext, create_app_context
from starflight.app.crash_reporting import CrashReporter
from starflight.app.logging import configure_logging
from starflight.i18n import install_translators, normalize_language_code
from starflight.platform.display_color_profile import display_color_space_for_geometry
from starflight.utils.image import configure_display_color_space_resolver
from starflight.views.icons import load_icon_asset
from starflight.views.main_window import MainWindow
from starflight.views.theme import apply_dark_theme


def main(crash_reporter: CrashReporter | None = None) -> int:
    """
    start the desktop application.

    use ``starflight.app.launcher.main`` as the process entry point so startup
    failures, native fault capture, and qt message logging are initialized first.
    """

    owns_reporter = crash_reporter is None
    reporter = crash_reporter or CrashReporter(configure_logging())
    if owns_reporter:
        reporter.start_native_fault_capture()

    reporter.logger.info("application startup beginning")
    try:
        app = QApplication(sys.argv)
        _configure_application_metadata()
        configure_display_color_space_resolver(display_color_space_for_geometry)
        icon_file = APP_ICON_MACOS_FILE if sys.platform == "darwin" else APP_ICON_FILE
        app.setWindowIcon(load_icon_asset(icon_file))
        apply_dark_theme(app)

        context = create_app_context(reporter)
        restore_exception_hooks = _install_global_exception_hooks(context)
        try:
            language = normalize_language_code(
                str(context.settings.value(SETTINGS_KEY_LANGUAGE, DEFAULT_LANGUAGE)),
            )
            install_translators(app, language)

            window = MainWindow(context)
            register_core_commands(context.command_registry, window)
            window.build_shell()
            window.retranslate_ui()
            QTimer.singleShot(100, context.error_service.present_pending_crash_reports)

            reporter.logger.info("application event loop starting")
            try:
                return app.exec()
            finally:
                reporter.logger.info("application event loop stopped")
        finally:
            restore_exception_hooks()
    finally:
        if owns_reporter:
            reporter.shutdown()


def _configure_application_metadata() -> None:
    QCoreApplication.setApplicationName(APP_DISPLAY_NAME)
    QApplication.setApplicationDisplayName(APP_DISPLAY_NAME)
    QApplication.setDesktopFileName(APP_ID)
    QCoreApplication.setOrganizationName(APP_ORGANIZATION)
    QCoreApplication.setOrganizationDomain(APP_ORGANIZATION_DOMAIN)


def _install_global_exception_hooks(context: AppContext) -> Callable[[], None]:
    """install Python exception hooks and return a restoration callback."""

    previous_main_hook = sys.excepthook
    previous_thread_hook = threading.excepthook
    previous_unraisable_hook = sys.unraisablehook

    def on_unhandled_exception(
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
    ) -> None:
        if exc_type in (SystemExit, KeyboardInterrupt):
            previous_main_hook(exc_type, exc, tb)
            return
        context.error_service.queue_crash_report(
            "unhandled exception in main thread",
            exc,
            tb,
            fatal=True,
        )
        if previous_main_hook is not sys.__excepthook__:
            previous_main_hook(exc_type, exc, tb)
        elif tb is not None:
            traceback.print_exception(exc_type, exc, tb)

    def on_thread_exception(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit or args.exc_value is None:
            previous_thread_hook(args)
            return
        thread_name = args.thread.name if args.thread is not None else "unknown"
        context.error_service.queue_crash_report(
            f"unhandled exception in worker thread '{thread_name}'",
            args.exc_value,
            args.exc_traceback,
            fatal=False,
        )
        previous_thread_hook(args)

    def on_unraisable_exception(args: sys.UnraisableHookArgs) -> None:
        exc = args.exc_value or RuntimeError(args.err_msg or "unraisable exception")
        context.error_service.queue_crash_report(
            args.err_msg or "unraisable Python exception",
            exc,
            args.exc_traceback,
            fatal=False,
        )
        previous_unraisable_hook(args)

    sys.excepthook = on_unhandled_exception
    threading.excepthook = on_thread_exception
    sys.unraisablehook = on_unraisable_exception

    def restore() -> None:
        sys.excepthook = previous_main_hook
        threading.excepthook = previous_thread_hook
        sys.unraisablehook = previous_unraisable_hook

    return restore


__all__ = ["main"]
