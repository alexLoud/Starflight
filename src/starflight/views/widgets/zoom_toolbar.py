"""Control preview zoom and the session star overlay."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QSizePolicy, QToolButton

from starflight.views.icons import load_icon_asset
from starflight.views.widgets.timeline_side_panel import TimelineSidePanel
from starflight.views.widgets.zoomable_viewport import ZoomablePreviewViewport

_STARS_GAP_BEFORE_ZOOM = 12
_ICON_SIZE = 18
_BUTTON_HEIGHT = 32


class ZoomToolbar(TimelineSidePanel):
    """zoom side panel on the timeline footer, identical layout to transport."""

    stars_enabled_changed = Signal(bool)

    def __init__(
        self,
        viewport: ZoomablePreviewViewport,
        parent=None,
    ) -> None:
        super().__init__("timeline_zoom", parent)
        self._viewport = viewport

        self.stars_button = self._create_stars_button()
        self.buttons_layout.addSpacing(_STARS_GAP_BEFORE_ZOOM)
        self.fit_button = self.add_button("zoom-fit.svg", self.tr("Fit to view"))
        self.zoom_out_button = self.add_button("zoom-out.svg", self.tr("Zoom out"))
        self.zoom_in_button = self.add_button("zoom-in.svg", self.tr("Zoom in"))
        self.zoom_level_label = self.caption_label
        self.zoom_level_label.setText("100%")

        self.stars_button.toggled.connect(self._on_stars_toggled)
        self.fit_button.clicked.connect(self._viewport.reset_to_fit)
        self.zoom_in_button.clicked.connect(self._viewport.zoom_in)
        self.zoom_out_button.clicked.connect(self._viewport.zoom_out)
        self._viewport.zoom_percent_changed.connect(self._on_zoom_changed)
        self._update_stars_label()

    def _create_stars_button(self) -> QToolButton:
        """create the labeled stars on/off toggle."""

        button = QToolButton(self.button_row)
        button.setObjectName("stars_toggle_button")
        button.setIcon(load_icon_asset("section-stars.svg"))
        button.setIconSize(QSize(_ICON_SIZE, _ICON_SIZE))
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setCheckable(True)
        button.setChecked(True)
        button.setFixedHeight(_BUTTON_HEIGHT)
        button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.buttons_layout.addWidget(button)
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
