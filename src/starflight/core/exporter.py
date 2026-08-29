"""Render video frames in worker processes and stream them to FFmpeg.

The exporter prepares star fade state before splitting the frame range. Each process writes one
ordered chunk so the main export thread can feed FFmpeg without keeping full frames in memory.
"""

from __future__ import annotations

import errno
import math
import os
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
from starflight.core.camera_motion import camera_motion_progress
from starflight.core.parallax import (
    create_parallax_depth,
    prepare_parallax_depth_v4,
    prepare_parallax_render_input,
)
from starflight.core.project import resolve_source_image_path
from starflight.core.renderer import FrameRenderer, create_renderer
from starflight.types.settings import (
    ImageMotionMode,
    Project,
    ProjectSettings,
    RenderQuality,
)
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


_prepare_parallax_render_input = prepare_parallax_render_input


_PREP_BAND_FRACTION = 0.10


class _ExportProgressTracker:
    """map export phases to fixed ui bands: prep 0-10%, render 10-100%."""

    def __init__(
        self,
        scale: int,
        emit_progress: Callable[[int, int], None],
        *,
        total_frames: int,
        has_parallax: bool,
        star_units: float,
        encode_units: float,
    ) -> None:
        """
        create a unified export progress tracker.

        scale
            integer progress scale (e.g. 10000)
        emit_progress
            callback(current: int, total: int)
        total_frames
            number of frames in the export
        has_parallax
            whether parallax depth is prepared before export
        star_units
            measured star-prep work units from timing probe (encode estimate only)
        encode_units
            estimated encode work units derived from render probe timing
        """

        self.scale = scale
        self._emit_progress = emit_progress
        self._value = 0
        self._total_frames = max(1, total_frames)
        self._has_parallax = has_parallax
        self._prep_cap = max(1, round(scale * _PREP_BAND_FRACTION))
        self._render_floor = self._prep_cap
        self._render_ceil = scale - 1
        self._render_units = float(self._total_frames)
        self._star_units = max(1.0, float(star_units))
        self._encode_units = max(1.0, float(encode_units))
        self._encode_base_value: int | None = None
        self._parallax_fraction = 0.0
        self._star_fraction = 0.0
        self._render_fraction = 0.0

    @property
    def total_frames(self) -> int:
        """return the export frame count tracked for render progress."""

        return self._total_frames

    def _prep_value(self) -> int:
        """return progress value for the preparation band (0 to prep cap)."""

        if self._has_parallax:
            fraction = self._parallax_fraction
        else:
            fraction = self._star_fraction
        return round(self._prep_cap * max(0.0, min(1.0, fraction)))

    def _render_value(self) -> int:
        """return progress value for the render band (prep cap to render ceil)."""

        if self._render_fraction <= 0.0:
            return self._render_floor
        span = max(1, self._render_ceil - self._render_floor)
        return self._render_floor + round(span * min(1.0, self._render_fraction))

    def _publish(self) -> None:
        """emit monotonic progress from fixed prep and render bands."""

        if self._render_fraction > 0.0:
            raw = self._render_value()
        else:
            raw = self._prep_value()
        value = max(self._value, min(self._render_ceil, raw))
        if value == self._value:
            return
        self._value = value
        self._emit_progress(value, self.scale)

    def report_parallax(self, fraction: float) -> None:
        """
        report parallax preparation progress.

        fraction
            normalized parallax completion from 0.0 to 1.0
        """

        fraction = max(0.0, min(float(fraction), 1.0))
        self._parallax_fraction = max(self._parallax_fraction, fraction)
        self._publish()

    def report_parallax_timed(
        self,
        elapsed_s: float,
        fraction: float,
        avg_render_s: float,
    ) -> None:
        """
        report parallax progress (ui uses fraction only; timing args ignored).

        elapsed_s
            elapsed parallax preparation time in seconds
        fraction
            normalized parallax completion from 0.0 to 1.0
        avg_render_s
            measured average render seconds per frame from timing probe
        """

        del elapsed_s, avg_render_s
        self.report_parallax(fraction)

    def finalize_parallax(self, elapsed_s: float, avg_render_s: float) -> None:
        """
        mark parallax preparation complete.

        elapsed_s
            total parallax preparation time in seconds
        avg_render_s
            measured average render seconds per frame from timing probe
        """

        del elapsed_s, avg_render_s
        self._parallax_fraction = 1.0
        self._publish()

    def refine_parallax_weight(self, avg_render_s: float) -> None:
        """
        no-op kept for export flow compatibility after post-parallax probe.

        avg_render_s
            updated average render seconds per frame
        """

        del avg_render_s

    def report_star_frames(self, done_frames: int) -> None:
        """
        report star fade preparation progress.

        done_frames
            number of prepared star frames
        """

        done_frames = max(0, min(int(done_frames), self._total_frames))
        self._star_fraction = done_frames / self._total_frames
        if self._has_parallax:
            return
        if done_frames >= self._total_frames:
            self._publish()

    def report_render_frames(self, done_frames: int) -> int:
        """
        report rendered frame progress.

        done_frames
            number of completed export frames

        Returns:
            clamped rendered frame count
        """

        done_frames = max(0, min(int(done_frames), self._total_frames))
        self._render_fraction = done_frames / self._total_frames
        self._publish()
        return done_frames

    def finish_render_phase(self) -> None:
        """mark all render frames complete before encode progress begins."""

        self._render_fraction = 1.0
        self._publish()

    def report_encode(self, fraction: float) -> None:
        """
        report ffmpeg encode progress.

        fraction
            normalized encode completion from 0.0 to 1.0
        """

        fraction = max(0.0, min(float(fraction), 1.0))
        if self._encode_base_value is None:
            self.finish_render_phase()
            self._encode_base_value = self._value
        target = self._encode_base_value + round(
            (self.scale - self._encode_base_value) * fraction
        )
        value = max(self._value, min(self.scale, target))
        if value == self._value:
            return
        self._value = value
        self._emit_progress(value, self.scale)

    def set_work_unit_weights(self, *, star_units: float, encode_units: float) -> None:
        """
        refine encode estimate weights after export timing probe.

        star_units
            measured star-prep work units
        encode_units
            estimated encode work units
        """

        self._star_units = max(1.0, float(star_units))
        self._encode_units = max(1.0, float(encode_units))

    def set_encode_units(self, encode_units: float) -> None:
        """
        refine encode work units after render timing probe.

        encode_units
            estimated encode work units derived from render probe timing
        """

        self.set_work_unit_weights(star_units=self._star_units, encode_units=encode_units)

    def encode_estimate_seconds(self, render_elapsed_s: float) -> float:
        """
        estimate ffmpeg encode duration from measured render duration.

        render_elapsed_s
            measured render phase duration in seconds
        """

        if self._render_units <= 0.0:
            return max(render_elapsed_s, 1e-6)
        return max(render_elapsed_s * (self._encode_units / self._render_units), 1e-6)

    def complete(self) -> None:
        """publish 100% progress."""

        if self._value == self.scale:
            return
        self._parallax_fraction = 1.0
        self._star_fraction = 1.0
        self._render_fraction = 1.0
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
        renderer.view_center_at_progress,
        RenderQuality.EXPORT,
        camera_motion_progress(
            time_seconds,
            renderer.settings.duration_seconds,
            renderer.settings.background,
            renderer.settings.stars.speed,
        ),
    )


_export_process_renderer: FrameRenderer | None = None


def _initialize_export_process(
    image_path: str,
    settings: ProjectSettings,
    parallax_depth: np.ndarray | None,
) -> None:
    """Create one reusable renderer inside each export worker process."""

    global _export_process_renderer

    source_image = load_image_bgr(image_path)
    source_image, render_settings = _prepare_parallax_render_input(source_image, settings)
    _export_process_renderer = create_renderer(
        source_image,
        render_settings,
        parallax_depth=parallax_depth,
    )


def _render_export_chunk(
    start_frame: int,
    end_frame: int,
    fps: float,
    chunk_path: str,
    fade_continuous: set[int],
    fade_starts: dict[int, float],
    progress_counter,
    progress_lock,
) -> tuple[int, int, str, int]:
    """
    render a contiguous export range into a raw rgb file on disk.

    start_frame
        inclusive start frame index
    end_frame
        exclusive end frame index
    fps
        frames per second
    chunk_path
        destination raw rgb24 file for this chunk
    fade_continuous
        fade continuity snapshot for start_frame
    fade_starts
        fade-in start times snapshot for start_frame
    progress_counter
        shared counter for completed rendered frames
    progress_lock
        shared lock guarding the progress counter
    """

    if _export_process_renderer is None:
        raise RuntimeError("export renderer was not initialized")

    renderer = _export_process_renderer
    renderer.stars.field.import_fade_state(fade_continuous, fade_starts)

    frame_count = end_frame - start_frame
    with open(chunk_path, "wb") as handle:
        for frame_index in range(start_frame, end_frame):
            frame = renderer.render_frame(frame_index / fps, RenderQuality.EXPORT)
            payload = np.ascontiguousarray(frame, dtype=np.uint8).tobytes()
            handle.write(payload)
            with progress_lock:
                progress_counter.value += 1

    return start_frame, end_frame, chunk_path, frame_count


def _create_export_staging_path(output_path: Path) -> Path:
    """Return a temporary export file in the destination folder."""

    output_path = output_path.expanduser()
    parent = output_path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, raw_path = tempfile.mkstemp(
        suffix=output_path.suffix,
        prefix=f".{output_path.stem}_",
        dir=parent,
    )
    os.close(fd)
    return Path(raw_path)


class ExportWorker(QThread):
    """background export worker thread."""

    progress_changed = Signal(int, int)
    frame_progress = Signal(int, int)
    status_changed = Signal(str)
    finished_success = Signal(str)
    finished_error = Signal(object)

    _PROGRESS_SCALE = 100

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
        self._staging_path: Path | None = None

    def cancel(self) -> None:
        """request export cancellation and stop worker processes."""

        self._cancel_requested = True
        pool = self._pool
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)
        if self._process is not None and self._process.poll() is None:
            self._process.terminate()

    def run(self) -> None:
        """run export in background thread."""

        try:
            self._export()
        except Exception as exc:
            if self._cancel_requested:
                self._cleanup_staging_output()
                self.finished_error.emit(EXPORT_CANCELLED)
                return
            self._cleanup_staging_output()
            self.finished_error.emit(exc)

    def _cleanup_staging_output(self) -> None:
        """remove the temporary export file when rendering fails or is cancelled."""

        staging_path = self._staging_path
        if staging_path is None:
            return
        if staging_path.exists():
            with suppress(OSError):
                staging_path.unlink()
        self._staging_path = None

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
        progress: _ExportProgressTracker,
        avg_render_s: float,
    ) -> np.ndarray:
        """
        build parallax depth while publishing monotonic export progress.

        source_image
            loaded bgr source image
        focus
            normalized parallax focus point
        progress
            unified export progress tracker
        avg_render_s
            measured average render seconds per frame from timing probe
        """

        parallax_t0 = time.perf_counter()

        def on_parallax_progress(fraction: float) -> None:
            if self._cancel_requested:
                raise RuntimeError(EXPORT_CANCELLED)
            elapsed = time.perf_counter() - parallax_t0
            progress.report_parallax_timed(elapsed, 0.75 * fraction, avg_render_s)

        raw_depth = create_parallax_depth(
            source_image,
            focus,
            on_progress=on_parallax_progress,
        )

        def on_v4_progress(fraction: float) -> None:
            if self._cancel_requested:
                raise RuntimeError(EXPORT_CANCELLED)
            elapsed = time.perf_counter() - parallax_t0
            progress.report_parallax_timed(elapsed, 0.75 + 0.25 * fraction, avg_render_s)

        depth = prepare_parallax_depth_v4(
            raw_depth,
            on_progress=on_v4_progress,
        )
        progress.finalize_parallax(time.perf_counter() - parallax_t0, avg_render_s)
        return depth

    @staticmethod
    def _probe_export_timing(
        image_path: Path,
        settings: ProjectSettings,
        fps: float,
        total_frames: int,
        parallax_depth: np.ndarray | None,
    ) -> tuple[float, float, float]:
        """
        probe star prep and render timing to derive work unit weights.

        image_path
            source image path
        settings
            project settings
        fps
            frames per second
        total_frames
            total export frame count
        parallax_depth
            optional prepared parallax depth map

        Returns:
            average render seconds per frame, star work units, encode work units
        """

        source_image = load_image_bgr(str(image_path))
        source_image, render_settings = _prepare_parallax_render_input(source_image, settings)
        renderer = create_renderer(
            source_image,
            render_settings,
            parallax_depth=parallax_depth,
        )

        star_samples: list[float] = []
        for sample_index in range(3):
            star_t0 = time.perf_counter()
            _advance_star_fade_state(renderer, sample_index / max(fps, 1.0))
            star_samples.append(max(time.perf_counter() - star_t0, 1e-6))

        frame_samples: list[float] = []
        for sample_index in range(3):
            frame_t0 = time.perf_counter()
            renderer.render_frame(sample_index / max(fps, 1.0), RenderQuality.EXPORT)
            frame_samples.append(max(time.perf_counter() - frame_t0, 1e-6))
        del renderer

        avg_star_s = sum(star_samples) / len(star_samples)
        avg_render_s = sum(frame_samples) / len(frame_samples)
        star_units = max(1.0, total_frames * avg_star_s / max(avg_render_s, 1e-6))
        encode_units = max(1.0, total_frames * avg_render_s)
        return avg_render_s, star_units, encode_units

    def _build_fade_snapshots(
        self,
        image_path: Path,
        settings: ProjectSettings,
        total_frames: int,
        fps: float,
        chunk_starts: set[int],
        progress: _ExportProgressTracker,
        parallax_depth: np.ndarray | None,
    ) -> dict[int, tuple[set[int], dict[int, float]]]:
        """
        build fade-state snapshots while updating export progress.

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
        progress
            unified export progress tracker
        parallax_depth
            optional prepared parallax depth map
        """

        self.status_changed.emit("preparing")
        progress.report_star_frames(0)
        source_image = load_image_bgr(str(image_path))
        source_image, render_settings = _prepare_parallax_render_input(source_image, settings)
        renderer = create_renderer(
            source_image,
            render_settings,
            parallax_depth=parallax_depth,
        )
        snapshots: dict[int, tuple[set[int], dict[int, float]]] = {
            0: renderer.stars.field.export_fade_state(),
        }

        def save_snapshot_after(frame_index: int) -> None:
            """store fade state for the next chunk start if needed."""

            next_frame = frame_index + 1
            if next_frame in chunk_starts:
                snapshots[next_frame] = renderer.stars.field.export_fade_state()

        for frame_index in range(total_frames):
            if self._cancel_requested:
                raise RuntimeError(EXPORT_CANCELLED)
            _advance_star_fade_state(renderer, frame_index / fps)
            save_snapshot_after(frame_index)
            done = frame_index + 1
            if done == total_frames or done % 3 == 0:
                progress.report_star_frames(done)

        progress.report_star_frames(total_frames)
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

        staging_path = _create_export_staging_path(self.output_path)
        self._staging_path = staging_path

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
            _ffmpeg_output_arg(staging_path),
        ]

        chunk_count = min(worker_count, total_frames)
        chunk_size = math.ceil(total_frames / chunk_count)
        ranges: list[tuple[int, int]] = []
        for start in range(0, total_frames, chunk_size):
            end = min(total_frames, start + chunk_size)
            ranges.append((start, end))
        chunk_starts = {start for start, _end in ranges}

        has_parallax = settings.background.motion_mode == ImageMotionMode.PARALLAX
        parallax_depth = None
        _avg_render_s, star_units, encode_units = self._probe_export_timing(
            image_path,
            settings,
            float(fps),
            total_frames,
            None,
        )
        progress = _ExportProgressTracker(
            self._PROGRESS_SCALE,
            self.progress_changed.emit,
            total_frames=total_frames,
            has_parallax=has_parallax,
            star_units=star_units,
            encode_units=encode_units,
        )

        if has_parallax:
            self.status_changed.emit("parallax")
            source_image = load_image_bgr(str(image_path))
            source_image, _render_settings = _prepare_parallax_render_input(
                source_image,
                settings,
            )
            parallax_depth = self._create_parallax_depth_with_progress(
                source_image,
                (0.5, 0.5),
                progress,
                _avg_render_s,
            )
            del source_image
            _avg_render_s, star_units, encode_units = self._probe_export_timing(
                image_path,
                settings,
                float(fps),
                total_frames,
                parallax_depth,
            )
            progress.set_work_unit_weights(star_units=star_units, encode_units=encode_units)
            progress.refine_parallax_weight(_avg_render_s)

        fade_snapshots = self._build_fade_snapshots(
            image_path,
            settings,
            total_frames,
            float(fps),
            chunk_starts,
            progress,
            parallax_depth,
        )
        missing = chunk_starts - set(fade_snapshots.keys())
        if missing:
            raise RuntimeError(
                self.tr("Fade snapshots are missing for chunk starts: {starts}").format(
                    starts=sorted(missing),
                )
            )

        self.status_changed.emit("rendering_workers")
        render_t0 = time.perf_counter()
        encode_estimate_s = encode_units * _avg_render_s

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
                rendering_status_set = False

                def emit_render_progress(rendered: int) -> None:
                    """publish render progress from completed frames."""

                    nonlocal last_frame_emitted, rendering_status_set
                    rendered = progress.report_render_frames(rendered)
                    if rendered > 0 and not rendering_status_set:
                        rendering_status_set = True
                        self.status_changed.emit("rendering")
                    if rendered != last_frame_emitted and (
                        rendered == total_frames or rendered % 3 == 0 or rendered <= 3
                    ):
                        last_frame_emitted = rendered
                        self.frame_progress.emit(rendered, total_frames)

                chunk_results: dict[int, tuple[int, str]] = {}

                with Manager() as manager:
                    progress_counter = manager.Value("i", 0)
                    progress_lock = manager.Lock()

                    try:
                        with ProcessPoolExecutor(
                            max_workers=chunk_count,
                            mp_context=get_context("spawn"),
                            initializer=_initialize_export_process,
                            initargs=(str(image_path), settings, parallax_depth),
                        ) as pool:
                            self._pool = pool
                            futures = {
                                pool.submit(
                                    _render_export_chunk,
                                    start,
                                    end,
                                    float(fps),
                                    str(Path(temp_dir) / f"chunk_{start:06d}.rgb"),
                                    fade_snapshots[start][0],
                                    fade_snapshots[start][1],
                                    progress_counter,
                                    progress_lock,
                                ): start
                                for start, end in ranges
                            }
                            pending = set(futures.keys())
                            next_write_start_index = 0

                            while pending or next_write_start_index < len(ranges):
                                if self._cancel_requested:
                                    process.terminate()
                                    self._cleanup_staging_output()
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
                                        start_frame, end_frame, chunk_path, _frame_count = (
                                            future.result()
                                        )
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
                progress.finish_render_phase()
                render_elapsed_s = max(time.perf_counter() - render_t0, 1e-6)
                encode_estimate_s = progress.encode_estimate_seconds(render_elapsed_s)

                process.stdin.close()
                self.status_changed.emit("encoding")
                encode_t0 = time.perf_counter()
                while process.poll() is None:
                    if self._cancel_requested:
                        process.terminate()
                        self._cleanup_staging_output()
                        self.finished_error.emit(EXPORT_CANCELLED)
                        return
                    encode_elapsed = max(time.perf_counter() - encode_t0, 0.0)
                    progress.report_encode(
                        min(0.99, encode_elapsed / max(encode_estimate_s, 1e-6))
                    )
                    time.sleep(0.1)
                progress.report_encode(1.0)
                return_code = process.returncode
                stderr = self._read_ffmpeg_stderr(stderr_log)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

        if self._cancel_requested:
            self._cleanup_staging_output()
            self.finished_error.emit(EXPORT_CANCELLED)
            return

        if return_code != 0:
            self._cleanup_staging_output()
            raise RuntimeError(
                self.tr("FFmpeg error: {error}").format(
                    error=stderr or self.tr("Unknown error"),
                )
            )

        try:
            staging_path.replace(self.output_path)
        except OSError as exc:
            self._cleanup_staging_output()
            raise RuntimeError(
                self.tr("The export file could not be saved: {error}").format(error=exc)
            ) from exc
        self._staging_path = None

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
