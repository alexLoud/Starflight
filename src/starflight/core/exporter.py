"""Render video frames in worker processes and stream them to FFmpeg.

The exporter prepares star fade state before splitting the frame range. Each process writes one
ordered chunk so the main export thread can feed FFmpeg without keeping full frames in memory.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import tempfile
import time
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import suppress
from io import BufferedIOBase
from multiprocessing import Manager, get_context
from pathlib import Path

import numpy as np
from PySide6.QtCore import QThread, Signal

from starflight.core.project import resolve_source_image_path
from starflight.core.renderer import FrameRenderer, create_renderer
from starflight.types.settings import Project, ProjectSettings, RenderQuality
from starflight.utils.image import load_image_bgr
from starflight.utils.validation import ffmpeg_executable

# stable machine-readable cancel token; never compare translated ui strings
EXPORT_CANCELLED = "export_cancelled"


def _export_worker_count() -> int:
    """choose process count for parallel export frame rendering."""

    cpu_count = os.cpu_count() or 4
    # Keep one logical core free for the UI, FFmpeg, and parent coordination.
    return max(1, cpu_count - 1)


class _WallClockProgress:
    """monotonic export progress from elapsed wall time and remaining work time."""

    def __init__(self, scale: int, emit_progress) -> None:
        """
        create a wall-clock progress tracker.

        scale
            integer progress scale (e.g. 10000)
        emit_progress
            callback(current: int, total: int)
        """

        self.scale = scale
        self._emit_progress = emit_progress
        self._t0 = time.perf_counter()
        self._value = 0
        self.render_estimate_s = 1.0

    def elapsed(self) -> float:
        """return seconds since export progress started."""

        return max(time.perf_counter() - self._t0, 1e-6)

    def set_render_estimate(self, seconds: float) -> None:
        """
        store the current render-time estimate used during preparation.

        seconds
            estimated remaining render wall time in seconds
        """

        self.render_estimate_s = max(float(seconds), 1e-6)

    def update(self, remaining_s: float) -> None:
        """
        publish progress for elapsed time versus remaining work.

        remaining_s
            estimated seconds of work still left (prep and/or render)
        """

        elapsed = self.elapsed()
        total = max(elapsed + max(remaining_s, 0.0), 1e-6)
        raw = int(round(self.scale * elapsed / total))
        # never jump backwards; leave the last unit for completion
        value = max(self._value, min(self.scale - 1, raw))
        if value == self._value:
            return
        self._value = value
        self._emit_progress(value, self.scale)

    def complete(self) -> None:
        """publish 100% progress."""

        if self._value == self.scale:
            return
        self._value = self.scale
        self._emit_progress(self.scale, self.scale)


def _advance_star_fade_state(renderer: FrameRenderer, time_seconds: float) -> None:
    """
    advance export star fade continuity without rendering pixels.

    renderer
        frame renderer owning the star field
    time_seconds
        animation time to apply
    """

    renderer.stars.field.project_at_time(
        time_seconds,
        renderer.settings.duration_seconds,
        renderer._view_center_at_progress,
        RenderQuality.EXPORT,
    )


def _render_export_chunk(
    image_path: str,
    settings: ProjectSettings,
    start_frame: int,
    end_frame: int,
    fps: float,
    progress_counter,
    progress_lock,
    chunk_path: str,
    fade_continuous: set[int],
    fade_starts: dict[int, float],
) -> tuple[int, int, str]:
    """
    render a contiguous export range into a raw rgb file on disk.

    image_path
        absolute path to the source image
    settings
        project settings for rendering
    start_frame
        inclusive start frame index
    end_frame
        exclusive end frame index
    fps
        frames per second
    progress_counter
        shared manager counter for completed rendered frames
    progress_lock
        shared lock guarding the progress counter
    chunk_path
        destination raw rgb24 file for this chunk
    fade_continuous
        fade continuity snapshot for start_frame
    fade_starts
        fade-in start times snapshot for start_frame
    """

    source_image = load_image_bgr(image_path)
    renderer = create_renderer(source_image, settings)
    renderer.stars.field.import_fade_state(fade_continuous, fade_starts)

    with open(chunk_path, "wb") as handle:
        for frame_index in range(start_frame, end_frame):
            frame = renderer.render_frame(frame_index / fps, RenderQuality.EXPORT)
            payload = np.ascontiguousarray(frame, dtype=np.uint8).tobytes()
            handle.write(payload)
            with progress_lock:
                progress_counter.value += 1

    return start_frame, end_frame, chunk_path


class ExportWorker(QThread):
    """background export worker thread."""

    progress_changed = Signal(int, int)
    frame_progress = Signal(int, int)
    status_changed = Signal(str)
    finished_success = Signal(str)
    finished_error = Signal(str)

    _PROGRESS_SCALE = 10000

    def __init__(
        self,
        project: Project,
        output_path: Path,
        project_path: Path | None = None,
    ) -> None:
        """
        create export worker.

        project
            project to export
        output_path
            destination mp4 path
        project_path
            optional project file path for resolving images
        """

        super().__init__()
        self.project = project
        self.output_path = output_path
        self.project_path = project_path
        self._cancel_requested = False
        self._process: subprocess.Popen[bytes] | None = None
        self._pool: ProcessPoolExecutor | None = None

    def cancel(self) -> None:
        """request export cancellation and stop worker processes."""

        self._cancel_requested = True
        pool = self._pool
        if pool is not None:
            # terminate active workers; shutdown alone can leave them running
            processes = getattr(pool, "_processes", None)
            if isinstance(processes, dict):
                for process in list(processes.values()):
                    with suppress(OSError, AssertionError):
                        process.terminate()
            pool.shutdown(wait=False, cancel_futures=True)
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()

    def run(self) -> None:
        """run export in background thread."""

        try:
            self._export()
        except Exception as exc:
            if self._cancel_requested:
                self._cleanup_partial_output()
                self.finished_error.emit(EXPORT_CANCELLED)
                return
            self._cleanup_partial_output()
            self.finished_error.emit(str(exc))

    def _cleanup_partial_output(self) -> None:
        """remove partial output file if export failed."""

        if self.output_path.exists():
            try:
                self.output_path.unlink()
            except OSError:
                pass

    def _write_chunk_file(
        self,
        process: subprocess.Popen[bytes],
        chunk_path: str,
        frame_count: int,
        frame_nbytes: int,
        stderr_log: BufferedIOBase,
    ) -> None:
        """
        stream one raw chunk file into ffmpeg stdin.

        process
            ffmpeg process
        chunk_path
            raw rgb24 chunk file
        frame_count
            number of frames stored in the file
        frame_nbytes
            bytes per frame
        stderr_log
            ffmpeg stderr capture
        """

        try:
            expected_bytes = frame_count * frame_nbytes
            actual_bytes = Path(chunk_path).stat().st_size
            if actual_bytes != expected_bytes:
                raise RuntimeError(
                    self.tr(
                        "A rendered chunk has an invalid size "
                        "({actual_bytes} instead of {expected_bytes})."
                    ).format(actual_bytes=actual_bytes, expected_bytes=expected_bytes)
                )
            if process.stdin is None:
                raise RuntimeError(self.tr("FFmpeg could not be started."))
            with open(chunk_path, "rb") as handle:
                while True:
                    payload = handle.read(min(frame_nbytes * 8, expected_bytes))
                    if not payload:
                        break
                    process.stdin.write(payload)
            process.stdin.flush()
        except BrokenPipeError as exc:
            stderr = self._read_ffmpeg_stderr(stderr_log)
            raise RuntimeError(
                self.tr("FFmpeg error: {error}").format(error=stderr or exc)
            ) from exc

    def _build_fade_snapshots(
        self,
        image_path: Path,
        settings: ProjectSettings,
        total_frames: int,
        fps: float,
        chunk_starts: set[int],
        worker_count: int,
        progress: _WallClockProgress,
    ) -> dict[int, tuple[set[int], dict[int, float]]]:
        """
        build fade-state snapshots while updating wall-clock export progress.

        image_path
            source image path
        settings
            project settings
        total_frames
            total export frame count
        fps
            frames per second
        chunk_starts
            inclusive frame indices where chunks begin
        worker_count
            parallel render worker count used for render-time estimate
        progress
            shared monotonic wall-clock progress tracker
        """

        self.status_changed.emit("preparing")
        source_image = load_image_bgr(str(image_path))
        renderer = create_renderer(source_image, settings)
        snapshots: dict[int, tuple[set[int], dict[int, float]]] = {
            0: renderer.stars.field.export_fade_state(),
        }

        def save_snapshot_after(frame_index: int) -> None:
            """store fade state for the next chunk start if needed."""

            next_frame = frame_index + 1
            if next_frame in chunk_starts:
                snapshots[next_frame] = renderer.stars.field.export_fade_state()

        load_t0 = time.perf_counter()
        probe_image = load_image_bgr(str(image_path))
        load_s = max(time.perf_counter() - load_t0, 1e-6)

        setup_t0 = time.perf_counter()
        probe = create_renderer(probe_image, settings)
        setup_s = max(time.perf_counter() - setup_t0, 1e-6)

        frame_samples: list[float] = []
        for sample_index in range(3):
            if self._cancel_requested:
                raise RuntimeError(EXPORT_CANCELLED)
            frame_t0 = time.perf_counter()
            probe.render_frame(sample_index / max(fps, 1.0), RenderQuality.EXPORT)
            frame_samples.append(max(time.perf_counter() - frame_t0, 1e-6))
        del probe
        if self._cancel_requested:
            raise RuntimeError(EXPORT_CANCELLED)

        avg_frame_s = sum(frame_samples) / len(frame_samples)
        # probe is single-process; real export contends across workers + ffmpeg
        effective_parallelism = max(1.0, float(worker_count) * 0.25)
        progress.set_render_estimate(
            (load_s + setup_s) + (total_frames * avg_frame_s / effective_parallelism)
        )

        fade_t0 = time.perf_counter()

        def publish_prep_progress(done_frames: int) -> None:
            """publish preparation progress from remaining fade + render estimates."""

            done_frames = max(0, min(done_frames, total_frames))
            fade_elapsed = max(time.perf_counter() - fade_t0, 1e-6)
            if done_frames <= 0:
                remaining_prep = fade_elapsed
            else:
                remaining_prep = (fade_elapsed / done_frames) * max(
                    0,
                    total_frames - done_frames,
                )
            progress.update(remaining_prep + progress.render_estimate_s)

        for frame_index in range(total_frames):
            if self._cancel_requested:
                raise RuntimeError(EXPORT_CANCELLED)
            _advance_star_fade_state(renderer, frame_index / fps)
            save_snapshot_after(frame_index)
            done = frame_index + 1
            if done == total_frames or done % 3 == 0:
                publish_prep_progress(done)

        publish_prep_progress(total_frames)
        return snapshots

    def _export(self) -> None:
        """perform ffmpeg export."""

        image_path = resolve_source_image_path(self.project_path, self.project.source_image)
        if image_path is None or not image_path.exists():
            raise RuntimeError("The image was not found.")

        settings = self.project.settings
        width = settings.resolution.width
        height = settings.resolution.height
        fps = settings.fps
        total_frames = max(1, round(settings.duration_seconds * fps))
        crf = settings.export.crf
        worker_count = _export_worker_count()
        frame_nbytes = width * height * 3

        ffmpeg_path = ffmpeg_executable()
        if ffmpeg_path is None:
            raise RuntimeError(
                self.tr(
                    "FFmpeg was not found. Install FFmpeg and make sure it is available on PATH."
                )
            )

        command = [
            ffmpeg_path,
            "-hide_banner",
            "-nostats",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{width}x{height}",
            "-r",
            str(fps),
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            str(crf),
            "-preset",
            "medium",
            str(self.output_path),
        ]

        chunk_count = min(worker_count, total_frames)
        chunk_size = math.ceil(total_frames / chunk_count)
        ranges: list[tuple[int, int]] = []
        for start in range(0, total_frames, chunk_size):
            end = min(total_frames, start + chunk_size)
            ranges.append((start, end))
        chunk_starts = {start for start, _end in ranges}

        progress = _WallClockProgress(
            self._PROGRESS_SCALE,
            self.progress_changed.emit,
        )
        fade_snapshots = self._build_fade_snapshots(
            image_path,
            settings,
            total_frames,
            float(fps),
            chunk_starts,
            chunk_count,
            progress,
        )
        missing = chunk_starts - set(fade_snapshots.keys())
        if missing:
            raise RuntimeError(
                self.tr("Fade snapshots are missing for chunk starts: {starts}").format(
                    starts=sorted(missing),
                )
            )

        self.status_changed.emit("rendering")
        self.frame_progress.emit(0, total_frames)
        # keep the bar moving with render-only remaining; never reset/jump back
        progress.update(progress.render_estimate_s)

        temp_dir = tempfile.mkdtemp(prefix="starflight_export_")
        try:
            with tempfile.TemporaryFile(mode="w+b") as stderr_log:
                # The command is a fixed argument list and never invokes a shell.
                process = subprocess.Popen(
                    command,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=stderr_log,
                )
                self._process = process

                if process.stdin is None:
                    raise RuntimeError(self.tr("FFmpeg could not be started."))

                last_frame_emitted = -1
                render_t0 = time.perf_counter()

                def emit_render_progress(rendered: int) -> None:
                    """publish render progress from remaining render wall time."""

                    nonlocal last_frame_emitted
                    rendered = max(0, min(int(rendered), total_frames))
                    render_elapsed = max(time.perf_counter() - render_t0, 1e-6)
                    if rendered <= 0:
                        remaining_render = progress.render_estimate_s
                    elif rendered >= total_frames:
                        remaining_render = 0.0
                    else:
                        remaining_render = (render_elapsed / rendered) * (
                            total_frames - rendered
                        )
                        # refine estimate for later updates while workers warm up
                        progress.set_render_estimate(
                            (render_elapsed / rendered) * total_frames
                        )
                    progress.update(remaining_render)
                    if rendered != last_frame_emitted:
                        last_frame_emitted = rendered
                        self.frame_progress.emit(rendered, total_frames)

                with Manager() as manager:
                    progress_counter = manager.Value("i", 0)
                    progress_lock = manager.Lock()
                    chunk_results: dict[int, tuple[int, str]] = {}

                    try:
                        with ProcessPoolExecutor(
                            max_workers=chunk_count,
                            mp_context=get_context("spawn"),
                        ) as pool:
                            self._pool = pool
                            futures = {
                                pool.submit(
                                    _render_export_chunk,
                                    str(image_path),
                                    settings,
                                    start,
                                    end,
                                    float(fps),
                                    progress_counter,
                                    progress_lock,
                                    str(Path(temp_dir) / f"chunk_{start:06d}.rgb"),
                                    fade_snapshots[start][0],
                                    fade_snapshots[start][1],
                                ): start
                                for start, end in ranges
                            }
                            pending = set(futures.keys())
                            next_write_start_index = 0

                            while pending or next_write_start_index < len(ranges):
                                if self._cancel_requested:
                                    process.terminate()
                                    self._cleanup_partial_output()
                                    self.finished_error.emit(EXPORT_CANCELLED)
                                    return

                                emit_render_progress(progress_counter.value)

                                if pending:
                                    done, pending = wait(
                                        pending,
                                        timeout=0.1,
                                        return_when=FIRST_COMPLETED,
                                    )
                                    for future in done:
                                        start_frame, end_frame, chunk_path = future.result()
                                        chunk_results[start_frame] = (end_frame, chunk_path)
                                else:
                                    time.sleep(0.05)

                                while next_write_start_index < len(ranges):
                                    start, _end = ranges[next_write_start_index]
                                    if start not in chunk_results:
                                        break
                                    end_frame, chunk_path = chunk_results.pop(start)
                                    frame_count = end_frame - start
                                    self._write_chunk_file(
                                        process,
                                        chunk_path,
                                        frame_count,
                                        frame_nbytes,
                                        stderr_log,
                                    )
                                    try:
                                        Path(chunk_path).unlink(missing_ok=True)
                                    except OSError:
                                        pass
                                    next_write_start_index += 1
                                    emit_render_progress(progress_counter.value)
                    finally:
                        self._pool = None

                    emit_render_progress(total_frames)

                process.stdin.close()
                return_code = process.wait()
                stderr = self._read_ffmpeg_stderr(stderr_log)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        if self._cancel_requested:
            self._cleanup_partial_output()
            self.finished_error.emit(EXPORT_CANCELLED)
            return

        if return_code != 0:
            self._cleanup_partial_output()
            raise RuntimeError(
                self.tr("FFmpeg error: {error}").format(
                    error=stderr or self.tr("Unknown error"),
                )
            )

        progress.complete()
        self.finished_success.emit(str(self.output_path))

    @staticmethod
    def _read_ffmpeg_stderr(stderr_log: BufferedIOBase) -> str:
        """
        read captured ffmpeg stderr output.

        stderr_log
            temporary file receiving ffmpeg stderr
        """

        stderr_log.seek(0)
        return stderr_log.read().decode("utf-8", errors="ignore")
