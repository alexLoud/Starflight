"""Cache source data and render frames for the interactive preview."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from starflight.core.renderer import FrameRenderer, create_renderer
from starflight.types.settings import Project, ProjectSettings, RenderQuality, StarSettings
from starflight.utils.image import load_image_bgr
from starflight.utils.validation import ValidationResult, validate_project_for_render


class PreviewService:
    """manages preview renderer cache and frame rendering."""

    def __init__(self) -> None:
        self._preview_renderer = None
        self._preview_settings: ProjectSettings | None = None
        self._loaded_image_bgr: np.ndarray | None = None
        self._last_preview_frame: np.ndarray | None = None

    @property
    def last_preview_frame(self) -> np.ndarray | None:
        """return last rendered preview frame if available."""

        return self._last_preview_frame

    def invalidate(self) -> None:
        """clear cached renderer and frame."""

        self._preview_renderer = None
        self._preview_settings = None
        self._loaded_image_bgr = None
        self._last_preview_frame = None

    def validate(self, project: Project, project_path: Path | None) -> ValidationResult:
        """
        validate project for preview rendering.

        project
            current project
        project_path
            optional project file path
        """

        return validate_project_for_render(project, project_path)

    def render_frame(
        self,
        project: Project,
        project_path: Path | None,
        preview_settings: ProjectSettings,
        time_seconds: float,
        include_stars: bool = True,
    ) -> tuple[bool, np.ndarray | None, str]:
        """
        render preview frame at given time.

        project
            current project
        project_path
            optional project file path
        preview_settings
            scaled settings for preview resolution
        time_seconds
            animation time in seconds
        include_stars
            when false, skip star rendering for a fluid preview

        returns success flag, rgb frame and message
        """

        from starflight.services.project_service import resolve_source_image_path

        validation = self.validate(project, project_path)
        if not validation.ok:
            return False, None, validation.message

        image_path = resolve_source_image_path(project_path, project.source_image)
        if image_path is None:
            return False, None, "preview_missing_image"

        if self._preview_renderer is None or self._preview_settings != preview_settings:
            try:
                self._loaded_image_bgr = load_image_bgr(str(image_path))
            except (OSError, ValueError) as exc:
                return False, None, str(exc)
            self._preview_settings = preview_settings.clone()
            self._preview_renderer = create_renderer(self._loaded_image_bgr, preview_settings)
        else:
            _sync_star_render_settings(self._preview_renderer, preview_settings)

        frame = self._preview_renderer.render_frame(
            time_seconds,
            RenderQuality.PREVIEW,
            include_stars=include_stars,
        )
        self._last_preview_frame = frame
        return True, frame, ""


def _sync_star_render_settings(renderer: FrameRenderer, preview_settings: ProjectSettings) -> None:
    """Copy live star settings into the cached preview renderer."""

    target = renderer.stars.settings
    source = preview_settings.stars
    _copy_star_render_settings(target, source)
    renderer.stars.field.settings = target
    renderer.settings.stars = target


def _copy_star_render_settings(target: StarSettings, source: StarSettings) -> None:
    """Copy fields that affect star rendering into the renderer-owned settings."""

    target.glow_intensity = source.glow_intensity
    target.glow_depth_boost = source.glow_depth_boost
    target.color_intensity = source.color_intensity
    target.brightness = source.brightness
    target.min_size = source.min_size
    target.max_size = source.max_size
    target.magnitude_realism = source.magnitude_realism
    target.size_spread = source.size_spread
    target.speed = source.speed


__all__ = ["PreviewService"]
