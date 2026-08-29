"""Prepare a compact V4 parallax source for explicit timeline previews."""

from __future__ import annotations

import threading

import cv2
from PySide6.QtCore import QThread, Signal

from starflight.core.parallax import (
    create_parallax_depth,
    prepare_parallax_depth_v4,
    prepare_parallax_render_input,
)
from starflight.types.preview import PreparedParallaxPreview
from starflight.types.settings import ProjectSettings, ResolutionSettings
from starflight.utils.image import load_image_bgr

PARALLAX_PREVIEW_LONG_EDGE = 640
PARALLAX_PREVIEW_ITERATIONS = 10


class _PreviewCancelledError(RuntimeError):
    """Stop a superseded preview preparation without reporting an error."""


def parallax_preview_size(width: int, height: int) -> tuple[int, int]:
    """Fit the target aspect ratio within the preview long-edge limit."""

    target_width = max(2, int(width))
    target_height = max(2, int(height))
    scale = min(1.0, PARALLAX_PREVIEW_LONG_EDGE / max(target_width, target_height))
    preview_width = max(2, round(target_width * scale))
    preview_height = max(2, round(target_height * scale))
    preview_width -= preview_width % 2
    preview_height -= preview_height % 2
    return max(2, preview_width), max(2, preview_height)


class ParallaxPreviewWorker(QThread):
    """Create the cropped and downscaled V4 disparity field off the GUI thread."""

    progress_changed = Signal(int)
    preview_ready = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        image_path: str,
        settings: ProjectSettings,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._image_path = image_path
        self._settings = settings.clone()
        self._cancel_requested = threading.Event()
        self._last_progress = -1

    def request_cancel(self) -> None:
        """Request cooperative cancellation at the next preparation progress update."""

        self._cancel_requested.set()

    def _report(self, fraction: float) -> None:
        if self._cancel_requested.is_set():
            raise _PreviewCancelledError
        progress = round(max(0.0, min(1.0, fraction)) * 100)
        if progress != self._last_progress:
            self._last_progress = progress
            self.progress_changed.emit(progress)

    def run(self) -> None:
        try:
            self._report(0.0)
            source_image = load_image_bgr(self._image_path)
            source_image, render_settings = prepare_parallax_render_input(
                source_image,
                self._settings,
            )
            preview_width, preview_height = parallax_preview_size(
                render_settings.resolution.width,
                render_settings.resolution.height,
            )
            preview_scale = min(
                preview_width / render_settings.resolution.width,
                preview_height / render_settings.resolution.height,
            )
            preview_source = cv2.resize(
                source_image,
                (preview_width, preview_height),
                interpolation=cv2.INTER_AREA,
            )
            render_settings.resolution = ResolutionSettings(preview_width, preview_height)
            render_settings.stars.min_size *= preview_scale
            render_settings.stars.max_size *= preview_scale
            self._report(0.05)

            raw_depth = create_parallax_depth(
                preview_source,
                (0.5, 0.5),
                on_progress=lambda fraction: self._report(0.05 + 0.70 * fraction),
            )
            disparity = prepare_parallax_depth_v4(
                raw_depth,
                on_progress=lambda fraction: self._report(0.75 + 0.25 * fraction),
            )
            self._report(1.0)
            self.preview_ready.emit(
                PreparedParallaxPreview(
                    source_image_bgr=preview_source,
                    settings=render_settings,
                    disparity=disparity,
                )
            )
        except _PreviewCancelledError:
            pass
        except Exception as exc:
            self.failed.emit(exc)


__all__ = [
    "PARALLAX_PREVIEW_ITERATIONS",
    "ParallaxPreviewWorker",
    "parallax_preview_size",
]
