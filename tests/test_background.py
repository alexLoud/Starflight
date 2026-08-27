"""Regression tests for background scale and rotation animation."""

from __future__ import annotations

import math
import unittest

import numpy as np

from starflight.core.background import BackgroundRenderer, effective_background_settings
from starflight.types.settings import BackgroundSettings, ImageMotionMode


def _make_renderer(
    source_w: int = 4000,
    source_h: int = 3000,
    frame_w: int = 1920,
    frame_h: int = 1080,
) -> BackgroundRenderer:
    source = np.zeros((source_h, source_w, 3), dtype=np.uint8)
    return BackgroundRenderer(source, frame_w, frame_h)


class BackgroundScaleTests(unittest.TestCase):
    def test_image_motion_modes_keep_only_their_active_camera_fields(self) -> None:
        settings = BackgroundSettings(
            motion_mode=ImageMotionMode.PARALLAX,
            scale_percent=125.0,
            zoom_percent=20.0,
            rotation_degrees=15.0,
            start_focus_enabled=True,
            end_focus_enabled=True,
            fill_frame=True,
        )

        parallax = effective_background_settings(settings)
        self.assertEqual(parallax.scale_percent, 100.0)
        self.assertFalse(parallax.fill_frame)
        self.assertEqual(parallax.zoom_percent, 0.0)
        self.assertEqual(parallax.rotation_degrees, 0.0)
        self.assertFalse(parallax.start_focus_enabled)
        self.assertFalse(parallax.end_focus_enabled)

        settings.motion_mode = ImageMotionMode.MANUAL
        settings.fill_frame = False
        manual = effective_background_settings(settings)
        self.assertEqual(manual.scale_percent, 125.0)
        self.assertFalse(manual.fill_frame)
        self.assertEqual(manual.zoom_percent, 20.0)
        self.assertEqual(manual.rotation_degrees, 15.0)

    def test_linear_scale_has_constant_rate(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            scale_percent=120.0,
            zoom_percent=10.0,
            rotation_degrees=18.0,
            end_focus_enabled=True,
            end_focus_x=0.8,
            end_focus_y=0.3,
            fill_frame=True,
        )

        scales = [renderer._linear_scale(progress / 100, settings) for progress in range(101)]
        deltas = [scales[index] - scales[index - 1] for index in range(1, len(scales))]
        expected_delta = deltas[-1]

        for delta in deltas[1:]:
            self.assertAlmostEqual(delta, expected_delta, places=6)

    def test_linear_scale_covers_required_scale_samples(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            scale_percent=150.0,
            rotation_degrees=18.0,
            end_focus_enabled=True,
            end_focus_x=0.85,
            end_focus_y=0.2,
            fill_frame=True,
        )

        for index in range(0, 101, 5):
            progress = index / 100
            angle = math.radians(settings.rotation_degrees * progress)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            center_x, center_y = renderer._desired_source_center(progress, settings)
            required = renderer._required_scale(
                progress, settings, cos_a, sin_a, center_x, center_y
            )
            linear = renderer._linear_scale(progress, settings)
            self.assertGreaterEqual(linear, required - 1e-9)

    def test_rotation_without_fill_frame_does_not_change_scale(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            rotation_degrees=15.0,
            fill_frame=False,
            zoom_percent=0.0,
        )

        start = renderer._linear_scale(0.0, settings)
        end = renderer._linear_scale(1.0, settings)
        cover = max(renderer.width / renderer.source_w, renderer.height / renderer.source_h)

        self.assertAlmostEqual(start, cover)
        self.assertAlmostEqual(end, cover)

    def test_fill_frame_can_increase_scale_for_rotation(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(rotation_degrees=15.0, fill_frame=True, zoom_percent=0.0)

        start = renderer._linear_scale(0.0, settings)
        end = renderer._linear_scale(1.0, settings)

        self.assertGreater(end, start)

    def test_rotation_angle_stays_linear(self) -> None:
        settings = BackgroundSettings(rotation_degrees=18.0)

        for progress in (0.0, 0.25, 0.5, 0.75, 1.0):
            expected = math.radians(settings.rotation_degrees * progress)
            actual = math.radians(settings.rotation_degrees * progress)
            self.assertAlmostEqual(actual, expected, places=9)


if __name__ == "__main__":
    unittest.main()
