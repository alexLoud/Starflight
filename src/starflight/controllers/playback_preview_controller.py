"""Coordinate cached timeline playback preview generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np

from starflight.controllers.preview_controller import PreviewController
from starflight.services.playback_preview_service import (
    PlaybackFrameCache,
    PlaybackPreviewWorker,
    PlaybackRenderSpec,
    playback_sample_index,
)
from starflight.services.preview_service import PreviewService
from starflight.services.project_service import resolve_source_image_path
from starflight.types.preview import PreparedParallaxPreview
from starflight.types.settings import Project


class _PreviewPanelSizing(Protocol):
    def playback_render_size(self) -> tuple[int, int]: ...

    def preview_render_size(self) -> tuple[int, int]: ...


@dataclass(frozen=True)
class PlaybackPreparePlan:
    """Describe one playback cache fill operation."""

    sample_indices: list[int]
    start_playback: bool
    missing: list[int]
    required: list[int]


class PlaybackPreviewController:
    """Own playback cache state and worker scheduling outside the main window."""

    def __init__(
        self,
        preview_service: PreviewService,
        preview_controller: PreviewController,
        *,
        duration_seconds: float,
    ) -> None:
        self._preview_service = preview_service
        self._preview_controller = preview_controller
        self.frame_cache = PlaybackFrameCache(duration_seconds)
        self.generation = 0
        self.worker: PlaybackPreviewWorker | None = None
        self.pending: tuple[list[int], bool] | None = None
        self.starts_playback = False
        self.required_indices: list[int] = []
        self.last_sample: int | None = None

    def reset_preparation(self) -> None:
        """Clear flags for an in-flight play request."""

        self.starts_playback = False
        self.required_indices = []

    def invalidate(self, *, duration_seconds: float) -> None:
        """Discard cached playback frames whenever their visual inputs change."""

        self.generation += 1
        self.frame_cache.clear(duration_seconds)
        self.last_sample = None
        self.pending = None
        self.reset_preparation()
        if self.worker is not None:
            self.worker.request_cancel()

    def is_current(self, token: int, worker: PlaybackPreviewWorker | None = None) -> bool:
        """Return whether the token and optional worker still belong to this revision."""

        if worker is not None and worker is not self.worker:
            return False
        return token == self.generation

    def store_frame(self, sample_index: int, payload: bytes) -> None:
        """Store one encoded playback frame in the cache."""

        self.frame_cache.store(sample_index, payload)

    def sample_index_for_time(self, time_seconds: float) -> int:
        """Map timeline time to the nearest cached playback sample."""

        return playback_sample_index(time_seconds, self.frame_cache.duration_seconds)

    def frame_for_time(self, time_seconds: float) -> tuple[int, np.ndarray | None]:
        """Return the cached sample index and frame for one timeline time."""

        sample_index = self.sample_index_for_time(time_seconds)
        return sample_index, self.frame_cache.frame(sample_index)

    def should_emit_frame(self, time_seconds: float) -> tuple[bool, int]:
        """Return whether playback should show a new cached frame."""

        sample_index = self.sample_index_for_time(time_seconds)
        if sample_index == self.last_sample:
            return False, sample_index
        return True, sample_index

    def mark_sample_shown(self, sample_index: int) -> None:
        """Remember the last sample shown during playback."""

        self.last_sample = sample_index

    def clear_last_sample(self) -> None:
        """Forget the last sample shown during playback."""

        self.last_sample = None

    def background_warmup_plan(self) -> PlaybackPreparePlan:
        """Build a sparse background cache fill plan."""

        indices = self.frame_cache.background_indices()
        missing = self.frame_cache.missing(indices)
        return PlaybackPreparePlan(
            sample_indices=indices,
            start_playback=False,
            missing=missing,
            required=[],
        )

    def play_plan(self, time_seconds: float) -> PlaybackPreparePlan:
        """Build a six-fps cache fill plan from the current playhead."""

        required = self.frame_cache.playback_indices_from(time_seconds)
        missing = self.frame_cache.missing(required)
        return PlaybackPreparePlan(
            sample_indices=required,
            start_playback=True,
            missing=missing,
            required=required,
        )

    def arm_playback_prepare(self, required: list[int]) -> None:
        """Mark that timeline playback should start once required frames exist."""

        self.starts_playback = True
        self.required_indices = list(required)

    def playback_cache_ready(self) -> bool:
        """Return whether every frame required for playback is cached."""

        return not self.frame_cache.missing(self.required_indices)

    def queue_worker(self, plan: PlaybackPreparePlan) -> bool:
        """Queue follow-up work while a worker is still running."""

        if self.worker is None:
            return False
        self.worker.request_cancel()
        self.pending = (plan.sample_indices, plan.start_playback)
        if plan.start_playback:
            self.starts_playback = True
            self.required_indices = list(plan.required)
        return True

    def attach_worker(
        self,
        worker: PlaybackPreviewWorker,
        *,
        start_playback: bool,
        required: list[int],
    ) -> int:
        """Track one active worker for the current generation."""

        self.worker = worker
        self.starts_playback = start_playback
        self.required_indices = list(required) if start_playback else []
        return self.generation

    def detach_worker(self) -> tuple[tuple[list[int], bool] | None, bool]:
        """
        Drop the active worker.

        returns queued follow-up work and whether preparing state should reset
        """

        self.worker = None
        should_reset = self.starts_playback and not self.playback_cache_ready()
        pending = self.pending
        self.pending = None
        if should_reset:
            self.reset_preparation()
        return pending, should_reset

    def cancel_active_worker(self) -> PlaybackPreviewWorker | None:
        """Cancel the active worker without clearing the cached frames."""

        worker = self.worker
        self.generation += 1
        self.pending = None
        self.reset_preparation()
        if worker is not None:
            worker.request_cancel()
        return worker

    def build_render_spec(
        self,
        project: Project,
        project_path: Path | None,
        preview_panel: _PreviewPanelSizing,
        *,
        crop_target_size: tuple[int, int],
        include_stars: bool,
        parallax_preview_enabled: bool,
    ) -> PlaybackRenderSpec | None:
        """Snapshot the inputs needed by background playback renderers."""

        validation = self._preview_service.validate(project, project_path)
        if not validation.ok:
            return None
        image_path = resolve_source_image_path(project_path, project.source_image)
        if image_path is None:
            return None

        settings = self._preview_controller.build_preview_settings(
            project,
            preview_panel,
            playback=True,
        )
        parallax_preview: PreparedParallaxPreview | None = None
        if parallax_preview_enabled:
            parallax_preview = self._preview_service.prepared_parallax_preview
        return PlaybackRenderSpec(
            image_path=str(image_path),
            settings=settings,
            crop_target_size=crop_target_size,
            include_stars=include_stars,
            parallax_preview=parallax_preview,
        )


__all__ = ["PlaybackPreparePlan", "PlaybackPreviewController"]
