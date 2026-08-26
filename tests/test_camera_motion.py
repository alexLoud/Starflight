"""Tests for camera easing and square resolution defaults."""

from __future__ import annotations

import unittest

from starflight.core.camera_motion import camera_motion_progress
from starflight.types.settings import (
    BackgroundSettings,
    EasingMode,
    ImageMotionMode,
    resolution_for_image_orientation,
    settings_from_dict,
    settings_to_dict,
)


def _progress(
    time_seconds: float,
    mode: EasingMode,
    *,
    duration: float = 10.0,
    speed: float = 1.0,
) -> float:
    """
    camera progress helper for tests.

    time_seconds
        clip time
    mode
        easing mode
    duration
        clip duration
    speed
        flight speed
    """

    return camera_motion_progress(
        time_seconds,
        duration,
        BackgroundSettings(easing=mode),
        speed,
    )


class CameraMotionTests(unittest.TestCase):
    def test_linear_easing_keeps_progress(self) -> None:
        self.assertAlmostEqual(_progress(2.5, EasingMode.LINEAR), 0.25)
        self.assertAlmostEqual(_progress(5.0, EasingMode.LINEAR), 0.5)

    def test_ease_in_moves_from_the_first_frames(self) -> None:
        at_first_second = _progress(1.0, EasingMode.EASE_IN)
        at_halfway = _progress(5.0, EasingMode.EASE_IN)
        self.assertGreater(at_first_second, 0.04)
        self.assertLess(at_first_second, 0.12)
        self.assertGreater(at_halfway, 0.40)
        self.assertLess(at_halfway, 0.52)
        self.assertAlmostEqual(_progress(0.0, EasingMode.EASE_IN), 0.0)
        self.assertAlmostEqual(_progress(10.0, EasingMode.EASE_IN), 1.0)

    def test_ease_in_is_strictly_increasing(self) -> None:
        previous = -1.0
        for frame in range(0, 301):
            current = _progress(frame / 30.0, EasingMode.EASE_IN)
            self.assertGreaterEqual(current, previous)
            previous = current

    def test_ease_out_starts_immediately_and_slows_at_the_end(self) -> None:
        at_first_second = _progress(1.0, EasingMode.EASE_OUT)
        at_last_second = _progress(9.0, EasingMode.EASE_OUT)
        self.assertGreater(at_first_second, 0.09)
        self.assertGreater(at_last_second, 0.88)
        self.assertLess(1.0 - at_last_second, at_first_second)
        self.assertAlmostEqual(_progress(0.0, EasingMode.EASE_OUT), 0.0)
        self.assertAlmostEqual(_progress(10.0, EasingMode.EASE_OUT), 1.0)

    def test_ease_in_out_is_near_linear_in_the_middle(self) -> None:
        at_start = _progress(1.0, EasingMode.EASE_IN_OUT)
        at_mid = _progress(5.0, EasingMode.EASE_IN_OUT)
        at_end = _progress(9.0, EasingMode.EASE_IN_OUT)
        self.assertLess(at_start, 0.12)
        self.assertAlmostEqual(at_mid, 0.5, places=2)
        self.assertGreater(at_end, 0.88)
        self.assertAlmostEqual(_progress(0.0, EasingMode.EASE_IN_OUT), 0.0)
        self.assertAlmostEqual(_progress(10.0, EasingMode.EASE_IN_OUT), 1.0)

    def test_faster_flight_shortens_the_ease_in_ramp(self) -> None:
        slow = _progress(1.0, EasingMode.EASE_IN, speed=0.5)
        normal = _progress(1.0, EasingMode.EASE_IN, speed=1.0)
        fast = _progress(1.0, EasingMode.EASE_IN, speed=2.0)
        self.assertLess(slow, normal)
        self.assertLess(normal, fast)

    def test_shorter_clips_scale_the_ramp(self) -> None:
        long_clip = _progress(1.0, EasingMode.EASE_IN, duration=10.0)
        short_clip = _progress(1.0, EasingMode.EASE_IN, duration=5.0)
        self.assertGreater(short_clip, long_clip)


class SettingsCompatibilityTests(unittest.TestCase):
    def test_old_projects_keep_linear_easing(self) -> None:
        settings = settings_from_dict({"background": {"zoom_percent": 10.0}})
        self.assertEqual(settings.background.easing, EasingMode.LINEAR)
        self.assertEqual(settings.background.motion_mode, ImageMotionMode.MANUAL)

    def test_legacy_hold_and_preset_fields_are_ignored(self) -> None:
        settings = settings_from_dict(
            {
                "background": {
                    "easing": "ease_out",
                    "camera_preset": "warp",
                    "hold_start_seconds": 2.0,
                    "hold_end_seconds": 1.0,
                }
            }
        )
        self.assertEqual(settings.background.easing, EasingMode.EASE_OUT)
        restored = settings_from_dict(settings_to_dict(settings))
        self.assertEqual(restored.background.easing, EasingMode.EASE_OUT)
        self.assertNotIn("camera_preset", settings_to_dict(settings)["background"])
        self.assertNotIn("hold_start_seconds", settings_to_dict(settings)["background"])

    def test_square_images_default_to_square_resolution(self) -> None:
        self.assertEqual(resolution_for_image_orientation(2000, 2000), (1080, 1080))
        self.assertEqual(resolution_for_image_orientation(2000, 1000), (1920, 1080))
        self.assertEqual(resolution_for_image_orientation(1000, 2000), (1080, 1920))


if __name__ == "__main__":
    unittest.main()
