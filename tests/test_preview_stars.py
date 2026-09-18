"""Regression tests for export-accurate stars in the interactive preview."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

import cv2
import numpy as np

from starflight.controllers.preview_controller import PreviewController
from starflight.core.camera_motion import rotation_radians
from starflight.core.renderer import create_renderer
from starflight.core.star_renderer import StarRenderer
from starflight.services.preview_compositor import render_parallax_preview_frame
from starflight.services.preview_service import _needs_renderer_rebuild
from starflight.types.settings import (
    FlightDirection,
    Project,
    ProjectSettings,
    RenderQuality,
    ResolutionSettings,
)


class PreviewStarTests(unittest.TestCase):
    def test_preview_can_use_the_exact_export_star_profile(self) -> None:
        source = np.zeros((64, 96, 3), dtype=np.uint8)
        settings = ProjectSettings(resolution=ResolutionSettings(96, 64))
        settings.stars.star_count = 80
        settings.stars.glow_intensity = 0.8
        settings.stars.color_intensity = 1.0

        preview = create_renderer(source, settings.clone()).render_frame(
            0.0,
            RenderQuality.PREVIEW,
            star_quality=RenderQuality.EXPORT,
        )
        exported = create_renderer(source, settings.clone()).render_frame(
            0.0,
            RenderQuality.EXPORT,
        )

        np.testing.assert_array_equal(preview, exported)

    def test_magnitude_realism_rebuilds_cached_star_seeds(self) -> None:
        current = ProjectSettings(resolution=ResolutionSettings(96, 64))
        incoming = current.clone()
        incoming.stars.magnitude_realism = 1.0

        self.assertTrue(_needs_renderer_rebuild(current, incoming))

    def test_export_profile_preview_is_visible_when_opened_mid_timeline(self) -> None:
        source = np.zeros((64, 96, 3), dtype=np.uint8)
        settings = ProjectSettings(resolution=ResolutionSettings(96, 64))
        settings.stars.star_count = 80

        preview = create_renderer(source, settings).render_frame(
            0.5,
            RenderQuality.PREVIEW,
            star_quality=RenderQuality.EXPORT,
        )

        self.assertGreater(int(preview.max()), 0)

    def test_playback_preserves_all_stars_and_compensates_their_display_size(self) -> None:
        project = Project()
        project.settings.resolution = ResolutionSettings(2160, 3840)
        project.settings.stars.star_count = 2500
        project.settings.stars.min_size = 2.0
        project.settings.stars.max_size = 12.0
        panel = Mock()
        panel.playback_render_size.return_value = (540, 960)
        panel.preview_render_size.return_value = (2160, 3840)
        controller = PreviewController(Mock())

        static = controller.build_preview_settings(project, panel)
        playback = controller.build_preview_settings(project, panel, playback=True)

        star_scale = 0.25**0.8
        self.assertEqual(static.resolution, ResolutionSettings(2160, 3840))
        self.assertEqual(static.stars.min_size, 2.0)
        self.assertEqual(static.stars.max_size, 12.0)
        self.assertEqual(playback.resolution, ResolutionSettings(540, 960))
        self.assertEqual(playback.stars.star_count, 2500)
        self.assertAlmostEqual(playback.stars.min_size, 2.0 * star_scale)
        self.assertAlmostEqual(playback.stars.max_size, 12.0 * star_scale)

    def test_playback_star_layer_remains_close_to_the_displayed_full_frame(self) -> None:
        project = Project()
        project.settings.resolution = ResolutionSettings(96, 160)
        project.settings.stars.star_count = 120
        project.settings.stars.min_size = 1.0
        project.settings.stars.max_size = 10.0
        project.settings.stars.glow_intensity = 0.3
        project.settings.stars.color_intensity = 0.5
        panel = Mock()
        panel.playback_render_size.return_value = (48, 80)
        playback_settings = PreviewController(Mock()).build_preview_settings(
            project,
            panel,
            playback=True,
        )

        full_layer = StarRenderer(project.settings.stars, 96, 160).render_layer(
            0.0,
            10.0,
            RenderQuality.EXPORT,
            track_visibility=False,
        )
        playback_layer = StarRenderer(playback_settings.stars, 48, 80).render_layer(
            0.0,
            10.0,
            RenderQuality.EXPORT,
            track_visibility=False,
        )
        full_display = cv2.resize(full_layer, (60, 100), interpolation=cv2.INTER_AREA)
        playback_display = cv2.resize(
            playback_layer,
            (60, 100),
            interpolation=cv2.INTER_AREA,
        )

        energy_ratio = float(playback_display.sum() / full_display.sum())
        full_visible = np.count_nonzero(full_display.max(axis=2) > 1.0)
        playback_visible = np.count_nonzero(playback_display.max(axis=2) > 1.0)
        visible_ratio = playback_visible / full_visible
        self.assertGreater(energy_ratio, 0.8)
        self.assertLess(energy_ratio, 1.4)
        self.assertGreater(visible_ratio, 0.8)
        self.assertLess(visible_ratio, 1.2)

    def test_parallax_preview_passes_away_field_rotation(self) -> None:
        background_renderer = Mock()
        background_renderer.settings.resolution.width = 96
        background_renderer.settings.resolution.height = 64
        background_renderer.settings.duration_seconds = 10.0
        background_renderer.settings.background.flight_direction = FlightDirection.TOWARD
        background_renderer.render_frame.return_value = np.zeros((64, 96, 3), dtype=np.uint8)
        background_renderer.view_center_at_progress.return_value = (48.0, 32.0)

        star_renderer = Mock()
        star_renderer.render_layer.return_value = np.zeros((64, 96, 3), dtype=np.float32)

        settings = ProjectSettings(resolution=ResolutionSettings(96, 64))
        settings.duration_seconds = 10.0
        settings.background.flight_direction = FlightDirection.AWAY
        settings.background.rotation_degrees = 20.0

        render_parallax_preview_frame(
            background_renderer,
            settings,
            0.0,
            include_stars=True,
            star_renderer=star_renderer,
        )

        kwargs = star_renderer.render_layer.call_args.kwargs
        self.assertAlmostEqual(
            kwargs["field_rotation_radians"],
            rotation_radians(0.0, 20.0, FlightDirection.AWAY),
        )
        self.assertEqual(kwargs["flight_direction"], FlightDirection.AWAY)
        self.assertFalse(kwargs["track_visibility"])


if __name__ == "__main__":
    unittest.main()
