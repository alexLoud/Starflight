"""Shared immutable preview inputs exchanged across services and workers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from starflight.types.settings import ProjectSettings


@dataclass(slots=True)
class PreparedParallaxPreview:
    """Snapshot inputs used to render low-resolution parallax frames on demand."""

    source_image_bgr: np.ndarray
    settings: ProjectSettings
    disparity: np.ndarray


@dataclass(slots=True)
class PlaybackRenderSpec:
    """Immutable inputs shared by playback-preview render processes."""

    image_path: str
    settings: ProjectSettings
    crop_target_size: tuple[int, int]
    include_stars: bool
    parallax_preview: PreparedParallaxPreview | None = None
