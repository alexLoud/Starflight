"""Edit the camera start and target points on a source image.

The control stores positions as normalized image coordinates. Its canvas handles drawing, hit
testing, and dragging while the outer widget owns the buttons and summary text.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPolygonF,
)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from starflight.views.theme import (
    BORDER,
    PANEL_BG,
    TEXT_MUTED,
)

_CANVAS_MIN_HEIGHT = 240.0
_MARKER_RADIUS = 11.0
_HIT_RADIUS = 16.0
_START_COLOR = "#4AA3A2"
_END_COLOR = "#E8A84C"


class FocusPointsControl(QWidget):
    """interactive start/end focus point editor over a source image preview."""

    focus_changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("focus_points_control")
        self.setMinimumHeight(int(_CANVAS_MIN_HEIGHT + 72))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._start_enabled = False
        self._end_enabled = False
        self._start_point = QPointF(0.5, 0.5)
        self._end_point = QPointF(0.5, 0.5)
        self._drag_target: str | None = None
        self._updates_blocked = False
        self._qimage: QImage | None = None
        self._image_width = 1
        self._image_height = 1

        self._start_button = QPushButton()
        self._start_button.setObjectName("focus_point_toggle")
        self._start_button.setCheckable(True)
        self._start_button.toggled.connect(self._on_start_toggled)

        self._end_button = QPushButton()
        self._end_button.setObjectName("focus_point_toggle")
        self._end_button.setCheckable(True)
        self._end_button.toggled.connect(self._on_end_toggled)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(8)
        button_row.addWidget(self._start_button)
        button_row.addWidget(self._end_button)
        button_row.addStretch(1)

        self._canvas = _FocusPointsCanvas(self)
        self._canvas.setObjectName("focus_points_canvas")
        self._canvas.setMinimumHeight(int(_CANVAS_MIN_HEIGHT))
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._canvas.setCursor(Qt.CursorShape.ArrowCursor)

        self._summary_label = QLabel(self)
        self._summary_label.setObjectName("focus_points_summary")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addLayout(button_row)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(self._summary_label)

        self.retranslate_ui()
        self._refresh_summary()

    def set_image(self, image: QImage | None, image_width: int, image_height: int) -> None:
        """
        set the source image preview.

        image
            preview image or None when unavailable
        image_width
            original image width in pixels
        image_height
            original image height in pixels
        """

        self._qimage = None if image is None or image.isNull() else image
        self._image_width = max(1, image_width)
        self._image_height = max(1, image_height)
        self._canvas.update()
        self._refresh_summary()

    def clear_image(self) -> None:
        """remove the current preview image."""

        self.set_image(None, 1, 1)

    def set_points(
        self,
        start_enabled: bool,
        start_x: float,
        start_y: float,
        end_enabled: bool,
        end_x: float,
        end_y: float,
    ) -> None:
        """
        set optional start and end focus points.

        start_enabled
            whether the start point is active
        start_x
            normalized start x in 0..1
        start_y
            normalized start y in 0..1
        end_enabled
            whether the end point is active
        end_x
            normalized end x in 0..1
        end_y
            normalized end y in 0..1
        """

        self._updates_blocked = True
        self._start_point = self._clamp_point(start_x, start_y)
        self._end_point = self._clamp_point(end_x, end_y)
        self._start_button.setChecked(start_enabled)
        self._end_button.setChecked(end_enabled)
        self._start_enabled = start_enabled
        self._end_enabled = end_enabled
        self._updates_blocked = False
        self._canvas.update()
        self._refresh_summary()

    def point_values(self) -> tuple[bool, float, float, bool, float, float]:
        """return enabled flags and normalized start/end coordinates."""

        return (
            self._start_enabled,
            self._start_point.x(),
            self._start_point.y(),
            self._end_enabled,
            self._end_point.x(),
            self._end_point.y(),
        )

    def retranslate_ui(self) -> None:
        """refresh button and summary label text."""

        self._start_button.setText(self.tr("Start"))
        self._start_button.setToolTip(
            self.tr("Optional start look-at. When unset, the camera starts at the image center."),
        )
        self._end_button.setText(self.tr("Target"))
        self._end_button.setToolTip(
            self.tr("Optional end look-at. When unset, the camera ends at the image center."),
        )
        self._refresh_summary()
        self._canvas.update()

    def setEnabled(self, enabled: bool) -> None:
        """
        enable or disable the whole control.

        enabled
            whether interaction is allowed
        """

        super().setEnabled(enabled)
        self._start_button.setEnabled(enabled)
        self._end_button.setEnabled(enabled)
        self._canvas.setEnabled(enabled)
        self._canvas.update()

    def _on_start_toggled(self, checked: bool) -> None:
        self._start_enabled = checked
        self._canvas.update()
        self._refresh_summary()
        self._emit_changed()

    def _on_end_toggled(self, checked: bool) -> None:
        self._end_enabled = checked
        self._canvas.update()
        self._refresh_summary()
        self._emit_changed()

    def _emit_changed(self) -> None:
        if not self._updates_blocked:
            self.focus_changed.emit()

    def _refresh_summary(self) -> None:
        if self._qimage is None:
            self._summary_label.setText(self.tr("No image loaded"))
            return

        if not self._start_enabled and not self._end_enabled:
            self._summary_label.setText(self.tr("No path set · camera stays centered"))
            return

        parts: list[str] = []
        if self._start_enabled:
            parts.append(
                self.tr("Start {x} · {y}").format(
                    x=f"{self._start_point.x() * 100:.0f}%",
                    y=f"{self._start_point.y() * 100:.0f}%",
                ),
            )
        else:
            parts.append(self.tr("Start: center"))

        if self._end_enabled:
            parts.append(
                self.tr("Target {x} · {y}").format(
                    x=f"{self._end_point.x() * 100:.0f}%",
                    y=f"{self._end_point.y() * 100:.0f}%",
                ),
            )
        else:
            parts.append(self.tr("Target: center"))

        self._summary_label.setText("  →  ".join(parts))

    @staticmethod
    def _clamp_point(x: float, y: float) -> QPointF:
        return QPointF(max(0.0, min(1.0, x)), max(0.0, min(1.0, y)))


class _FocusPointsCanvas(QWidget):
    """painted preview surface for focus markers and path."""

    def __init__(self, owner: FocusPointsControl) -> None:
        super().__init__(owner)
        self._owner = owner

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        owner = self._owner
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        canvas = QRectF(0, 0, float(self.width()), float(self.height()))
        painter.fillRect(canvas, QColor(PANEL_BG))
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(canvas.adjusted(0.5, 0.5, -0.5, -0.5), 4, 4)

        if owner._qimage is None:
            painter.setPen(QColor(TEXT_MUTED))
            painter.drawText(
                canvas,
                int(Qt.AlignmentFlag.AlignCenter),
                self.tr("Load an image to set the camera path."),
            )
            return

        image_rect = self._image_rect()
        painter.drawImage(image_rect, owner._qimage)

        if not self.isEnabled():
            painter.fillRect(image_rect, QColor(12, 15, 20, 160))
            return

        start_canvas = (
            self._point_to_canvas(owner._start_point) if owner._start_enabled else None
        )
        end_canvas = self._point_to_canvas(owner._end_point) if owner._end_enabled else None

        if start_canvas is not None and end_canvas is not None:
            self._paint_path(painter, start_canvas, end_canvas)

        if start_canvas is not None:
            self._paint_marker(painter, start_canvas, self.tr("S"), QColor(_START_COLOR))
        if end_canvas is not None:
            self._paint_marker(painter, end_canvas, self.tr("T"), QColor(_END_COLOR))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        owner = self._owner
        if (
            not self.isEnabled()
            or owner._qimage is None
            or event.button() != Qt.MouseButton.LeftButton
        ):
            return

        point = event.position()
        if not self._image_rect().contains(point):
            return

        hit = self._hit_marker(point)
        if hit is not None:
            owner._drag_target = hit
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        normalized = self._point_to_normalized(point)
        if owner._start_enabled and not owner._end_enabled:
            owner._start_point = owner._clamp_point(normalized.x(), normalized.y())
            owner._drag_target = "start"
        elif owner._end_enabled:
            owner._end_point = owner._clamp_point(normalized.x(), normalized.y())
            owner._drag_target = "end"
        elif owner._start_enabled:
            owner._start_point = owner._clamp_point(normalized.x(), normalized.y())
            owner._drag_target = "start"
        else:
            return

        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.update()
        owner._refresh_summary()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        owner = self._owner
        if owner._drag_target is None:
            hit = self._hit_marker(event.position()) if self.isEnabled() else None
            self.setCursor(
                Qt.CursorShape.OpenHandCursor if hit is not None else Qt.CursorShape.ArrowCursor,
            )
            return

        normalized = self._point_to_normalized(event.position())
        if owner._drag_target == "start":
            owner._start_point = owner._clamp_point(normalized.x(), normalized.y())
        else:
            owner._end_point = owner._clamp_point(normalized.x(), normalized.y())
        self.update()
        owner._refresh_summary()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        owner = self._owner
        if event.button() != Qt.MouseButton.LeftButton or owner._drag_target is None:
            return

        owner._drag_target = None
        hit = self._hit_marker(event.position())
        self.setCursor(
            Qt.CursorShape.OpenHandCursor if hit is not None else Qt.CursorShape.ArrowCursor,
        )
        self.update()
        owner._refresh_summary()
        owner._emit_changed()

    def _hit_marker(self, point: QPointF) -> str | None:
        owner = self._owner
        candidates: list[tuple[str, QPointF]] = []
        if owner._end_enabled:
            candidates.append(("end", self._point_to_canvas(owner._end_point)))
        if owner._start_enabled:
            candidates.append(("start", self._point_to_canvas(owner._start_point)))

        for name, marker in candidates:
            if (point - marker).manhattanLength() <= _HIT_RADIUS * 1.4:
                return name
        return None

    def _image_rect(self) -> QRectF:
        owner = self._owner
        available_width = max(1.0, float(self.width()) - 8.0)
        available_height = max(1.0, float(self.height()) - 8.0)
        scale = min(available_width / owner._image_width, available_height / owner._image_height)
        width = owner._image_width * scale
        height = owner._image_height * scale
        left = (float(self.width()) - width) / 2.0
        top = (float(self.height()) - height) / 2.0
        return QRectF(left, top, width, height)

    def _point_to_canvas(self, point: QPointF) -> QPointF:
        image_rect = self._image_rect()
        return QPointF(
            image_rect.left() + point.x() * image_rect.width(),
            image_rect.top() + point.y() * image_rect.height(),
        )

    def _point_to_normalized(self, point: QPointF) -> QPointF:
        image_rect = self._image_rect()
        x = (point.x() - image_rect.left()) / image_rect.width()
        y = (point.y() - image_rect.top()) / image_rect.height()
        return QPointF(max(0.0, min(1.0, x)), max(0.0, min(1.0, y)))

    def _paint_path(self, painter: QPainter, start: QPointF, end: QPointF) -> None:
        painter.setPen(QPen(QColor("#F4F7FB"), 1.5, Qt.PenStyle.SolidLine))
        painter.drawLine(start, end)

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        length = math.hypot(dx, dy)
        if length < 18.0:
            return

        ux = dx / length
        uy = dy / length
        # several chevrons along the path point toward the target.
        for fraction in (0.35, 0.55, 0.75):
            center = QPointF(start.x() + dx * fraction, start.y() + dy * fraction)
            self._paint_chevron(painter, center, ux, uy)

    def _paint_chevron(self, painter: QPainter, center: QPointF, ux: float, uy: float) -> None:
        px = -uy
        py = ux
        tip = QPointF(center.x() + ux * 6.0, center.y() + uy * 6.0)
        left = QPointF(center.x() - ux * 4.0 + px * 5.0, center.y() - uy * 4.0 + py * 5.0)
        right = QPointF(center.x() - ux * 4.0 - px * 5.0, center.y() - uy * 4.0 - py * 5.0)
        painter.setBrush(QColor("#F4F7FB"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(QPolygonF([tip, left, right]))

    def _paint_marker(self, painter: QPainter, center: QPointF, label: str, color: QColor) -> None:
        badge = QRectF(center.x() - 8.0, center.y() - _MARKER_RADIUS - 16.0, 16.0, 14.0)
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(badge, 3, 3)

        font = QFont(painter.font())
        font.setBold(True)
        font.setPointSize(9)
        painter.setFont(font)
        painter.setPen(QColor("#0C0F14"))
        painter.drawText(badge, int(Qt.AlignmentFlag.AlignCenter), label)

        painter.setBrush(color)
        painter.setPen(QPen(QColor("#F4F7FB"), 1.5))
        painter.drawEllipse(center, _MARKER_RADIUS, _MARKER_RADIUS)

        painter.setPen(QPen(QColor("#F4F7FB"), 1))
        painter.drawLine(
            QPointF(center.x() - 4.0, center.y()),
            QPointF(center.x() + 4.0, center.y()),
        )
        painter.drawLine(
            QPointF(center.x(), center.y() - 4.0),
            QPointF(center.x(), center.y() + 4.0),
        )


__all__ = ["FocusPointsControl"]
