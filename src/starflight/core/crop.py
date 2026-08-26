"""Resolve and extract a fixed-aspect source-image crop."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from starflight.types.settings import CropSettings


@dataclass(frozen=True)
class NormalizedCropRect:
    """Crop rectangle in normalized source-image coordinates."""

    x: float
    y: float
    width: float
    height: float


def resolve_crop_rect(
    settings: CropSettings,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> NormalizedCropRect:
    """Return a clamped crop with the target frame aspect ratio."""

    source_width = max(1, int(source_width))
    source_height = max(1, int(source_height))
    target_width = max(1, int(target_width))
    target_height = max(1, int(target_height))

    source_aspect = source_width / source_height
    target_aspect = target_width / target_height
    if source_aspect >= target_aspect:
        maximum_width = target_aspect / source_aspect
        maximum_height = 1.0
    else:
        maximum_width = 1.0
        maximum_height = source_aspect / target_aspect

    scale = max(0.01, min(1.0, float(settings.scale)))
    width = maximum_width * scale
    height = maximum_height * scale
    half_width = width / 2.0
    half_height = height / 2.0
    center_x = max(half_width, min(1.0 - half_width, float(settings.center_x)))
    center_y = max(half_height, min(1.0 - half_height, float(settings.center_y)))
    return NormalizedCropRect(
        x=center_x - half_width,
        y=center_y - half_height,
        width=width,
        height=height,
    )


def map_look_at_to_source(
    look_x: float,
    look_y: float,
    settings: CropSettings,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> tuple[float, float]:
    """Map a 0..1 look-at from the active image area into full-source coordinates."""

    look_x = max(0.0, min(1.0, float(look_x)))
    look_y = max(0.0, min(1.0, float(look_y)))
    rect = resolve_crop_rect(
        settings,
        source_width,
        source_height,
        target_width,
        target_height,
    )
    return (
        rect.x + look_x * rect.width,
        rect.y + look_y * rect.height,
    )


def map_look_at_from_source(
    source_x: float,
    source_y: float,
    settings: CropSettings,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> tuple[float, float]:
    """Map a full-source look-at back into the active crop coordinate space."""

    rect = resolve_crop_rect(
        settings,
        source_width,
        source_height,
        target_width,
        target_height,
    )
    look_x = (float(source_x) - rect.x) / max(rect.width, 1e-6)
    look_y = (float(source_y) - rect.y) / max(rect.height, 1e-6)
    return (
        max(0.0, min(1.0, look_x)),
        max(0.0, min(1.0, look_y)),
    )


def remap_look_at_for_crop(
    look_x: float,
    look_y: float,
    old_crop: CropSettings,
    new_crop: CropSettings,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> tuple[float, float]:
    """Keep a crop-local look-at on the same source pixel after the crop changes."""

    source_x, source_y = map_look_at_to_source(
        look_x,
        look_y,
        old_crop,
        source_width,
        source_height,
        target_width,
        target_height,
    )
    return map_look_at_from_source(
        source_x,
        source_y,
        new_crop,
        source_width,
        source_height,
        target_width,
        target_height,
    )


def framing_base_scale(
    settings: CropSettings,
    source_width: int,
    source_height: int,
    output_width: int,
    output_height: int,
    target_width: int,
    target_height: int,
) -> float:
    """Return the source-to-output scale that fills the frame with the active window."""

    output_width = max(1, int(output_width))
    output_height = max(1, int(output_height))
    rect = resolve_crop_rect(
        settings,
        source_width,
        source_height,
        target_width,
        target_height,
    )
    return output_width / max(1e-6, rect.width * max(1, int(source_width)))


def crop_pixel_bounds(
    settings: CropSettings,
    source_width: int,
    source_height: int,
    target_width: int,
    target_height: int,
) -> tuple[int, int, int, int]:
    """Return deterministic integer slice bounds for a resolved crop."""

    rect = resolve_crop_rect(
        settings,
        source_width,
        source_height,
        target_width,
        target_height,
    )
    left = max(0, min(source_width - 1, round(rect.x * source_width)))
    top = max(0, min(source_height - 1, round(rect.y * source_height)))
    right = max(left + 1, min(source_width, round((rect.x + rect.width) * source_width)))
    bottom = max(top + 1, min(source_height, round((rect.y + rect.height) * source_height)))
    return left, top, right, bottom


def crop_source_image(
    source_image: np.ndarray,
    settings: CropSettings,
    target_width: int,
    target_height: int,
) -> np.ndarray:
    """Return the selected source pixels without resampling them."""

    source_height, source_width = source_image.shape[:2]
    left, top, right, bottom = crop_pixel_bounds(
        settings,
        source_width,
        source_height,
        target_width,
        target_height,
    )
    return np.ascontiguousarray(source_image[top:bottom, left:right])


__all__ = [
    "NormalizedCropRect",
    "crop_pixel_bounds",
    "crop_source_image",
    "framing_base_scale",
    "map_look_at_from_source",
    "map_look_at_to_source",
    "remap_look_at_for_crop",
    "resolve_crop_rect",
]
