"""Estimate structural depth and render continuous single-image parallax."""

from __future__ import annotations

import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError

import cv2
import numpy as np

from starflight.core.crop import crop_source_image
from starflight.types.settings import (
    CropSettings,
    ImageMotionMode,
    ParallaxStrength,
    ProjectSettings,
    coerce_parallax_strength,
)

PARALLAX_LAYER_COUNT = 4
_ANALYSIS_LONG_EDGE = 1920
_INNER_AREA = 0.12
_OUTER_AREA = 0.50
_DEPTH_MIN = 0.12
_V4_INITIAL_SMOOTHING_SCALE = 0.10
_V4_FINAL_SMOOTHING_SCALE = 0.14
_V4_DEPTH_MIN = 0.08
_V4_DEPTH_GAMMA = 0.82
_V4_DISPARITY_GAMMA = 0.66
_V4_PLANE_BLEND = 0.18
_V4_MIN_DEPTH_RANGE = 1e-4
_V4_INVERSE_BISECTION_ITERATIONS = 24
_V4_BISECTION_CONVERGENCE = 1.0 / 4096.0
_V4_MOTION: dict[ParallaxStrength, tuple[float, float]] = {
    ParallaxStrength.LIGHT: (0.230769, 0.540865),
    ParallaxStrength.MEDIUM: (0.375, 0.878906),
    ParallaxStrength.STRONG: (0.543147, 1.273),
    ParallaxStrength.VERY_STRONG: (0.64, 1.5),
}


def parallax_motion_for_strength(
    strength: ParallaxStrength | str | int | float,
) -> tuple[float, float]:
    """Return perspective travel and lateral motion for one V4 preset."""

    return _V4_MOTION[coerce_parallax_strength(strength)]


def prepare_parallax_render_input(
    source_image: np.ndarray,
    settings: ProjectSettings,
) -> tuple[np.ndarray, ProjectSettings]:
    """Apply the selected crop before parallax analysis and frame rendering."""

    if settings.background.motion_mode != ImageMotionMode.PARALLAX:
        return source_image, settings
    cropped_source = crop_source_image(
        source_image,
        settings.crop,
        settings.resolution.width,
        settings.resolution.height,
    )
    render_settings = settings.clone()
    render_settings.crop = CropSettings()
    return cropped_source, render_settings


def _soft_five_plane_disparity(depth: np.ndarray) -> np.ndarray:
    """Convert continuous V3 depth into five softly separated disparity bands."""

    low = float(depth.min())
    high = float(depth.max())
    normalized = np.clip((depth - low) / max(high - low, 1e-6), 0.0, 1.0)
    thresholds = np.array((0.125, 0.375, 0.625, 0.875), dtype=np.float32)
    transition_half_width = 0.10
    disparity = np.zeros_like(normalized, dtype=np.float32)
    for threshold in thresholds:
        transition = np.clip(
            (normalized - (threshold - transition_half_width)) / (2.0 * transition_half_width),
            0.0,
            1.0,
        )
        transition = transition * transition * (3.0 - 2.0 * transition)
        disparity += transition / len(thresholds)
    return disparity


def prepare_parallax_depth_v4(
    depth: np.ndarray,
    on_progress: Callable[[float], None] | None = None,
) -> np.ndarray:
    """Prepare the shared soft five-plane disparity field used by every V4 preset."""

    def report(fraction: float) -> None:
        if on_progress is not None:
            on_progress(max(0.0, min(1.0, fraction)))

    report(0.0)
    low = float(depth.min())
    high = float(depth.max())
    if high - low <= _V4_MIN_DEPTH_RANGE:
        report(1.0)
        return np.clip(depth, 0.0, 1.0).astype(np.float32)

    sigma = min(depth.shape) * _V4_INITIAL_SMOOTHING_SCALE
    smoothed = cv2.GaussianBlur(
        depth,
        (0, 0),
        sigma,
        borderType=cv2.BORDER_REFLECT_101,
    )
    smoothed = np.clip(smoothed, low, high)
    report(0.25)

    smoothed_low = float(smoothed.min())
    smoothed_high = float(smoothed.max())
    continuous = np.clip(
        (smoothed - smoothed_low) / max(smoothed_high - smoothed_low, 1e-6),
        0.0,
        1.0,
    )
    continuous = _V4_DEPTH_MIN + (1.0 - _V4_DEPTH_MIN) * np.power(
        continuous,
        _V4_DEPTH_GAMMA,
    )
    report(0.45)

    normalized = (continuous - float(continuous.min())) / max(
        float(np.ptp(continuous)),
        1e-6,
    )
    five_plane = _soft_five_plane_disparity(continuous)
    disparity = (1.0 - _V4_PLANE_BLEND) * normalized
    disparity += _V4_PLANE_BLEND * five_plane
    disparity = np.power(np.clip(disparity, 0.0, 1.0), _V4_DISPARITY_GAMMA)
    report(0.65)

    disparity = cv2.GaussianBlur(
        disparity,
        (0, 0),
        min(disparity.shape) * _V4_FINAL_SMOOTHING_SCALE,
        borderType=cv2.BORDER_REFLECT_101,
    )
    disparity_low = float(disparity.min())
    disparity_high = float(disparity.max())
    prepared = np.clip(
        (disparity - disparity_low) / max(disparity_high - disparity_low, 1e-6),
        0.0,
        1.0,
    ).astype(np.float32)
    report(1.0)
    return prepared


def _normalize(values: np.ndarray) -> np.ndarray:
    low, high = np.percentile(values, (2.0, 98.0))
    normalized = (values - low) / max(float(high - low), 1e-6)
    return np.clip(normalized, 0.0, 1.0).astype(np.float32)


def _analysis_image(source_bgr: np.ndarray) -> np.ndarray:
    source_height, source_width = source_bgr.shape[:2]
    longest_edge = max(source_width, source_height)
    if longest_edge <= _ANALYSIS_LONG_EDGE:
        return source_bgr
    scale = _ANALYSIS_LONG_EDGE / longest_edge
    size = (max(2, round(source_width * scale)), max(2, round(source_height * scale)))
    return cv2.resize(source_bgr, size, interpolation=cv2.INTER_AREA)


def _progressive_bilateral_filter(
    values: np.ndarray,
    sigma_color: float,
    sigma_space: float,
    on_progress: Callable[[float], None] | None = None,
) -> np.ndarray:
    """Run the full bilateral filter while reporting calibrated elapsed progress."""

    radius = max(1, round(sigma_space * 1.5))
    diameter = radius * 2 + 1
    if on_progress is None:
        return cv2.bilateralFilter(values, diameter, sigma_color, sigma_space)

    height, width = values.shape
    sample_height = min(height, max(128, diameter * 2))
    sample_width = width
    sample_top = (height - sample_height) // 2
    sample_left = (width - sample_width) // 2
    sample = np.ascontiguousarray(
        values[
            sample_top : sample_top + sample_height,
            sample_left : sample_left + sample_width,
        ]
    )
    benchmark_t0 = time.perf_counter()
    cv2.bilateralFilter(
        sample,
        diameter,
        sigma_color,
        sigma_space,
    )
    benchmark_s = max(time.perf_counter() - benchmark_t0, 1e-6)
    estimated_s = max(benchmark_s * values.size / sample.size, 0.25)
    on_progress(0.05)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            cv2.bilateralFilter,
            values,
            diameter,
            sigma_color,
            sigma_space,
        )
        filter_t0 = time.perf_counter()
        while True:
            try:
                filtered = future.result(timeout=0.25)
                break
            except FutureTimeoutError:
                elapsed = time.perf_counter() - filter_t0
                estimated_fraction = min(0.98, elapsed / estimated_s)
                on_progress(0.05 + 0.94 * estimated_fraction)
    on_progress(1.0)
    return filtered


def _structure_field(
    source_bgr: np.ndarray,
    focus: tuple[float, float],
    on_progress: Callable[[float], None] | None = None,
) -> np.ndarray:
    def report(fraction: float) -> None:
        if on_progress is not None:
            on_progress(max(0.0, min(1.0, fraction)))

    report(0.0)
    luminance = cv2.cvtColor(source_bgr, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    luminance /= 255.0
    height, width = luminance.shape
    scale = min(height, width)
    edge_aware = _progressive_bilateral_filter(
        luminance,
        0.10,
        max(8.0, scale * 0.030),
        on_progress=lambda fraction: report(0.95 * fraction),
    )
    local = cv2.GaussianBlur(edge_aware, (0, 0), max(2.0, scale * 0.008))
    broad = cv2.GaussianBlur(edge_aware, (0, 0), max(6.0, scale * 0.025))
    contrast = cv2.GaussianBlur(
        np.abs(local - broad),
        (0, 0),
        max(1.5, scale * 0.007),
    )

    score = 0.78 * _normalize(broad) + 0.22 * _normalize(contrast)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    focus_x = focus[0] * width
    focus_y = focus[1] * height
    distance = np.sqrt(((xx - focus_x) / width) ** 2 + ((yy - focus_y) / height) ** 2)
    report(1.0)
    return np.clip(score - 0.10 * distance, 0.0, 1.0).astype(np.float32)


def _structural_seed(score: np.ndarray, focus: tuple[float, float]) -> tuple[int, int]:
    height, width = score.shape
    margin = max(2, round(min(height, width) * 0.025))
    focus_x = min(width - margin - 1, max(margin, round(focus[0] * width)))
    focus_y = min(height - margin - 1, max(margin, round(focus[1] * height)))
    radius = max(2, round(min(height, width) * 0.04))
    left = max(margin, focus_x - radius)
    right = min(width - margin, focus_x + radius + 1)
    top = max(margin, focus_y - radius)
    bottom = min(height - margin, focus_y + radius + 1)
    local_y, local_x = np.unravel_index(
        int(np.argmax(score[top:bottom, left:right])),
        (bottom - top, right - left),
    )
    return left + int(local_x), top + int(local_y)


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    padded = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, value=0)
    outside = cv2.bitwise_not(padded)
    flood_mask = np.zeros((outside.shape[0] + 2, outside.shape[1] + 2), np.uint8)
    cv2.floodFill(outside, flood_mask, (0, 0), 0)
    filled = cv2.bitwise_or(padded, outside)
    return filled[1:-1, 1:-1]


def _seed_component(
    score: np.ndarray,
    threshold: float,
    seed: tuple[int, int],
    close_kernel: np.ndarray,
) -> np.ndarray:
    binary = np.where(score >= threshold, 255, 0).astype(np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, close_kernel)
    _count, labels = cv2.connectedComponents(binary, connectivity=8)
    seed_label = labels[seed[1], seed[0]]
    if seed_label == 0:
        return np.zeros_like(binary)
    component = np.where(labels == seed_label, 255, 0).astype(np.uint8)
    return _fill_holes(component)


def _mask_for_target_area(
    score: np.ndarray,
    target_area: float,
    seed: tuple[int, int],
    close_kernel: np.ndarray,
    on_progress: Callable[[float], None] | None = None,
) -> np.ndarray:
    low = 0.0
    high = max(1e-5, min(0.999, float(score[seed[1], seed[0]]) * 0.995))
    best_mask = np.zeros(score.shape, dtype=np.uint8)
    best_error = float("inf")
    iteration_count = 24
    for iteration in range(iteration_count):
        threshold = (low + high) / 2.0
        mask = _seed_component(score, threshold, seed, close_kernel)
        area = float(np.count_nonzero(mask)) / mask.size
        error = abs(area - target_area)
        if error < best_error:
            best_error = error
            best_mask = mask
        if area < target_area:
            high = threshold
        else:
            low = threshold
        if on_progress is not None:
            on_progress((iteration + 1) / iteration_count)
    return best_mask


def _keep_seed_component(mask: np.ndarray, seed: tuple[int, int]) -> np.ndarray:
    _count, labels = cv2.connectedComponents(mask, connectivity=8)
    seed_label = labels[seed[1], seed[0]]
    if seed_label == 0:
        raise ValueError("the parallax focus is outside the generated structure")
    component = np.where(labels == seed_label, 255, 0).astype(np.uint8)
    return _fill_holes(component)


def _nested_hard_masks(
    source_bgr: np.ndarray,
    focus: tuple[float, float],
    on_progress: Callable[[float], None] | None = None,
) -> np.ndarray:
    def report(fraction: float) -> None:
        if on_progress is not None:
            on_progress(max(0.0, min(1.0, fraction)))

    report(0.0)
    score = _structure_field(
        source_bgr,
        focus,
        on_progress=lambda fraction: report(0.90 * fraction),
    )
    report(0.90)
    height, width = score.shape
    if float(np.ptp(score)) <= 1e-6:
        report(1.0)
        return np.zeros(
            (height, width, PARALLAX_LAYER_COUNT - 1),
            dtype=np.bool_,
        )
    seed = _structural_seed(score, focus)
    kernel_radius = max(2, round(min(height, width) * 0.012))
    kernel_size = kernel_radius * 2 + 1
    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (kernel_size, kernel_size),
    )
    target_areas = np.linspace(_INNER_AREA, _OUTER_AREA, PARALLAX_LAYER_COUNT - 1)
    masks = []
    area_count = len(target_areas)
    for index, area in enumerate(target_areas):
        phase_start = 0.90 + 0.08 * index / area_count
        phase_span = 0.08 / area_count
        mask = _mask_for_target_area(
            score,
            float(area),
            seed,
            close_kernel,
            on_progress=lambda fraction, start=phase_start, span=phase_span: report(
                start + span * fraction
            ),
        )
        masks.append(mask)

    gap_radius = max(3, round(min(height, width) * 0.022))
    gap_kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (gap_radius * 2 + 1, gap_radius * 2 + 1),
    )
    frame_margin = gap_radius + 2
    for index, mask in enumerate(masks):
        if index > 0:
            mask = cv2.bitwise_or(mask, cv2.dilate(masks[index - 1], gap_kernel))
        mask[:frame_margin, :] = 0
        mask[-frame_margin:, :] = 0
        mask[:, :frame_margin] = 0
        mask[:, -frame_margin:] = 0
        masks[index] = _keep_seed_component(mask, seed)
        report(0.98 + 0.02 * (index + 1) / len(masks))
    return np.stack(masks, axis=2) >= 128


def _box_mean(values: np.ndarray, radius: int) -> np.ndarray:
    size = radius * 2 + 1
    return cv2.boxFilter(
        values,
        ddepth=-1,
        ksize=(size, size),
        normalize=True,
        borderType=cv2.BORDER_REFLECT_101,
    )


def _color_guided_filter(
    guide: np.ndarray,
    values: np.ndarray,
    radius: int,
    epsilon: float,
    on_progress: Callable[[float], None] | None = None,
) -> np.ndarray:
    def report(fraction: float) -> None:
        if on_progress is not None:
            on_progress(max(0.0, min(1.0, fraction)))

    report(0.0)
    mean_guide = _box_mean(guide, radius)
    mean_values = _box_mean(values, radius)
    report(0.10)
    covariance = np.empty((*values.shape, 3, 3), dtype=np.float32)
    covariance_guide_values = np.empty((*values.shape, 3), dtype=np.float32)

    for row in range(3):
        covariance_guide_values[..., row] = (
            _box_mean(guide[..., row] * values, radius) - mean_guide[..., row] * mean_values
        )
        for column in range(3):
            covariance[..., row, column] = (
                _box_mean(guide[..., row] * guide[..., column], radius)
                - mean_guide[..., row] * mean_guide[..., column]
            )
        report(0.10 + 0.15 * (row + 1))
    covariance[..., 0, 0] += epsilon
    covariance[..., 1, 1] += epsilon
    covariance[..., 2, 2] += epsilon

    coefficients = np.linalg.solve(
        covariance.reshape(-1, 3, 3),
        covariance_guide_values.reshape(-1, 3, 1),
    ).reshape(*values.shape, 3)
    report(0.78)
    offsets = mean_values - np.sum(coefficients * mean_guide, axis=2)
    report(0.86)
    filtered = np.sum(_box_mean(coefficients, radius) * guide, axis=2)
    filtered += _box_mean(offsets, radius)
    report(1.0)
    return filtered.astype(np.float32)


def create_parallax_depth(
    source_bgr: np.ndarray,
    focus: tuple[float, float],
    *,
    on_progress: Callable[[float], None] | None = None,
) -> np.ndarray:
    """
    create the continuous structural depth map once before video export.

    on_progress
        optional callback receiving normalized completion 0..1
    """

    def report(fraction: float) -> None:
        if on_progress is not None:
            on_progress(max(0.0, min(1.0, fraction)))

    report(0.0)
    analysis = _analysis_image(source_bgr)
    report(0.01)
    hard_masks = _nested_hard_masks(
        analysis,
        focus,
        on_progress=lambda fraction: report(0.01 + 0.87 * fraction),
    )
    report(0.88)
    guide = cv2.cvtColor(analysis, cv2.COLOR_BGR2LAB).astype(np.float32) / 255.0
    guide = cv2.GaussianBlur(guide, (0, 0), 1.2)
    radius = max(5, round(min(analysis.shape[:2]) * 0.025))
    report(0.89)

    masks: list[np.ndarray] = []
    layer_count = hard_masks.shape[2]
    for index in range(layer_count):
        phase_start = 0.89 + 0.10 * index / layer_count
        phase_span = 0.10 / layer_count
        alpha = _color_guided_filter(
            guide,
            hard_masks[..., index].astype(np.float32),
            radius,
            0.004,
            on_progress=lambda fraction, start=phase_start, span=phase_span: report(
                start + span * fraction
            ),
        )
        alpha = np.clip(alpha, 0.0, 1.0)
        alpha = (alpha * alpha * (3.0 - 2.0 * alpha)).astype(np.float32)
        if masks:
            alpha = np.maximum(alpha, masks[-1])
        masks.append(alpha)
        report(phase_start + phase_span)

    depths = np.linspace(_DEPTH_MIN, 1.0, PARALLAX_LAYER_COUNT, dtype=np.float32)
    depth = np.full(analysis.shape[:2], depths[-1], dtype=np.float32)
    for index in reversed(range(len(masks))):
        depth += (depths[index] - depths[index + 1]) * masks[index]
    depth = np.clip(depth, depths[0], depths[-1]).astype(np.float32)
    report(1.0)
    return depth


def _sample_depth(
    depth: np.ndarray,
    map_x: np.ndarray,
    map_y: np.ndarray,
    source_width: int,
    source_height: int,
) -> np.ndarray:
    depth_height, depth_width = depth.shape
    depth_x = map_x * ((depth_width - 1) / max(source_width - 1, 1))
    depth_y = map_y * ((depth_height - 1) / max(source_height - 1, 1))
    return cv2.remap(
        depth,
        depth_x,
        depth_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REPLICATE,
    )


def parallax_coordinate_maps(
    disparity: np.ndarray,
    base_map_x: np.ndarray,
    base_map_y: np.ndarray,
    source_size: tuple[int, int],
    center: tuple[float, float],
    progress: float,
    travel: float,
    lateral_percent: float,
    *,
    iterations: int = _V4_INVERSE_BISECTION_ITERATIONS,
) -> tuple[np.ndarray, np.ndarray]:
    """Solve the inverse V4 perspective map with guaranteed bounded convergence."""

    source_width, source_height = source_size
    center_x, center_y = center
    amount = max(0.0, min(float(progress), 1.0))
    if amount <= 0.0 or travel <= 0.0:
        return base_map_x.astype(np.float32), base_map_y.astype(np.float32)

    vector_x = base_map_x - center_x
    vector_y = base_map_y - center_y

    disparity_min = float(disparity.min())
    disparity_max = float(disparity.max())
    if disparity_max - disparity_min <= 1e-6:
        uniform_disparity = np.full(
            base_map_x.shape,
            disparity_min,
            dtype=np.float32,
        )
        source_scale = np.maximum(
            1.0 - travel * uniform_disparity * amount,
            0.20,
        )
        map_x = center_x + vector_x * source_scale
        map_y = center_y + vector_y * source_scale
        map_x += source_width * lateral_percent * 0.01 * uniform_disparity * amount
        return map_x.astype(np.float32), map_y.astype(np.float32)

    def maps_for(local_disparity: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        source_scale = np.maximum(1.0 - travel * local_disparity * amount, 0.20)
        map_x = center_x + vector_x * source_scale
        map_y = center_y + vector_y * source_scale
        map_x += source_width * lateral_percent * 0.01 * local_disparity * amount
        return map_x, map_y

    lower = np.zeros(base_map_x.shape, dtype=np.float32)
    upper = np.ones(base_map_x.shape, dtype=np.float32)
    for _iteration in range(max(1, int(iterations))):
        local_disparity = (lower + upper) * 0.5
        map_x, map_y = maps_for(local_disparity)
        sampled_disparity = _sample_depth(
            disparity,
            map_x,
            map_y,
            source_width,
            source_height,
        )
        search_upper = local_disparity >= sampled_disparity
        upper = np.where(search_upper, local_disparity, upper)
        lower = np.where(search_upper, lower, local_disparity)
        if float(np.max(upper - lower)) <= _V4_BISECTION_CONVERGENCE:
            break

    map_x, map_y = maps_for((lower + upper) * 0.5)
    return map_x.astype(np.float32), map_y.astype(np.float32)


__all__ = [
    "create_parallax_depth",
    "parallax_coordinate_maps",
    "parallax_motion_for_strength",
    "prepare_parallax_depth_v4",
    "prepare_parallax_render_input",
]
