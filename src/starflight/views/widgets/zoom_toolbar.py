"""Control preview zoom and the session star overlay."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from starflight.views.icons import load_icon_asset
from starflight.views.theme import PANEL_BG
from starflight.views.widgets.timeline_side_panel import ZOOM_PANEL_WIDTH
from starflight.views.widgets.zoomable_viewport import ZoomablePreviewViewport

_STARS_GAP_BEFORE_ZOOM = 12
_ICON_SIZE = 18
_BUTTON_HEIGHT = 32
_BUTTON_SIZE = 32
_BUTTON_SPACING = 6
_ROW_SPACING = 4
_SIDE_MARGINS = (10, 0, 10, 0)
_CAPTION_HEIGHT = 16


class ZoomToolbar(QWidget):
    """zoom side panel on the timeline footer."""

    stars_enabled_changed = Signal(bool)

    def __init__(
        self,
        viewport: ZoomablePreviewViewport,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._viewport = viewport
        self.setObjectName("timeline_zoom")
        self.setAutoFillBackground(True)
        self.setFixedWidth(ZOOM_PANEL_WIDTH)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Window, QColor(PANEL_BG))
        self.setPalette(palette)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(*_SIDE_MARGINS)
        outer.setSpacing(0)

        grid = QGridLayout()
        grid.setHorizontalSpacing(_STARS_GAP_BEFORE_ZOOM)
        grid.setVerticalSpacing(_ROW_SPACING)
        grid.setContentsMargins(0, 0, 0, 0)

        self.stars_button = self._create_stars_button()
        self.fit_button = self._create_icon_button("zoom-fit.svg", self.tr("Fit to view"))
        self.zoom_out_button = self._create_icon_button("zoom-out.svg", self.tr("Zoom out"))
        self.zoom_in_button = self._create_icon_button("zoom-in.svg", self.tr("Zoom in"))

        zoom_row = QWidget(self)
        zoom_row.setObjectName("timeline_side_row")
        zoom_layout = QHBoxLayout(zoom_row)
        zoom_layout.setContentsMargins(0, 0, 0, 0)
        zoom_layout.setSpacing(_BUTTON_SPACING)
        zoom_layout.addWidget(self.fit_button)
        zoom_layout.addWidget(self.zoom_out_button)
        zoom_layout.addWidget(self.zoom_in_button)

        self.zoom_level_label = QLabel(self)
        self.zoom_level_label.setObjectName("timeline_time_label")
        self.zoom_level_label.setFixedHeight(_CAPTION_HEIGHT)
        self.zoom_level_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        )
        self.zoom_level_label.setText("100%")

        grid.addWidget(
            self.stars_button,
            0,
            0,
            Qt.AlignmentFlag.AlignVCenter,
        )
        grid.addWidget(zoom_row, 0, 1)
        grid.addWidget(
            self.zoom_level_label,
            1,
            1,
            Qt.AlignmentFlag.AlignHCenter,
        )

        outer.addStretch(1)
        outer.addLayout(grid)
        outer.addStretch(1)

        self.stars_button.toggled.connect(self._on_stars_toggled)
        self.fit_button.clicked.connect(self._viewport.reset_to_fit)
        self.zoom_in_button.clicked.connect(self._viewport.zoom_in)
        self.zoom_out_button.clicked.connect(self._viewport.zoom_out)
        self._viewport.zoom_percent_changed.connect(self._on_zoom_changed)
        self._update_stars_label()

    def _create_stars_button(self) -> QToolButton:
        """create the labeled stars on/off toggle."""

        button = QToolButton(self)
        button.setObjectName("stars_toggle_button")
        button.setIcon(load_icon_asset("section-stars.svg"))
        button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setCheckable(True)
        button.setChecked(True)
        button.setFixedHeight(_BUTTON_HEIGHT)
        button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        return button

    def _create_icon_button(self, icon_file: str, tooltip: str) -> QToolButton:
        """
        create a square transport-style icon button.

        icon_file
            svg icon file name
        tooltip
            hover tooltip
        """

        button = QToolButton(self)
        button.setObjectName("transport_button")
        button.setIcon(load_icon_asset(icon_file))
        button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        button.setToolTip(tooltip)
        button.setFixedSize(_BUTTON_SIZE, _BUTTON_SIZE)
        return button

    @property
    def stars_enabled(self) -> bool:
        """return whether preview stars are currently enabled."""

        return self.stars_button.isChecked()

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self._update_stars_label()
        self.fit_button.setToolTip(self.tr("Fit to view"))
        self.zoom_out_button.setToolTip(self.tr("Zoom out"))
        self.zoom_in_button.setToolTip(self.tr("Zoom in"))

    def _on_stars_toggled(self, checked: bool) -> None:
        """
        update label and notify listeners when stars toggle changes.

        checked
            true when preview stars are enabled
        """

        self._update_stars_label()
        self.stars_enabled_changed.emit(checked)

    def _update_stars_label(self) -> None:
        """set stars button text from the current toggle state."""

        if self.stars_button.isChecked():
            self.stars_button.setText(self.tr("Stars on"))
        else:
            self.stars_button.setText(self.tr("Stars off"))

    def _on_zoom_changed(self, percent: int) -> None:
        self.zoom_level_label.setText(f"{percent}%")


__all__ = ["ZoomToolbar"]
