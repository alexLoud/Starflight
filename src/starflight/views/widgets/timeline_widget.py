"""Show the video timeline, playback controls, and frame scrubber."""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QMouseEvent, QPainter, QPaintEvent, QPen, QPolygonF
from PySide6.QtWidgets import QSizePolicy, QWidget

from starflight.views.icons import load_icon_asset
from starflight.views.theme import (
    BORDER,
    PANEL_BG,
    TEXT_MUTED,
    TIMELINE_PLAYHEAD,
    TIMELINE_RULER,
    TIMELINE_TRACK,
)
from starflight.views.widgets.timeline_side_panel import (
    SIDE_PANEL_WIDTH,
    ZOOM_PANEL_WIDTH,
    TimelineSidePanel,
)

_SIDE_PANEL_WIDTH = SIDE_PANEL_WIDTH
_ZOOM_PANEL_WIDTH = ZOOM_PANEL_WIDTH
_RULER_HEIGHT = 22
_TRACK_HEIGHT = 34
_PADDING = 10


class TimelineWidget(QWidget):
    """video-editor style timeline with transport controls."""

    frame_index_changed = Signal(int)
    play_state_changed = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("timeline_widget")
        self.setMinimumHeight(_RULER_HEIGHT + _TRACK_HEIGHT + 28)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._fps = 30
        self._duration_seconds = 10.0
        self._total_frames = 300
        self._current_frame = 0
        self._is_playing = False
        self._dragging = False
        self._zoom_panel: QWidget | None = None
        self._play_anchor_seconds = 0.0
        self._play_anchor_frame = 0

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_timer_tick)

        self._build_transport()
        self._update_time_label()

    def set_zoom_panel(self, panel: QWidget) -> None:
        """
        attach zoom controls to the right side of the timeline.

        panel
            zoom toolbar widget
        """

        self._zoom_panel = panel
        panel.setParent(self)
        panel.show()

    def _build_transport(self) -> None:
        self._transport = TimelineSidePanel("timeline_transport", self)

        self.step_back_button = self._transport.add_button("step-back.svg")
        self.step_back_button.clicked.connect(self.step_backward)

        self.play_button = self._transport.add_button("play.svg")
        self.play_button.clicked.connect(self.toggle_playback)

        self.stop_button = self._transport.add_button("stop.svg")
        self.stop_button.clicked.connect(self.stop)

        self.step_forward_button = self._transport.add_button("step-forward.svg")
        self.step_forward_button.clicked.connect(self.step_forward)

        self.time_label = self._transport.caption_label

    def configure(
        self,
        duration_seconds: float,
        fps: int,
        *,
        preserve_time: bool = False,
    ) -> None:
        """
        configure timeline duration and frame rate.

        duration_seconds
            clip duration
        fps
            frames per second
        preserve_time
            keep the current playhead time when remapping frames
        """

        previous_time = self.current_time_seconds() if preserve_time else None
        self._duration_seconds = max(0.1, duration_seconds)
        self._fps = max(1, fps)
        self._total_frames = max(1, round(self._duration_seconds * self._fps) - 1)
        if previous_time is not None:
            self._current_frame = int(
                max(0, min(self._total_frames, round(previous_time * self._fps))),
            )
        else:
            self._current_frame = min(self._current_frame, self._total_frames)
        self._update_timer_interval()
        self._update_time_label()
        self.update()

    def set_frame_index(self, frame_index: int, *, emit_signal: bool = True) -> None:
        """
        set current frame index.

        frame_index
            frame to display
        emit_signal
            whether to emit change signal
        """

        frame_index = int(max(0, min(self._total_frames, frame_index)))
        self._current_frame = frame_index
        self._update_time_label()
        self.update()
        if emit_signal:
            self.frame_index_changed.emit(frame_index)

    def current_time_seconds(self) -> float:
        """return current time in seconds."""

        return self._current_frame / self._fps

    def toggle_playback(self) -> None:
        """toggle play/pause."""

        if self._is_playing:
            self.pause()
        else:
            self.play()

    def play(self) -> None:
        """start playback."""

        self._is_playing = True
        self._play_anchor_seconds = time.perf_counter()
        self._play_anchor_frame = self._current_frame
        self.play_button.setIcon(load_icon_asset("pause.svg"))
        self._timer.start()
        self.play_state_changed.emit(True)

    def pause(self) -> None:
        """pause playback."""

        self._is_playing = False
        self.play_button.setIcon(load_icon_asset("play.svg"))
        self._timer.stop()
        self.play_state_changed.emit(False)

    def stop(self) -> None:
        """stop playback and return to start."""

        self.pause()
        self.set_frame_index(0, emit_signal=True)

    def step_backward(self) -> None:
        """move one frame backward."""

        if self._is_playing:
            self.pause()
        self.set_frame_index(self._current_frame - 1, emit_signal=True)

    def step_forward(self) -> None:
        """move one frame forward."""

        if self._is_playing:
            self.pause()
        self.set_frame_index(self._current_frame + 1, emit_signal=True)

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self.step_back_button.setToolTip(self.tr("Previous frame"))
        self.play_button.setToolTip(self.tr("Play / Pause"))
        self.stop_button.setToolTip(self.tr("Stop"))
        self.step_forward_button.setToolTip(self.tr("Next frame"))

    def _zoom_panel_width(self) -> int:
        if self._zoom_panel is None:
            return 0
        return _ZOOM_PANEL_WIDTH

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._transport.setGeometry(0, 0, _SIDE_PANEL_WIDTH, self.height())
        if self._zoom_panel is not None:
            zoom_width = self._zoom_panel_width()
            self._zoom_panel.setGeometry(
                max(_SIDE_PANEL_WIDTH, self.width() - zoom_width),
                0,
                zoom_width,
                self.height(),
            )

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        track_left = _SIDE_PANEL_WIDTH
        track_right = self.width() - self._zoom_panel_width()
        track_width = max(1.0, track_right - track_left)
        painter.fillRect(self.rect(), QColor(PANEL_BG))

        ruler_rect = QRectF(track_left + _PADDING, 6, track_width - _PADDING * 2, _RULER_HEIGHT)
        track_area = QRectF(
            track_left + _PADDING,
            ruler_rect.bottom() + 4,
            ruler_rect.width(),
            _TRACK_HEIGHT,
        )

        self._paint_ruler(painter, ruler_rect)
        self._paint_track(painter, track_area)
        self._paint_playhead(painter, ruler_rect, track_area)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return
        track_rect = self._track_rect()
        if not track_rect.contains(event.position()):
            return
        self._dragging = True
        if self._is_playing:
            self.pause()
        self._set_frame_from_x(event.position().x(), emit_signal=True)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if not self._dragging:
            return
        self._set_frame_from_x(event.position().x(), emit_signal=True)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        del event
        self._dragging = False

    def _track_rect(self) -> QRectF:
        track_left = _SIDE_PANEL_WIDTH
        track_right = self.width() - self._zoom_panel_width()
        return QRectF(
            track_left + _PADDING,
            6 + _RULER_HEIGHT + 4,
            max(1.0, track_right - track_left - _PADDING * 2),
            _TRACK_HEIGHT,
        )

    def _set_frame_from_x(self, x: float, *, emit_signal: bool) -> None:
        track_rect = self._track_rect()
        ratio = (x - track_rect.left()) / max(1.0, track_rect.width())
        ratio = max(0.0, min(1.0, ratio))
        frame_index = round(ratio * self._total_frames)
        self.set_frame_index(frame_index, emit_signal=emit_signal)

    def _paint_ruler(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.drawLine(QPointF(rect.left(), rect.bottom()), QPointF(rect.right(), rect.bottom()))

        tick_color = QColor(TIMELINE_RULER)
        text_color = QColor(TEXT_MUTED)
        font = QFont(self.font())
        font.setPointSize(9)
        painter.setFont(font)

        duration = self._duration_seconds
        if duration <= 0:
            return

        interval = self._choose_tick_interval(duration, rect.width())
        tick_index = 0
        seconds = 0.0
        while seconds <= duration + 0.001:
            ratio = seconds / duration if duration > 0 else 0.0
            x = rect.left() + ratio * rect.width()
            is_major = tick_index % 5 == 0
            tick_height = 8 if is_major else 4
            painter.setPen(QPen(tick_color, 1))
            painter.drawLine(QPointF(x, rect.bottom()), QPointF(x, rect.bottom() - tick_height))
            if is_major:
                label = self._format_ruler_time(seconds)
                painter.setPen(text_color)
                painter.drawText(
                    QRectF(x - 24, rect.top(), 48, rect.height() - tick_height - 1),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
                    label,
                )
            seconds += interval
            tick_index += 1

    def _paint_track(self, painter: QPainter, rect: QRectF) -> None:
        painter.setPen(QPen(QColor(BORDER), 1))
        painter.setBrush(QColor(TIMELINE_TRACK))
        painter.drawRoundedRect(rect, 4, 4)

        clip_rect = QRectF(rect.left() + 2, rect.top() + 2, rect.width() - 4, rect.height() - 4)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#243040"))
        painter.drawRoundedRect(clip_rect, 3, 3)

    def _paint_playhead(self, painter: QPainter, ruler_rect: QRectF, track_rect: QRectF) -> None:
        ratio = self._current_frame / max(1, self._total_frames)
        x = track_rect.left() + ratio * track_rect.width()

        painter.setPen(QPen(QColor(TIMELINE_PLAYHEAD), 2))
        painter.drawLine(QPointF(x, ruler_rect.top()), QPointF(x, track_rect.bottom() + 2))

        triangle = QPolygonF(
            [
                QPointF(x - 5, ruler_rect.top()),
                QPointF(x + 5, ruler_rect.top()),
                QPointF(x, ruler_rect.top() + 8),
            ],
        )
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(TIMELINE_PLAYHEAD))
        painter.drawPolygon(triangle)

    def _on_timer_tick(self) -> None:
        """advance the playhead to the wall-clock target frame."""

        if not self._is_playing:
            return

        elapsed_seconds = max(0.0, time.perf_counter() - self._play_anchor_seconds)
        target_frame = self._play_anchor_frame + int(elapsed_seconds * self._fps)
        if target_frame > self._total_frames:
            self.set_frame_index(0, emit_signal=True)
            self.pause()
            return
        if target_frame != self._current_frame:
            self.set_frame_index(target_frame, emit_signal=True)

    def _update_timer_interval(self) -> None:
        # poll faster than fps so catch-up stays smooth after slow renders
        self._timer.setInterval(max(1, min(16, int(1000 / self._fps))))

    def _update_time_label(self) -> None:
        current = self._format_time(self.current_time_seconds())
        total = self._format_time(self._duration_seconds)
        self.time_label.setText(f"{current} / {total}")

    @staticmethod
    def _format_time(seconds: float) -> str:
        total_seconds = int(seconds)
        minutes = total_seconds // 60
        remainder = seconds - total_seconds
        return f"{minutes}:{total_seconds % 60:02d}.{int(remainder * 100):02d}"

    @staticmethod
    def _format_ruler_time(seconds: float) -> str:
        total_seconds = int(seconds)
        minutes = total_seconds // 60
        if minutes > 0:
            return f"{minutes}:{total_seconds % 60:02d}"
        if seconds < 1:
            return f"{seconds:.1f}s"
        return f"{total_seconds}s"

    @staticmethod
    def _choose_tick_interval(duration: float, width: float) -> float:
        target_ticks = max(4, int(width / 70))
        raw = duration / target_ticks
        candidates = [0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60]
        for candidate in candidates:
            if raw <= candidate:
                return candidate
        return 60.0


__all__ = ["TimelineWidget"]
