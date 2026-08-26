"""Combine the animated background with the generated star layer."""

from __future__ import annotations

import numpy as np

from starflight.core.background import BackgroundRenderer
from starflight.core.camera_motion import camera_motion_progress
from starflight.core.parallax import parallax_strength_for_level
from starflight.core.star_renderer import StarRenderer
from starflight.types.settings import ProjectSettings, RenderQuality
from starflight.utils.image import bgr_to_rgb


class FrameRenderer:
    """cached frame renderer for a project."""

    def __init__(
        self,
        source_image_bgr: np.ndarray,
        settings: ProjectSettings,
        parallax_depth: np.ndarray | None = None,
    ) -> None:
        """
        initialize renderers for the current settings.

        source_image_bgr
            loaded source image in bgr format
        settings
            project settings
        """

        width = settings.resolution.width
        height = settings.resolution.height
        self.settings = settings
        self.background = BackgroundRenderer(
            source_image_bgr,
            width,
            height,
            parallax_depth=parallax_depth,
        )
        self.stars = StarRenderer(settings.stars, width, height)

    def render_frame(
        self,
        time_seconds: float,
        quality: RenderQuality,
        include_stars: bool = True,
    ) -> np.ndarray:
        """
        render a full rgb frame.

        time_seconds
            current time in seconds
        quality
            preview or export render quality
        include_stars
            when false, skip the star layer entirely
        """

        duration = self.settings.duration_seconds
        motion_progress = camera_motion_progress(
            time_seconds,
            duration,
            self.settings.background,
            self.settings.stars.speed,
        )
        background_bgr = self.background.render(
            time_seconds,
            duration,
            self.settings.background,
            self.settings.stars.speed,
            parallax_strength=(
                parallax_strength_for_level(self.settings.parallax.strength)
                if quality == RenderQuality.EXPORT and self.settings.parallax.enabled
                else 0.0
            ),
        )
        background_rgb = bgr_to_rgb(background_bgr).astype(np.float32)
        if not include_stars:
            return np.clip(background_rgb, 0, 255).astype(np.uint8)

        star_layer = self.stars.render_layer(
            time_seconds,
            duration,
            quality,
            self._view_center_at_progress,
            motion_progress,
        )
        composite = _composite_additive(background_rgb, star_layer)
        return np.clip(composite, 0, 255).astype(np.uint8)

    def _view_center_at_progress(self, progress: float) -> tuple[float, float]:
        """
        return the on-screen focus position used as the star vanishing point.

        progress
            normalized animation progress 0..1
        """

        return self.background.focus_screen_position(progress, self.settings.background)


def _composite_additive(background: np.ndarray, stars: np.ndarray) -> np.ndarray:
    """
    blend stars onto the background using screen compositing for visible light points.

    background
        background rgb float layer
    stars
        star rgb float layer
    """

    stars_clamped = np.clip(stars, 0.0, 255.0)
    return 255.0 - (255.0 - background) * (255.0 - stars_clamped) / 255.0


def create_renderer(
    source_image_bgr: np.ndarray,
    settings: ProjectSettings,
    parallax_depth: np.ndarray | None = None,
) -> FrameRenderer:
    """
    create a frame renderer for source image and settings.

    source_image_bgr
        source image in bgr format
    settings
        project settings
    """

    return FrameRenderer(source_image_bgr, settings, parallax_depth=parallax_depth)
