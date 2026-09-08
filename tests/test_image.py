"""Tests for lightweight image metadata and preview sizing."""

from __future__ import annotations

import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

import cv2

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QLocale
from PySide6.QtGui import QColor, QColorSpace, QImage, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from starflight.controllers.project_controller import ProjectController
from starflight.utils.image import (
    fit_size_within,
    load_image_bgr,
    read_image_dimensions,
    read_source_color_space,
)
from starflight.views.widgets.preview_panel import PreviewPanel
from starflight.views.widgets.timeline_widget import TimelineWidget


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

    def test_missing_image_profile_falls_back_to_srgb(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "unmanaged.png"
            image = QImage(8, 8, QImage.Format.Format_RGB888)
            image.fill(QColor(20, 80, 180))
            self.assertTrue(image.save(str(path), "PNG"))

            color_space = read_source_color_space(str(path))

        self.assertEqual(color_space, QColorSpace(QColorSpace.NamedColorSpace.SRgb))

    def test_non_srgb_source_is_converted_into_srgb_working_space(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "adobe.png"
            image = QImage(8, 8, QImage.Format.Format_RGB888)
            image.fill(QColor(200, 40, 40))
            image.setColorSpace(
                QColorSpace(
                    QColorSpace.Primaries.AdobeRgb,
                    QColorSpace.TransferFunction.Gamma,
                    2.2,
                )
            )
            self.assertTrue(image.save(str(path), "PNG"))

            color_space = read_source_color_space(str(path))
            loaded = load_image_bgr(str(path))
            unmanaged = cv2.imread(str(path), cv2.IMREAD_COLOR)

        self.assertEqual(color_space.primaries(), QColorSpace.Primaries.AdobeRgb)
        self.assertIsNotNone(unmanaged)
        self.assertFalse((loaded == unmanaged).all())

    def test_prophoto_source_is_converted_into_srgb_working_space(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "prophoto.png"
            image = QImage(8, 8, QImage.Format.Format_RGB888)
            image.fill(QColor(200, 40, 40))
            image.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.ProPhotoRgb))
            self.assertTrue(image.save(str(path), "PNG"))

            color_space = read_source_color_space(str(path))
            loaded = load_image_bgr(str(path))
            unmanaged = cv2.imread(str(path), cv2.IMREAD_COLOR)

        self.assertTrue(color_space.isValid())
        self.assertNotEqual(color_space, QColorSpace(QColorSpace.NamedColorSpace.SRgb))
        self.assertIsNotNone(unmanaged)
        self.assertFalse((loaded == unmanaged).all())

    def test_preview_size_keeps_aspect_ratio_and_caps_work(self) -> None:
        self.assertEqual(fit_size_within(1920, 1080, 800, 600), (800, 450))
        self.assertEqual(fit_size_within(2160, 3840, 1200, 900), (462, 820))

    def test_preview_panel_keeps_the_original_full_target_render_size(self) -> None:
        panel = PreviewPanel()
        panel.set_target_resolution(2161, 3841)

        self.assertEqual(panel.preview_render_size(), (2162, 3842))

    def test_playback_preview_uses_a_960_pixel_long_edge(self) -> None:
        panel = PreviewPanel()
        panel.set_target_resolution(2160, 3840)

        self.assertEqual(panel.playback_render_size(), (540, 960))

        panel.set_target_resolution(3840, 2160)

        self.assertEqual(panel.playback_render_size(), (960, 540))

    def test_empty_preview_offers_image_import(self) -> None:
        panel = PreviewPanel()
        load_requests: list[bool] = []
        panel.load_image_requested.connect(lambda: load_requests.append(True))

        panel.empty_state.load_button.click()

        self.assertEqual(load_requests, [True])

    def test_empty_preview_has_a_wide_compact_import_layout(self) -> None:
        panel = PreviewPanel()

        self.assertGreaterEqual(panel.empty_state.content.minimumWidth(), 320)
        self.assertIn("JPG, PNG, TIFF", panel.empty_state.hint_label.text())

    def test_dropped_image_path_updates_the_project_without_open_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "portrait.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 8 + struct.pack(">II", 640, 960))
            controller = ProjectController(Mock())

            loaded = controller.load_image_path(path, QWidget())

        self.assertTrue(loaded)
        self.assertEqual(controller.project.source_image, str(path))
        resolution = controller.project.settings.resolution
        self.assertEqual((resolution.width, resolution.height), (1080, 1920))

    def test_manual_zoom_stays_visually_stable_during_lower_resolution_playback(self) -> None:
        panel = PreviewPanel()
        viewport = panel.viewport
        source = QPixmap(1080, 1920)
        source.fill(QColor("#FFFFFF"))
        playback = QPixmap(540, 960)
        playback.fill(QColor("#FFFFFF"))

        viewport.set_frame_pixmap(source)
        viewport.set_zoom_percent(50)
        viewport.set_frame_pixmap(playback)

        self.assertEqual(viewport.current_zoom_percent(), 100)

    def test_pausing_requests_an_exact_redraw_of_the_current_frame(self) -> None:
        timeline = TimelineWidget()
        frames: list[int] = []
        timeline.frame_index_changed.connect(frames.append)

        timeline.play()
        self.assertTrue(timeline.is_playing)
        timeline.pause()

        self.assertFalse(timeline.is_playing)
        self.assertEqual(frames, [0])

    def test_ruler_labels_keep_fractional_seconds_in_the_active_locale(self) -> None:
        previous_locale = QLocale()
        self.addCleanup(QLocale.setDefault, previous_locale)
        QLocale.setDefault(QLocale(QLocale.Language.German, QLocale.Country.Germany))

        self.assertEqual(TimelineWidget._format_ruler_time(2.5), "2,5s")
        self.assertEqual(TimelineWidget._format_ruler_time(2.0), "2s")
        self.assertEqual(TimelineWidget._format_ruler_time(65.0), "1:05")

    def test_play_button_requests_cache_preparation_before_timeline_starts(self) -> None:
        timeline = TimelineWidget()
        requests: list[bool] = []
        timeline.play_requested.connect(lambda: requests.append(True))

        timeline.toggle_playback()

        self.assertEqual(requests, [True])
        self.assertFalse(timeline.is_playing)


if __name__ == "__main__":
    unittest.main()
