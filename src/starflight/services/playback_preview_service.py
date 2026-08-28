"""Pre-render timeline preview frames outside the GUI thread."""

from __future__ import annotations

import threading
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from dataclasses import dataclass
from multiprocessing import get_context

import cv2
import numpy as np
from PySide6.QtCore import QThread, Signal

from starflight.core.background import effective_background_settings
from starflight.core.camera_motion import camera_motion_progress
from starflight.core.renderer import FrameRenderer, composite_star_layer, create_renderer
from starflight.core.star_renderer import StarRenderer
from starflight.services.parallax_preview_service import PreparedParallaxPreview
from starflight.types.settings import ProjectSettings, RenderQuality
from starflight.utils.image import load_image_bgr

PLAYBACK_PREVIEW_FPS = 6
BACKGROUND_PREVIEW_FPS = 2
PLAYBACK_PARALLAX_ITERATIONS = 6
_PLAYBACK_JPEG_QUALITY = 100


@dataclass(slots=True)
class PlaybackRenderSpec:
    """Immutable inputs shared by playback-preview render processes."""

    image_path: str
    settings: ProjectSettings
    crop_target_size: tuple[int, int]
    include_stars: bool
    parallax_preview: PreparedParallaxPreview | None = None


class PlaybackFrameCache:
    """Keep rendered frames for one project/settings revision."""

    def __init__(self, duration_seconds: float) -> None:
        self.duration_seconds = max(0.1, float(duration_seconds))
        self._frames: dict[int, bytes] = {}

    @property
    def frame_count(self) -> int:
        return playback_sample_count(self.duration_seconds)

    def clear(self, duration_seconds: float) -> None:
        self.duration_seconds = max(0.1, float(duration_seconds))
        self._frames.clear()

    def store(self, sample_index: int, payload: bytes) -> None:
        if 0 <= sample_index < self.frame_count:
            self._frames[sample_index] = payload

    def frame(self, sample_index: int) -> np.ndarray | None:
        payload = self._frames.get(sample_index)
        if payload is None:
            return None
        encoded = np.frombuffer(payload, dtype=np.uint8)
        return cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    def missing(self, sample_indices: list[int]) -> list[int]:
        return [index for index in sample_indices if index not in self._frames]

    def background_indices(self) -> list[int]:
        step = max(1, PLAYBACK_PREVIEW_FPS // BACKGROUND_PREVIEW_FPS)
        return list(range(0, self.frame_count, step))

    def playback_indices_from(self, time_seconds: float) -> list[int]:
        start = playback_sample_index(time_seconds, self.duration_seconds)
        return list(range(start, self.frame_count))


def playback_sample_count(duration_seconds: float) -> int:
    """Return the number of cached frames needed for one non-looping preview."""

    return max(1, round(max(0.1, duration_seconds) * PLAYBACK_PREVIEW_FPS))


def playback_sample_index(time_seconds: float, duration_seconds: float) -> int:
    """Map timeline time onto the nearest cached playback frame."""

    last_index = playback_sample_count(duration_seconds) - 1
    return max(0, min(last_index, round(max(0.0, time_seconds) * PLAYBACK_PREVIEW_FPS)))


_process_renderer: FrameRenderer | None = None
_process_parallax_renderer: FrameRenderer | None = None
_process_star_renderer: StarRenderer | None = None
_process_settings: ProjectSettings | None = None
_process_include_stars = True


def _initialize_playback_process(spec: PlaybackRenderSpec) -> None:
    """Create one reusable renderer inside each worker process."""

    global _process_renderer
    global _process_parallax_renderer
    global _process_star_renderer
    global _process_settings
    global _process_include_stars

    _process_settings = spec.settings.clone()
    _process_include_stars = spec.include_stars
    if spec.parallax_preview is None:
        source = load_image_bgr(spec.image_path)
        _process_renderer = create_renderer(
            source,
            _process_settings,
            crop_target_size=spec.crop_target_size,
        )
        _process_parallax_renderer = None
        _process_star_renderer = None
        return

    preview = spec.parallax_preview
    _process_renderer = None
    _process_parallax_renderer = create_renderer(
        preview.source_image_bgr,
        preview.settings.clone(),
        parallax_depth=preview.disparity,
        parallax_iterations=PLAYBACK_PARALLAX_ITERATIONS,
    )
    _process_star_renderer = StarRenderer(
        _process_settings.stars,
        _process_settings.resolution.width,
        _process_settings.resolution.height,
    )


def _render_playback_sample(sample_index: int) -> tuple[int, bytes]:
    """Render one cached timeline sample inside a worker process."""

    time_seconds = sample_index / PLAYBACK_PREVIEW_FPS
    if _process_renderer is not None:
        frame = _process_renderer.render_frame(
            time_seconds,
            RenderQuality.PREVIEW,
            include_stars=_process_include_stars,
            star_quality=RenderQuality.EXPORT,
        )
        return sample_index, _encode_playback_frame(frame)

    if (
        _process_parallax_renderer is None
        or _process_star_renderer is None
        or _process_settings is None
    ):
        raise RuntimeError("playback preview renderer was not initialized")

    background = _process_parallax_renderer.render_frame(
        time_seconds,
        RenderQuality.PREVIEW,
        include_stars=False,
        include_parallax=True,
    )
    width = _process_settings.resolution.width
    height = _process_settings.resolution.height
    if background.shape[:2] != (height, width):
        background = cv2.resize(background, (width, height), interpolation=cv2.INTER_LINEAR)
    if not _process_include_stars:
        return sample_index, _encode_playback_frame(background)

    source_width = _process_parallax_renderer.settings.resolution.width
    source_height = _process_parallax_renderer.settings.resolution.height
    scale_x = width / source_width
    scale_y = height / source_height

    def view_center_at_progress(progress: float) -> tuple[float, float]:
        center_x, center_y = _process_parallax_renderer.view_center_at_progress(progress)
        return center_x * scale_x, center_y * scale_y

    background_settings = effective_background_settings(_process_settings.background)
    motion_progress = camera_motion_progress(
        time_seconds,
        _process_settings.duration_seconds,
        background_settings,
        _process_settings.stars.speed,
    )
    star_layer = _process_star_renderer.render_layer(
        time_seconds,
        _process_settings.duration_seconds,
        RenderQuality.EXPORT,
        view_center_at_progress,
        motion_progress,
        track_visibility=False,
    )
    frame = np.clip(composite_star_layer(background, star_layer), 0, 255).astype(np.uint8)
    return sample_index, _encode_playback_frame(frame)


def _encode_playback_frame(frame: np.ndarray) -> bytes:
    """Compress one cached frame to keep long previews memory-bounded."""

    ok, encoded = cv2.imencode(
        ".jpg",
        frame,
        [cv2.IMWRITE_JPEG_QUALITY, _PLAYBACK_JPEG_QUALITY],
    )
    if not ok:
        raise RuntimeError("playback preview frame could not be encoded")
    return encoded.tobytes()


class PlaybackPreviewWorker(QThread):
    """Render requested playback frames in parallel without blocking Qt."""

    frame_ready = Signal(int, object)
    progress_changed = Signal(int, int)
    completed = Signal()
    failed = Signal(object)

    def __init__(
        self,
        spec: PlaybackRenderSpec,
        sample_indices: list[int],
        *,
        render_workers: int,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._spec = spec
        self._sample_indices = list(dict.fromkeys(sample_indices))
        self._render_workers = max(1, int(render_workers))
        self._cancel_requested = threading.Event()

    def request_cancel(self) -> None:
        """Request cancellation after currently running frames finish."""

        self._cancel_requested.set()

    def run(self) -> None:
        if not self._sample_indices:
            self.completed.emit()
            return

        pool: ProcessPoolExecutor | None = None
        try:
            pool = ProcessPoolExecutor(
                max_workers=min(self._render_workers, len(self._sample_indices)),
                mp_context=get_context("spawn"),
                initializer=_initialize_playback_process,
                initargs=(self._spec,),
            )
            pending = {}
            next_index = 0
            completed = 0
            total = len(self._sample_indices)
            queue_limit = max(1, self._render_workers * 2)

            while next_index < total and len(pending) < queue_limit:
                sample_index = self._sample_indices[next_index]
                pending[pool.submit(_render_playback_sample, sample_index)] = sample_index
                next_index += 1

            while pending and not self._cancel_requested.is_set():
                done, _not_done = wait(
                    pending,
                    timeout=0.05,
                    return_when=FIRST_COMPLETED,
                )
                for future in done:
                    pending.pop(future)
                    sample_index, frame = future.result()
                    completed += 1
                    self.frame_ready.emit(sample_index, frame)
                    self.progress_changed.emit(completed, total)
                    if next_index < total:
                        next_sample = self._sample_indices[next_index]
                        pending[pool.submit(_render_playback_sample, next_sample)] = next_sample
                        next_index += 1

            if not self._cancel_requested.is_set():
                self.completed.emit()
        except Exception as exc:
            if not self._cancel_requested.is_set():
                self.failed.emit(exc)
        finally:
            if pool is not None:
                pool.shutdown(
                    wait=not self._cancel_requested.is_set(),
                    cancel_futures=True,
                )


__all__ = [
    "BACKGROUND_PREVIEW_FPS",
    "PLAYBACK_PARALLAX_ITERATIONS",
    "PLAYBACK_PREVIEW_FPS",
    "PlaybackFrameCache",
    "PlaybackPreviewWorker",
    "PlaybackRenderSpec",
    "playback_sample_count",
    "playback_sample_index",
]
