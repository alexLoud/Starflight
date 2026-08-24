"""Small reset control for sidebar setting fields."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QToolButton, QWidget

from starflight.views.icons import load_icon_asset

_RESET_ICON_SIZE = 14
_RESET_BUTTON_SIZE = 24


class SettingResetButton(QToolButton):
    """subtle icon button that restores a setting to its default value."""

    def __init__(
        self,
        reset_handler: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """
        create a reset button for one setting field.

        reset_handler
            callback that restores the default value
        parent
            optional parent widget
        """

        super().__init__(parent)
        self.setObjectName("setting_reset_button")
        self.setAutoRaise(True)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self.setFixedSize(_RESET_BUTTON_SIZE, _RESET_BUTTON_SIZE)
        self.setIcon(load_icon_asset("reset.svg"))
        self.setIconSize(QSize(_RESET_ICON_SIZE, _RESET_ICON_SIZE))
        if reset_handler is not None:
            self.clicked.connect(reset_handler)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """refresh tooltip text."""

        self.setToolTip(self.tr("Reset to default"))


__all__ = ["SettingResetButton"]
