"""Compact confirmation popup shown under the reset toolbar button."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_GAP_BELOW_ANCHOR = 8
_POPOVER_WIDTH = 260


class ResetConfirmPopover(QFrame):
    """small popup that asks before resetting all settings."""

    confirmed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup)
        self.setObjectName("reset_confirm_popover")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.setFixedWidth(_POPOVER_WIDTH)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        self._title_label = QLabel(self)
        self._title_label.setObjectName("reset_confirm_title")
        self._title_label.setWordWrap(True)
        layout.addWidget(self._title_label)

        self._message_label = QLabel(self)
        self._message_label.setObjectName("reset_confirm_message")
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 2, 0, 0)
        buttons.setSpacing(8)
        buttons.addStretch(1)

        self._cancel_button = QPushButton(self)
        self._cancel_button.setObjectName("reset_confirm_cancel")
        self._cancel_button.setDefault(True)
        self._cancel_button.clicked.connect(self.close)
        buttons.addWidget(self._cancel_button)

        self._confirm_button = QPushButton(self)
        self._confirm_button.setObjectName("primary_button")
        self._confirm_button.setAutoDefault(False)
        self._confirm_button.clicked.connect(self._on_confirm)
        buttons.addWidget(self._confirm_button)

        layout.addLayout(buttons)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """refresh popover texts."""

        self._title_label.setText(self.tr("Reset all settings?"))
        self._message_label.setText(self.tr("The loaded image will be kept."))
        self._cancel_button.setText(self.tr("Cancel"))
        self._confirm_button.setText(self.tr("Reset"))

    def show_below(self, anchor: QWidget) -> None:
        """
        open the popover under an anchor widget.

        anchor
            toolbar button that triggered the confirmation
        """

        self.adjustSize()
        origin = anchor.mapToGlobal(QPoint(0, anchor.height() + _GAP_BELOW_ANCHOR))
        x = origin.x() + (anchor.width() - self.width()) // 2
        y = origin.y()
        screen = anchor.screen()
        if screen is not None:
            available = screen.availableGeometry()
            x = min(max(x, available.left()), available.right() - self.width() + 1)
            if y + self.height() > available.bottom():
                y = anchor.mapToGlobal(QPoint(0, 0)).y() - self.height() - _GAP_BELOW_ANCHOR
            y = min(max(y, available.top()), available.bottom() - self.height() + 1)
        self.move(x, y)
        self.show()
        self.raise_()
        self._cancel_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def _on_confirm(self) -> None:
        """accept the reset and close the popover."""

        self.confirmed.emit()
        self.close()


__all__ = ["ResetConfirmPopover"]
