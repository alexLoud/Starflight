"""Display rendered frames in a zoomable viewport."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from starflight.utils.image import numpy_rgb_to_qimage
from starflight.views.widgets.zoomable_viewport import ZoomablePreviewViewport

_PLAYBACK_PREVIEW_LONG_EDGE = 960


class PreviewPanel(QWidget):
    """left preview area with zoomable viewport."""

    resized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_width = 1920
        self._target_height = 1080

        self.viewport = ZoomablePreviewViewport(self)
        self.viewport.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        container = QWidget(self)
        container.setObjectName("preview_container")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.viewport)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)
        layout.addWidget(container, stretch=1)

    def set_target_resolution(self, width: int, height: int) -> None:
        """
        store target resolution for aspect ratio preview sizing.

        width
            target video width
        height
            target video height
        """

        self._target_width = max(2, width)
        self._target_height = max(2, height)

    def preview_render_size(self) -> tuple[int, int]:
        """
        compute preview dimensions at full target resolution.

        returns width and height in pixels
        """

        width = self._target_width
        height = self._target_height
        if width % 2 != 0:
            width += 1
        if height % 2 != 0:
            height += 1
        return width, height

    def playback_render_size(self) -> tuple[int, int]:
        """Return a high-quality render size used only during timeline playback."""

        scale = min(
            1.0,
            _PLAYBACK_PREVIEW_LONG_EDGE / max(self._target_width, self._target_height),
        )
        width = max(2, round(self._target_width * scale))
        height = max(2, round(self._target_height * scale))
        if width % 2 != 0:
            width += 1
        if height % 2 != 0:
            height += 1
        return width, height

    def show_frame(self, image_rgb) -> None:
        """
        display rendered rgb frame.

        image_rgb
            rgb numpy frame
        """

        qimage = numpy_rgb_to_qimage(image_rgb, screen=self.screen())
        pixmap = QPixmap.fromImage(qimage)
        pixmap.setDevicePixelRatio(1.0)
        self.viewport.set_frame_pixmap(pixmap)

    def show_message(self, message: str) -> None:
        """
        show placeholder message.

        message
            message text
        """

        self.viewport.set_message(message)

    def show_empty_preview_message(self) -> None:
        """show placeholder when no source image is loaded."""

        self.show_message(self.tr("Load at least one image to see the preview."))

    def retranslate_ui(self) -> None:
        """Refresh translatable texts."""

        return

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.resized.emit()


__all__ = ["PreviewPanel"]
