"""Wrap a setting input with a trailing reset button."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtWidgets import QHBoxLayout, QWidget

from starflight.views.widgets.setting_reset_button import SettingResetButton


class SettingFieldRow(QWidget):
    """setting input with a trailing reset button."""

    def __init__(
        self,
        field: QWidget,
        reset_handler: Callable[[], None],
        parent: QWidget | None = None,
    ) -> None:
        """
        wrap one input widget and its reset control.

        field
            primary setting input widget
        reset_handler
            callback that restores the default value
        parent
            optional parent widget
        """

        super().__init__(parent)
        self.setObjectName("setting_field_row")

        self.field = field
        self.reset_button = SettingResetButton(reset_handler, self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(field, stretch=1)
        layout.addWidget(self.reset_button, stretch=0)

    def retranslate_ui(self) -> None:
        """refresh translatable texts for child controls."""

        self.reset_button.retranslate_ui()


__all__ = ["SettingFieldRow"]
