"""Tests for fixed-aspect source-image cropping."""

from __future__ import annotations

import unittest

import numpy as np

from starflight.core.crop import (
    crop_pixel_bounds,
    crop_source_image,
    framing_base_scale,
    map_look_at_to_source,
    remap_look_at_for_crop,
    resolve_crop_rect,
)
from starflight.core.renderer import create_renderer
from starflight.types.settings import (
    CropSettings,
    ImageMotionMode,
    ProjectSettings,
    RenderQuality,
    ResolutionSettings,
)


class CropGeometryTests(unittest.TestCase):
    def test_default_crop_is_centered_and_matches_target_aspect(self) -> None:
        crop = resolve_crop_rect(CropSettings(), 6000, 4000, 1080, 1920)

        self.assertAlmostEqual(crop.x, 0.3125)
        self.assertAlmostEqual(crop.y, 0.0)
        self.assertAlmostEqual(crop.width, 0.375)
        self.assertAlmostEqual(crop.height, 1.0)
        self.assertAlmostEqual((crop.width * 6000) / (crop.height * 4000), 9 / 16)

    def test_crop_center_is_clamped_without_changing_size(self) -> None:
        crop = resolve_crop_rect(
            CropSettings(center_x=0.0, center_y=1.0, scale=0.5),
            6000,
            4000,
            1080,
            1920,
        )

        self.assertAlmostEqual(crop.x, 0.0)
        self.assertAlmostEqual(crop.y + crop.height, 1.0)
        self.assertAlmostEqual(crop.width, 0.1875)
        self.assertAlmostEqual(crop.height, 0.5)

    def test_crop_extracts_original_pixels_without_resampling(self) -> None:
        source = np.arange(80 * 120 * 3, dtype=np.uint16).reshape(80, 120, 3)
        settings = CropSettings(center_x=1 / 6, center_y=0.5, scale=1.0)

        left, top, right, bottom = crop_pixel_bounds(settings, 120, 80, 20, 40)
        cropped = crop_source_image(source, settings, 20, 40)

        self.assertEqual((left, top, right, bottom), (0, 0, 40, 80))
        np.testing.assert_array_equal(cropped, source[:, :40])
        self.assertTrue(cropped.flags.c_contiguous)

    def test_look_at_stays_on_the_same_source_pixel_when_crop_moves(self) -> None:
        old_crop = CropSettings(center_x=0.5, scale=1.0)
        new_crop = CropSettings(center_x=0.4, scale=0.8)
        source = map_look_at_to_source(0.35, 0.6, old_crop, 6000, 4000, 1080, 1920)

        remapped = remap_look_at_for_crop(0.35, 0.6, old_crop, new_crop, 6000, 4000, 1080, 1920)
        restored = map_look_at_to_source(*remapped, new_crop, 6000, 4000, 1080, 1920)

        self.assertAlmostEqual(source[0], restored[0])
        self.assertAlmostEqual(source[1], restored[1])


class CropRenderTests(unittest.TestCase):
    def test_renderer_uses_the_selected_crop_in_preview(self) -> None:
        source = np.zeros((80, 120, 3), dtype=np.uint8)
        source[:, :, 0] = np.arange(120, dtype=np.uint8)[None, :]
        settings = ProjectSettings(resolution=ResolutionSettings(width=20, height=40))
        settings.background.motion_mode = ImageMotionMode.MANUAL

        centered = create_renderer(source, settings).render_frame(
            0.0,
            RenderQuality.PREVIEW,
            include_stars=False,
        )
        settings.crop.center_x = 1 / 6
        left = create_renderer(source, settings).render_frame(
            0.0,
            RenderQuality.PREVIEW,
            include_stars=False,
        )

        self.assertGreater(float(centered[..., 2].mean()), float(left[..., 2].mean()))

    def test_preview_crop_uses_the_exact_export_aspect_ratio(self) -> None:
        source = np.zeros((800, 1200, 3), dtype=np.uint8)
        preview_settings = ProjectSettings(resolution=ResolutionSettings(width=462, height=820))

        renderer = create_renderer(
            source,
            preview_settings,
            crop_target_size=(1080, 1920),
        )

        self.assertEqual(renderer.background.source_image.shape[:2], (800, 1200))
        export_scale = framing_base_scale(
            preview_settings.crop,
            1200,
            800,
            462,
            820,
            1080,
            1920,
        )
        preview_scale = framing_base_scale(
            preview_settings.crop,
            1200,
            800,
            462,
            820,
            462,
            820,
        )
        self.assertAlmostEqual(
            renderer.background._required_scale(
                0.0,
                preview_settings.background,
                1.0,
                0.0,
                *renderer.background._desired_source_center(0.0, preview_settings.background),
            ),
            export_scale,
        )
        self.assertNotAlmostEqual(export_scale, preview_scale)

    def test_enabled_crop_keeps_the_full_source_for_rotation(self) -> None:
        source = np.zeros((80, 120, 3), dtype=np.uint8)
        settings = ProjectSettings(resolution=ResolutionSettings(width=40, height=20))
        settings.background.motion_mode = ImageMotionMode.MANUAL
        settings.background.rotation_degrees = 15.0
        settings.background.fill_frame = False
        settings.crop.scale = 0.5

        renderer = create_renderer(source, settings)
        start = renderer.background._linear_scale(0.0, settings.background)
        end = renderer.background._linear_scale(1.0, settings.background)

        self.assertEqual(renderer.background.source_image.shape[:2], (80, 120))
        self.assertAlmostEqual(start, end)


if __name__ == "__main__":
    unittest.main()
