"""Integration checks for away-flight zoom, parallax, and star motion on eagle.jpg."""

from __future__ import annotations

import math
import os
import unittest
from itertools import pairwise
from pathlib import Path

import cv2
import numpy as np

from starflight.core.camera_motion import camera_motion_progress
from starflight.core.parallax import prepare_parallax_depth_v4
from starflight.core.renderer import create_renderer
from starflight.core.star_field import StarField
from starflight.types.settings import (
    FlightDirection,
    ImageMotionMode,
    ParallaxStrength,
    ProjectSettings,
    RenderQuality,
    ResolutionSettings,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_EAGLE_PATH = _REPO_ROOT / "eagle.jpg"
_WIDTH = 270
_HEIGHT = 480
_DURATION = 10.0
_FPS = 30
_FRAME_STEP = 10
_STAR_COUNT = 800
_STAR_SPEED = 1.5
_STAR_SEED = 42
_ZOOM_PERCENT = 40.0


def _eagle_source() -> np.ndarray | None:
    """load and downscale eagle.jpg for geometric checks."""

    if not _EAGLE_PATH.is_file():
        return None
    image = cv2.imread(str(_EAGLE_PATH), cv2.IMREAD_COLOR)
    if image is None:
        return None
    height, width = image.shape[:2]
    max_edge = 960
    longest = max(height, width)
    if longest > max_edge:
        scale = max_edge / longest
        image = cv2.resize(
            image,
            (max(1, round(width * scale)), max(1, round(height * scale))),
            interpolation=cv2.INTER_AREA,
        )
    return image


def _base_settings(*, away: bool, parallax: bool, stars: bool) -> ProjectSettings:
    """build shared project settings for the eagle verification."""

    settings = ProjectSettings(
        resolution=ResolutionSettings(width=_WIDTH, height=_HEIGHT),
        duration_seconds=_DURATION,
        fps=_FPS,
    )
    settings.background.flight_direction = FlightDirection.AWAY if away else FlightDirection.TOWARD
    settings.background.zoom_percent = _ZOOM_PERCENT
    settings.background.rotation_degrees = 0.0
    settings.background.fill_frame = False
    settings.background.motion_mode = (
        ImageMotionMode.PARALLAX if parallax else ImageMotionMode.MANUAL
    )
    settings.parallax.strength = ParallaxStrength.VERY_STRONG
    settings.stars.star_count = _STAR_COUNT if stars else 50
    settings.stars.seed = _STAR_SEED
    settings.stars.speed = _STAR_SPEED
    return settings


def _radial_depth(height: int, width: int) -> np.ndarray:
    """build a center-near radial depth map and prepare it like export."""

    sample_y, sample_x = np.mgrid[0:height, 0:width]
    radius = np.hypot(sample_x - (width - 1) / 2.0, sample_y - (height - 1) / 2.0)
    peak = float(radius.max()) or 1.0
    depth = (1.0 - radius / peak).astype(np.float32)
    return prepare_parallax_depth_v4(depth)


def _sampled_frames() -> list[int]:
    """return start frame, every tenth frame, and the last frame."""

    last = round(_DURATION * _FPS)
    frames = list(range(0, last, _FRAME_STEP))
    if frames[-1] != last:
        frames.append(last)
    return frames


def _star_field() -> StarField:
    """build the away-flight star field used by the frame walk."""

    settings = _base_settings(away=True, parallax=False, stars=True).stars
    return StarField(settings, _WIDTH, _HEIGHT)


def _project_away(field: StarField, time_seconds: float) -> list:
    """project away-flight stars at an eased clock matching FrameRenderer."""

    motion_progress = camera_motion_progress(
        time_seconds,
        _DURATION,
        _base_settings(away=True, parallax=False, stars=True).background,
        _STAR_SPEED,
    )
    return field.project_at_time(
        time_seconds,
        _DURATION,
        quality=RenderQuality.PREVIEW,
        motion_progress=motion_progress,
        flight_direction=FlightDirection.AWAY,
    )


def _resolve_away(field: StarField, index: int, time_seconds: float):
    """resolve one away star at the renderer travel clock."""

    motion_progress = camera_motion_progress(
        time_seconds,
        _DURATION,
        _base_settings(away=True, parallax=False, stars=True).background,
        _STAR_SPEED,
    )
    travel = field._max_travel(field.settings, _DURATION) * (1.0 - motion_progress)
    focal = min(field.width, field.height) * field._FOCAL_SCALE
    center_x = field.width / 2.0
    center_y = field.height / 2.0
    return field._resolve_render_depth(
        field._stars[index],
        travel,
        focal,
        center_x,
        center_y,
        field.settings.max_size * 6.0,
        field.settings,
        field._max_travel(field.settings, _DURATION),
        _DURATION,
    )


def _projection_keys(items: list) -> list[tuple[float, float, float]]:
    """return sortable rounded projection tuples for seek comparison."""

    return sorted((round(item.x, 5), round(item.y, 5), round(item.radius, 5)) for item in items)


def _screen_state(field: StarField, index: int, depth: float) -> tuple[float, float, float, float]:
    """return distance-to-center, radius, x, y for a resolved away star."""

    seed = field._stars[index]
    focal = min(field.width, field.height) * field._FOCAL_SCALE
    center_x = field.width / 2.0
    center_y = field.height / 2.0
    screen_x, screen_y = field._project_screen_position(
        seed,
        depth,
        focal,
        center_x,
        center_y,
    )
    radius = field._estimate_radius(seed, field._depth_gain(depth), field.settings)
    distance = math.hypot(screen_x - center_x, screen_y - center_y)
    return distance, radius, screen_x, screen_y


def _feature_patch(frame_rgb: np.ndarray, size: int = 48) -> tuple[np.ndarray, int, int]:
    """pick the highest-variance interior patch for template matching."""

    gray = cv2.cvtColor(frame_rgb, cv2.COLOR_RGB2GRAY)
    height, width = gray.shape
    best_score = -1.0
    best_x = width // 2 - size // 2
    best_y = height // 2 - size // 2
    step = max(8, size // 2)
    for top in range(size, height - 2 * size, step):
        for left in range(size, width - 2 * size, step):
            patch = gray[top : top + size, left : left + size]
            score = float(patch.var())
            if score > best_score:
                best_score = score
                best_x = left
                best_y = top
    return gray[best_y : best_y + size, best_x : best_x + size], best_x, best_y


def _match_scale(template: np.ndarray, image: np.ndarray) -> float:
    """return the scale at which the start patch best matches a later frame."""

    best_score = -1.0
    best_scale = 1.0
    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY) if image.ndim == 3 else image
    for scale in np.linspace(0.45, 1.15, 36):
        width = max(8, round(float(template.shape[1] * scale)))
        height = max(8, round(float(template.shape[0] * scale)))
        if height >= gray.shape[0] or width >= gray.shape[1]:
            continue
        resized = cv2.resize(template, (width, height), interpolation=cv2.INTER_AREA)
        scores = cv2.matchTemplate(gray, resized, cv2.TM_CCOEFF_NORMED)
        score = float(scores.max())
        if score > best_score:
            best_score = score
            best_scale = float(scale)
    return best_scale


@unittest.skipUnless(_EAGLE_PATH.is_file(), "eagle.jpg is not in the project root")
class AwayFlightEagleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = _eagle_source()
        assert source is not None
        cls.source = source

    def test_away_zoom_makes_the_eagle_smaller(self) -> None:
        settings = _base_settings(away=True, parallax=False, stars=False)
        renderer = create_renderer(self.source, settings)
        background = renderer.background
        scales = [
            background._linear_scale(frame / (_DURATION * _FPS), settings.background)
            for frame in _sampled_frames()
        ]
        for previous, current in pairwise(scales):
            self.assertLess(current, previous)

        start_scale = scales[0]
        end_scale = scales[-1]
        self.assertAlmostEqual(end_scale / start_scale, 1.0 / 1.4, places=5)

        start = renderer.render_frame(0.0, RenderQuality.PREVIEW, include_stars=False)
        end = renderer.render_frame(_DURATION, RenderQuality.PREVIEW, include_stars=False)
        template, _, _ = _feature_patch(start)
        self.assertGreater(float(template.var()), 40.0)
        apparent = _match_scale(template, end)
        self.assertLess(
            apparent,
            0.92,
            f"eagle did not shrink; match scale={apparent:.3f}",
        )

        toward = _base_settings(away=False, parallax=False, stars=False)
        toward_renderer = create_renderer(self.source, toward)
        toward_start = toward_renderer.background._linear_scale(0.0, toward.background)
        toward_end = toward_renderer.background._linear_scale(1.0, toward.background)
        self.assertAlmostEqual(toward_end / toward_start, 1.4)

    def test_away_parallax_starts_warped_and_ends_as_identity(self) -> None:
        depth = _radial_depth(*self.source.shape[:2])
        away = _base_settings(away=True, parallax=True, stars=False)
        toward = _base_settings(away=False, parallax=True, stars=False)
        away_renderer = create_renderer(self.source, away, parallax_depth=depth)
        toward_renderer = create_renderer(self.source, toward, parallax_depth=depth)
        plain_away = create_renderer(
            self.source,
            _base_settings(away=True, parallax=False, stars=False),
        )
        plain_toward = create_renderer(
            self.source,
            _base_settings(away=False, parallax=False, stars=False),
        )

        away_start = away_renderer.render_frame(0.0, RenderQuality.EXPORT, include_stars=False)
        away_end = away_renderer.render_frame(_DURATION, RenderQuality.EXPORT, include_stars=False)
        toward_start = toward_renderer.render_frame(0.0, RenderQuality.EXPORT, include_stars=False)
        toward_end = toward_renderer.render_frame(
            _DURATION, RenderQuality.EXPORT, include_stars=False
        )
        plain_away_start = plain_away.render_frame(0.0, RenderQuality.EXPORT, include_stars=False)
        plain_away_end = plain_away.render_frame(
            _DURATION, RenderQuality.EXPORT, include_stars=False
        )
        plain_toward_start = plain_toward.render_frame(
            0.0, RenderQuality.EXPORT, include_stars=False
        )

        start_delta = np.mean(
            np.abs(away_start.astype(np.float32) - plain_away_start.astype(np.float32))
        )
        end_delta = np.mean(np.abs(away_end.astype(np.float32) - plain_away_end.astype(np.float32)))
        toward_start_delta = np.mean(
            np.abs(toward_start.astype(np.float32) - plain_toward_start.astype(np.float32))
        )

        self.assertGreater(start_delta, 1.5)
        self.assertLess(end_delta, 0.05)
        self.assertLess(toward_start_delta, 0.05)
        np.testing.assert_allclose(away_start, toward_end, atol=1.0)
        np.testing.assert_allclose(away_end, toward_start, atol=1.0)

    def test_away_stars_recede_and_recycle_on_sampled_frames(self) -> None:
        field = _star_field()
        originals = [(star.offset_x, star.offset_y, star.z, star.size) for star in field._stars]
        last_frame = round(_DURATION * _FPS)
        sampled = set(_sampled_frames())
        previous: dict[int, tuple[float, float, float]] = {}
        generations = 0
        appearances = 0
        inner_left, inner_right = field.width * 0.25, field.width * 0.75
        inner_top, inner_bottom = field.height * 0.25, field.height * 0.75
        large_radius = (
            field.settings.min_size + (field.settings.max_size - field.settings.min_size) * 0.5
        )

        for frame in range(last_frame + 1):
            time_seconds = frame / _FPS
            visible = 0
            bins = [[0] * 3 for _ in range(3)]
            for index in range(len(field._stars)):
                depth = _resolve_away(field, index, time_seconds)
                if depth is None:
                    previous.pop(index, None)
                    continue
                visible += 1
                distance, radius, screen_x, screen_y = _screen_state(field, index, depth)
                self.assertTrue(math.isfinite(screen_x) and math.isfinite(screen_y))
                self.assertGreater(radius, 0.0)

                wrapped = False
                if index in previous:
                    prev_depth, prev_distance, prev_radius = previous[index]
                    wrapped = depth + 0.05 < prev_depth
                    if not wrapped:
                        self.assertLessEqual(distance, prev_distance + 1e-5)
                        self.assertGreaterEqual(depth, prev_depth - 1e-9)
                        self.assertLessEqual(radius, prev_radius + 1e-5)
                elif frame > 0:
                    wrapped = True
                    appearances += 1

                if wrapped:
                    generations += 1
                    in_interior = (
                        inner_left < screen_x < inner_right and inner_top < screen_y < inner_bottom
                    )
                    self.assertFalse(
                        in_interior and radius >= large_radius,
                        f"star {index} popped inside at frame {frame} "
                        f"({screen_x:.1f}, {screen_y:.1f})",
                    )

                previous[index] = (depth, distance, radius)
                if 0.0 <= screen_x < field.width and 0.0 <= screen_y < field.height:
                    column = min(2, int(screen_x / field.width * 3))
                    row = min(2, int(screen_y / field.height * 3))
                    bins[row][column] += 1

            if frame not in sampled:
                continue
            self.assertGreater(visible, 80, f"too few stars at frame {frame}")
            if frame in (0, last_frame) or frame % 50 == 0:
                border = [
                    bins[row][column]
                    for row in range(3)
                    for column in range(3)
                    if not (row == 1 and column == 1)
                ]
                self.assertTrue(
                    all(count > 0 for count in border),
                    f"empty border at frame {frame}: {bins}",
                )

        self.assertEqual(
            originals,
            [(star.offset_x, star.offset_y, star.z, star.size) for star in field._stars],
        )
        self.assertGreater(appearances, 0)
        self.assertGreater(generations, 0)

        sequential = _star_field()
        seeked = _star_field()
        for frame in range(last_frame + 1):
            stepped = _project_away(sequential, frame / _FPS)
            if frame in sampled:
                target = _project_away(seeked, frame / _FPS)
                self.assertEqual(
                    _projection_keys(target),
                    _projection_keys(stepped),
                    f"seek mismatch at frame {frame}",
                )

        start_layer = _project_away(_star_field(), 0.0)
        end_layer = _project_away(_star_field(), _DURATION)
        self.assertGreater(len(start_layer), 80)
        self.assertGreater(len(end_layer), 80)

        renderer = create_renderer(
            self.source,
            _base_settings(away=True, parallax=False, stars=True),
        )
        start_frame = renderer.render_frame(
            0.0,
            RenderQuality.PREVIEW,
            include_stars=True,
        )
        end_frame = renderer.render_frame(
            _DURATION,
            RenderQuality.PREVIEW,
            include_stars=True,
        )
        self.assertGreater(int(start_frame.max()), 0)
        self.assertGreater(int(end_frame.max()), 0)


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    unittest.main()
