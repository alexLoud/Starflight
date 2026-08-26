"""Regression tests for export worker scaling and ffmpeg pipe handling."""

from __future__ import annotations

import errno
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from starflight.app.settings import DEFAULT_RENDER_WORKER_COUNT
from starflight.core.exporter import (
    _PIPE_WRITE_CHUNK_SIZE,
    ExportWorker,
    _export_worker_count,
    _ffmpeg_output_arg,
    _ffmpeg_popen_kwargs,
    _is_closed_pipe_error,
    _LinearProgressPhase,
    _stream_file_to_pipe,
)
from starflight.types.settings import Project
from starflight.views.dialogs.export_dialog import default_export_output_path


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


class ExportPipeTests(unittest.TestCase):
    def test_ffmpeg_popen_hides_console_on_windows(self) -> None:
        with patch("starflight.core.exporter.sys.platform", "win32"):
            kwargs = _ffmpeg_popen_kwargs()
        self.assertEqual(kwargs, {"creationflags": 0x08000000})

    def test_ffmpeg_popen_does_not_set_creationflags_on_other_platforms(self) -> None:
        with patch("starflight.core.exporter.sys.platform", "linux"):
            kwargs = _ffmpeg_popen_kwargs()
        self.assertEqual(kwargs, {})

    def test_stream_file_to_pipe_writes_in_small_chunks(self) -> None:
        payload = b"x" * (_PIPE_WRITE_CHUNK_SIZE * 2 + 11)
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(payload)
            path = tmp.name
        sink = io.BytesIO()
        writes: list[int] = []
        original_write = sink.write

        def tracking_write(data: bytes) -> int:
            writes.append(len(data))
            return original_write(data)

        sink.write = tracking_write  # type: ignore[method-assign]
        try:
            _stream_file_to_pipe(path, sink)
            self.assertEqual(sink.getvalue(), payload)
            self.assertGreater(len(writes), 1)
            self.assertLessEqual(max(writes), _PIPE_WRITE_CHUNK_SIZE)
        finally:
            os.unlink(path)

    def test_windows_einval_is_treated_as_closed_pipe(self) -> None:
        with patch("starflight.core.exporter.sys.platform", "win32"):
            self.assertTrue(_is_closed_pipe_error(OSError(errno.EINVAL, "Invalid argument")))
        with patch("starflight.core.exporter.sys.platform", "linux"):
            self.assertFalse(_is_closed_pipe_error(OSError(errno.EINVAL, "Invalid argument")))
        self.assertTrue(_is_closed_pipe_error(BrokenPipeError()))
        self.assertFalse(_is_closed_pipe_error(OSError(errno.EIO, "input/output error")))

    def test_write_chunk_file_maps_windows_einval_to_ffmpeg_error(self) -> None:
        worker = ExportWorker(Project(), Path("out.mp4"))
        stdin = MagicMock()
        stdin.write.side_effect = OSError(errno.EINVAL, "Invalid argument")
        process = MagicMock()
        process.stdin = stdin
        process.poll.return_value = None
        stderr_log = io.BytesIO(b"encoder failed")
        payload = b"\x00" * 10
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(payload)
            path = tmp.name
        try:
            with patch("starflight.core.exporter.sys.platform", "win32"):
                with self.assertRaises(RuntimeError) as ctx:
                    worker._write_chunk_file(process, path, 1, len(payload), stderr_log)
            self.assertIn("encoder failed", str(ctx.exception))
        finally:
            os.unlink(path)

    def test_write_chunk_file_reports_ffmpeg_exit_before_stdin_write(self) -> None:
        worker = ExportWorker(Project(), Path("out.mp4"))
        process = MagicMock()
        process.stdin = MagicMock()
        process.poll.return_value = 1
        stderr_log = io.BytesIO(b"unknown encoder 'libx264'")
        payload = b"\x00" * 10
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(payload)
            path = tmp.name
        try:
            with self.assertRaises(RuntimeError) as ctx:
                worker._write_chunk_file(process, path, 1, len(payload), stderr_log)
            self.assertIn("unknown encoder 'libx264'", str(ctx.exception))
            process.stdin.write.assert_not_called()
        finally:
            os.unlink(path)


class ExportProgressTests(unittest.TestCase):
    def test_linear_phase_progress_stays_in_its_global_range(self) -> None:
        updates: list[tuple[int, int]] = []
        progress = _LinearProgressPhase(
            100,
            1,
            40,
            lambda current, total: updates.append((current, total)),
        )

        for fraction in (0.0, 0.5, 0.25, 1.0):
            progress.update(fraction)

        self.assertEqual(updates, [(1, 100), (20, 100), (40, 100)])

    def test_parallax_depth_creation_updates_export_progress(self) -> None:
        worker = ExportWorker(Project(), Path("out.mp4"))
        updates: list[tuple[int, int]] = []
        source_image = __import__("numpy").zeros((64, 64, 3), dtype=__import__("numpy").uint8)

        def fake_create_parallax_depth(source_bgr, focus, *, on_progress=None):
            if on_progress is not None:
                on_progress(0.0)
                on_progress(0.5)
                on_progress(1.0)
            return __import__("numpy").ones((32, 32), dtype=__import__("numpy").float32)

        with patch(
            "starflight.core.exporter.create_parallax_depth",
            side_effect=fake_create_parallax_depth,
        ):
            progress = _LinearProgressPhase(
                100,
                1,
                40,
                lambda current, total: updates.append((current, total)),
            )
            worker._create_parallax_depth_with_progress(
                source_image,
                (0.5, 0.5),
                progress=progress,
            )

        self.assertEqual(updates, [(1, 100), (20, 100), (40, 100)])

    def test_ffmpeg_output_arg_uses_file_url_on_windows(self) -> None:
        windows_path = MagicMock()
        windows_path.expanduser.return_value = windows_path
        windows_path.is_absolute.return_value = True
        windows_path.as_posix.return_value = "C:/Users/ELAUTAL/Desktop/video.mp4"
        with patch("starflight.core.exporter.sys.platform", "win32"):
            argument = _ffmpeg_output_arg(windows_path)
        self.assertEqual(argument, "file:C:/Users/ELAUTAL/Desktop/video.mp4")
        self.assertEqual(argument, "file:C:/Users/ELAUTAL/Desktop/video.mp4")

    def test_ffmpeg_output_arg_keeps_native_path_on_other_platforms(self) -> None:
        path = Path("/tmp/video.mp4")
        with patch("starflight.core.exporter.sys.platform", "linux"):
            self.assertEqual(_ffmpeg_output_arg(path), str(path))

    def test_default_export_path_skips_missing_desktop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            documents = Path(directory) / "Documents"
            documents.mkdir()
            missing_desktop = Path(directory) / "Desktop"

            def fake_location(location) -> str:
                from PySide6.QtCore import QStandardPaths

                if location == QStandardPaths.StandardLocation.DesktopLocation:
                    return str(missing_desktop)
                if location == QStandardPaths.StandardLocation.DocumentsLocation:
                    return str(documents)
                return ""

            with patch(
                "starflight.views.dialogs.export_dialog.QStandardPaths.writableLocation",
                side_effect=fake_location,
            ):
                path = default_export_output_path("clip.mp4")
            self.assertEqual(path, documents / "clip.mp4")

    def test_default_export_path_prefers_existing_desktop(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            desktop = Path(directory) / "Desktop"
            desktop.mkdir()

            def fake_location(location) -> str:
                from PySide6.QtCore import QStandardPaths

                if location == QStandardPaths.StandardLocation.DesktopLocation:
                    return str(desktop)
                return ""

            with patch(
                "starflight.views.dialogs.export_dialog.QStandardPaths.writableLocation",
                side_effect=fake_location,
            ):
                path = default_export_output_path("clip.mp4")
            self.assertEqual(path, desktop / "clip.mp4")


if __name__ == "__main__":
    unittest.main()
