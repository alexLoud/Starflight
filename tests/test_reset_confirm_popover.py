"""Tests for the reset confirmation popover."""

from __future__ import annotations

import os
import unittest
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QApplication, QToolButton, QWidget

from starflight.views.widgets.reset_confirm_popover import ResetConfirmPopover


class ResetConfirmPopoverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_confirm_emits_and_closes(self) -> None:
        host = QWidget()
        popover = ResetConfirmPopover(host)
        confirmed = Mock()
        closed = Mock()
        popover.confirmed.connect(confirmed)
        popover.destroyed.connect(closed)
        popover.show()
        self.app.processEvents()
        popover._confirm_button.click()
        self.app.processEvents()
        confirmed.assert_called_once_with()
        closed.assert_called()

    def test_cancel_closes_without_confirming(self) -> None:
        host = QWidget()
        popover = ResetConfirmPopover(host)
        confirmed = Mock()
        closed = Mock()
        popover.confirmed.connect(confirmed)
        popover.destroyed.connect(closed)
        popover.show()
        self.app.processEvents()
        popover._cancel_button.click()
        self.app.processEvents()
        confirmed.assert_not_called()
        closed.assert_called()

    def test_show_below_places_the_popover_under_the_anchor(self) -> None:
        host = QWidget()
        host.setGeometry(40, 40, 400, 300)
        host.show()
        anchor = QToolButton(host)
        anchor.setGeometry(80, 20, 90, 40)
        anchor.show()
        popover = ResetConfirmPopover(host)
        popover.show_below(anchor)
        self.app.processEvents()
        expected_top = anchor.mapToGlobal(QPoint(0, anchor.height() + 8)).y()
        self.assertGreaterEqual(popover.y(), expected_top)
        self.assertLess(popover.y(), expected_top + 12)
        popover.close()
        host.close()


if __name__ == "__main__":
    unittest.main()
