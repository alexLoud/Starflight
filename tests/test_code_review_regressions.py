"""Regression tests for code-review findings."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from starflight.controllers.playback_preview_controller import PlaybackPreviewController
from starflight.controllers.project_controller import ProjectController
from starflight.core.exporter import ExportWorker, _create_export_staging_path
from starflight.core.preset import PresetError, save_user_preset
from starflight.core.project import ProjectError, make_relative_image_path, save_project
from starflight.services.playback_preview_service import PlaybackFrameCache
from starflight.types.preset import LookPreset, look_from_project_settings
from starflight.types.settings import Project, ProjectSettings


class ExportStagingTests(unittest.TestCase):
    def test_cleanup_staging_output_leaves_existing_destination_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "clip.mp4"
            destination.write_bytes(b"existing-export")
            worker = ExportWorker(Project(), destination)
            staging_path = _create_export_staging_path(destination)
            worker._staging_path = staging_path
            staging_path.write_bytes(b"partial")

            worker._cleanup_staging_output()

            self.assertFalse(staging_path.exists())
            self.assertEqual(destination.read_bytes(), b"existing-export")


class SaveAsPathTests(unittest.TestCase):
    def test_save_as_rebases_relative_image_path_to_new_project_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            old_dir = Path(directory) / "old"
            new_dir = Path(directory) / "new"
            old_dir.mkdir()
            new_dir.mkdir()
            image_path = old_dir / "photo.jpg"
            image_path.write_bytes(b"jpg")
            old_project = old_dir / "project.sf"
            old_project.write_text("{}", encoding="utf-8")

            controller = ProjectController(Mock())
            controller.project = Project()
            controller.project.source_image = make_relative_image_path(old_project, image_path)
            controller.project_path = old_project

            rebased = controller._source_image_for_save_target(new_dir / "copy.sf")

            self.assertEqual((new_dir / rebased).resolve(), image_path.resolve())


class PresetValidationTests(unittest.TestCase):
    def test_invalid_preset_id_is_rejected(self) -> None:
        preset = LookPreset(
            id="../escape",
            name="Broken",
            description="",
            settings=look_from_project_settings(ProjectSettings()),
            source_settings={},
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(PresetError):
                save_user_preset(preset, user_directory=Path(directory))


class AtomicSaveTests(unittest.TestCase):
    def test_project_save_writes_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.sf"
            project = Project()
            project.name = "saved"

            save_project(project, path)

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["name"], "saved")

    def test_project_save_keeps_original_file_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "project.sf"
            path.write_text(
                json.dumps({"name": "original"}, ensure_ascii=False),
                encoding="utf-8",
            )
            project = Project()
            project.name = "updated"

            with patch.object(Path, "replace", side_effect=OSError("disk full")):
                with self.assertRaises(ProjectError):
                    save_project(project, path)

            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(payload["name"], "original")


class ExportCancelTests(unittest.TestCase):
    def test_export_cancel_cleans_staging_without_touching_destination(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "clip.mp4"
            destination.write_bytes(b"existing-export")
            worker = ExportWorker(Project(), destination)
            staging_path = _create_export_staging_path(destination)
            worker._staging_path = staging_path
            staging_path.write_bytes(b"partial")

            worker.cancel()
            worker._cleanup_staging_output()

            self.assertFalse(staging_path.exists())
            self.assertEqual(destination.read_bytes(), b"existing-export")


class PlaybackPreparingCancelTests(unittest.TestCase):
    def test_detach_worker_resets_preparation_when_required_frames_are_missing(self) -> None:
        controller = PlaybackPreviewController(Mock(), Mock(), duration_seconds=1.0)
        controller.worker = Mock()
        controller.arm_playback_prepare(list(range(controller.frame_cache.frame_count)))

        _pending, should_reset = controller.detach_worker()

        self.assertTrue(should_reset)
        self.assertFalse(controller.starts_playback)
        self.assertEqual(controller.required_indices, [])


class PlaybackCacheBudgetTests(unittest.TestCase):
    def test_cache_evicts_oldest_frames_when_memory_budget_is_exceeded(self) -> None:
        cache = PlaybackFrameCache(10.0)
        large_payload = b"x" * (1024 * 1024 + 512 * 1024)

        for index in range(cache.frame_count):
            cache.store(index, large_payload)

        self.assertLessEqual(cache._stored_bytes, 64 * 1024 * 1024)
        self.assertGreater(len(cache._frames), 0)


class ProjectPathSecurityTests(unittest.TestCase):
    def test_resolve_source_image_rejects_paths_outside_project_root(self) -> None:
        from starflight.core.project import resolve_source_image_path

        with tempfile.TemporaryDirectory() as directory:
            project_path = Path(directory) / "project.sf"
            project_path.write_text("{}", encoding="utf-8")
            resolved = resolve_source_image_path(project_path, "../../etc/passwd")
            self.assertIsNone(resolved)


if __name__ == "__main__":
    unittest.main()
