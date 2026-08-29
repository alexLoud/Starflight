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

_PREVIEW_GAP_BEFORE_ZOOM = 12
_ICON_SIZE = 18
_BUTTON_HEIGHT = 32
_BUTTON_SIZE = 32
_BUTTON_SPACING = 6
_ROW_SPACING = 4
_SIDE_MARGINS = (10, 0, 10, 0)
_CAPTION_HEIGHT = 16


class ZoomToolbar(QWidget):
    """Timeline preview-mode, star-layer, and zoom controls."""

    stars_enabled_changed = Signal(bool)
    parallax_preview_enabled_changed = Signal(bool)

    def __init__(
        self,
        viewport: ZoomablePreviewViewport,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._viewport = viewport
        self.setObjectName("timeline_zoom")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
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
        grid.setHorizontalSpacing(_PREVIEW_GAP_BEFORE_ZOOM)
        grid.setVerticalSpacing(_ROW_SPACING)
        grid.setContentsMargins(0, 0, 0, 0)

        self.parallax_button = self._create_labeled_toggle(
            "section-background.svg",
            checked=False,
            object_name="parallax_preview_toggle_button",
        )
        self.parallax_button.setEnabled(False)
        self.stars_button = self._create_labeled_toggle(
            "section-stars.svg",
            checked=True,
            object_name="stars_toggle_button",
        )
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

        preview_row = QWidget(self)
        preview_row.setObjectName("timeline_side_row")
        preview_layout = QHBoxLayout(preview_row)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setSpacing(_BUTTON_SPACING)
        preview_layout.addWidget(self.parallax_button)
        preview_layout.addWidget(self.stars_button)

        self.preview_heading_label = QLabel(self)
        self.preview_heading_label.setObjectName("timeline_preview_heading")
        self.preview_heading_label.setFixedHeight(_CAPTION_HEIGHT)
        self.preview_heading_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        )

        self.preview_status_label = QLabel(self)
        self.preview_status_label.setObjectName("timeline_preview_status")
        self.preview_status_label.setFixedHeight(_CAPTION_HEIGHT)
        self.preview_status_label.setAlignment(
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter,
        )

        grid.addWidget(
            self.preview_heading_label,
            0,
            0,
            Qt.AlignmentFlag.AlignLeft,
        )
        grid.addWidget(preview_row, 1, 0, Qt.AlignmentFlag.AlignVCenter)
        grid.addWidget(zoom_row, 1, 1)
        grid.addWidget(
            self.preview_status_label,
            2,
            0,
            Qt.AlignmentFlag.AlignHCenter,
        )
        grid.addWidget(
            self.zoom_level_label,
            2,
            1,
            Qt.AlignmentFlag.AlignHCenter,
        )

        outer.addStretch(1)
        outer.addLayout(grid)
        outer.addStretch(1)

        self.stars_button.toggled.connect(self._on_stars_toggled)
        self.parallax_button.toggled.connect(self._on_parallax_toggled)
        self.fit_button.clicked.connect(self._viewport.reset_to_fit)
        self.zoom_in_button.clicked.connect(self._viewport.zoom_in)
        self.zoom_out_button.clicked.connect(self._viewport.zoom_out)
        self._viewport.zoom_percent_changed.connect(self._on_zoom_changed)
        self._parallax_preview_available = False
        self._parallax_preview_status = "none"
        self._update_preview_heading()
        self._update_parallax_text()
        self._update_stars_label()

    def _create_labeled_toggle(
        self,
        icon_file: str,
        *,
        checked: bool,
        object_name: str,
    ) -> QToolButton:
        """Create a labeled on/off control for one preview layer."""

        button = QToolButton(self)
        button.setObjectName(object_name)
        button.setIcon(load_icon_asset(icon_file))
        button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setCheckable(True)
        button.setChecked(checked)
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

    @property
    def parallax_preview_enabled(self) -> bool:
        """Return whether the generated parallax snapshot is selected."""

        return self.parallax_button.isChecked() and self._parallax_preview_available

    def set_parallax_preview_state(self, *, available: bool, status: str) -> None:
        """Enable the mode switch and describe whether its snapshot is current."""

        if status not in {"disabled", "none", "ready", "stale", "generating"}:
            raise ValueError(f"unknown parallax preview status: {status}")
        self._parallax_preview_available = bool(available)
        self._parallax_preview_status = status
        if not available and self.parallax_button.isChecked():
            self.parallax_button.setChecked(False)
        self.parallax_button.setEnabled(available)
        self._update_parallax_text()

    def set_parallax_preview_enabled(self, enabled: bool) -> None:
        """Select the generated preview when it is available."""

        self.parallax_button.setChecked(bool(enabled) and self._parallax_preview_available)

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self._update_stars_label()
        self._update_parallax_text()
        self._update_preview_heading()
        self.fit_button.setToolTip(self.tr("Fit to view"))
        self.zoom_out_button.setToolTip(self.tr("Zoom out"))
        self.zoom_in_button.setToolTip(self.tr("Zoom in"))

    def _update_preview_heading(self) -> None:
        """set the small heading above the preview toggles."""

        self.preview_heading_label.setText(self.tr("Preview options:"))

    def _on_stars_toggled(self, checked: bool) -> None:
        """
        update label and notify listeners when stars toggle changes.

        checked
            true when preview stars are enabled
        """

        self._update_stars_label()
        self.stars_enabled_changed.emit(checked)

    def _on_parallax_toggled(self, checked: bool) -> None:
        """Notify the window that the preview source changed."""

        self._update_parallax_text()
        self.parallax_preview_enabled_changed.emit(checked)

    def _update_parallax_text(self) -> None:
        """Translate the parallax toggle, status, and tooltip."""

        if self.parallax_button.isChecked():
            self.parallax_button.setText(self.tr("Parallax on"))
        else:
            self.parallax_button.setText(self.tr("Parallax off"))
        self.parallax_button.setToolTip(
            self.tr("Switch between the normal and generated parallax preview."),
        )
        status = self._parallax_preview_status
        if status == "disabled":
            self.parallax_button.setToolTip(
                self.tr("Enable the parallax effect in the sidebar first."),
            )
        self.preview_status_label.setText("")
        self.preview_status_label.setProperty("previewStatus", status)
        self.preview_status_label.style().unpolish(self.preview_status_label)
        self.preview_status_label.style().polish(self.preview_status_label)

    def _update_stars_label(self) -> None:
        """set stars button text from the current toggle state."""

        if self.stars_button.isChecked():
            self.stars_button.setText(self.tr("Stars on"))
        else:
            self.stars_button.setText(self.tr("Stars off"))

    def _on_zoom_changed(self, percent: int) -> None:
        self.zoom_level_label.setText(f"{percent}%")


__all__ = ["ZoomToolbar"]
