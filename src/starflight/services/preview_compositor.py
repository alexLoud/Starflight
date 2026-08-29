"""Shared helpers for preview-only background and star compositing."""

from __future__ import annotations

import cv2
import numpy as np

from starflight.core.camera_motion import camera_motion_progress
from starflight.core.renderer import FrameRenderer, composite_star_layer
from starflight.core.star_renderer import StarRenderer
from starflight.types.settings import ProjectSettings, RenderQuality


def render_parallax_preview_frame(
    background_renderer: FrameRenderer,
    preview_settings: ProjectSettings,
    time_seconds: float,
    *,
    include_stars: bool,
    star_renderer: StarRenderer | None = None,
) -> np.ndarray:
    """Render a parallax preview frame with an optional star overlay."""

    background = background_renderer.render_frame(
        time_seconds,
        RenderQuality.PREVIEW,
        include_stars=False,
        include_parallax=True,
    )
    width = preview_settings.resolution.width
    height = preview_settings.resolution.height
    if background.shape[:2] != (height, width):
        background = cv2.resize(background, (width, height), interpolation=cv2.INTER_LINEAR)
    if not include_stars or star_renderer is None:
        return background

    source_width = background_renderer.settings.resolution.width
    source_height = background_renderer.settings.resolution.height
    scale_x = width / source_width
    scale_y = height / source_height

    def view_center_at_progress(progress: float) -> tuple[float, float]:
        center_x, center_y = background_renderer.view_center_at_progress(progress)
        return center_x * scale_x, center_y * scale_y

    duration = preview_settings.duration_seconds
    motion_progress = camera_motion_progress(
        time_seconds,
        duration,
        preview_settings.background,
        preview_settings.stars.speed,
    )
    star_layer = star_renderer.render_layer(
        time_seconds,
        duration,
        RenderQuality.EXPORT,
        view_center_at_progress,
        motion_progress,
        track_visibility=False,
    )
    return np.clip(composite_star_layer(background, star_layer), 0, 255).astype(np.uint8)
