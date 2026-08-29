"""Tests for the new-user welcome tour."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QDialog

from starflight.app.constants import SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED
from starflight.app.context import AppContext
from starflight.commands.registry import CommandRegistry
from starflight.views.dialogs.welcome_dialog import WelcomeDialog
from starflight.views.main_window import MainWindow

try:
    from qt_test_helpers import welcome_splash_network_patch
except ModuleNotFoundError:
    from tests.qt_test_helpers import welcome_splash_network_patch


class WelcomeDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        self._temporary_directory = tempfile.TemporaryDirectory()
        self._settings = QSettings(
            str(Path(self._temporary_directory.name) / "ui.ini"),
            QSettings.Format.IniFormat,
        )

    def tearDown(self) -> None:
        self._settings.sync()
        self._temporary_directory.cleanup()

    def test_navigation_and_dont_show_preference_are_persisted(self) -> None:
        dialog = WelcomeDialog(self._settings)

        self.assertEqual(dialog._step_index, 0)
        self.assertFalse(dialog._back_button.isEnabled())
        self.assertFalse(dialog._dont_show_again.isChecked())
        dialog._next_step()
        self.assertEqual(dialog._step_index, 1)
        self.assertTrue(dialog._back_button.isEnabled())
        dialog._previous_step()
        self.assertEqual(dialog._step_index, 0)

        dialog._dont_show_again.setChecked(True)
        dialog.done(QDialog.DialogCode.Rejected)
        self.assertTrue(
            self._settings.value(
                SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED,
                False,
                type=bool,
            )
        )

    def test_maybe_show_welcome_tour_only_opens_for_new_settings(self) -> None:
        context = AppContext(
            logger=Mock(),
            error_service=Mock(),
            settings=self._settings,
            command_registry=CommandRegistry(Mock()),
        )
        window = MainWindow(context)
        window.open_welcome_tour = Mock()

        window.maybe_show_welcome_tour()
        window.open_welcome_tour.assert_called_once_with()

        self._settings.setValue(SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED, True)
        window.open_welcome_tour.reset_mock()
        window.maybe_show_welcome_tour()
        window.open_welcome_tour.assert_not_called()
        window.close()

    def test_entering_workspace_schedules_tour_once(self) -> None:
        context = AppContext(
            logger=Mock(),
            error_service=Mock(),
            settings=self._settings,
            command_registry=CommandRegistry(Mock()),
        )
        with welcome_splash_network_patch():
            window = MainWindow(context)

        with patch("starflight.views.main_window.QTimer.singleShot") as single_shot:
            window._show_workspace()
            window._show_workspace()

        single_shot.assert_called_once_with(0, window.maybe_show_welcome_tour)
        window.close()


if __name__ == "__main__":
    unittest.main()
