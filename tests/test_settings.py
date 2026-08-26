"""Regression tests for project settings conversion."""

from __future__ import annotations

import math
import unittest

from starflight.types.settings import ImageMotionMode, settings_from_dict, settings_to_dict


class SettingsConversionTests(unittest.TestCase):
    def test_empty_data_keeps_the_legacy_target_point_enabled(self) -> None:
        settings = settings_from_dict({})

        self.assertFalse(settings.background.start_focus_enabled)
        self.assertTrue(settings.background.end_focus_enabled)
        self.assertEqual(settings.background.motion_mode, ImageMotionMode.MANUAL)
        self.assertFalse(settings.ui.crop_section_expanded)
        self.assertFalse(settings.ui.focus_section_expanded)

    def test_old_focus_fields_enable_the_target_point(self) -> None:
        settings = settings_from_dict({"background": {"focus_x": 0.25, "focus_y": 0.75}})

        self.assertTrue(settings.background.end_focus_enabled)
        self.assertEqual(settings.background.end_focus_x, 0.25)
        self.assertEqual(settings.background.end_focus_y, 0.75)
        self.assertEqual(settings.background.motion_mode, ImageMotionMode.MANUAL)

    def test_boolean_fields_keep_the_original_truthiness_conversion(self) -> None:
        settings = settings_from_dict({"background": {"fill_frame": "false"}})

        self.assertTrue(settings.background.fill_frame)

    def test_non_finite_values_keep_the_original_conversion(self) -> None:
        settings = settings_from_dict({"duration_seconds": math.nan})

        self.assertTrue(math.isnan(settings.duration_seconds))

    def test_image_motion_mode_migrates_parallax_and_round_trips(self) -> None:
        defaults = settings_from_dict({})
        self.assertEqual(defaults.background.motion_mode, ImageMotionMode.MANUAL)
        self.assertEqual(defaults.parallax.strength, 4)

        none_mode = settings_from_dict({"background": {"motion_mode": "none"}})
        self.assertEqual(none_mode.background.motion_mode, ImageMotionMode.MANUAL)

        settings = settings_from_dict({"parallax": {"enabled": True, "strength": 10}})
        restored = settings_from_dict(settings_to_dict(settings))

        self.assertEqual(settings.background.motion_mode, ImageMotionMode.PARALLAX)
        self.assertEqual(restored.background.motion_mode, ImageMotionMode.PARALLAX)
        self.assertEqual(restored.parallax.strength, 10)
        self.assertNotIn("enabled", settings_to_dict(restored)["parallax"])

    def test_crop_settings_round_trip(self) -> None:
        settings = settings_from_dict(
            {"crop": {"center_x": 0.2, "center_y": 0.7, "scale": 0.6}}
        )

        restored = settings_from_dict(settings_to_dict(settings))

        self.assertEqual(restored.crop.center_x, 0.2)
        self.assertEqual(restored.crop.center_y, 0.7)
        self.assertEqual(restored.crop.scale, 0.6)

    def test_legacy_image_enlargement_stays_on_background_scale(self) -> None:
        settings = settings_from_dict({"background": {"scale_percent": 125.0}})

        self.assertEqual(settings.crop.scale, 1.0)
        self.assertEqual(settings.background.scale_percent, 125.0)
        self.assertEqual(settings.background.motion_mode, ImageMotionMode.MANUAL)


if __name__ == "__main__":
    unittest.main()
