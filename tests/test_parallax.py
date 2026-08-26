"""Regression tests for structural parallax depth and export rendering."""

from __future__ import annotations

import unittest

import cv2
import numpy as np

from starflight.core.parallax import (
    _progressive_bilateral_filter,
    create_parallax_depth,
    parallax_coordinate_maps,
    parallax_strength_for_level,
    smooth_parallax_depth_for_strength,
)
from starflight.core.renderer import create_renderer
from starflight.types.settings import ProjectSettings, RenderQuality, ResolutionSettings


class ParallaxDepthTests(unittest.TestCase):
    def test_progressive_bilateral_filter_matches_the_original_full_image_filter(self) -> None:
        values = np.random.default_rng(42).random((620, 32), dtype=np.float32)
        sigma_color = 0.10
        sigma_space = 20.0
        progress: list[float] = []

        expected = cv2.bilateralFilter(values, 0, sigma_color, sigma_space)
        actual = _progressive_bilateral_filter(
            values,
            sigma_color,
            sigma_space,
            progress.append,
        )

        np.testing.assert_array_equal(actual, expected)
        self.assertGreater(len(progress), 1)
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[-1], 1.0)

    def test_strength_levels_map_to_five_through_fifty_percent(self) -> None:
        self.assertAlmostEqual(parallax_strength_for_level(1), 0.05)
        self.assertAlmostEqual(parallax_strength_for_level(4), 0.20)
        self.assertAlmostEqual(parallax_strength_for_level(10), 0.50)
        self.assertAlmostEqual(parallax_strength_for_level(0), 0.05)
        self.assertAlmostEqual(parallax_strength_for_level(11), 0.50)

    def test_generated_depth_keeps_the_center_behind_the_exterior(self) -> None:
        height, width = 180, 240
        yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
        radius = ((xx - width / 2.0) / 70.0) ** 2 + ((yy - height / 2.0) / 55.0) ** 2
        intensity = np.clip(np.exp(-radius) * 255.0, 0.0, 255.0).astype(np.uint8)
        source = cv2.merge((intensity // 2, intensity, intensity))

        progress: list[float] = []
        depth = create_parallax_depth(source, (0.5, 0.5), on_progress=progress.append)

        self.assertEqual(depth.shape, (height, width))
        self.assertTrue(np.all(np.isfinite(depth)))
        self.assertGreaterEqual(float(depth.min()), 0.12)
        self.assertLessEqual(float(depth.max()), 1.0)
        self.assertLess(float(depth[height // 2, width // 2]), float(depth[0, 0]))
        self.assertGreater(len(progress), 20)
        self.assertEqual(progress, sorted(progress))
        self.assertEqual(progress[0], 0.0)
        self.assertEqual(progress[-1], 1.0)

    def test_stronger_zoom_broadens_depth_transitions_without_changing_range(self) -> None:
        depth = np.full((120, 160), 0.12, dtype=np.float32)
        depth[:, 80:] = 1.0

        low = smooth_parallax_depth_for_strength(depth, 1)
        high = smooth_parallax_depth_for_strength(depth, 10)

        self.assertEqual(high.shape, depth.shape)
        self.assertEqual(high.dtype, np.float32)
        self.assertGreaterEqual(float(high.min()), float(depth.min()))
        self.assertLessEqual(float(high.max()), float(depth.max()))
        high_gradient = float(np.max(np.abs(np.diff(high, axis=1))))
        low_gradient = float(np.max(np.abs(np.diff(low, axis=1))))
        self.assertLess(high_gradient, low_gradient)

    def test_maximum_strength_keeps_transition_warp_from_folding_or_stretching(self) -> None:
        height, width = 120, 160
        depth = np.full((height, width), 0.12, dtype=np.float32)
        depth[:, width // 2 :] = 1.0
        depth = smooth_parallax_depth_for_strength(depth, 10)
        base_y, base_x = np.mgrid[0:height, 0:width].astype(np.float32)

        map_x, map_y = parallax_coordinate_maps(
            depth,
            base_x,
            base_y,
            (width, height),
            (width / 2.0, height / 2.0),
            1.0,
            parallax_strength_for_level(10),
        )

        dx_x = cv2.Sobel(map_x, cv2.CV_32F, 1, 0, ksize=3) / 8.0
        dx_y = cv2.Sobel(map_x, cv2.CV_32F, 0, 1, ksize=3) / 8.0
        dy_x = cv2.Sobel(map_y, cv2.CV_32F, 1, 0, ksize=3) / 8.0
        dy_y = cv2.Sobel(map_y, cv2.CV_32F, 0, 1, ksize=3) / 8.0
        determinant = dx_x * dy_y - dx_y * dy_x
        squared_sum = dx_x**2 + dx_y**2 + dy_x**2 + dy_y**2
        discriminant = np.sqrt(np.maximum(squared_sum**2 - 4.0 * determinant**2, 0.0))
        singular_max = np.sqrt(np.maximum((squared_sum + discriminant) / 2.0, 0.0))
        singular_min = np.abs(determinant) / np.maximum(singular_max, 1e-6)
        anisotropy = singular_max / np.maximum(singular_min, 1e-6)
        interior = np.s_[2:-2, 2:-2]

        self.assertGreater(float(determinant[interior].min()), 0.0)
        self.assertLess(float(anisotropy[interior].max()), 1.8)

    def test_continuous_warp_composes_with_any_existing_affine_map(self) -> None:
        depth = np.ones((20, 30), dtype=np.float32)
        yy, xx = np.mgrid[0:12, 0:16].astype(np.float32)
        base_x = 8.0 + 0.83 * xx + 0.21 * yy
        base_y = 6.0 - 0.17 * xx + 0.91 * yy
        center = (15.0, 10.0)
        progress = 0.75
        strength = 0.06

        map_x, map_y = parallax_coordinate_maps(
            depth,
            base_x,
            base_y,
            (30, 20),
            center,
            progress,
            strength,
        )

        factor = 1.0 + strength * progress
        expected_x = center[0] + (base_x - center[0]) / factor
        expected_y = center[1] + (base_y - center[1]) / factor
        np.testing.assert_allclose(map_x, expected_x, atol=1e-6)
        np.testing.assert_allclose(map_y, expected_y, atol=1e-6)

    def test_parallax_zoom_is_monotonic_without_oscillation(self) -> None:
        depth = np.ones((10, 10), dtype=np.float32)
        base_x = np.array([[2.0, 8.0]], dtype=np.float32)
        base_y = np.array([[5.0, 5.0]], dtype=np.float32)
        center = (5.0, 5.0)

        distances = []
        for progress in (0.0, 0.25, 0.5, 0.75, 1.0):
            map_x, map_y = parallax_coordinate_maps(
                depth,
                base_x,
                base_y,
                (10, 10),
                center,
                progress,
            )
            distances.append(float(np.hypot(map_x[0, 0] - center[0], map_y[0, 0] - center[1])))

        self.assertEqual(distances, sorted(distances, reverse=True))


class ParallaxRenderModeTests(unittest.TestCase):
    def test_parallax_is_applied_only_to_export_frames(self) -> None:
        height, width = 90, 120
        yy, xx = np.mgrid[0:height, 0:width]
        source = np.stack(
            (
                (xx * 3) % 256,
                (yy * 5) % 256,
                ((xx + yy) * 7) % 256,
            ),
            axis=2,
        ).astype(np.uint8)
        settings = ProjectSettings(
            resolution=ResolutionSettings(width=80, height=60),
            duration_seconds=1.0,
        )
        settings.background.zoom_percent = 8.0
        settings.background.rotation_degrees = 12.0
        settings.background.end_focus_enabled = True
        settings.background.end_focus_x = 0.6
        settings.background.end_focus_y = 0.4
        settings.parallax.enabled = True
        settings.parallax.strength = 10
        depth = np.ones((height, width), dtype=np.float32)
        renderer = create_renderer(source, settings, parallax_depth=depth)
        ordinary = create_renderer(source, settings)

        preview = renderer.render_frame(1.0, RenderQuality.PREVIEW, include_stars=False)
        ordinary_preview = ordinary.render_frame(1.0, RenderQuality.PREVIEW, include_stars=False)
        exported = renderer.render_frame(1.0, RenderQuality.EXPORT, include_stars=False)

        np.testing.assert_array_equal(preview, ordinary_preview)
        self.assertFalse(np.array_equal(exported, ordinary_preview))

        settings.parallax.enabled = False
        disabled_export = renderer.render_frame(1.0, RenderQuality.EXPORT, include_stars=False)
        ordinary_export = ordinary.render_frame(1.0, RenderQuality.EXPORT, include_stars=False)
        np.testing.assert_array_equal(disabled_export, ordinary_export)


if __name__ == "__main__":
    unittest.main()
