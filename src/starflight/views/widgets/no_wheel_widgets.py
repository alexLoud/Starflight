"""Prevent accidental value changes from unfocused mouse wheel input."""

from __future__ import annotations

from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox, QDoubleSpinBox, QSlider, QSpinBox


class NoWheelSlider(QSlider):
    """horizontal slider that ignores wheel events without focus."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


class NoWheelSpinBox(QSpinBox):
    """spin box that ignores wheel events without focus."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """double spin box that ignores wheel events without focus."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


class NoWheelComboBox(QComboBox):
    """combo box that ignores wheel events without focus."""

    def wheelEvent(self, event: QWheelEvent) -> None:
        if not self.hasFocus():
            event.ignore()
            return
        super().wheelEvent(event)


__all__ = [
    "NoWheelComboBox",
    "NoWheelDoubleSpinBox",
    "NoWheelSlider",
    "NoWheelSpinBox",
]
