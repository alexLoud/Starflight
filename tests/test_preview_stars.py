"""Regression tests for export-accurate stars in the interactive preview."""

from __future__ import annotations

import unittest

import numpy as np

from starflight.core.renderer import create_renderer
from starflight.services.preview_service import _needs_renderer_rebuild
from starflight.types.settings import ProjectSettings, RenderQuality, ResolutionSettings


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


if __name__ == "__main__":
    unittest.main()
