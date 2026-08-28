"""Build preview settings and send rendered frames to the preview panel."""

from __future__ import annotations

from pathlib import Path

from starflight.i18n import tr_validation
from starflight.services.preview_service import PreviewService
from starflight.types.settings import Project, ProjectSettings
from starflight.views.widgets.preview_panel import PreviewPanel


class PreviewController:
    """coordinates preview rendering with ui panel."""

    def __init__(self, preview_service: PreviewService) -> None:
        self._preview_service = preview_service

    def invalidate(self) -> None:
        """clear preview cache."""

        self._preview_service.invalidate()

    def build_preview_settings(
        self,
        project: Project,
        preview_panel: PreviewPanel,
        *,
        playback: bool = False,
    ) -> ProjectSettings:
        """
        build scaled settings for preview rendering.

        project
            current project
        preview_panel
            preview ui panel
        playback
            use high-quality downscaled settings during timeline playback
        """

        preview_settings = project.settings.clone()
        target_width = project.settings.resolution.width
        target_height = project.settings.resolution.height
        if playback:
            width, height = preview_panel.playback_render_size()
            resolution_scale = min(
                1.0,
                width / target_width,
                height / target_height,
            )
            # Direct radius scaling loses most sub-pixel stars after display downsampling.
            # This compensation preserves their apparent energy without changing the count.
            star_scale = resolution_scale**0.8
            preview_settings.stars.min_size *= star_scale
            preview_settings.stars.max_size *= star_scale
        else:
            width, height = preview_panel.preview_render_size()
        preview_settings.resolution.width = width
        preview_settings.resolution.height = height
        return preview_settings

    def refresh_preview(
        self,
        project: Project,
        project_path: Path | None,
        preview_panel: PreviewPanel,
        timeline_time_seconds: float,
        include_stars: bool = True,
        use_parallax_preview: bool = False,
    ) -> bool:
        """
        render and display current preview frame.

        project
            current project
        project_path
            optional project path
        preview_panel
            preview ui panel
        timeline_time_seconds
            current timeline time
        include_stars
            when false, skip stars in the preview render
        use_parallax_preview
            show the explicitly generated low-resolution parallax snapshot
        returns True when frame was rendered
        """

        preview_settings = self.build_preview_settings(project, preview_panel)
        if use_parallax_preview:
            frame = self._preview_service.render_parallax_frame(
                timeline_time_seconds,
                preview_settings,
                include_stars=include_stars,
            )
            if frame is not None:
                preview_panel.show_frame(frame)
                return True

        ok, frame, message = self._preview_service.render_frame(
            project,
            project_path,
            preview_settings,
            timeline_time_seconds,
            include_stars=include_stars,
        )
        if not ok:
            if not project.source_image or message == "preview_missing_image":
                preview_panel.show_empty_preview_message()
            else:
                preview_panel.show_message(tr_validation(message))
            return False

        preview_panel.show_frame(frame)
        return True


__all__ = ["PreviewController"]
