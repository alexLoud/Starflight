"""Regression tests for explicit low-resolution parallax previews."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
from PySide6.QtWidgets import QApplication

from starflight.services.parallax_preview_service import (
    ParallaxPreviewWorker,
    PreparedParallaxPreview,
    parallax_preview_size,
)
from starflight.services.preview_service import PreviewService
from starflight.types.settings import ImageMotionMode, ProjectSettings, ResolutionSettings
from starflight.views.main_window import MainWindow
from starflight.views.widgets.settings_panel import SettingsPanel
from starflight.views.widgets.zoom_toolbar import ZoomToolbar
from starflight.views.widgets.zoomable_viewport import ZoomablePreviewViewport


class ParallaxPreviewPreparationTests(unittest.TestCase):
    def test_preview_size_preserves_common_target_aspects(self) -> None:
        self.assertEqual(parallax_preview_size(1080, 1920), (360, 640))
        self.assertEqual(parallax_preview_size(1920, 1080), (640, 360))
        self.assertEqual(parallax_preview_size(1080, 1080), (640, 640))
        self.assertEqual(parallax_preview_size(480, 480), (480, 480))

    def test_worker_prepares_a_downscaled_snapshot_without_rendering_a_clip(self) -> None:
        source = np.zeros((96, 128, 3), dtype=np.uint8)
        settings = ProjectSettings(resolution=ResolutionSettings(1080, 1920))
        settings.background.motion_mode = ImageMotionMode.PARALLAX
        results: list[PreparedParallaxPreview] = []
        failures: list[object] = []
        progress: list[int] = []
        worker = ParallaxPreviewWorker("source.jpg", settings)
        worker.preview_ready.connect(results.append)
        worker.failed.connect(failures.append)
        worker.progress_changed.connect(progress.append)

        def uniform_depth(image: np.ndarray, _focus, *, on_progress=None) -> np.ndarray:
            if on_progress is not None:
                on_progress(1.0)
            return np.ones(image.shape[:2], dtype=np.float32)

        with (
            patch(
                "starflight.services.parallax_preview_service.load_image_bgr",
                return_value=source,
            ),
            patch(
                "starflight.services.parallax_preview_service.create_parallax_depth",
                side_effect=uniform_depth,
            ),
            patch(
                "starflight.services.parallax_preview_service.prepare_parallax_depth_v4",
                side_effect=lambda depth, on_progress=None: depth,
            ),
        ):
            worker.run()

        self.assertEqual(failures, [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].source_image_bgr.shape, (640, 360, 3))
        self.assertEqual(results[0].disparity.shape, (640, 360))
        self.assertEqual(results[0].settings.resolution, ResolutionSettings(360, 640))
        self.assertAlmostEqual(results[0].settings.stars.min_size, 1.0 / 3.0)
        self.assertAlmostEqual(results[0].settings.stars.max_size, 5.0 / 3.0)
        self.assertEqual(progress[-1], 100)


class ParallaxPreviewCacheTests(unittest.TestCase):
    def test_cached_snapshot_renders_only_when_explicitly_requested(self) -> None:
        height, width = 32, 48
        yy, xx = np.mgrid[0:height, 0:width]
        source = np.stack((xx * 4, yy * 6, (xx + yy) * 3), axis=2).astype(np.uint8)
        settings = ProjectSettings(
            resolution=ResolutionSettings(width, height),
            duration_seconds=1.0,
        )
        settings.background.motion_mode = ImageMotionMode.PARALLAX
        preview = PreparedParallaxPreview(
            source_image_bgr=source,
            settings=settings,
            disparity=np.ones((height, width), dtype=np.float32),
        )
        service = PreviewService()

        self.assertFalse(service.has_parallax_preview)
        service.install_parallax_preview(preview)
        frame = service.render_parallax_frame(1.0, include_stars=False)

        self.assertTrue(service.has_parallax_preview)
        self.assertIsNotNone(frame)
        self.assertEqual(frame.shape, source.shape)
        service.clear_parallax_preview()
        self.assertIsNone(service.render_parallax_frame(1.0, include_stars=False))


class ParallaxPreviewToggleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_parallax_and_star_toggles_are_independent(self) -> None:
        toolbar = ZoomToolbar(ZoomablePreviewViewport())
        toolbar.set_parallax_preview_state(available=True, status="ready")

        toolbar.set_parallax_preview_enabled(True)
        toolbar.stars_button.setChecked(False)

        self.assertTrue(toolbar.parallax_preview_enabled)
        self.assertFalse(toolbar.stars_enabled)

        toolbar.stars_button.setChecked(True)
        self.assertTrue(toolbar.parallax_preview_enabled)
        self.assertTrue(toolbar.stars_enabled)

        toolbar.set_parallax_preview_state(available=False, status="none")
        self.assertFalse(toolbar.parallax_preview_enabled)
        self.assertTrue(toolbar.stars_enabled)

    def test_parallax_toggle_has_explicit_disabled_state(self) -> None:
        toolbar = ZoomToolbar(ZoomablePreviewViewport())

        toolbar.set_parallax_preview_state(available=False, status="disabled")

        self.assertFalse(toolbar.parallax_button.isEnabled())
        self.assertEqual(toolbar.preview_status_label.text(), "")
        self.assertEqual(toolbar.parallax_button.objectName(), "parallax_preview_toggle_button")
        self.assertEqual(toolbar.preview_status_label.property("previewStatus"), "disabled")

        toolbar.set_parallax_preview_state(available=False, status="generating")
        self.assertNotEqual(toolbar.preview_status_label.text(), "")

        toolbar.set_parallax_preview_state(available=True, status="stale")
        self.assertEqual(toolbar.preview_status_label.text(), "")


class ParallaxPreviewRefreshTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_settings_slider_requests_refresh_only_when_released(self) -> None:
        panel = SettingsPanel()
        releases: list[bool] = []
        panel.slider_adjustment_finished.connect(lambda: releases.append(True))

        panel.zoom_row.slider.setSliderDown(True)
        panel.zoom_row.slider.setValue(panel.zoom_row.slider.value() + 1)

        self.assertTrue(panel.slider_adjustment_active)
        self.assertEqual(releases, [])

        panel.zoom_row.slider.setSliderDown(False)

        self.assertFalse(panel.slider_adjustment_active)
        self.assertEqual(releases, [True])

    def test_refresh_is_scheduled_only_for_missing_or_active_stale_preview(self) -> None:
        cases = (
            (False, False, False, False, True),
            (True, True, True, False, True),
            (True, True, False, False, False),
            (True, False, True, False, False),
            (False, False, False, True, False),
        )
        for has_preview, stale, active, slider_active, should_start in cases:
            with self.subTest(
                has_preview=has_preview,
                stale=stale,
                active=active,
                slider_active=slider_active,
            ):
                timer = Mock()
                window = SimpleNamespace(
                    _project_controller=SimpleNamespace(
                        project=SimpleNamespace(source_image="source.jpg"),
                    ),
                    _preview_service=SimpleNamespace(
                        has_parallax_preview=has_preview,
                    ),
                    _parallax_preview_stale=stale,
                    _parallax_preview_refresh_timer=timer,
                    settings_panel=SimpleNamespace(
                        slider_adjustment_active=slider_active,
                    ),
                    preview_workspace=SimpleNamespace(
                        zoom_toolbar=SimpleNamespace(
                            parallax_preview_enabled=active,
                        ),
                    ),
                    _parallax_effect_enabled=lambda: True,
                )

                MainWindow._schedule_parallax_preview_refresh(window)

                if should_start:
                    timer.start.assert_called_once_with()
                    timer.stop.assert_not_called()
                else:
                    timer.stop.assert_called_once_with()
                    timer.start.assert_not_called()


if __name__ == "__main__":
    unittest.main()
