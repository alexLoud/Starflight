"""Regression tests for shrinkable project-mode window layout."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect, QSettings
from PySide6.QtWidgets import QApplication

from starflight.app.command_setup import register_core_commands
from starflight.app.context import AppContext
from starflight.commands.models import Command
from starflight.commands.registry import CommandRegistry
from starflight.views.icons import TOOLBAR_ICON_FILES
from starflight.views.main_window import MainWindow
from starflight.views.widgets.main_toolbar import MainToolbar
from starflight.views.widgets.settings_panel import SettingsPanel


class SettingsPanelSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_sidebar_size_hint_does_not_include_full_content_height(self) -> None:
        panel = SettingsPanel()
        self.assertEqual(panel.minimumSizeHint().height(), 0)
        self.assertLess(panel.sizeHint().height(), 400)
        self.assertEqual(panel.minimumSizeHint().width(), panel.minimumWidth())


class MainToolbarSizeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_toolbar_does_not_force_the_full_button_row_width(self) -> None:
        registry = CommandRegistry(Mock())
        for command_id in TOOLBAR_ICON_FILES:
            registry.register(
                Command(command_id, command_id, ("File",), toolbar_visible=True),
                lambda: None,
            )
        toolbar = MainToolbar(registry)
        self.assertLessEqual(toolbar.minimumSizeHint().width(), 0)
        self.assertGreater(toolbar.minimumSizeHint().height(), 40)
        self.assertGreater(toolbar.sizeHint().width(), toolbar.minimumSizeHint().width())


class MainWindowLayoutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._temp_directory = tempfile.TemporaryDirectory()
        self._settings = QSettings(
            str(Path(self._temp_directory.name) / "ui.ini"),
            QSettings.Format.IniFormat,
        )

    def tearDown(self) -> None:
        self._temp_directory.cleanup()

    def _make_window(self) -> MainWindow:
        context = AppContext(
            logger=Mock(),
            error_service=Mock(),
            settings=self._settings,
            command_registry=CommandRegistry(Mock()),
        )
        window = MainWindow(context)
        register_core_commands(context.command_registry, window)
        window.build_shell()
        return window

    def test_project_mode_minimum_size_fits_the_available_screen(self) -> None:
        window = self._make_window()
        window._show_workspace()
        self.app.processEvents()
        screen = window.screen() or self.app.primaryScreen()
        self.assertIsNotNone(screen)
        available = screen.availableGeometry()
        self.assertLessEqual(window.minimumWidth(), available.width())
        self.assertLessEqual(window.minimumHeight(), available.height())
        self.assertLessEqual(window.minimumWidth(), 800)
        self.assertLessEqual(window.minimumHeight(), 520)
        window.close()

    def test_project_mode_frame_stays_inside_the_available_screen(self) -> None:
        window = self._make_window()
        window._show_workspace()
        self.app.processEvents()
        screen = window.screen() or self.app.primaryScreen()
        self.assertIsNotNone(screen)
        available = screen.availableGeometry()
        frame = window.frameGeometry()
        self.assertLessEqual(frame.width(), available.width())
        self.assertLessEqual(frame.height(), available.height())
        window.close()

    def test_client_rect_maps_the_frame_into_the_available_area(self) -> None:
        available = QRect(0, 25, 1280, 700)
        frame = QRect(0, 25, 1280, 758)
        client = QRect(0, 53, 1280, 730)
        target = MainWindow._client_rect_for_frame(available, frame, client)
        self.assertEqual(target, QRect(0, 53, 1280, 672))


if __name__ == "__main__":
    unittest.main()
