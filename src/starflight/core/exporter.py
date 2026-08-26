"""Render video frames in worker processes and stream them to FFmpeg.

The exporter prepares star fade state before splitting the frame range. Each process writes one
ordered chunk so the main export thread can feed FFmpeg without keeping full frames in memory.
"""

from __future__ import annotations

import errno
import math
import shutil
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from contextlib import suppress
from io import BufferedIOBase
from multiprocessing import Manager, get_context
from pathlib import Path

import numpy as np
from PySide6.QtCore import QThread, Signal

from starflight.app.settings import DEFAULT_RENDER_WORKER_COUNT, max_available_render_workers
from starflight.core.background import effective_background_settings, resolve_camera_path
from starflight.core.camera_motion import camera_motion_progress
from starflight.core.crop import map_look_at_to_source
from starflight.core.parallax import (
    create_parallax_depth,
    smooth_parallax_depth_for_strength,
)
from starflight.core.project import resolve_source_image_path
from starflight.core.renderer import FrameRenderer, create_renderer
from starflight.types.settings import ImageMotionMode, Project, ProjectSettings, RenderQuality
from starflight.utils.image import load_image_bgr
from starflight.utils.validation import ffmpeg_executable

# stable machine-readable cancel token; never compare translated ui strings
EXPORT_CANCELLED = "export_cancelled"
# windows writefile rejects a single pipe write above 32 kib with einval
_PIPE_WRITE_CHUNK_SIZE = 32767


def _ffmpeg_popen_kwargs() -> dict[str, int]:
    """return extra popen kwargs so ffmpeg does not open a console on windows."""

    if sys.platform != "win32":
        return {}
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    return {"creationflags": creationflags}


def _ffmpeg_output_arg(path: Path) -> str:
    """
    return a local output path that ffmpeg can open on windows.

    path
        destination video path
    """

    resolved = path.expanduser()
    if not resolved.is_absolute():
        resolved = Path(resolved).absolute()
    if sys.platform == "win32":
        # ffmpeg treats backslashes and drive-letter urls unreliably on windows
        return f"file:{resolved.as_posix()}"
    return str(resolved)


def _is_closed_pipe_error(exc: BaseException) -> bool:
    """
    return whether a pipe write failed because the child closed stdin.

    exc
        exception raised while writing to ffmpeg stdin
    """

    if isinstance(exc, BrokenPipeError):
        return True
    if not isinstance(exc, OSError):
        return False
    if exc.errno == errno.EPIPE:
        return True
    # windows maps a closed pipe to einval instead of epipe
    return sys.platform == "win32" and exc.errno == errno.EINVAL


def _stream_file_to_pipe(source_path: str, stream: BufferedIOBase) -> None:
    """
    copy a raw file to a pipe in windows-safe chunks.

    source_path
        path to the rendered rgb24 chunk file
    stream
        destination pipe, typically ffmpeg stdin
    """

    with open(source_path, "rb") as handle:
        shutil.copyfileobj(handle, stream, length=_PIPE_WRITE_CHUNK_SIZE)


def _export_worker_count(configured: int | None = None) -> int:
    """
    choose process count for parallel export frame rendering.

    configured
        user-selected worker count; defaults to four cores capped by availability
    """

    requested = configured if configured is not None else DEFAULT_RENDER_WORKER_COUNT
    return min(max(1, requested), max_available_render_workers())


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


class _LinearProgressPhase:
    """Map normalized work in one export phase to a fixed global range."""

    def __init__(
        self,
        scale: int,
        start: int,
        end: int,
        emit_progress: Callable[[int, int], None],
    ) -> None:
        self.scale = scale
        self.start = start
        self.end = end
        self._emit_progress = emit_progress
        self._value = start - 1

    def update(self, fraction: float) -> None:
        """Publish monotonic progress for normalized phase completion 0..1."""

        amount = max(0.0, min(float(fraction), 1.0))
        value = round(self.start + (self.end - self.start) * amount)
        value = max(self._value, min(self.end, value))
        if value == self._value:
            return
        self._value = value
        self._emit_progress(value, self.scale)


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
        camera_motion_progress(
            time_seconds,
            renderer.settings.duration_seconds,
            renderer.settings.background,
            renderer.settings.stars.speed,
        ),
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
    parallax_depth: np.ndarray | None,
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
    renderer = create_renderer(source_image, settings, parallax_depth=parallax_depth)
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
    finished_error = Signal(object)

    _PROGRESS_SCALE = 10000
    _PARALLAX_PROGRESS_START = 100
    _PARALLAX_PROGRESS_END = 4500
    _STAR_PREP_PROGRESS_END = 5000
    _RENDER_PROGRESS_END = _PROGRESS_SCALE - 1

    def __init__(
        self,
        project: Project,
        output_path: Path,
        project_path: Path | None = None,
        *,
        render_workers: int | None = None,
    ) -> None:
        """
        create export worker.

        project
            project to export
        output_path
            destination mp4 path
        project_path
            optional project file path for resolving images
        render_workers
            configured parallel render worker count
        """

        super().__init__()
        self.project = project
        self.output_path = output_path
        self.project_path = project_path
        self._render_workers = render_workers
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
            self.finished_error.emit(exc)

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
        if process.poll() is not None:
            stderr = self._read_ffmpeg_stderr(stderr_log)
            raise RuntimeError(
                self.tr("FFmpeg error: {error}").format(
                    error=stderr or self.tr("Unknown error"),
                )
            )
        try:
            _stream_file_to_pipe(chunk_path, process.stdin)
            process.stdin.flush()
        except OSError as exc:
            if not _is_closed_pipe_error(exc):
                raise
            stderr = self._read_ffmpeg_stderr(stderr_log)
            raise RuntimeError(
                self.tr("FFmpeg error: {error}").format(error=stderr or exc)
            ) from exc

    def _create_parallax_depth_with_progress(
        self,
        source_image: np.ndarray,
        focus: tuple[float, float],
        progress: _LinearProgressPhase,
    ) -> np.ndarray:
        """
        build parallax depth while publishing monotonic export progress.

        source_image
            loaded bgr source image
        focus
            normalized parallax focus point
        progress
            linear progress range for parallax preparation
        """

        def on_parallax_progress(fraction: float) -> None:
            if self._cancel_requested:
                raise RuntimeError(EXPORT_CANCELLED)
            progress.update(fraction)

        depth = create_parallax_depth(
            source_image,
            focus,
            on_progress=on_parallax_progress,
        )
        on_parallax_progress(1.0)
        return depth

    def _build_fade_snapshots(
        self,
        image_path: Path,
        settings: ProjectSettings,
        total_frames: int,
        fps: float,
        chunk_starts: set[int],
        worker_count: int,
        progress: _WallClockProgress | None,
        parallax_depth: np.ndarray | None,
        phase_progress: _LinearProgressPhase | None = None,
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
            wall-clock progress tracker for exports without parallax
        phase_progress
            fixed progress range for star preparation with parallax
        """

        self.status_changed.emit("preparing")
        if phase_progress is not None:
            phase_progress.update(0.0)
        source_image = load_image_bgr(str(image_path))
        renderer = create_renderer(source_image, settings, parallax_depth=parallax_depth)
        if phase_progress is not None:
            phase_progress.update(0.15)
        snapshots: dict[int, tuple[set[int], dict[int, float]]] = {
            0: renderer.stars.field.export_fade_state(),
        }

        def save_snapshot_after(frame_index: int) -> None:
            """store fade state for the next chunk start if needed."""

            next_frame = frame_index + 1
            if next_frame in chunk_starts:
                snapshots[next_frame] = renderer.stars.field.export_fade_state()

        if progress is not None:
            load_t0 = time.perf_counter()
            probe_image = load_image_bgr(str(image_path))
            load_s = max(time.perf_counter() - load_t0, 1e-6)

            setup_t0 = time.perf_counter()
            probe = create_renderer(probe_image, settings, parallax_depth=parallax_depth)
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
            if phase_progress is not None:
                phase_progress.update(0.15 + 0.85 * done_frames / total_frames)
                return
            if progress is None:
                return
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
        worker_count = _export_worker_count(self._render_workers)
        frame_nbytes = width * height * 3

        output_parent = self.output_path.expanduser().parent
        if not output_parent.is_dir():
            self.finished_error.emit(
                self.tr("The output folder does not exist:\n{path}").format(path=output_parent)
            )
            return

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
            _ffmpeg_output_arg(self.output_path),
        ]

        chunk_count = min(worker_count, total_frames)
        chunk_size = math.ceil(total_frames / chunk_count)
        ranges: list[tuple[int, int]] = []
        for start in range(0, total_frames, chunk_size):
            end = min(total_frames, start + chunk_size)
            ranges.append((start, end))
        chunk_starts = {start for start, _end in ranges}

        progress: _WallClockProgress | None = None
        star_phase_progress: _LinearProgressPhase | None = None
        render_phase_progress: _LinearProgressPhase | None = None
        parallax_depth = None
        if settings.background.motion_mode == ImageMotionMode.PARALLAX:
            parallax_progress = _LinearProgressPhase(
                self._PROGRESS_SCALE,
                self._PARALLAX_PROGRESS_START,
                self._PARALLAX_PROGRESS_END,
                self.progress_changed.emit,
            )
            star_phase_progress = _LinearProgressPhase(
                self._PROGRESS_SCALE,
                self._PARALLAX_PROGRESS_END,
                self._STAR_PREP_PROGRESS_END,
                self.progress_changed.emit,
            )
            render_phase_progress = _LinearProgressPhase(
                self._PROGRESS_SCALE,
                self._STAR_PREP_PROGRESS_END,
                self._RENDER_PROGRESS_END,
                self.progress_changed.emit,
            )
            self.status_changed.emit("parallax")
            source_image = load_image_bgr(str(image_path))
            source_h, source_w = source_image.shape[:2]
            background_settings = effective_background_settings(settings.background)
            _start_focus, end_focus = resolve_camera_path(background_settings)
            end_focus = map_look_at_to_source(
                end_focus[0],
                end_focus[1],
                settings.crop,
                source_w,
                source_h,
                settings.resolution.width,
                settings.resolution.height,
            )
            parallax_depth = self._create_parallax_depth_with_progress(
                source_image,
                end_focus,
                parallax_progress,
            )
            parallax_depth = smooth_parallax_depth_for_strength(
                parallax_depth,
                settings.parallax.strength,
            )
            del source_image
        else:
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
            parallax_depth,
            star_phase_progress,
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
        if render_phase_progress is not None:
            render_phase_progress.update(0.0)
        elif progress is not None:
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
                    **_ffmpeg_popen_kwargs(),
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
                    if render_phase_progress is not None:
                        render_phase_progress.update(rendered / total_frames)
                    elif progress is not None:
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
                            progress.set_render_estimate((render_elapsed / rendered) * total_frames)
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
                                    parallax_depth,
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

        if progress is not None:
            progress.complete()
        else:
            self.progress_changed.emit(self._PROGRESS_SCALE, self._PROGRESS_SCALE)
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
