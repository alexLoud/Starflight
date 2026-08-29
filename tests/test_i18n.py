"""Runtime checks for the compiled German translations."""

from __future__ import annotations

import os
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from starflight.i18n import install_translators

CATALOG_PATH = Path(__file__).resolve().parents[1] / "src/starflight/i18n/starflight_de.ts"


def catalog_translation(context_name: str, source: str) -> str:
    """return one finished translation from the German source catalog."""

    catalog = ET.parse(CATALOG_PATH)
    for context in catalog.getroot().findall("context"):
        if context.findtext("name") != context_name:
            continue
        for message in context.findall("message"):
            if message.findtext("source") == source:
                return message.findtext("translation", default="")
    return ""


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

    def test_parallax_preview_controls_are_translated(self) -> None:
        messages = {
            "MainWindow": ("Preview unavailable",),
            "ZoomToolbar": (
                "Switch between the normal and generated parallax preview.",
                "Enable the parallax effect in the sidebar first.",
            ),
        }
        for context, sources in messages.items():
            for source in sources:
                translated = QCoreApplication.translate(context, source)
                self.assertNotEqual(translated, source)
                self.assertEqual(translated, catalog_translation(context, source))

    def test_reset_confirm_popover_is_translated(self) -> None:
        for source in (
            "Reset all settings?",
            "The loaded image will be kept.",
            "Cancel",
            "Reset",
        ):
            translated = QCoreApplication.translate("ResetConfirmPopover", source)
            self.assertNotEqual(translated, source)
            self.assertEqual(translated, catalog_translation("ResetConfirmPopover", source))

    def test_crash_report_actions_are_translated(self) -> None:
        for source in (
            "Starflight Error",
            "An application error occurred",
            "Show technical details",
            "Hide technical details",
            "Copy report",
            "Open log folder",
            "Quit Starflight",
            "Close message",
            "The affected operation could not be completed. You can copy the diagnostic "
            "report and continue using Starflight. The report is stored locally and is "
            "not sent automatically.",
            "Starflight cannot continue safely and must be closed. Your project "
            "files were not changed. You can copy the diagnostic report for "
            "troubleshooting. The report is stored locally and is not sent "
            "automatically.",
        ):
            translated = QCoreApplication.translate("CrashReportDialog", source)
            self.assertNotEqual(translated, source)
            self.assertEqual(
                translated,
                catalog_translation("CrashReportDialog", source),
            )

    def test_recovered_crash_report_is_translated(self) -> None:
        for source in (
            "Previous Starflight Crash",
            "Starflight closed unexpectedly during the previous session",
            "A diagnostic report was recovered. You can copy it for troubleshooting "
            "and then continue using Starflight. The report is stored locally and is "
            "not sent automatically.",
            "The most recent of {count} recovered diagnostic reports is shown. "
            "You can copy it for troubleshooting and then continue using "
            "Starflight. Additional reports remain in the log folder. The "
            "report is stored locally and is not sent automatically.",
        ):
            translated = QCoreApplication.translate("RecoveredCrashReportDialog", source)
            self.assertNotEqual(translated, source)
            self.assertEqual(
                translated,
                catalog_translation("RecoveredCrashReportDialog", source),
            )


if __name__ == "__main__":
    unittest.main()
