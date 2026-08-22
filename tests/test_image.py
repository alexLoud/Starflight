"""Tests for lightweight image metadata and preview sizing."""

from __future__ import annotations

import os
import struct
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from starflight.utils.image import compute_preview_size, read_image_dimensions
from starflight.views.widgets.preview_panel import PreviewPanel


class ImageUtilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_reads_png_dimensions_from_header(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 640, 480))

            self.assertEqual(read_image_dimensions(str(path)), (640, 480))

    def test_reads_jpeg_dimensions_without_decoding_pixels(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.jpg"
            app_segment = b"\xff\xe0\x00\x04\x00\x00"
            size_segment = b"\xff\xc0\x00\x07\x08" + struct.pack(">HH", 600, 800)
            path.write_bytes(b"\xff\xd8" + app_segment + size_segment + b"\xff\xd9")

            self.assertEqual(read_image_dimensions(str(path)), (800, 600))

    def test_preview_size_keeps_aspect_ratio_and_caps_work(self) -> None:
        self.assertEqual(compute_preview_size(1920, 1080, 800, 600), (800, 450))
        self.assertEqual(compute_preview_size(2160, 3840, 1200, 900), (462, 820))

    def test_preview_panel_keeps_the_original_full_target_render_size(self) -> None:
        panel = PreviewPanel()
        panel.set_target_resolution(2161, 3841)

        self.assertEqual(panel.preview_render_size(), (2162, 3842))


if __name__ == "__main__":
    unittest.main()
