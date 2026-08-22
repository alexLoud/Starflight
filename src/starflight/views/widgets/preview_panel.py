"""Display rendered frames in a zoomable viewport."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QSizePolicy, QStackedWidget, QVBoxLayout, QWidget

from starflight.utils.image import numpy_rgb_to_qimage
from starflight.views.widgets.welcome_splash import WelcomeSplash
from starflight.views.widgets.zoomable_viewport import ZoomablePreviewViewport


class PreviewPanel(QWidget):
    """left preview area with zoomable viewport."""

    resized = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_width = 1080
        self._target_height = 1920

        self.viewport = ZoomablePreviewViewport(self)
        self.viewport.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.welcome_splash = WelcomeSplash(self)

        self._preview_stack = QStackedWidget(self)
        self._preview_stack.setObjectName("preview_stack")
        self._preview_stack.addWidget(self.viewport)
        self._preview_stack.addWidget(self.welcome_splash)
        self._preview_stack.setCurrentWidget(self.welcome_splash)

        self.welcome_splash.dismissed.connect(self._on_welcome_dismissed)

        container = QWidget(self)
        container.setObjectName("preview_container")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self._preview_stack)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 8, 4)
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
        self.welcome_splash.dismiss()

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

        self.welcome_splash.retranslate_ui()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.resized.emit()

    def _on_welcome_dismissed(self) -> None:
        """
        switch from the welcome splash back to the preview viewport.

        """

        self._preview_stack.setCurrentWidget(self.viewport)


__all__ = ["PreviewPanel"]
