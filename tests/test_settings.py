"""Regression tests for project settings conversion."""

from __future__ import annotations

import math
import unittest

from starflight.types.settings import settings_from_dict


class SettingsConversionTests(unittest.TestCase):
    def test_empty_data_keeps_the_legacy_target_point_enabled(self) -> None:
        settings = settings_from_dict({})

        self.assertFalse(settings.background.start_focus_enabled)
        self.assertTrue(settings.background.end_focus_enabled)

    def test_old_focus_fields_enable_the_target_point(self) -> None:
        settings = settings_from_dict({"background": {"focus_x": 0.25, "focus_y": 0.75}})

        self.assertTrue(settings.background.end_focus_enabled)
        self.assertEqual(settings.background.end_focus_x, 0.25)
        self.assertEqual(settings.background.end_focus_y, 0.75)

    def test_boolean_fields_keep_the_original_truthiness_conversion(self) -> None:
        settings = settings_from_dict({"background": {"fill_frame": "false"}})

        self.assertTrue(settings.background.fill_frame)

    def test_non_finite_values_keep_the_original_conversion(self) -> None:
        settings = settings_from_dict({"duration_seconds": math.nan})

        self.assertTrue(math.isnan(settings.duration_seconds))


if __name__ == "__main__":
    unittest.main()
