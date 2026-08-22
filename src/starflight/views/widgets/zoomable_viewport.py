"""Display preview frames with fit and manual zoom modes."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPixmap, QResizeEvent, QWheelEvent
from PySide6.QtWidgets import QFrame, QGraphicsPixmapItem, QGraphicsScene, QGraphicsView, QWidget

from starflight.views.theme import CHECKER_A, CHECKER_B

_ZOOM_STEP = 1.15
_MIN_ZOOM_PERCENT = 50
_MIN_SCALE = _MIN_ZOOM_PERCENT / 100.0
_MAX_SCALE = 32.0
_SCALE_EPSILON = 1e-6
_CHECKER_TILE = 12


class ZoomablePreviewViewport(QGraphicsView):
    """graphics view with wheel zoom, pan and fit-to-view."""

    fit_mode_changed = Signal(bool)
    zoom_percent_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("preview_viewport")

        self._scene = QGraphicsScene(self)
        self._pixmap_item = QGraphicsPixmapItem()
        self._scene.addItem(self._pixmap_item)
        self._checker_brush = self._build_checker_brush()

        self._fit_mode = True
        self._applying_fit = False
        self._message = ""

        self.setScene(self._scene)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.SmartViewportUpdate)
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    def set_message(self, message: str) -> None:
        """
        show placeholder message when no frame is available.

        message
            placeholder text
        """

        self._message = message
        self._pixmap_item.setPixmap(QPixmap())
        self.resetTransform()
        self._scene.setSceneRect(
            QRectF(
                0,
                0,
                max(1, self.viewport().width()),
                max(1, self.viewport().height()),
            )
        )
        self.viewport().update()

    def set_frame_pixmap(self, pixmap: QPixmap) -> None:
        """
        display rendered frame pixmap.

        pixmap
            frame to display
        """

        self._message = ""
        self._pixmap_item.setPixmap(pixmap)
        self._scene.setSceneRect(QRectF(0, 0, pixmap.width(), pixmap.height()))
        if self._fit_mode:
            self.reset_to_fit()
        else:
            self._emit_zoom_percent()

    def reset_to_fit(self) -> None:
        """fit current frame into the viewport."""

        pixmap = self._pixmap_item.pixmap()
        if pixmap.isNull():
            return
        self._apply_fit_transform()
        self._set_fit_mode(True)

    def reset_zoom(self) -> None:
        """reset zoom to 100% and leave fit mode."""

        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.resetTransform()
        if not self._pixmap_item.pixmap().isNull():
            self.centerOn(self._pixmap_item)
        if self._fit_mode:
            self._fit_mode = False
            self.fit_mode_changed.emit(False)
        self.zoom_percent_changed.emit(100)

    def zoom_in(self) -> None:
        """zoom in one step from viewport center."""

        self._zoom_from_center(_ZOOM_STEP)

    def zoom_out(self) -> None:
        """zoom out one step from viewport center."""

        self._zoom_from_center(1.0 / _ZOOM_STEP)

    def set_zoom_percent(self, percent: int) -> None:
        """
        set absolute zoom percentage.

        percent
            zoom level in percent relative to native pixel size
        """

        pixmap = self._pixmap_item.pixmap()
        if pixmap.isNull():
            return

        target_scale = max(_MIN_SCALE, min(_MAX_SCALE, percent / 100.0))

        self._enable_manual_zoom()
        self.resetTransform()
        self.scale(target_scale, target_scale)
        self.centerOn(self._pixmap_item)
        self._set_fit_mode(False)
        self._emit_zoom_percent()

    def current_zoom_percent(self) -> int:
        """return current zoom level in percent."""

        if self._fit_mode:
            pixmap = self._pixmap_item.pixmap()
            if pixmap.isNull():
                return 100
            return round(self.transform().m11() * 100)
        return round(self.transform().m11() * 100)

    def is_fit_mode(self) -> bool:
        """return whether fit mode is active."""

        return self._fit_mode

    def wheelEvent(self, event: QWheelEvent) -> None:
        if self._pixmap_item.pixmap().isNull():
            super().wheelEvent(event)
            return

        delta = event.angleDelta().y() or event.pixelDelta().y()
        if delta == 0:
            super().wheelEvent(event)
            return

        factor = _ZOOM_STEP ** (delta / 120.0)
        current_scale = self.transform().m11()
        if current_scale <= 0:
            return

        minimum_scale = self._minimum_zoom_scale()
        target_scale = max(minimum_scale, min(_MAX_SCALE, current_scale * factor))

        self._enable_manual_zoom()
        self._apply_absolute_scale(target_scale)
        self._set_fit_mode(False)
        self._emit_zoom_percent()
        event.accept()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        pixmap = self._pixmap_item.pixmap()
        if pixmap.isNull():
            self.viewport().update()
            return
        if self._fit_mode:
            self._apply_fit_transform()
            return

        minimum_scale = self._minimum_zoom_scale()
        if self.transform().m11() < minimum_scale - _SCALE_EPSILON:
            self._apply_absolute_scale(minimum_scale)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        painter.fillRect(rect, self._checker_brush)

        if self._message and self._pixmap_item.pixmap().isNull():
            painter.save()
            painter.resetTransform()
            painter.setPen(QColor("#8A97A8"))
            text_rect = self.viewport().rect().adjusted(24, 24, -24, -24)
            painter.drawText(
                text_rect,
                int(Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap),
                self._message,
            )
            painter.restore()

    def _zoom_from_center(self, factor: float) -> None:
        pixmap = self._pixmap_item.pixmap()
        if pixmap.isNull():
            return

        current_scale = self.transform().m11()
        if current_scale <= 0:
            return

        minimum_scale = self._minimum_zoom_scale()
        target_scale = max(minimum_scale, min(_MAX_SCALE, current_scale * factor))

        self._enable_manual_zoom()
        center_before = self.mapToScene(self.viewport().rect().center())
        self._apply_absolute_scale(target_scale)
        center_after = self.mapToScene(self.viewport().rect().center())
        delta = center_before - center_after
        self.translate(delta.x(), delta.y())
        self._set_fit_mode(False)
        self._emit_zoom_percent()

    def _enable_manual_zoom(self) -> None:
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def _apply_fit_transform(self) -> None:
        if self._applying_fit:
            return
        pixmap = self._pixmap_item.pixmap()
        if pixmap.isNull():
            return

        self._applying_fit = True
        try:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            self.resetTransform()
            self.fitInView(self._pixmap_item, Qt.AspectRatioMode.KeepAspectRatio)
            self.centerOn(self._pixmap_item)
            self._emit_zoom_percent()
        finally:
            self._applying_fit = False

    def _minimum_zoom_scale(self) -> float:
        """return minimum allowed zoom relative to native pixel size."""

        return _MIN_SCALE

    def _apply_absolute_scale(self, target_scale: float) -> None:
        current_scale = self.transform().m11()
        if current_scale <= 0:
            return
        factor = target_scale / current_scale
        if factor <= 0 or abs(factor - 1.0) < _SCALE_EPSILON:
            return
        self.scale(factor, factor)

    def _set_fit_mode(self, enabled: bool) -> None:
        if self._fit_mode == enabled:
            return
        self._fit_mode = enabled
        self.fit_mode_changed.emit(enabled)
        self._emit_zoom_percent()

    def _emit_zoom_percent(self) -> None:
        self.zoom_percent_changed.emit(self.current_zoom_percent())

    @staticmethod
    def _build_checker_brush() -> QBrush:
        tile = _CHECKER_TILE
        pattern = QPixmap(tile * 2, tile * 2)
        pattern.fill(QColor(CHECKER_B))
        painter = QPainter(pattern)
        painter.fillRect(0, 0, tile, tile, QColor(CHECKER_A))
        painter.fillRect(tile, tile, tile, tile, QColor(CHECKER_A))
        painter.end()
        return QBrush(pattern)


__all__ = ["ZoomablePreviewViewport"]
