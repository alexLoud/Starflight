"""Tests for the away-flight star simulation (inverse of the toward flight)."""

from __future__ import annotations

import math
import unittest

import numpy as np

from starflight.core.camera_motion import motion_amount
from starflight.core.star_field import StarField
from starflight.types.settings import FlightDirection, RenderQuality, StarSettings

_WIDTH = 320
_HEIGHT = 180


def _field(
    star_count: int = 200,
    seed: int = 42,
    speed: float = 1.0,
    width: int = _WIDTH,
    height: int = _HEIGHT,
) -> StarField:
    """Build a deterministic star field for away-flight checks."""

    settings = StarSettings(star_count=star_count, seed=seed, speed=speed)
    return StarField(settings, width=width, height=height)


def _keys(projections: list) -> list[tuple[float, float, float]]:
    """Return sortable (x, y, radius) tuples for projection comparison."""

    return sorted((round(p.x, 6), round(p.y, 6), round(p.radius, 6)) for p in projections)


def _projection_context(field: StarField) -> tuple[float, float, float, float]:
    """Return focal, center_x, center_y and base_margin as used by project_at_time."""

    focal = min(field.width, field.height) * field._FOCAL_SCALE
    return focal, field.width / 2.0, field.height / 2.0, field.settings.max_size * 6.0


def _resolve_away(
    field: StarField,
    index: int,
    time_seconds: float,
    center: tuple[float, float] | None = None,
    rotation: float = 0.0,
) -> float | None:
    """Resolve the render depth for one star through the away branch at an absolute time."""

    focal, center_x, center_y, base_margin = _projection_context(field)
    if center is not None:
        center_x, center_y = center
    travel = field._max_travel(field.settings, 10.0) * motion_amount(
        time_seconds / 10.0, FlightDirection.AWAY
    )
    max_travel = field._max_travel(field.settings, 10.0)
    return field._resolve_render_depth(
        field._stars[index],
        travel,
        focal,
        center_x,
        center_y,
        base_margin,
        field.settings,
        max_travel,
        10.0,
        rotation,
    )


def _on_screen(field: StarField, projections: list) -> list[tuple[float, float]]:
    """Return projected positions that lie inside the frame."""

    return [
        (item.x, item.y)
        for item in projections
        if 0.0 <= item.x < field.width and 0.0 <= item.y < field.height
    ]


def _coverage(
    field: StarField,
    points: list[tuple[float, float]],
    center: tuple[float, float],
) -> dict[str, int]:
    """Count stars in the four 10% edge strips, the inner 20% box, and around the hub."""

    width = float(field.width)
    height = float(field.height)
    inner_x = (width * 0.4, width * 0.6)
    inner_y = (height * 0.4, height * 0.6)
    hub_radius = min(width, height) * 0.10
    counts = {"top": 0, "bottom": 0, "left": 0, "right": 0, "inner": 0, "hub": 0}
    for x, y in points:
        if y < height * 0.10:
            counts["top"] += 1
        if y >= height * 0.90:
            counts["bottom"] += 1
        if x < width * 0.10:
            counts["left"] += 1
        if x >= width * 0.90:
            counts["right"] += 1
        if inner_x[0] <= x < inner_x[1] and inner_y[0] <= y < inner_y[1]:
            counts["inner"] += 1
        if math.hypot(x - center[0], y - center[1]) < hub_radius:
            counts["hub"] += 1
    return counts


def _radial_histogram(
    points: list[tuple[float, float]],
    center: tuple[float, float],
    bins: int = 5,
) -> list[int]:
    """Bin on-screen stars by distance to the vanishing point (equal-width bins)."""

    distances = [math.hypot(x - center[0], y - center[1]) for x, y in points]
    limit = max(distances) if distances else 1.0
    histogram = [0] * bins
    for distance in distances:
        histogram[min(bins - 1, int(distance / limit * bins))] += 1
    return histogram


class StarFieldAwayTests(unittest.TestCase):
    def test_default_direction_is_toward(self) -> None:
        field = _field(speed=1.5)
        implicit = field.project_at_time(4.0, 10.0, quality=RenderQuality.PREVIEW)
        explicit = field.project_at_time(
            4.0,
            10.0,
            quality=RenderQuality.PREVIEW,
            flight_direction=FlightDirection.TOWARD,
        )
        self.assertEqual(_keys(implicit), _keys(explicit))

    def test_away_last_frame_matches_toward_first(self) -> None:
        field = _field(speed=1.5)
        toward_start = field.project_at_time(0.0, 10.0, quality=RenderQuality.PREVIEW)
        away_end = field.project_at_time(
            10.0,
            10.0,
            quality=RenderQuality.PREVIEW,
            flight_direction=FlightDirection.AWAY,
        )
        self.assertEqual(_keys(toward_start), _keys(away_end))

    def test_away_depth_increases_and_radius_shrinks_for_pinned_star(self) -> None:
        field = _field(star_count=4, seed=7, speed=1.0)
        star = field._stars[0]
        star.offset_x = 0.08
        star.offset_y = 0.05
        star.z = 0.95
        star.size = 2.0

        z_first = _resolve_away(field, 0, 0.0)
        z_later = _resolve_away(field, 0, 8.0)
        self.assertIsNotNone(z_first)
        self.assertIsNotNone(z_later)
        self.assertGreater(z_later, z_first)
        self.assertLessEqual(z_later, field._MAX_Z)

        settings = field.settings
        radius_first = field._estimate_radius(star, field._depth_gain(z_first), settings)
        radius_later = field._estimate_radius(star, field._depth_gain(z_later), settings)
        self.assertLess(radius_later, radius_first)

    def test_away_depth_wraps_into_the_band_like_toward(self) -> None:
        field = _field(star_count=300, seed=11, speed=2.0)
        duration = 10.0
        time_away = 1.0
        max_travel = field._max_travel(field.settings, duration)
        travel = max_travel * motion_amount(time_away / duration, FlightDirection.AWAY)
        wrapped = 0
        focal, center_x, center_y, base_margin = _projection_context(field)
        for index, star in enumerate(field._stars):
            away_z = _resolve_away(field, index, time_away)
            toward_z = field._resolve_render_depth(
                star,
                travel,
                focal,
                center_x,
                center_y,
                base_margin,
                field.settings,
                max_travel,
                duration,
            )
            self.assertEqual(away_z, toward_z)
            if away_z is None:
                continue
            if star.z - travel < field._MIN_Z:
                wrapped += 1
        self.assertGreater(wrapped, 0)

    def test_away_matches_toward_at_complementary_time(self) -> None:
        field = _field(star_count=300, seed=11, speed=1.0)
        duration = 10.0
        for time_seconds in (0.0, 2.5, 5.0, 7.5, 10.0):
            away = field.project_at_time(
                time_seconds,
                duration,
                quality=RenderQuality.PREVIEW,
                flight_direction=FlightDirection.AWAY,
            )
            toward = field.project_at_time(
                duration - time_seconds,
                duration,
                quality=RenderQuality.PREVIEW,
                flight_direction=FlightDirection.TOWARD,
            )
            self.assertEqual(_keys(away), _keys(toward), f"t={time_seconds}")

    def test_seeds_are_never_mutated(self) -> None:
        field = _field(star_count=300, seed=11, speed=2.0)
        before = [(s.offset_x, s.offset_y, s.z, s.size) for s in field._stars]
        for progress in (0.3, 0.6, 1.0):
            field.project_at_time(
                progress * 10.0,
                10.0,
                quality=RenderQuality.PREVIEW,
                motion_progress=progress,
                flight_direction=FlightDirection.AWAY,
            )
        self.assertEqual(before, [(s.offset_x, s.offset_y, s.z, s.size) for s in field._stars])

    def test_unwrapped_stars_move_inward_between_frames(self) -> None:
        field = _field(star_count=300, seed=11, speed=2.0)
        focal, center_x, center_y, _ = _projection_context(field)
        duration = 10.0
        max_travel = field._max_travel(field.settings, duration)
        checked = 0
        for frame in range(0, 300):
            t0 = frame / 30.0
            t1 = (frame + 1) / 30.0
            travel0 = max_travel * motion_amount(t0 / duration, FlightDirection.AWAY)
            travel1 = max_travel * motion_amount(t1 / duration, FlightDirection.AWAY)
            for index, star in enumerate(field._stars):
                if star.z - travel0 < field._MIN_Z or star.z - travel1 < field._MIN_Z:
                    continue
                z0 = _resolve_away(field, index, t0)
                z1 = _resolve_away(field, index, t1)
                if z0 is None or z1 is None:
                    continue
                x0, y0 = field._project_screen_position(star, z0, focal, center_x, center_y)
                x1, y1 = field._project_screen_position(star, z1, focal, center_x, center_y)
                d0 = math.hypot(x0 - center_x, y0 - center_y)
                d1 = math.hypot(x1 - center_x, y1 - center_y)
                self.assertLessEqual(
                    d1,
                    d0 + 1e-9,
                    f"star {index} moved outward at t={t1:.2f}",
                )
                checked += 1
        self.assertGreater(checked, 0)

    def test_seek_matches_sequential_playback(self) -> None:
        duration = 10.0
        seeked = _field(speed=2.0)
        sequential = _field(speed=2.0)
        target = seeked.project_at_time(
            5.0,
            duration,
            quality=RenderQuality.PREVIEW,
            flight_direction=FlightDirection.AWAY,
        )
        frames = int(5.0 * 30)
        stepped = None
        for frame in range(frames + 1):
            stepped = sequential.project_at_time(
                frame / 30.0,
                duration,
                quality=RenderQuality.PREVIEW,
                flight_direction=FlightDirection.AWAY,
            )
        self.assertIsNotNone(stepped)
        self.assertGreater(len(target), 0)
        self.assertEqual(_keys(target), _keys(stepped))

    def _assert_full_frame(
        self,
        field: StarField,
        projections: list,
        center: tuple[float, float],
        label: str,
    ) -> None:
        """Assert edges, inner box, hub and every radial bin around the look-at are populated."""

        points = _on_screen(field, projections)
        self.assertGreater(len(points), 100, label)
        counts = _coverage(field, points, center)
        empty = [name for name, count in counts.items() if count == 0]
        self.assertEqual(empty, [], f"{label}: empty regions {counts}")
        histogram = _radial_histogram(points, center)
        self.assertTrue(all(count > 0 for count in histogram), f"{label}: ring {histogram}")
        self.assertLess(max(histogram), 0.6 * len(points), f"{label}: ring {histogram}")

    def test_full_frame_coverage_late_in_clip_with_off_center_look_at(self) -> None:
        # user's sidebar: portrait, 10 s, rotation 0, look-at on the nebula (eagle.sf)
        field = _field(star_count=1500, seed=42, speed=1.0, width=270, height=480)
        center = (field.width * 0.39, field.height * 0.45)

        for progress in (0.5, 0.8, 0.95, 1.0):
            projections = field.project_at_time(
                progress * 10.0,
                10.0,
                lambda _p, c=center: c,
                quality=RenderQuality.PREVIEW,
                motion_progress=progress,
                flight_direction=FlightDirection.AWAY,
            )
            self._assert_full_frame(field, projections, center, f"progress={progress}")

    def test_full_frame_coverage_with_rotation_and_long_clip(self) -> None:
        # eagle.sf: 20 s, rotation unwinding from 20.8° to 0, look-at on the nebula
        field = _field(star_count=1500, seed=42, speed=1.0, width=270, height=480)
        center = (field.width * 0.39, field.height * 0.45)

        for progress in (0.25, 0.5, 0.75, 1.0):
            rotation = math.radians(20.8 * (1.0 - progress))
            projections = field.project_at_time(
                progress * 20.0,
                20.0,
                lambda _p, c=center: c,
                quality=RenderQuality.PREVIEW,
                motion_progress=progress,
                field_rotation_radians=rotation,
                flight_direction=FlightDirection.AWAY,
            )
            self._assert_full_frame(field, projections, center, f"progress={progress}")

    def test_hub_stays_populated_after_every_star_has_wrapped(self) -> None:
        # fast, long clip: travel exceeds the depth band several times over
        field = _field(star_count=1500, seed=42, speed=2.0, width=270, height=480)
        center = (field.width * 0.39, field.height * 0.45)
        for progress in (0.6, 0.8, 1.0):
            projections = field.project_at_time(
                progress * 30.0,
                30.0,
                lambda _p, c=center: c,
                quality=RenderQuality.PREVIEW,
                motion_progress=progress,
                flight_direction=FlightDirection.AWAY,
            )
            self._assert_full_frame(field, projections, center, f"progress={progress}")

    def test_full_frame_coverage_with_corner_look_at_and_fast_flight(self) -> None:
        field = _field(star_count=2500, seed=77, speed=2.0, width=270, height=480)
        center = (field.width * 0.2, field.height * 0.8)
        projections = field.project_at_time(
            9.5,
            10.0,
            lambda _p, c=center: c,
            quality=RenderQuality.PREVIEW,
            motion_progress=0.95,
            field_rotation_radians=math.radians(30.0),
            flight_direction=FlightDirection.AWAY,
        )
        for item in projections:
            self.assertTrue(math.isfinite(item.x) and math.isfinite(item.y))
        self._assert_full_frame(field, projections, center, "corner look-at")

    def test_offset_box_is_the_original_half_frame_at_max_depth(self) -> None:
        field = _field(star_count=50, seed=1, width=270, height=480)
        focal = min(field.width, field.height) * field._FOCAL_SCALE
        max_offset_x, max_offset_y = field._offset_limits()
        # at max_z the seed box projects to exactly half the frame around the vanishing point
        self.assertAlmostEqual(max_offset_x / field._MAX_Z * focal, field.width / 2.0)
        self.assertAlmostEqual(max_offset_y / field._MAX_Z * focal, field.height / 2.0)

    def test_on_screen_star_count_stays_stable_over_the_clip(self) -> None:
        field = _field(star_count=2000, seed=3, speed=1.0, width=270, height=480)
        counts = []
        for progress in np.linspace(0.0, 1.0, 11):
            projections = field.project_at_time(
                float(progress) * 10.0,
                10.0,
                quality=RenderQuality.PREVIEW,
                motion_progress=float(progress),
                flight_direction=FlightDirection.AWAY,
            )
            counts.append(len(_on_screen(field, projections)))
        # the wrapped pool is stationary: no draining of the field toward the end
        self.assertGreater(min(counts), 0.6 * counts[0], f"counts={counts}")

    def test_direction_switch_resets_export_fade_state(self) -> None:
        field = _field(star_count=100, seed=3, speed=2.0)
        field.project_at_time(0.0, 10.0, quality=RenderQuality.EXPORT)
        field.project_at_time(3.0, 10.0, quality=RenderQuality.EXPORT)
        self.assertTrue(field._continuous_from_start or field._fade_start_by_index)
        field.project_at_time(
            3.0,
            10.0,
            quality=RenderQuality.EXPORT,
            flight_direction=FlightDirection.AWAY,
        )
        # the away call rebuilt state from scratch: nothing may claim continuity from t=0
        # and every fade start must be this frame's time
        self.assertFalse(field._continuous_from_start)
        self.assertTrue(all(start == 3.0 for start in field._fade_start_by_index.values()))


if __name__ == "__main__":
    unittest.main()
