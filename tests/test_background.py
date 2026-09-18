"""Regression tests for background scale and rotation animation."""

from __future__ import annotations

import math
import unittest

import numpy as np

from starflight.core.background import BackgroundRenderer
from starflight.types.settings import BackgroundSettings, FlightDirection


def _matrix_angle(matrix: np.ndarray) -> float:
    """return the rotation encoded in an inverse affine matrix."""

    return math.atan2(float(matrix[0, 1]), float(matrix[0, 0]))


def _make_renderer(
    source_w: int = 4000,
    source_h: int = 3000,
    frame_w: int = 1920,
    frame_h: int = 1080,
) -> BackgroundRenderer:
    source = np.zeros((source_h, source_w, 3), dtype=np.uint8)
    return BackgroundRenderer(source, frame_w, frame_h)


class BackgroundScaleTests(unittest.TestCase):
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

    def test_toward_rotation_starts_at_zero_and_ends_at_hub(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            rotation_degrees=20.0,
            fill_frame=False,
            flight_direction=FlightDirection.TOWARD,
        )
        start = renderer._build_transform_matrix(0.0, settings)
        end = renderer._build_transform_matrix(1.0, settings)

        self.assertAlmostEqual(_matrix_angle(start), 0.0, places=6)
        self.assertAlmostEqual(_matrix_angle(end), math.radians(20.0), places=6)

    def test_away_rotation_starts_at_hub_and_ends_at_zero(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            rotation_degrees=20.0,
            fill_frame=False,
            flight_direction=FlightDirection.AWAY,
        )
        start = renderer._build_transform_matrix(0.0, settings)
        end = renderer._build_transform_matrix(1.0, settings)

        self.assertAlmostEqual(_matrix_angle(start), math.radians(20.0), places=6)
        self.assertAlmostEqual(_matrix_angle(end), 0.0, places=6)

    def test_away_fill_frame_covers_rotation_at_the_start(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            rotation_degrees=15.0,
            fill_frame=True,
            zoom_percent=0.0,
            flight_direction=FlightDirection.AWAY,
        )
        start = renderer._linear_scale(0.0, settings)
        end = renderer._linear_scale(1.0, settings)

        self.assertGreater(start, end)
        self.assertFalse(renderer.has_empty_edges(10.0, 30, settings, 1.0))

    def test_empty_edge_detection_checks_every_exported_frame(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(rotation_degrees=15.0, fill_frame=False)

        self.assertTrue(renderer.has_empty_edges(10.0, 30, settings, 1.0))

    def test_empty_edge_detection_stays_hidden_when_fill_frame_covers_rotation(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(rotation_degrees=15.0, fill_frame=True)

        self.assertFalse(renderer.has_empty_edges(10.0, 30, settings, 1.0))

    def test_empty_edge_detection_ignores_landscape_crop_floating_point_bounds(self) -> None:
        renderer = _make_renderer(source_w=1800, source_h=1200, frame_w=1920, frame_h=1080)
        settings = BackgroundSettings()

        self.assertFalse(renderer.has_empty_edges(10.0, 30, settings, 1.0))

    def test_toward_zoom_scales_from_one_to_hub(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            zoom_percent=20.0,
            rotation_degrees=0.0,
            fill_frame=False,
            flight_direction=FlightDirection.TOWARD,
        )
        start = renderer._linear_scale(0.0, settings)
        end = renderer._linear_scale(1.0, settings)
        center_start_x, center_start_y = renderer._desired_source_center(0.0, settings)
        center_end_x, center_end_y = renderer._desired_source_center(1.0, settings)
        required_start = renderer._required_scale(
            0.0, settings, 1.0, 0.0, center_start_x, center_start_y
        )
        required_end = renderer._required_scale(1.0, settings, 1.0, 0.0, center_end_x, center_end_y)

        self.assertAlmostEqual(end / start, 1.2)
        self.assertAlmostEqual(required_end / required_start, 1.2)
        self.assertAlmostEqual(start, required_start)
        self.assertAlmostEqual(end, required_end)

    def test_away_zoom_scales_from_hub_to_one(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            zoom_percent=40.0,
            rotation_degrees=0.0,
            fill_frame=False,
            flight_direction=FlightDirection.AWAY,
        )
        start = renderer._linear_scale(0.0, settings)
        end = renderer._linear_scale(1.0, settings)
        center_start_x, center_start_y = renderer._desired_source_center(0.0, settings)
        center_end_x, center_end_y = renderer._desired_source_center(1.0, settings)
        required_start = renderer._required_scale(
            0.0, settings, 1.0, 0.0, center_start_x, center_start_y
        )
        required_end = renderer._required_scale(1.0, settings, 1.0, 0.0, center_end_x, center_end_y)

        self.assertAlmostEqual(required_end / required_start, 1.0 / 1.4)
        self.assertAlmostEqual(end / start, 1.0 / 1.4)
        self.assertAlmostEqual(start, required_start)
        self.assertAlmostEqual(end, required_end)

    def test_away_envelope_slope_can_be_negative(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            zoom_percent=40.0,
            rotation_degrees=0.0,
            fill_frame=False,
            flight_direction=FlightDirection.AWAY,
        )
        _start, slope = renderer._compute_scale_envelope(settings)
        self.assertLess(slope, 0.0)

    def test_toward_envelope_slope_is_not_negative(self) -> None:
        renderer = _make_renderer()
        settings = BackgroundSettings(
            zoom_percent=0.0,
            rotation_degrees=0.0,
            fill_frame=True,
            start_focus_enabled=True,
            start_focus_x=0.1,
            start_focus_y=0.1,
            end_focus_enabled=True,
            end_focus_x=0.5,
            end_focus_y=0.5,
            flight_direction=FlightDirection.TOWARD,
        )
        start = renderer._linear_scale(0.0, settings)
        end = renderer._linear_scale(1.0, settings)
        _envelope_start, slope = renderer._compute_scale_envelope(settings)
        self.assertGreaterEqual(slope, 0.0)
        self.assertGreaterEqual(end, start)


if __name__ == "__main__":
    unittest.main()
