"""Regression tests for the export worker scaling."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from starflight.app.settings import DEFAULT_RENDER_WORKER_COUNT
from starflight.core.exporter import _export_worker_count


class ExportResourceTests(unittest.TestCase):
    def test_worker_count_defaults_to_four_cores(self) -> None:
        with patch("starflight.app.settings.os.cpu_count", return_value=8):
            self.assertEqual(_export_worker_count(), DEFAULT_RENDER_WORKER_COUNT)

    def test_worker_count_caps_at_available_cpus(self) -> None:
        with patch("starflight.app.settings.os.cpu_count", return_value=2):
            self.assertEqual(_export_worker_count(), 1)

    def test_worker_count_uses_configured_value(self) -> None:
        with patch("starflight.app.settings.os.cpu_count", return_value=16):
            self.assertEqual(_export_worker_count(2), 2)

    def test_worker_count_clamps_configured_value_to_available_cpus(self) -> None:
        with patch("starflight.app.settings.os.cpu_count", return_value=64):
            self.assertEqual(_export_worker_count(100), 63)


if __name__ == "__main__":
    unittest.main()
