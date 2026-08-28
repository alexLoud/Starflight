"""Tests for cached six-fps timeline playback previews."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import cv2
import numpy as np

from starflight.services.parallax_preview_service import PreparedParallaxPreview
from starflight.services.playback_preview_service import (
    PlaybackFrameCache,
    PlaybackPreviewWorker,
    PlaybackRenderSpec,
    _initialize_playback_process,
    _render_playback_sample,
    playback_sample_count,
    playback_sample_index,
)
from starflight.types.settings import ImageMotionMode, ProjectSettings, ResolutionSettings
from starflight.views.main_window import MainWindow


class PlaybackFrameCacheTests(unittest.TestCase):
    def test_ten_seconds_keep_twenty_background_and_sixty_playback_frames(self) -> None:
        cache = PlaybackFrameCache(10.0)

        self.assertEqual(cache.frame_count, 60)
        self.assertEqual(len(cache.background_indices()), 20)
        self.assertEqual(cache.playback_indices_from(5.0), list(range(30, 60)))

    def test_timeline_times_map_to_the_nearest_six_fps_sample(self) -> None:
        self.assertEqual(playback_sample_count(1.0), 6)
        self.assertEqual(playback_sample_index(0.0, 1.0), 0)
        self.assertEqual(playback_sample_index(0.18, 1.0), 1)
        self.assertEqual(playback_sample_index(1.0, 1.0), 5)

    def test_cache_reports_only_frames_that_still_need_rendering(self) -> None:
        cache = PlaybackFrameCache(1.0)
        frame = np.zeros((2, 2, 3), dtype=np.uint8)
        _ok, encoded = cv2.imencode(".jpg", frame)
        cache.store(0, encoded.tobytes())

        self.assertEqual(cache.missing([0, 1, 2]), [1, 2])

    def test_playing_timeline_displays_cached_frame_without_live_rendering(self) -> None:
        cache = PlaybackFrameCache(1.0)
        _ok, encoded = cv2.imencode(
            ".jpg",
            np.full((4, 6, 3), 64, dtype=np.uint8),
        )
        cache.store(0, encoded.tobytes())
        timeline = SimpleNamespace(
            is_playing=True,
            current_time_seconds=lambda: 0.0,
            pause=Mock(),
        )
        panel = SimpleNamespace(show_frame=Mock())
        window = SimpleNamespace(
            preview_workspace=SimpleNamespace(timeline=timeline, preview_panel=panel),
            _playback_frame_cache=cache,
            _last_playback_sample=None,
            refresh_preview=Mock(),
        )

        MainWindow._on_frame_changed(window, 0)

        panel.show_frame.assert_called_once()
        window.refresh_preview.assert_not_called()
        timeline.pause.assert_not_called()


class PlaybackRenderProcessTests(unittest.TestCase):
    def test_normal_playback_uses_target_cache_resolution(self) -> None:
        source = np.zeros((24, 32, 3), dtype=np.uint8)
        settings = ProjectSettings(resolution=ResolutionSettings(48, 72))
        settings.stars.star_count = 20
        spec = PlaybackRenderSpec(
            image_path="source.png",
            settings=settings,
            crop_target_size=(96, 144),
            include_stars=True,
        )

        with patch(
            "starflight.services.playback_preview_service.load_image_bgr",
            return_value=source,
        ):
            _initialize_playback_process(spec)
        sample_index, payload = _render_playback_sample(1)
        frame = cv2.imdecode(
            np.frombuffer(payload, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )

        self.assertEqual(sample_index, 1)
        self.assertEqual(frame.shape, (72, 48, 3))
        self.assertGreater(int(frame.max()), 0)

    def test_worker_processes_return_a_complete_encoded_frame_set(self) -> None:
        settings = ProjectSettings(resolution=ResolutionSettings(48, 72))
        settings.stars.star_count = 20
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "source.png"
            cv2.imwrite(str(image_path), np.zeros((24, 32, 3), dtype=np.uint8))
            spec = PlaybackRenderSpec(
                image_path=str(image_path),
                settings=settings,
                crop_target_size=(96, 144),
                include_stars=True,
            )
            frames: dict[int, bytes] = {}
            failures: list[object] = []
            worker = PlaybackPreviewWorker(spec, [0, 1], render_workers=2)
            worker.frame_ready.connect(frames.__setitem__)
            worker.failed.connect(failures.append)

            worker.run()

        self.assertEqual(failures, [])
        self.assertEqual(set(frames), {0, 1})
        self.assertTrue(all(payload.startswith(b"\xff\xd8") for payload in frames.values()))

    def test_parallax_background_is_upscaled_before_target_sized_stars_are_composited(self) -> None:
        source = np.zeros((24, 16, 3), dtype=np.uint8)
        snapshot_settings = ProjectSettings(resolution=ResolutionSettings(16, 24))
        snapshot_settings.background.motion_mode = ImageMotionMode.PARALLAX
        preview = PreparedParallaxPreview(
            source_image_bgr=source,
            settings=snapshot_settings,
            disparity=np.ones((24, 16), dtype=np.float32),
        )
        target_settings = snapshot_settings.clone()
        target_settings.resolution = ResolutionSettings(48, 72)
        target_settings.stars.star_count = 20
        spec = PlaybackRenderSpec(
            image_path="unused.png",
            settings=target_settings,
            crop_target_size=(96, 144),
            include_stars=True,
            parallax_preview=preview,
        )

        _initialize_playback_process(spec)
        _sample_index, payload = _render_playback_sample(0)
        frame = cv2.imdecode(
            np.frombuffer(payload, dtype=np.uint8),
            cv2.IMREAD_COLOR,
        )

        self.assertEqual(frame.shape, (72, 48, 3))
        self.assertGreater(int(frame.max()), 0)


class PlaybackPlayRequestTests(unittest.TestCase):
    def test_play_request_stops_standstill_refresh_and_blocks_it_during_prep(self) -> None:
        refresh_timer = Mock()
        timeline = SimpleNamespace(
            current_time_seconds=lambda: 0.0,
            set_playback_preparing=Mock(),
        )
        cache = PlaybackFrameCache(10.0)
        window = SimpleNamespace(
            _playback_worker_starts_playback=False,
            _refresh_timer=refresh_timer,
            _playback_preview_refresh_timer=Mock(),
            _playback_frame_cache=cache,
            preview_workspace=SimpleNamespace(timeline=timeline),
            _set_status=Mock(),
            tr=Mock(side_effect=lambda text: text),
            _start_playback_preview_worker=Mock(),
        )

        MainWindow._on_play_requested(window)

        refresh_timer.stop.assert_called_once_with()
        self.assertTrue(window._playback_worker_starts_playback)
        self.assertEqual(len(window._playback_worker_required), cache.frame_count)
        window._start_playback_preview_worker.assert_called_once()
        timeline.set_playback_preparing.assert_called_once_with(True)

        window._playback_worker_starts_playback = True
        window._workspace_active = True
        MainWindow.refresh_preview(window)

        refresh_timer.stop.assert_called()

    def test_play_completion_waits_for_all_required_frames_not_only_missing(self) -> None:
        cache = PlaybackFrameCache(1.0)
        _ok, encoded = cv2.imencode(".jpg", np.zeros((2, 2, 3), dtype=np.uint8))
        cache.store(0, encoded.tobytes())
        timeline = SimpleNamespace(
            current_time_seconds=lambda: 0.0,
            set_playback_preparing=Mock(),
            play=Mock(),
        )
        panel = SimpleNamespace(show_frame=Mock())
        worker = Mock()
        window = SimpleNamespace(
            _playback_worker_starts_playback=True,
            _playback_worker_required=list(range(cache.frame_count)),
            _playback_frame_cache=cache,
            _playback_preview_worker=worker,
            _playback_preview_generation=0,
            _last_playback_sample=None,
            preview_workspace=SimpleNamespace(timeline=timeline, preview_panel=panel),
            _set_status=Mock(),
            tr=Mock(side_effect=lambda text: text),
            _begin_cached_playback=Mock(),
        )

        MainWindow._on_playback_preview_completed(window, worker, token=0)

        window._begin_cached_playback.assert_not_called()

        cache.store(1, encoded.tobytes())
        cache.store(2, encoded.tobytes())
        cache.store(3, encoded.tobytes())
        cache.store(4, encoded.tobytes())
        cache.store(5, encoded.tobytes())

        MainWindow._on_playback_preview_completed(window, worker, token=0)

        window._begin_cached_playback.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
