"""Last-frame away-flight star coverage checks on a real black JPEG source."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from starflight.core.camera_motion import camera_motion_progress, rotation_radians
from starflight.core.renderer import FrameRenderer, create_renderer
from starflight.core.star_field import StarField
from starflight.types.settings import (
    FlightDirection,
    ImageMotionMode,
    ProjectSettings,
    RenderQuality,
    ResolutionSettings,
)

# portrait output like the user's 1080x1920 session, halved to keep the renders fast.
# star geometry is resolution independent (offsets scale with the frame), only pixel
# sizes differ.
_WIDTH = 540
_HEIGHT = 960
_FPS = 30
_DURATION = 10.0
_STAR_COUNT = 3000
_CORNER_FRACTION = 0.15
_QUADRANT_TOLERANCE = 0.75
# with the original half-frame offset box roughly 39% of the seeds project on screen at
# t=0 (mean of (z / max_z)^2 over the depth band); the 4x box would drop that to ~10%
_TOWARD_DENSITY_FLOOR = 0.25
_OUTPUT_ROOT = Path(tempfile.gettempdir()) / "starflight-away-last-frame"


def _apply_eagle_stars(settings: ProjectSettings) -> None:
    """copy the star settings from eagle.sf onto project settings."""

    settings.stars.star_count = _STAR_COUNT
    settings.stars.min_size = 0.9
    settings.stars.max_size = 8.7
    settings.stars.brightness = 0.89
    settings.stars.glow_intensity = 0.39
    settings.stars.glow_depth_boost = 0.66
    settings.stars.color_intensity = 0.69
    settings.stars.speed = 1.0
    settings.stars.magnitude_realism = 0.47
    settings.stars.size_spread = 0.21
    settings.stars.seed = 42


def _settings(
    *,
    direction: FlightDirection = FlightDirection.AWAY,
    end_focus: tuple[float, float] | None = None,
    rotation_degrees: float = 0.0,
) -> ProjectSettings:
    """user's sidebar: 10 s, zoom 30.3 %, fill frame off, parallax off."""

    settings = ProjectSettings(
        resolution=ResolutionSettings(width=_WIDTH, height=_HEIGHT),
        duration_seconds=_DURATION,
        fps=_FPS,
    )
    settings.background.flight_direction = direction
    settings.background.motion_mode = ImageMotionMode.MANUAL
    settings.background.zoom_percent = 30.3
    settings.background.rotation_degrees = rotation_degrees
    settings.background.fill_frame = False
    settings.background.start_focus_enabled = False
    settings.background.end_focus_enabled = end_focus is not None
    if end_focus is not None:
        settings.background.end_focus_x, settings.background.end_focus_y = end_focus
    _apply_eagle_stars(settings)
    return settings


def _write_black_jpeg(directory: Path) -> np.ndarray:
    """write a real black jpeg source and load it back through opencv."""

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "black.jpg"
    black = np.zeros((_HEIGHT * 2, _WIDTH * 2, 3), dtype=np.uint8)
    assert cv2.imwrite(str(path), black, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
    source = cv2.imread(str(path), cv2.IMREAD_COLOR)
    assert source is not None
    return source


def _on_screen_points(
    renderer: FrameRenderer,
    settings: ProjectSettings,
    time_seconds: float,
) -> tuple[list[tuple[float, float]], tuple[float, float]]:
    """project stars at the renderer clock and return on-screen points with the vanishing point."""

    field: StarField = renderer.stars.field
    background = settings.background
    motion_progress = camera_motion_progress(
        time_seconds,
        _DURATION,
        background,
        settings.stars.speed,
    )
    rotation = rotation_radians(
        motion_progress,
        background.rotation_degrees,
        background.flight_direction,
    )
    projections = field.project_at_time(
        time_seconds,
        _DURATION,
        renderer.view_center_at_progress,
        quality=RenderQuality.PREVIEW,
        motion_progress=motion_progress,
        field_rotation_radians=rotation,
        flight_direction=background.flight_direction,
    )
    points = [
        (item.x, item.y)
        for item in projections
        if 0.0 <= item.x < _WIDTH and 0.0 <= item.y < _HEIGHT
    ]
    return points, renderer.view_center_at_progress(motion_progress)


def _quadrant_counts(points: list[tuple[float, float]]) -> dict[str, int]:
    """count stars in the four frame quadrants split at width/2 and height/2."""

    counts = {"top-left": 0, "top-right": 0, "bottom-left": 0, "bottom-right": 0}
    for x, y in points:
        vertical = "top" if y < _HEIGHT / 2.0 else "bottom"
        horizontal = "left" if x < _WIDTH / 2.0 else "right"
        counts[f"{vertical}-{horizontal}"] += 1
    return counts


def _corner_counts(points: list[tuple[float, float]]) -> dict[str, int]:
    """count stars in the four corner squares of ~15% of the shorter frame edge."""

    edge = min(_WIDTH, _HEIGHT) * _CORNER_FRACTION
    counts = {"top-left": 0, "top-right": 0, "bottom-left": 0, "bottom-right": 0}
    for x, y in points:
        near_top = y < edge
        near_bottom = y >= _HEIGHT - edge
        near_left = x < edge
        near_right = x >= _WIDTH - edge
        if near_top and near_left:
            counts["top-left"] += 1
        elif near_top and near_right:
            counts["top-right"] += 1
        elif near_bottom and near_left:
            counts["bottom-left"] += 1
        elif near_bottom and near_right:
            counts["bottom-right"] += 1
    return counts


def _edge_counts(points: list[tuple[float, float]]) -> dict[str, int]:
    """count stars in the outer 12% strips of the frame (top, bottom, left, right)."""

    inset_x = _WIDTH * 0.12
    inset_y = _HEIGHT * 0.12
    return {
        "top": sum(1 for _x, y in points if y < inset_y),
        "bottom": sum(1 for _x, y in points if y >= _HEIGHT - inset_y),
        "left": sum(1 for x, _y in points if x < inset_x),
        "right": sum(1 for x, _y in points if x >= _WIDTH - inset_x),
    }


class AwayLastFrameTests(unittest.TestCase):
    def _render_last_frame(
        self,
        settings: ProjectSettings,
        name: str,
    ) -> tuple[list[tuple[float, float]], tuple[float, float]]:
        """export the last frame as png and return its on-screen star points and vanishing point."""

        output_dir = _OUTPUT_ROOT / name
        source = _write_black_jpeg(output_dir)
        renderer = create_renderer(source, settings)
        points, center = _on_screen_points(renderer, settings, _DURATION)
        rgb = renderer.render_frame(_DURATION, RenderQuality.PREVIEW, include_stars=True)
        cv2.imwrite(str(output_dir / "last_frame.png"), cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        return points, center

    def _assert_balanced_last_frame(self, settings: ProjectSettings, name: str) -> None:
        """assert the last frame covers all four quadrants and corners harmoniously."""

        points, center = self._render_last_frame(settings, name)
        quadrants = _quadrant_counts(points)
        corners = _corner_counts(points)
        label = f"{name} VP={tuple(round(c, 1) for c in center)}"
        self.assertGreater(len(points), 200, f"{label}: too few stars on screen")

        mean = sum(quadrants.values()) / 4.0
        for key, count in quadrants.items():
            self.assertGreaterEqual(
                count,
                _QUADRANT_TOLERANCE * mean,
                f"{label}: sparse quadrant {key} {quadrants}",
            )
        for key, count in corners.items():
            self.assertGreater(count, 0, f"{label}: empty corner {key} {corners}")
        edges = _edge_counts(points)
        edge_mean = sum(edges.values()) / 4.0
        for key, count in edges.items():
            self.assertGreaterEqual(
                count,
                0.70 * edge_mean,
                f"{label}: sparse edge {key} {edges}",
            )

    def test_last_frame_edges_with_left_look_at(self) -> None:
        settings = _settings(end_focus=(0.22, 0.45))
        output_dir = _OUTPUT_ROOT / "away-left-edges"
        source = _write_black_jpeg(output_dir)
        renderer = create_renderer(source, settings)
        first_points, _ = _on_screen_points(renderer, settings, 0.0)
        self.assertGreater(len(first_points), 0)
        points, center = _on_screen_points(renderer, settings, _DURATION)
        rgb = renderer.render_frame(_DURATION, RenderQuality.PREVIEW, include_stars=True)
        cv2.imwrite(
            str(output_dir / "last_frame.png"),
            cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
        )
        edges = _edge_counts(points)
        tag = f"last VP={tuple(round(c, 1) for c in center)} {edges}"
        self.assertGreater(len(points), 200, tag)
        edge_mean = sum(edges.values()) / 4.0
        for _key, count in edges.items():
            self.assertGreaterEqual(count, 0.70 * edge_mean, tag)

    def test_last_frame_without_look_at(self) -> None:
        self._assert_balanced_last_frame(_settings(), "away-center")

    def test_last_frame_with_left_look_at(self) -> None:
        self._assert_balanced_last_frame(_settings(end_focus=(0.22, 0.45)), "away-left")

    def test_last_frame_with_nebula_look_at(self) -> None:
        self._assert_balanced_last_frame(
            _settings(end_focus=(0.3907793339397762, 0.44847552766525206)),
            "away-nebula",
        )

    def test_last_frame_with_look_at_and_rotation(self) -> None:
        self._assert_balanced_last_frame(
            _settings(end_focus=(0.3907793339397762, 0.44847552766525206), rotation_degrees=20.0),
            "away-rotation",
        )

    def test_toward_density_is_unchanged(self) -> None:
        settings = _settings(direction=FlightDirection.TOWARD)
        output_dir = _OUTPUT_ROOT / "toward"
        source = _write_black_jpeg(output_dir)
        renderer = create_renderer(source, settings)
        floor = _TOWARD_DENSITY_FLOOR * _STAR_COUNT
        for label, time_seconds in (("first", 0.0), ("last", _DURATION)):
            points, _ = _on_screen_points(renderer, settings, time_seconds)
            self.assertGreaterEqual(len(points), floor, f"toward {label} frame thinned")
            rgb = renderer.render_frame(time_seconds, RenderQuality.PREVIEW, include_stars=True)
            cv2.imwrite(
                str(output_dir / f"{label}_frame.png"),
                cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
            )

            cv2.imwrite(
                str(output_dir / f"{label}_frame.png"),
                cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
            )


if __name__ == "__main__":
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    unittest.main()
