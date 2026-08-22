"""Regression tests for the original export worker scaling."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from starflight.core.exporter import _export_worker_count


class ExportResourceTests(unittest.TestCase):
    def test_worker_count_keeps_one_core_free(self) -> None:
        with patch("starflight.core.exporter.os.cpu_count", return_value=2):
            self.assertEqual(_export_worker_count(), 1)

    def test_worker_count_scales_with_available_cpus(self) -> None:
        with patch("starflight.core.exporter.os.cpu_count", return_value=64):
            self.assertEqual(_export_worker_count(), 63)


if __name__ == "__main__":
    unittest.main()
