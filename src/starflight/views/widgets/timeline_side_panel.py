"""Provide the shared layout used beside the timeline."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QToolButton, QVBoxLayout, QWidget

from starflight.views.icons import load_icon_asset
from starflight.views.theme import PANEL_BG

SIDE_PANEL_WIDTH = 188
ZOOM_PANEL_WIDTH = 268
_SIDE_MARGINS = (10, 0, 10, 0)
_BUTTON_ROW_HEIGHT = 34
_BUTTON_SIZE = 32
_ICON_SIZE = 18
_BUTTON_SPACING = 6
_ROW_SPACING = 4
_CAPTION_HEIGHT = 16


class TimelineSidePanel(QWidget):
    """button row with caption below, used on both timeline sides."""

    def __init__(self, object_name: str, parent: QWidget | None = None) -> None:
        """
        create timeline side panel.

        object_name
            qt object name for styling (timeline_transport or timeline_zoom)
        parent
            optional parent widget
        """

        super().__init__(parent)
        self.setObjectName(object_name)
        self.setAutoFillBackground(True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(PANEL_BG))
        self.setPalette(palette)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*_SIDE_MARGINS)
        layout.setSpacing(_ROW_SPACING)

        self.button_row = QWidget(self)
        self.button_row.setObjectName("timeline_side_row")
        self.button_row.setFixedHeight(_BUTTON_ROW_HEIGHT)
        self.buttons_layout = QHBoxLayout(self.button_row)
        self.buttons_layout.setContentsMargins(0, 0, 0, 0)
        self.buttons_layout.setSpacing(_BUTTON_SPACING)
        self.buttons_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.caption_label = QLabel(self)
        self.caption_label.setObjectName("timeline_time_label")
        self.caption_label.setFixedHeight(_CAPTION_HEIGHT)
        self.caption_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.caption_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        )

        layout.addStretch(1)
        layout.addWidget(self.button_row, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self.caption_label, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

    def add_button(self, icon_file: str, tooltip: str = "") -> QToolButton:
        """
        add a transport-style icon button to the row.

        icon_file
            svg icon file name
        tooltip
            optional hover tooltip
        """

        button = QToolButton(self.button_row)
        button.setObjectName("transport_button")
        button.setIcon(load_icon_asset(icon_file))
        button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        button.setToolTip(tooltip)
        button.setFixedSize(_BUTTON_SIZE, _BUTTON_SIZE)
        self.buttons_layout.addWidget(button)
        return button


__all__ = ["SIDE_PANEL_WIDTH", "ZOOM_PANEL_WIDTH", "TimelineSidePanel"]
