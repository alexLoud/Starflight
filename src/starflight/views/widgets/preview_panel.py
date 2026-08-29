"""Display rendered frames in a zoomable viewport."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent, QPixmap
from PySide6.QtWidgets import (
    QGridLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from starflight.utils.image import numpy_rgb_to_qimage
from starflight.views.widgets.zoomable_viewport import ZoomablePreviewViewport

_PLAYBACK_PREVIEW_LONG_EDGE = 960


class _EmptyPreviewDropZone(QWidget):
    """Show the first import action and accept a source image drop."""

    load_requested = Signal()
    image_dropped = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preview_empty_state")
        self.setAcceptDrops(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(0)
        layout.addStretch(1)

        self.content = QWidget(self)
        self.content.setObjectName("preview_empty_content")
        self.content.setMinimumWidth(320)
        self.content.setMaximumWidth(420)
        self.content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        self.title_label = QLabel(self.tr("Import an image without stars"), self.content)
        self.title_label.setObjectName("preview_empty_title")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.title_label)
        content_layout.addSpacing(20)

        self.message_label = QLabel(self.content)
        self.message_label.setObjectName("preview_empty_message")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        content_layout.addWidget(self.message_label)

        self.load_button = QPushButton(self.tr("Choose image…"), self.content)
        self.load_button.setObjectName("preview_empty_load_button")
        self.load_button.setMinimumWidth(180)
        self.load_button.clicked.connect(self.load_requested)
        content_layout.addWidget(self.load_button, alignment=Qt.AlignmentFlag.AlignHCenter)
        content_layout.addSpacing(12)

        self.hint_label = QLabel(self.tr("or drag it here \u00b7 JPG, PNG, TIFF"), self.content)
        self.hint_label.setObjectName("preview_empty_hint")
        self.hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(self.hint_label)

        layout.addWidget(self.content, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)

        self.set_message("")

    def set_message(self, message: str) -> None:
        """Update the context shown above the import action."""

        self.message_label.setText(message)
        self.message_label.setVisible(bool(message))

    def retranslate_ui(self) -> None:
        """Refresh static texts owned by the empty import state."""

        self.title_label.setText(self.tr("Import an image without stars"))
        self.load_button.setText(self.tr("Choose image…"))
        self.hint_label.setText(self.tr("or drag it here \u00b7 JPG, PNG, TIFF"))

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._local_path_from_event(event) is None:
            event.ignore()
            return
        self._set_drag_active(True)
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._local_path_from_event(event)
        self._set_drag_active(False)
        if path is None:
            event.ignore()
            return
        self.image_dropped.emit(path)
        event.acceptProposedAction()

    @staticmethod
    def _local_path_from_event(event) -> str | None:
        urls = event.mimeData().urls()
        if not urls:
            return None
        url = urls[0]
        if not url.isLocalFile():
            return None
        return url.toLocalFile()

    def _set_drag_active(self, active: bool) -> None:
        if self.property("dragActive") == active:
            return
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)


class PreviewPanel(QWidget):
    """left preview area with zoomable viewport."""

    resized = Signal()
    load_image_requested = Signal()
    image_dropped = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._target_width = 1920
        self._target_height = 1080

        self.viewport = ZoomablePreviewViewport(self)
        self.viewport.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.empty_state = _EmptyPreviewDropZone(self)
        self.empty_state.load_requested.connect(self.load_image_requested.emit)
        self.empty_state.image_dropped.connect(self.image_dropped.emit)
        self.empty_edge_warning = QLabel(self)
        self.empty_edge_warning.setObjectName("preview_empty_edge_warning")
        self.empty_edge_warning.setText(
            self.tr("Empty edges will appear in the export — enable “Avoid empty areas”."),
        )

        container = QWidget(self)
        container.setObjectName("preview_container")
        container_layout = QGridLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.addWidget(self.viewport, 0, 0)
        container_layout.addWidget(self.empty_state, 0, 0)
        container_layout.addWidget(
            self.empty_edge_warning,
            0,
            0,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(0)
        layout.addWidget(container, stretch=1)

        self.viewport.hide()
        self.empty_edge_warning.hide()

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
        self.empty_state.hide()
        self.viewport.show()
        self.viewport.set_frame_pixmap(pixmap)

    def show_message(self, message: str) -> None:
        """
        show placeholder message.

        message
            message text
        """

        self.empty_state.set_message(message)
        self.viewport.hide()
        self.empty_edge_warning.hide()
        self.empty_state.show()

    def show_empty_preview_message(self) -> None:
        """show placeholder when no source image is loaded."""

        self.show_message("")

    def set_empty_edge_warning(self, visible: bool) -> None:
        """Show an exact export warning after the preview renderer checked every frame."""

        self.empty_edge_warning.setVisible(visible)

    def retranslate_ui(self) -> None:
        """Refresh translatable texts."""

        self.empty_state.retranslate_ui()
        self.empty_edge_warning.setText(
            self.tr("Empty edges will appear in the export — enable “Avoid empty areas”."),
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.resized.emit()


__all__ = ["PreviewPanel"]
