"""Tests for coupling background rotation into star-field projection."""

from __future__ import annotations

import math
import unittest

from starflight.core.star_field import StarField
from starflight.types.settings import RenderQuality, StarSettings


def _field(star_count: int = 24, seed: int = 42) -> StarField:
    """Build a small deterministic star field for projection checks."""

    settings = StarSettings(star_count=star_count, seed=seed, speed=0.0)
    return StarField(settings, width=200, height=160)


class StarFieldRotationTests(unittest.TestCase):
    def test_zero_rotation_is_identity(self) -> None:
        field = _field()
        plain = field.project_at_time(0.0, 10.0, quality=RenderQuality.EXPORT)
        rotated = field.project_at_time(
            0.0,
            10.0,
            quality=RenderQuality.EXPORT,
            field_rotation_radians=0.0,
        )
        self.assertEqual(len(plain), len(rotated))
        for left, right in zip(plain, rotated, strict=True):
            self.assertAlmostEqual(left.x, right.x)
            self.assertAlmostEqual(left.y, right.y)
            self.assertAlmostEqual(left.spike_angle, right.spike_angle)

    def test_t0_with_nonzero_theta_still_rotates_offsets(self) -> None:
        """t=0 only implies identity when θ=0; explicit θ still applies."""

        field = _field()
        theta = math.radians(30.0)
        plain = field.project_at_time(
            0.0,
            10.0,
            quality=RenderQuality.EXPORT,
            track_visibility=False,
        )
        rotated = field.project_at_time(
            0.0,
            10.0,
            quality=RenderQuality.EXPORT,
            field_rotation_radians=theta,
            track_visibility=False,
        )
        plain_keys = {(round(p.x, 3), round(p.y, 3)) for p in plain}
        rotated_keys = {(round(p.x, 3), round(p.y, 3)) for p in rotated}
        self.assertNotEqual(plain_keys, rotated_keys)

    def test_positive_rotation_rotates_offsets_and_adds_to_spike_angle(self) -> None:
        field = _field(star_count=8, seed=7)
        # Pin one seed so offset math is exact and independent of culling.
        star = field._stars[0]
        star.offset_x = 0.40
        star.offset_y = 0.0
        star.z = 0.80
        star.spike_roll = 0.25
        theta = math.radians(90.0)

        projections = field.project_at_time(
            0.0,
            10.0,
            quality=RenderQuality.EXPORT,
            field_rotation_radians=theta,
            track_visibility=False,
        )
        self.assertGreaterEqual(len(projections), 1)

        # Re-project the pinned star alone via the private helper for exact R_θ.
        focal = min(field.width, field.height) * field._FOCAL_SCALE
        center_x, center_y = field.width / 2.0, field.height / 2.0
        sx, sy = field._project_screen_position(
            star,
            star.z,
            focal,
            center_x,
            center_y,
            theta,
        )
        cos_t, sin_t = math.cos(theta), math.sin(theta)
        expected_ox = star.offset_x * cos_t - star.offset_y * sin_t
        expected_oy = star.offset_x * sin_t + star.offset_y * cos_t
        expected_x = center_x + (expected_ox / star.z) * focal
        expected_y = center_y + (expected_oy / star.z) * focal
        self.assertAlmostEqual(sx, expected_x)
        self.assertAlmostEqual(sy, expected_y)
        # R_θ at +90°: (0.4, 0) -> (0, 0.4)
        self.assertAlmostEqual(expected_ox, 0.0, places=6)
        self.assertAlmostEqual(expected_oy, 0.40, places=6)

        matching = [
            item
            for item in projections
            if abs(item.x - expected_x) < 1e-4 and abs(item.y - expected_y) < 1e-4
        ]
        self.assertTrue(matching)
        self.assertAlmostEqual(matching[0].spike_angle, star.spike_roll + theta)

    def test_negative_rotation_degrees_sense(self) -> None:
        field = _field(star_count=4, seed=3)
        star = field._stars[0]
        star.offset_x = 0.50
        star.offset_y = 0.0
        star.z = 0.90
        theta = math.radians(-90.0)
        focal = min(field.width, field.height) * field._FOCAL_SCALE
        center_x, center_y = field.width / 2.0, field.height / 2.0
        sx, sy = field._project_screen_position(
            star,
            star.z,
            focal,
            center_x,
            center_y,
            theta,
        )
        # R_{-90°}: (0.5, 0) -> (0, -0.5) so screen y decreases from center.
        self.assertAlmostEqual(sx, center_x, places=5)
        self.assertLess(sy, center_y)

        projections = field.project_at_time(
            0.0,
            10.0,
            quality=RenderQuality.EXPORT,
            field_rotation_radians=theta,
            track_visibility=False,
        )
        for item in projections:
            self.assertTrue(math.isfinite(item.x) and math.isfinite(item.y))
            self.assertTrue(math.isfinite(item.spike_angle))

    def test_rotation_changes_visibility_path_positions(self) -> None:
        field = _field(star_count=40, seed=11)
        plain = field.project_at_time(
            0.0,
            10.0,
            quality=RenderQuality.EXPORT,
            field_rotation_radians=0.0,
            track_visibility=False,
        )
        rotated = field.project_at_time(
            0.0,
            10.0,
            quality=RenderQuality.EXPORT,
            field_rotation_radians=math.radians(35.0),
            track_visibility=False,
        )
        plain_keys = {(round(p.x, 3), round(p.y, 3)) for p in plain}
        rotated_keys = {(round(p.x, 3), round(p.y, 3)) for p in rotated}
        self.assertNotEqual(plain_keys, rotated_keys)

    def test_shared_progress_formula_matches_frame_renderer(self) -> None:
        """FrameRenderer uses θ = radians(rotation_degrees * motion_progress)."""

        rotation_degrees = 40.0
        motion_progress = 0.25
        theta = math.radians(rotation_degrees * motion_progress)
        self.assertAlmostEqual(theta, math.radians(10.0))

        field = _field(star_count=6, seed=5)
        projections = field.project_at_time(
            2.5,
            10.0,
            quality=RenderQuality.EXPORT,
            motion_progress=motion_progress,
            field_rotation_radians=theta,
            track_visibility=False,
        )
        for item, star in zip(
            # spike_angle is always seed.spike_roll + θ even when strength is 0
            projections,
            field._stars,
            strict=False,
        ):
            # Only assert finite + that some spike_angle equals roll+θ among seeds.
            self.assertTrue(math.isfinite(item.spike_angle))
        # At least one projected star carries roll + θ for its matching seed roll.
        rolls = {star.spike_roll + theta for star in field._stars}
        angles = {item.spike_angle for item in projections}
        self.assertTrue(angles & rolls)

    def test_recycle_with_rotation_returns_finite_positions(self) -> None:
        settings = StarSettings(star_count=30, seed=99, speed=2.5)
        field = StarField(settings, width=180, height=120)
        theta = math.radians(55.0)
        # Late in the clip so travel wraps some stars past min_z.
        projections = field.project_at_time(
            9.5,
            10.0,
            quality=RenderQuality.EXPORT,
            motion_progress=0.95,
            field_rotation_radians=theta,
            track_visibility=False,
        )
        self.assertGreater(len(projections), 0)
        for item in projections:
            self.assertTrue(math.isfinite(item.x))
            self.assertTrue(math.isfinite(item.y))
            self.assertTrue(math.isfinite(item.spike_angle))
            self.assertFalse(math.isnan(item.x) or math.isnan(item.y))


if __name__ == "__main__":
    unittest.main()
