"""Create the Qt application and start the main window."""

from __future__ import annotations

import sys
import threading
from types import TracebackType

from PySide6.QtCore import QCoreApplication
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
from starflight.i18n import install_translators, normalize_language_code
from starflight.platform.display_color_profile import display_color_space_for_geometry
from starflight.utils.image import configure_display_color_space_resolver
from starflight.views.icons import load_icon_asset
from starflight.views.main_window import MainWindow
from starflight.views.theme import apply_dark_theme


def main() -> int:
    """start the desktop application."""

    app = QApplication(sys.argv)
    _configure_application_metadata()
    configure_display_color_space_resolver(display_color_space_for_geometry)
    icon_file = APP_ICON_MACOS_FILE if sys.platform == "darwin" else APP_ICON_FILE
    app.setWindowIcon(load_icon_asset(icon_file))
    apply_dark_theme(app)

    context = create_app_context()
    _install_global_exception_hooks(context)

    language = normalize_language_code(
        str(context.settings.value(SETTINGS_KEY_LANGUAGE, DEFAULT_LANGUAGE)),
    )
    install_translators(app, language)

    window = MainWindow(context)
    register_core_commands(context.command_registry, window)
    window.build_shell()
    window.retranslate_ui()

    return app.exec()


def _configure_application_metadata() -> None:
    QCoreApplication.setApplicationName(APP_DISPLAY_NAME)
    QApplication.setApplicationDisplayName(APP_DISPLAY_NAME)
    QApplication.setDesktopFileName(APP_ID)
    QCoreApplication.setOrganizationName(APP_ORGANIZATION)
    QCoreApplication.setOrganizationDomain(APP_ORGANIZATION_DOMAIN)


def _install_global_exception_hooks(context: AppContext) -> None:
    def on_unhandled_exception(
        exc_type: type[BaseException],
        exc: BaseException,
        _tb: TracebackType | None,
    ) -> None:
        del exc_type
        context.error_service.report_exception("unhandled exception in main thread", exc)

    def on_thread_exception(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is not None:
            context.error_service.report_exception(
                "unhandled exception in worker thread",
                args.exc_value,
            )

    sys.excepthook = on_unhandled_exception
    threading.excepthook = on_thread_exception


__all__ = ["main"]
