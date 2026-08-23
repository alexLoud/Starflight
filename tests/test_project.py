"""Regression tests for project file persistence."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from starflight.core.project import ProjectError, load_project, save_project
from starflight.types.settings import Project


class ProjectPersistenceTests(unittest.TestCase):
    def test_project_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.sf"
            project = Project(name="Sample")

            save_project(project, path)
            loaded = load_project(path)

            self.assertEqual(list(Path(directory).iterdir()), [path])

        self.assertEqual(loaded.name, "Sample")
        self.assertEqual(loaded.settings, project.settings)

    def test_invalid_json_is_reported_as_project_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.sf"
            path.write_text("{", encoding="utf-8")

            with self.assertRaises(ProjectError):
                load_project(path)

    def test_non_object_project_is_reported_as_project_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.sf"
            path.write_text(json.dumps([]), encoding="utf-8")

            with self.assertRaises(ProjectError):
                load_project(path)

    def test_invalid_settings_are_reported_as_project_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid-settings.sf"
            path.write_text('{"settings": []}', encoding="utf-8")

            with self.assertRaises(ProjectError):
                load_project(path)

    def test_invalid_utf8_is_reported_as_project_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid-encoding.sf"
            path.write_bytes(b"\xff\xfe")

            with self.assertRaises(ProjectError):
                load_project(path)

    def test_non_finite_integer_is_reported_as_project_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "invalid-number.sf"
            path.write_text('{"version": 1e999}', encoding="utf-8")

            with self.assertRaises(ProjectError):
                load_project(path)


if __name__ == "__main__":
    unittest.main()
