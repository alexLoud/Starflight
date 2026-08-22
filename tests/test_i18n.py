"""Runtime checks for the compiled German translations."""

from __future__ import annotations

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from starflight.i18n import install_translators


class GermanTranslationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        install_translators(cls.app, "de")

    def test_new_project_name_is_translated(self) -> None:
        translated = QCoreApplication.translate("ProjectController", "Untitled Project")
        self.assertNotEqual(translated, "Untitled Project")

    def test_validation_message_is_translated(self) -> None:
        translated = QCoreApplication.translate(
            "Validation",
            "Width and height must be even numbers.",
        )
        self.assertNotEqual(translated, "Width and height must be even numbers.")


if __name__ == "__main__":
    unittest.main()
