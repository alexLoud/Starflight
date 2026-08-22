"""Combine the preview viewport, timeline, and zoom controls."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from starflight.views.widgets.preview_panel import PreviewPanel
from starflight.views.widgets.timeline_widget import TimelineWidget
from starflight.views.widgets.zoom_toolbar import ZoomToolbar


class PreviewWorkspace(QWidget):
    """preview area with timeline and zoom controls in the footer."""

    resized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preview_workspace")

        self.preview_panel = PreviewPanel()
        self.timeline = TimelineWidget()
        self.zoom_toolbar = ZoomToolbar(self.preview_panel.viewport)
        self.timeline.set_zoom_panel(self.zoom_toolbar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.preview_panel, stretch=1)
        layout.addWidget(self.timeline, stretch=0)

        self.preview_panel.resized.connect(self.resized.emit)

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self.preview_panel.retranslate_ui()
        self.timeline.retranslate_ui()
        self.zoom_toolbar.retranslate_ui()


__all__ = ["PreviewWorkspace"]
