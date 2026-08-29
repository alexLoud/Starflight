"""Regression checks for public helpers retained during the review."""

from __future__ import annotations

import unittest

from starflight.commands.registry import CommandRegistry
from starflight.controllers.project_controller import ProjectController
from starflight.types.settings import apply_density_preset, coerce_export_quality
from starflight.utils.image import cover_resize_bgr
from starflight.utils.star_colors import apply_color_intensity, star_rgb_from_temperature
from starflight.views.dialogs.image_open_dialog import IMAGE_FILTER
from starflight.views.dialogs.project_open_dialog import PROJECT_FILTER
from starflight.views.dialogs.video_save_dialog import VIDEO_FILTER
from starflight.views.main_window import MainWindow


class CompatibilityTests(unittest.TestCase):
    def test_existing_methods_are_still_available(self) -> None:
        self.assertTrue(callable(CommandRegistry.list))
        self.assertTrue(callable(ProjectController.mark_clean))
        self.assertTrue(callable(MainWindow.build_shell))

    def test_existing_helpers_are_still_available(self) -> None:
        helpers = (
            apply_density_preset,
            coerce_export_quality,
            cover_resize_bgr,
            apply_color_intensity,
            star_rgb_from_temperature,
        )
        self.assertTrue(all(callable(helper) for helper in helpers))

    def test_existing_file_filter_constants_are_still_available(self) -> None:
        self.assertTrue(IMAGE_FILTER)
        self.assertTrue(PROJECT_FILTER)
        self.assertTrue(VIDEO_FILTER)


if __name__ == "__main__":
    unittest.main()
