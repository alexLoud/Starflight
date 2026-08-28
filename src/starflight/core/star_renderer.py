"""Draw projected stars with compact point spread profiles.

Export frames use a larger working layer for smoother edges. Each star is limited to a small local
area so rendering cost follows the visible star sizes instead of the full frame size.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import cv2
import numpy as np

from starflight.core.star_field import StarField, StarProjection
from starflight.types.settings import RenderQuality, StarSettings

_GLOW_HALO_SCALE = 0.10
_GLOW_SIGMA_RADIUS_FACTOR = 2.1
_GLOW_MIN_SIGMA = 0.85
_GLOW_EDGE_SIGMAS = 3.5
_STAMP_WINDOW_INNER_RATIO = 0.82


def _glow_strength_for_star(
    render_radius: float,
    star_brightness: float,
    glow_intensity: float,
    depth_gain: float,
    glow_depth_boost: float,
    *,
    quality: RenderQuality = RenderQuality.EXPORT,
) -> float:
    """
    compute isotropic halo strength for large bright stars.

    render_radius
        rendered star radius in pixels
    star_brightness
        projected star brightness before energy scaling
    glow_intensity
        user glow slider from 0 to 1
    depth_gain
        normalized proximity to camera
    glow_depth_boost
        optional depth-based glow boost from 0 to 1
    quality
        preview or export quality
    """

    if glow_intensity <= 0.0:
        return 0.0

    eligibility_radius = render_radius
    if quality == RenderQuality.PREVIEW:
        # preview renders without supersampling, so match export glow eligibility.
        eligibility_radius = render_radius * 2.0

    if eligibility_radius <= 2.0:
        return 0.0

    size_gate = _clamp((eligibility_radius - 2.0) / 2.2, 0.0, 1.0)
    brightness_gate = _clamp((star_brightness - 0.40) / 0.55, 0.0, 1.0)
    depth_boost = _clamp(glow_depth_boost, 0.0, 1.0)
    depth_gate = (
        1.0
        if depth_boost <= 0.0
        else (1.0 - depth_boost) + _clamp(depth_gain, 0.0, 1.0) * depth_boost
    )
    return size_gate * brightness_gate * _clamp(glow_intensity, 0.0, 1.0) * depth_gate


def _glow_sigma_for_radius(radius: float) -> float:
    """
    return gaussian sigma for the atmospheric halo.

    radius
        star radius in render pixels
    """

    return max(_GLOW_MIN_SIGMA, radius * _GLOW_SIGMA_RADIUS_FACTOR)


def _star_stamp_support(radius: float, glow_strength: float) -> int:
    """
    return stamp half-size so the psf fades out before the square border.

    radius
        star radius in render pixels
    glow_strength
        isotropic halo strength from 0 to 1
    """

    support = max(2.0, radius * 2.8 + 2.0)
    if glow_strength > 0.0:
        support = max(support, _glow_sigma_for_radius(radius) * _GLOW_EDGE_SIGMAS)
    return math.ceil(support)


def _circular_stamp_window(r2: np.ndarray, support: int) -> np.ndarray:
    """
    build a circular falloff so truncated stamps never show square edges.

    r2
        squared distance from star center
    support
        stamp half-size in pixels
    """

    radius_limit = float(max(support, 1))
    inner = radius_limit * _STAMP_WINDOW_INNER_RATIO
    fade_width = max(radius_limit - inner, 1e-6)
    radius = np.sqrt(np.maximum(r2, 0.0))
    t = np.clip((radius_limit - radius) / fade_width, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    """
    clamp value to range.

    value
        input value
    minimum
        lower bound
    maximum
        upper bound
    """

    return max(minimum, min(maximum, value))


def _energy_scale_for_quality(quality: RenderQuality) -> float:
    """
    return energy multiplier for render quality.

    quality
        preview or export quality
    """

    if quality == RenderQuality.EXPORT:
        return 1.34
    return 1.10


def _add_star_psf(
    layer: np.ndarray,
    center_x: float,
    center_y: float,
    radius: float,
    energy: float,
    color: tuple[float, float, float],
    glow_intensity: float,
    color_intensity: float,
    allow_glow: bool,
    star_brightness: float,
    depth_gain: float = 1.0,
    glow_depth_boost: float = 0.0,
    quality: RenderQuality = RenderQuality.EXPORT,
) -> None:
    """
    stamp a star point-spread function onto the rgb layer.

    layer
        float32 rgb layer
    center_x
        sub-pixel center x
    center_y
        sub-pixel center y
    radius
        star radius in pixels
    energy
        star energy multiplier
    color
        normalized rgb color
    glow_intensity
        user glow intensity 0..1
    color_intensity
        user color intensity 0..1
    allow_glow
        whether atmospheric glow is allowed
    star_brightness
        projected star brightness before energy scaling
    depth_gain
        normalized proximity to camera
    glow_depth_boost
        depth-based glow boost from 0 to 1
    quality
        preview or export quality
    """

    if energy <= 0.0:
        return

    height, width, _ = layer.shape
    glow_strength = 0.0
    if allow_glow:
        glow_strength = _glow_strength_for_star(
            radius,
            star_brightness,
            glow_intensity,
            depth_gain,
            glow_depth_boost,
            quality=quality,
        )

    support = _star_stamp_support(radius, glow_strength)
    left = max(0, math.floor(center_x) - support)
    right = min(width, math.floor(center_x) + support + 1)
    top = max(0, math.floor(center_y) - support)
    bottom = min(height, math.floor(center_y) + support + 1)
    if left >= right or top >= bottom:
        return

    # 1d axes are much cheaper than np.mgrid for every star stamp
    ys = np.arange(top, bottom, dtype=np.float32) + 0.5 - float(center_y)
    xs = np.arange(left, right, dtype=np.float32) + 0.5 - float(center_x)
    r2 = xs[np.newaxis, :] * xs[np.newaxis, :] + ys[:, np.newaxis] * ys[:, np.newaxis]

    moffat_alpha = max(0.28, radius * 0.44)
    moffat_beta = 4.0
    inv_alpha2 = 1.0 / (moffat_alpha * moffat_alpha)
    core = (1.0 + r2 * inv_alpha2) ** (-moffat_beta)
    pinpoint_sigma = max(0.14, radius * 0.22)
    inv_pinpoint = 1.0 / (pinpoint_sigma * pinpoint_sigma)
    pinpoint = np.exp(-0.5 * r2 * inv_pinpoint)

    profile = core * 0.88 + pinpoint * 0.62

    if glow_strength > 0.0:
        glow_sigma = _glow_sigma_for_radius(radius)
        inv_glow = 1.0 / (glow_sigma * glow_sigma)
        glow = np.exp(-0.5 * r2 * inv_glow)
        profile += glow * (_GLOW_HALO_SCALE * glow_strength)

    profile *= _circular_stamp_window(r2, support)

    star_color = np.asarray(color, dtype=np.float32)
    chroma = float(star_color.max() - star_color.min())
    body_saturation = 1.0 + _clamp(color_intensity, 0.0, 1.0) * 0.55
    luminance = float(star_color.mean())
    body_color = luminance + (star_color - luminance) * body_saturation
    body_color = np.clip(body_color, 0.0, 1.0)

    white_core_strength = _clamp((radius - 1.8) / 2.4, 0.0, 1.0)
    white_mix_scale = _clamp(1.0 - chroma * 1.65, 0.12, 1.0)
    white_mix_scale *= 1.0 - _clamp(color_intensity, 0.0, 1.0) * 0.72
    white_mix = np.clip(pinpoint**1.6, 0.0, 1.0) * white_core_strength * 0.28 * white_mix_scale
    local_color = body_color[np.newaxis, np.newaxis, :] * (1.0 - white_mix[:, :, np.newaxis])
    local_color += white_mix[:, :, np.newaxis] * np.array([1.0, 1.0, 1.0], dtype=np.float32)

    layer[top:bottom, left:right] += profile[:, :, np.newaxis] * local_color * energy


def _stamp_spikes(
    layer: np.ndarray,
    center_x: float,
    center_y: float,
    radius: float,
    intensity: float,
    angle: float,
    color: tuple[float, float, float],
) -> None:
    """
    stamp subtle diffraction spikes for bright stars.

    layer
        float32 rgb layer
    center_x
        star center x
    center_y
        star center y
    radius
        star radius
    intensity
        spike strength
    angle
        rotation angle
    color
        normalized rgb star color
    """

    if intensity <= 0.01:
        return

    height, width = layer.shape[:2]
    length = int(max(4, radius * 6.0))
    thickness = max(1, round(radius * 0.16))
    spike_color = np.asarray(color, dtype=np.float32)

    for direction in (angle, angle + np.pi / 2.0):
        dx = math.cos(direction)
        dy = math.sin(direction)
        for sign in (-1.0, 1.0):
            for step in range(1, length):
                px = round(center_x + dx * step * sign)
                py = round(center_y + dy * step * sign)
                falloff = (1.0 - step / length) ** 2
                value = intensity * 0.16 * falloff
                for ox in range(-thickness, thickness + 1):
                    for oy in range(-thickness, thickness + 1):
                        x = px + ox
                        y = py + oy
                        if 0 <= x < width and 0 <= y < height:
                            layer[y, x] += spike_color * value


def _render_star_layer(
    projections: list[StarProjection],
    width: int,
    height: int,
    quality: RenderQuality,
    glow_intensity: float,
    color_intensity: float,
    glow_depth_boost: float,
) -> np.ndarray:
    """
    render stars into a float rgb layer.

    projections
        projected stars
    width
        layer width
    height
        layer height
    quality
        preview or export quality
    glow_intensity
        user glow intensity 0..1
    color_intensity
        user color intensity 0..1
    glow_depth_boost
        depth-based glow boost from 0 to 1
    """

    supersample = 2 if quality == RenderQuality.EXPORT else 1
    render_w = width * supersample
    render_h = height * supersample
    layer = np.zeros((render_h, render_w, 3), dtype=np.float32)

    scale = float(supersample)
    energy_scale = _energy_scale_for_quality(quality)
    glow_amount = _clamp(glow_intensity, 0.0, 1.0)
    color_amount = _clamp(color_intensity, 0.0, 1.0)

    for star in projections:
        sx = star.x * scale
        sy = star.y * scale
        radius = max(0.0, star.radius * scale)
        energy = star.brightness * energy_scale * 255.0
        if radius <= 0.0 or energy <= 0.0:
            continue

        _add_star_psf(
            layer,
            sx,
            sy,
            radius,
            energy,
            star.color,
            glow_amount,
            color_amount,
            allow_glow=True,
            star_brightness=star.brightness,
            depth_gain=star.depth_gain,
            glow_depth_boost=glow_depth_boost,
            quality=quality,
        )

        if (
            quality == RenderQuality.EXPORT
            and star.spike_strength > 0.01
            and star.brightness > 0.55
        ):
            _stamp_spikes(layer, sx, sy, radius, star.spike_strength, star.spike_angle, star.color)

    if supersample > 1:
        layer = cv2.resize(layer, (width, height), interpolation=cv2.INTER_AREA)
        layer *= float(supersample * supersample)

    return layer


class StarRenderer:
    """high quality star renderer."""

    def __init__(self, settings: StarSettings, width: int, height: int) -> None:
        """
        create renderer with starfield simulation.

        settings
            star settings
        width
            frame width
        height
            frame height
        """

        self.settings = settings
        self.field = StarField(settings, width, height)

    def render_layer(
        self,
        time_seconds: float,
        duration_seconds: float,
        quality: RenderQuality,
        view_center_at_progress: Callable[[float], tuple[float, float]] | None = None,
        motion_progress: float | None = None,
        track_visibility: bool | None = None,
    ) -> np.ndarray:
        """
        render star rgb layer at a given time.

        time_seconds
            animation time in seconds
        duration_seconds
            total clip duration in seconds
        quality
            preview or export quality
        view_center_at_progress
            optional callback returning the screen-space aim point
        motion_progress
            optional eased progress for look-at and star travel
        track_visibility
            whether to update sequential export fade state
        """

        projections = self.field.project_at_time(
            time_seconds,
            duration_seconds,
            view_center_at_progress,
            quality,
            motion_progress,
            track_visibility,
        )
        width = self.field.width
        height = self.field.height
        glow_depth_boost = (
            self.settings.glow_depth_boost if self.settings.glow_intensity > 0.0 else 0.0
        )
        return _render_star_layer(
            projections,
            width,
            height,
            quality,
            self.settings.glow_intensity,
            self.settings.color_intensity,
            glow_depth_boost,
        )
