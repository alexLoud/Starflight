"""Regression tests for look preset conversion and persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starflight.core.preset import (
    PresetError,
    delete_user_preset,
    load_library,
    load_preset,
    save_look_from_settings,
    save_user_preset,
)
from starflight.types.preset import (
    apply_look,
    look_from_project_settings,
    look_preset_from_settings,
    look_settings_from_dict,
    look_settings_to_dict,
    preset_id_from_name,
    unique_preset_id,
)
from starflight.types.settings import (
    DensityPreset,
    EasingMode,
    ImageMotionMode,
    ParallaxStrength,
    ProjectSettings,
)


class LookPresetConversionTests(unittest.TestCase):
    def test_round_trip_keeps_look_fields(self) -> None:
        settings = ProjectSettings()
        settings.stars.density_preset = DensityPreset.HIGH
        settings.stars.star_count = 2500
        settings.stars.speed = 1.3
        settings.background.zoom_percent = 18.0
        settings.background.easing = EasingMode.EASE_IN
        settings.background.motion_mode = ImageMotionMode.PARALLAX
        settings.parallax.strength = ParallaxStrength.STRONG

        restored = look_settings_from_dict(
            look_settings_to_dict(look_from_project_settings(settings))
        )

        self.assertEqual(restored.stars.density_preset, DensityPreset.HIGH)
        self.assertEqual(restored.stars.star_count, 2500)
        self.assertEqual(restored.stars.speed, 1.3)
        self.assertEqual(restored.background.zoom_percent, 18.0)
        self.assertEqual(restored.background.easing, EasingMode.EASE_IN)
        self.assertEqual(restored.background.motion_mode, ImageMotionMode.PARALLAX)
        self.assertEqual(restored.parallax.strength, ParallaxStrength.STRONG)

    def test_look_dict_omits_image_specific_fields(self) -> None:
        data = look_settings_to_dict(look_from_project_settings(ProjectSettings()))

        self.assertNotIn("scale_percent", data["background"])
        self.assertNotIn("start_focus_x", data["background"])
        self.assertNotIn("end_focus_y", data["background"])
        self.assertEqual(set(data), {"stars", "background", "parallax"})

    def test_apply_look_leaves_crop_focus_and_timeline_untouched(self) -> None:
        settings = ProjectSettings()
        settings.resolution.width = 1080
        settings.resolution.height = 1920
        settings.duration_seconds = 14.0
        settings.fps = 60
        settings.crop.center_x = 0.3
        settings.crop.center_y = 0.7
        settings.crop.scale = 0.8
        settings.background.scale_percent = 125.0
        settings.background.start_focus_enabled = True
        settings.background.start_focus_x = 0.2
        settings.background.start_focus_y = 0.4
        settings.background.end_focus_enabled = True
        settings.background.end_focus_x = 0.8
        settings.background.end_focus_y = 0.6
        settings.export.crf = 23
        settings.ui.crop_section_expanded = True

        preset = look_preset_from_settings(
            "Soft Drift",
            "",
            ProjectSettings(),
            preset_id="soft-drift",
        )
        preset.settings.stars.star_count = 500
        preset.settings.stars.density_preset = DensityPreset.LOW
        preset.settings.stars.speed = 0.6
        preset.settings.background.zoom_percent = 6.0
        preset.settings.background.fill_frame = True
        preset.settings.background.easing = EasingMode.EASE_IN_OUT
        preset.source_settings = look_settings_to_dict(preset.settings)

        apply_look(settings, preset)

        self.assertEqual(settings.stars.star_count, 500)
        self.assertEqual(settings.stars.speed, 0.6)
        self.assertEqual(settings.background.zoom_percent, 6.0)
        self.assertTrue(settings.background.fill_frame)
        self.assertEqual(settings.background.easing, EasingMode.EASE_IN_OUT)

        self.assertEqual(settings.resolution.width, 1080)
        self.assertEqual(settings.resolution.height, 1920)
        self.assertEqual(settings.duration_seconds, 14.0)
        self.assertEqual(settings.fps, 60)
        self.assertEqual(settings.crop.center_x, 0.3)
        self.assertEqual(settings.crop.center_y, 0.7)
        self.assertEqual(settings.crop.scale, 0.8)
        self.assertEqual(settings.background.scale_percent, 125.0)
        self.assertTrue(settings.background.start_focus_enabled)
        self.assertEqual(settings.background.start_focus_x, 0.2)
        self.assertEqual(settings.background.start_focus_y, 0.4)
        self.assertTrue(settings.background.end_focus_enabled)
        self.assertEqual(settings.background.end_focus_x, 0.8)
        self.assertEqual(settings.background.end_focus_y, 0.6)
        self.assertEqual(settings.export.crf, 23)
        self.assertTrue(settings.ui.crop_section_expanded)

    def test_missing_look_fields_keep_current_values(self) -> None:
        settings = ProjectSettings()
        settings.stars.star_count = 1800
        settings.stars.speed = 0.4
        settings.background.zoom_percent = 9.0

        preset = look_preset_from_settings("Partial", "", ProjectSettings(), preset_id="partial")
        preset.source_settings = {"stars": {"speed": 1.5}}
        preset.settings.stars.speed = 1.5

        apply_look(settings, preset)

        self.assertEqual(settings.stars.speed, 1.5)
        self.assertEqual(settings.stars.star_count, 1800)
        self.assertEqual(settings.background.zoom_percent, 9.0)

    def test_preset_id_from_name_is_filesystem_safe(self) -> None:
        self.assertEqual(preset_id_from_name("Soft Drift"), "soft-drift")
        self.assertEqual(preset_id_from_name("  "), "preset")
        self.assertEqual(unique_preset_id("soft-drift", {"soft-drift"}), "soft-drift-2")


class LookPresetPersistenceTests(unittest.TestCase):
    def test_builtin_library_includes_the_test_presets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = load_library(user_directory=Path(directory))
        builtin_ids = {preset.id for preset in library if preset.builtin}

        self.assertIn("soft-drift", builtin_ids)
        self.assertIn("deep-glow", builtin_ids)

        soft = next(preset for preset in library if preset.id == "soft-drift")
        deep = next(preset for preset in library if preset.id == "deep-glow")
        self.assertEqual(soft.settings.stars.density_preset, DensityPreset.LOW)
        self.assertEqual(soft.settings.background.zoom_percent, 6.0)
        self.assertEqual(deep.settings.stars.density_preset, DensityPreset.HIGH)
        self.assertEqual(deep.settings.background.motion_mode, ImageMotionMode.PARALLAX)
        self.assertEqual(deep.settings.parallax.strength, ParallaxStrength.STRONG)

    def test_user_preset_round_trip_and_delete(self) -> None:
        settings = ProjectSettings()
        settings.stars.speed = 0.55
        settings.background.rotation_degrees = 4.0

        with tempfile.TemporaryDirectory() as directory:
            user_dir = Path(directory)
            saved = save_look_from_settings(
                "My Look",
                "Custom description",
                settings,
                preset_id="my-look",
                user_directory=user_dir,
            )
            loaded = load_preset(saved.path or user_dir / "my-look.json", builtin=False)

            self.assertEqual(loaded.name, "My Look")
            self.assertEqual(loaded.description, "Custom description")
            self.assertEqual(loaded.settings.stars.speed, 0.55)
            self.assertEqual(loaded.settings.background.rotation_degrees, 4.0)
            self.assertFalse(loaded.builtin)

            library = load_library(user_directory=user_dir)
            user_presets = [preset for preset in library if not preset.builtin]
            self.assertEqual(len(user_presets), 1)

            delete_user_preset(loaded)
            self.assertFalse((user_dir / "my-look.json").exists())

    def test_save_look_from_settings_overwrites_existing_user_preset(self) -> None:
        original = ProjectSettings()
        original.stars.speed = 0.4
        original.background.zoom_percent = 5.0
        updated = ProjectSettings()
        updated.stars.speed = 1.8
        updated.background.zoom_percent = 22.0

        with tempfile.TemporaryDirectory() as directory:
            user_dir = Path(directory)
            save_look_from_settings(
                "My Look",
                "Keep this text",
                original,
                preset_id="my-look",
                user_directory=user_dir,
            )
            saved = save_look_from_settings(
                "My Look",
                "Keep this text",
                updated,
                preset_id="my-look",
                user_directory=user_dir,
            )
            loaded = load_preset(saved.path or user_dir / "my-look.json", builtin=False)

            self.assertEqual(loaded.name, "My Look")
            self.assertEqual(loaded.description, "Keep this text")
            self.assertEqual(loaded.settings.stars.speed, 1.8)
            self.assertEqual(loaded.settings.background.zoom_percent, 22.0)

    def test_invalid_json_is_reported_as_preset_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{", encoding="utf-8")

            with self.assertRaises(PresetError):
                load_preset(path, builtin=False)

    def test_non_object_preset_is_reported_as_preset_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text(json.dumps([]), encoding="utf-8")

            with self.assertRaises(PresetError):
                load_preset(path, builtin=False)

    def test_invalid_user_json_is_skipped_by_the_library(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            user_dir = Path(directory)
            (user_dir / "broken.json").write_text("{", encoding="utf-8")
            save_user_preset(
                look_preset_from_settings("Kept", "", ProjectSettings(), preset_id="kept"),
                user_directory=user_dir,
            )

            library = load_library(user_directory=user_dir)
            user_ids = {preset.id for preset in library if not preset.builtin}
            self.assertEqual(user_ids, {"kept"})

    def test_builtin_presets_cannot_be_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            library = load_library(user_directory=Path(directory))
        builtin = next(preset for preset in library if preset.builtin)

        with self.assertRaises(PresetError):
            delete_user_preset(builtin)


if __name__ == "__main__":
    unittest.main()
