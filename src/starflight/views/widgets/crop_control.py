"""Edit a fixed-aspect crop directly on the source image."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from starflight.core.crop import crop_pixel_bounds, resolve_crop_rect
from starflight.types.settings import CropSettings
from starflight.views.theme import ACCENT, BORDER, PANEL_BG, TEXT_MUTED
from starflight.views.widgets.setting_reset_button import SettingResetButton

_CANVAS_MIN_HEIGHT = 240
_HANDLE_SIZE = 9.0
_HANDLE_HIT_RADIUS = 16.0
_MIN_SELECTION_SIZE = 32.0


class CropControl(QWidget):
    """Interactive crop editor constrained to the target frame aspect ratio."""

    crop_changed = Signal()
    adjustment_finished = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("crop_control")
        self.setMinimumHeight(_CANVAS_MIN_HEIGHT + 66)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._settings = CropSettings()
        self._qimage: QImage | None = None
        self._image_width = 1
        self._image_height = 1
        self._target_width = 1
        self._target_height = 1
        self._updates_blocked = False

        self._reset_button = SettingResetButton(lambda: self.reset_crop())

        self._canvas = _CropCanvas(self)
        self._canvas.setObjectName("crop_canvas")
        self._canvas.setMinimumHeight(_CANVAS_MIN_HEIGHT)
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._canvas.setMouseTracking(True)

        self._summary_label = QLabel()
        self._summary_label.setObjectName("crop_summary")

        footer = QHBoxLayout()
        footer.setContentsMargins(0, 0, 0, 0)
        footer.setSpacing(6)
        footer.addWidget(self._summary_label)
        footer.addStretch(1)
        footer.addWidget(self._reset_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._canvas, 1)
        layout.addLayout(footer)

        self.retranslate_ui()
        self._refresh_summary()

    def set_image(self, image: QImage | None, image_width: int, image_height: int) -> None:
        """Set the full source-image preview and its original pixel dimensions."""

        self._qimage = None if image is None or image.isNull() else image
        self._image_width = max(1, int(image_width))
        self._image_height = max(1, int(image_height))
        if self._qimage is not None:
            self._clamp_settings()
        self._canvas.update()
        self._refresh_summary()

    def clear_image(self) -> None:
        """Remove the current source image."""

        self.set_image(None, 1, 1)

    def set_target_resolution(self, width: int, height: int) -> None:
        """Update the crop aspect ratio without changing its center or relative size."""

        self._target_width = max(1, int(width))
        self._target_height = max(1, int(height))
        if self._qimage is not None:
            self._clamp_settings()
        self._canvas.update()
        self._refresh_summary()

    def set_crop(self, center_x: float, center_y: float, scale: float) -> None:
        """Load normalized crop values without emitting a user edit."""

        self._updates_blocked = True
        self._settings = CropSettings(center_x=center_x, center_y=center_y, scale=scale)
        if self._qimage is not None:
            self._clamp_settings()
        else:
            self._settings.scale = max(0.01, min(1.0, float(scale)))
        self._updates_blocked = False
        self._canvas.update()
        self._refresh_summary()

    def crop_values(self) -> tuple[float, float, float]:
        """Return normalized crop center and relative size."""

        return (
            self._settings.center_x,
            self._settings.center_y,
            self._settings.scale,
        )

    def is_adjusting(self) -> bool:
        """Return whether the user is currently dragging the crop rectangle."""

        return self._canvas.is_adjusting()

    def reset_crop(self, *, emit_change: bool = True) -> None:
        """Restore the largest centered crop for the current target aspect ratio."""

        changed = self._settings != CropSettings()
        self._settings = CropSettings()
        self._canvas.update()
        self._refresh_summary()
        if changed and emit_change and not self._updates_blocked:
            self.crop_changed.emit()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            self._refresh_summary()
            self._canvas.update()

    def retranslate_ui(self) -> None:
        """Refresh user-visible text."""

        self._reset_button.retranslate_ui()
        self._refresh_summary()
        self._canvas.update()

    def _set_crop(self, center_x: float, center_y: float, scale: float) -> None:
        previous = self._settings
        self._settings = CropSettings(center_x=center_x, center_y=center_y, scale=scale)
        self._clamp_settings()
        self._canvas.update()
        self._refresh_summary()
        if self._settings != previous and not self._updates_blocked:
            self.crop_changed.emit()

    def _clamp_settings(self) -> None:
        rect = resolve_crop_rect(
            self._settings,
            self._image_width,
            self._image_height,
            self._target_width,
            self._target_height,
        )
        self._settings = CropSettings(
            center_x=rect.x + rect.width / 2.0,
            center_y=rect.y + rect.height / 2.0,
            scale=max(0.01, min(1.0, self._settings.scale)),
        )

    def _refresh_summary(self) -> None:
        if self._qimage is None:
            self._summary_label.setText(self.tr("No image loaded"))
            return
        left, top, right, bottom = crop_pixel_bounds(
            self._settings,
            self._image_width,
            self._image_height,
            self._target_width,
            self._target_height,
        )
        self._summary_label.setText(
            self.tr("Crop: {width} x {height} px · {scale}%").format(
                width=right - left,
                height=bottom - top,
                scale=round(self._settings.scale * 100),
            ),
        )


class _CropCanvas(QWidget):
    """Paint and manipulate the fixed-aspect crop rectangle."""

    def __init__(self, owner: CropControl) -> None:
        super().__init__(owner)
        self._owner = owner
        self._drag_mode: str | None = None
        self._press_position = QPointF()
        self._press_rect = QRectF()

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
                self.tr("Load an image to choose a crop."),
            )
            return

        image_rect = self._image_rect()
        painter.drawImage(image_rect, owner._qimage)
        selection = self._selection_rect()
        shade = QColor(0, 0, 0, 150)
        painter.fillRect(
            QRectF(
                image_rect.left(),
                image_rect.top(),
                image_rect.width(),
                selection.top() - image_rect.top(),
            ),
            shade,
        )
        painter.fillRect(
            QRectF(
                image_rect.left(),
                selection.bottom(),
                image_rect.width(),
                image_rect.bottom() - selection.bottom(),
            ),
            shade,
        )
        painter.fillRect(
            QRectF(
                image_rect.left(),
                selection.top(),
                selection.left() - image_rect.left(),
                selection.height(),
            ),
            shade,
        )
        painter.fillRect(
            QRectF(
                selection.right(),
                selection.top(),
                image_rect.right() - selection.right(),
                selection.height(),
            ),
            shade,
        )

        painter.setPen(QPen(QColor(ACCENT), 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(selection)
        painter.setPen(QPen(QColor("#FFFFFF"), 1))
        painter.setBrush(QColor(ACCENT))
        for point in self._handle_points(selection).values():
            painter.drawRect(
                QRectF(
                    point.x() - _HANDLE_SIZE / 2.0,
                    point.y() - _HANDLE_SIZE / 2.0,
                    _HANDLE_SIZE,
                    _HANDLE_SIZE,
                ),
            )

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if (
            not self.isEnabled()
            or self._owner._qimage is None
            or event.button() != Qt.MouseButton.LeftButton
        ):
            return
        position = event.position()
        selection = self._selection_rect()
        handle = self._hit_handle(position, selection)
        if handle is None and not selection.contains(position):
            return
        self._drag_mode = handle or "move"
        self._press_position = position
        self._press_rect = selection
        self.setCursor(
            Qt.CursorShape.ClosedHandCursor
            if self._drag_mode == "move"
            else self._cursor_for_handle(self._drag_mode)
        )
        event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        position = event.position()
        if self._drag_mode == "move":
            self._move_selection(position)
            return
        if self._drag_mode is not None:
            self._resize_selection(position)
            return

        selection = self._selection_rect()
        handle = self._hit_handle(position, selection)
        if handle is not None:
            self.setCursor(self._cursor_for_handle(handle))
        elif selection.contains(position):
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or self._drag_mode is None:
            return
        self._drag_mode = None
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._owner.adjustment_finished.emit()
        event.accept()

    def is_adjusting(self) -> bool:
        """Return whether a crop drag or resize is in progress."""

        return self._drag_mode is not None

    def _image_rect(self) -> QRectF:
        owner = self._owner
        if owner._qimage is None:
            return QRectF()
        available = QRectF(1, 1, max(1, self.width() - 2), max(1, self.height() - 2))
        scale = min(
            available.width() / owner._image_width,
            available.height() / owner._image_height,
        )
        width = owner._image_width * scale
        height = owner._image_height * scale
        return QRectF(
            available.center().x() - width / 2.0,
            available.center().y() - height / 2.0,
            width,
            height,
        )

    def _selection_rect(self) -> QRectF:
        owner = self._owner
        image_rect = self._image_rect()
        crop = resolve_crop_rect(
            owner._settings,
            owner._image_width,
            owner._image_height,
            owner._target_width,
            owner._target_height,
        )
        return QRectF(
            image_rect.left() + crop.x * image_rect.width(),
            image_rect.top() + crop.y * image_rect.height(),
            crop.width * image_rect.width(),
            crop.height * image_rect.height(),
        )

    @staticmethod
    def _handle_points(rect: QRectF) -> dict[str, QPointF]:
        return {
            "top_left": rect.topLeft(),
            "top_right": rect.topRight(),
            "bottom_left": rect.bottomLeft(),
            "bottom_right": rect.bottomRight(),
        }

    def _hit_handle(self, position: QPointF, rect: QRectF) -> str | None:
        for name, point in self._handle_points(rect).items():
            if (
                abs(position.x() - point.x()) <= _HANDLE_HIT_RADIUS
                and abs(position.y() - point.y()) <= _HANDLE_HIT_RADIUS
            ):
                return name
        return None

    @staticmethod
    def _cursor_for_handle(handle: str) -> Qt.CursorShape:
        if handle in {"top_left", "bottom_right"}:
            return Qt.CursorShape.SizeFDiagCursor
        return Qt.CursorShape.SizeBDiagCursor

    def _move_selection(self, position: QPointF) -> None:
        image_rect = self._image_rect()
        offset = position - self._press_position
        rect = self._press_rect.translated(offset)
        if rect.left() < image_rect.left():
            rect.moveLeft(image_rect.left())
        if rect.right() > image_rect.right():
            rect.moveRight(image_rect.right())
        if rect.top() < image_rect.top():
            rect.moveTop(image_rect.top())
        if rect.bottom() > image_rect.bottom():
            rect.moveBottom(image_rect.bottom())
        self._apply_canvas_rect(rect)

    def _resize_selection(self, position: QPointF) -> None:
        image_rect = self._image_rect()
        handle = self._drag_mode
        if handle is None:
            return
        anchors = {
            "top_left": self._press_rect.bottomRight(),
            "top_right": self._press_rect.bottomLeft(),
            "bottom_left": self._press_rect.topRight(),
            "bottom_right": self._press_rect.topLeft(),
        }
        anchor = anchors[handle]
        left_handle = handle in {"top_left", "bottom_left"}
        top_handle = handle in {"top_left", "top_right"}
        available_width = (
            anchor.x() - image_rect.left() if left_handle else image_rect.right() - anchor.x()
        )
        available_height = (
            anchor.y() - image_rect.top() if top_handle else image_rect.bottom() - anchor.y()
        )
        aspect = self._owner._target_width / self._owner._target_height
        raw_width = abs(position.x() - anchor.x())
        raw_height = abs(position.y() - anchor.y())
        width = max(raw_width, raw_height * aspect)
        height = width / aspect
        maximum_scale = min(
            1.0,
            available_width / max(width, 1e-6),
            available_height / max(height, 1e-6),
        )
        width *= maximum_scale
        height *= maximum_scale
        minimum_width = max(_MIN_SELECTION_SIZE, _MIN_SELECTION_SIZE * aspect)
        width = max(width, min(available_width, minimum_width))
        height = width / aspect
        if height > available_height:
            height = available_height
            width = height * aspect

        left = anchor.x() - width if left_handle else anchor.x()
        top = anchor.y() - height if top_handle else anchor.y()
        self._apply_canvas_rect(QRectF(left, top, width, height))

    def _apply_canvas_rect(self, rect: QRectF) -> None:
        image_rect = self._image_rect()
        maximum = resolve_crop_rect(
            CropSettings(),
            self._owner._image_width,
            self._owner._image_height,
            self._owner._target_width,
            self._owner._target_height,
        )
        normalized_width = rect.width() / image_rect.width()
        normalized_height = rect.height() / image_rect.height()
        scale = min(
            normalized_width / maximum.width,
            normalized_height / maximum.height,
        )
        self._owner._set_crop(
            (rect.center().x() - image_rect.left()) / image_rect.width(),
            (rect.center().y() - image_rect.top()) / image_rect.height(),
            scale,
        )


__all__ = ["CropControl"]
