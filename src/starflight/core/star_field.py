"""Generate and project the animated star field.

Seeded star data stays stable for the life of a renderer. Projection tracks depth wrapping and
fade state so stars enter and leave smoothly across sequential export frames.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from starflight.types.settings import RenderQuality, StarSettings
from starflight.utils.star_colors import (
    bias_temperature_for_star_strength,
    resolve_star_color,
    sample_star_brightness,
    sample_star_temperatures,
)

_STAR_SIZE_MAX = 2.6


@dataclass
class StarProjection:
    """projected star data for rendering."""

    x: float
    y: float
    radius: float
    brightness: float
    color: tuple[float, float, float]
    spike_strength: float
    spike_angle: float
    depth_gain: float


@dataclass
class _StarSeed:
    """internal star seed state."""

    offset_x: float
    offset_y: float
    z: float
    size: float
    brightness: float
    temperature: float
    tint_strength: float
    spike_roll: float


class StarField:
    """deterministic starfield simulation matching starflight codex."""

    _MIN_Z = 0.20
    _MAX_Z = 1.35
    _Z_EPSILON = 1e-4
    _TRAVEL_SCALE = 0.55
    # speed 1.0 keeps the previous feel of a 10s clip
    _REFERENCE_DURATION_SECONDS = 10.0
    _FOCAL_SCALE = 0.52
    _RECYCLE_GRACE_FRAMES = 5
    _FADE_SECONDS = 4.0
    _FRAMES_PER_SECOND = 30.0
    _OFFSET_MARGIN = 1.0

    def __init__(self, settings: StarSettings, width: int, height: int) -> None:
        """
        initialize star seeds from settings.

        settings
            star settings including count and seed
        width
            frame width
        height
            frame height
        """

        self.settings = settings
        self.width = width
        self.height = height
        self._stars = self._create_stars(settings)
        self._cached_color_intensity: float | None = None
        self._cached_star_colors: list[tuple[float, float, float]] = []
        self._continuous_from_start: set[int] = set()
        self._fade_start_by_index: dict[int, float] = {}

    def export_fade_state(self) -> tuple[set[int], dict[int, float]]:
        """
        return a copy of export fade continuity state.

        """

        return set(self._continuous_from_start), dict(self._fade_start_by_index)

    def import_fade_state(
        self,
        continuous_from_start: set[int],
        fade_start_by_index: dict[int, float],
    ) -> None:
        """
        restore export fade continuity state.

        continuous_from_start
            star indices continuously visible from the clip start
        fade_start_by_index
            first-seen time per star index for fade-in
        """

        self._continuous_from_start = set(continuous_from_start)
        self._fade_start_by_index = dict(fade_start_by_index)

    def _z_range(self) -> float:
        """
        return normalized depth span used for recycling.
        """

        return self._MAX_Z - self._MIN_Z

    def _max_travel(self, settings: StarSettings, duration_seconds: float) -> float:
        """
        return total normalized travel at the end of a clip.

        settings
            star settings
        duration_seconds
            clip duration in seconds
        """

        return self._travel_at_time(settings, duration_seconds)

    def _travel_at_time(self, settings: StarSettings, time_seconds: float) -> float:
        """
        return normalized travel for an absolute animation time.

        settings
            star settings
        time_seconds
            animation time in seconds
        """

        return (
            settings.speed
            * self._TRAVEL_SCALE
            * (max(0.0, time_seconds) / self._REFERENCE_DURATION_SECONDS)
        )

    def _offset_limits(self) -> tuple[float, float]:
        """
        return angular offset limits that cover the full frame at max depth.
        """

        focal = min(self.width, self.height) * self._FOCAL_SCALE
        max_offset_x = self._MAX_Z * (self.width / 2.0) / focal * self._OFFSET_MARGIN
        max_offset_y = self._MAX_Z * (self.height / 2.0) / focal * self._OFFSET_MARGIN
        return max_offset_x, max_offset_y

    def _create_stars(self, settings: StarSettings) -> list[_StarSeed]:
        """
        create deterministic star seeds.

        settings
            star settings
        """

        rng = np.random.default_rng(settings.seed)
        temperatures = sample_star_temperatures(rng, settings.star_count)
        max_offset_x, max_offset_y = self._offset_limits()
        stars: list[_StarSeed] = []
        for index in range(settings.star_count):
            brightness = sample_star_brightness(rng, settings.magnitude_realism)
            offset_x = float(rng.uniform(-max_offset_x, max_offset_x))
            offset_y = float(rng.uniform(-max_offset_y, max_offset_y))
            z = float(rng.uniform(self._MIN_Z + 0.02, self._MAX_Z))
            size_mean = -0.20 + 0.25 * float(np.clip(settings.size_spread, 0.0, 1.0))
            size_sigma = 0.42 - 0.04 * float(np.clip(settings.size_spread, 0.0, 1.0))
            size = float(
                np.clip(
                    rng.lognormal(mean=size_mean, sigma=size_sigma),
                    0.35,
                    _STAR_SIZE_MAX,
                )
            )
            temperature = bias_temperature_for_star_strength(
                float(temperatures[index]),
                brightness,
                size,
                size_min=0.35,
                size_max=_STAR_SIZE_MAX,
            )
            stars.append(
                _StarSeed(
                    offset_x=offset_x,
                    offset_y=offset_y,
                    z=z,
                    size=size,
                    brightness=brightness,
                    temperature=temperature,
                    tint_strength=float(rng.uniform(0.66, 0.96)),
                    spike_roll=float(rng.uniform(0.0, np.pi)),
                )
            )

        return stars

    def _smoothstep(self, value: float) -> float:
        """
        smooth interpolation curve for visibility fades.

        value
            normalized input 0..1
        """

        clamped = float(np.clip(value, 0.0, 1.0))
        return clamped * clamped * (3.0 - 2.0 * clamped)

    def _frame_travel(self, max_travel: float, duration_seconds: float) -> float:
        """
        return normalized travel distance per frame.

        max_travel
            total travel at clip end
        duration_seconds
            clip duration in seconds
        """

        frame_count = max(1.0, duration_seconds * self._FRAMES_PER_SECOND)
        return max_travel / frame_count

    def _resolve_view_center(
        self,
        progress: float,
        view_center_at_progress: Callable[[float], tuple[float, float]] | None,
    ) -> tuple[float, float]:
        """
        resolve the radial projection center for a given animation progress.

        progress
            normalized animation progress 0..1
        view_center_at_progress
            optional callback returning the screen-space aim point
        """

        if view_center_at_progress is None:
            return self.width / 2.0, self.height / 2.0

        return view_center_at_progress(progress)

    def _visibility_for_star(
        self,
        star_index: int,
        time_seconds: float,
        quality: RenderQuality,
    ) -> float:
        """
        return star visibility for the requested render quality.

        star_index
            star index in the field
        time_seconds
            current animation time in seconds
        quality
            preview or export quality
        """

        if quality == RenderQuality.PREVIEW:
            return 1.0

        if time_seconds <= 0.0:
            return 1.0

        if star_index in self._continuous_from_start:
            return 1.0

        if star_index not in self._fade_start_by_index:
            self._fade_start_by_index[star_index] = time_seconds

        fade_age = max(0.0, time_seconds - self._fade_start_by_index[star_index])
        if fade_age >= self._FADE_SECONDS:
            return 1.0

        return self._smoothstep(fade_age / self._FADE_SECONDS)

    def _project_screen_position(
        self,
        star: _StarSeed,
        z: float,
        focal: float,
        center_x: float,
        center_y: float,
    ) -> tuple[float, float]:
        """
        project a star seed to screen coordinates.

        star
            star seed
        z
            depth value
        focal
            projection focal length
        center_x
            screen center x
        center_y
            screen center y
        """

        z_safe = max(z, self._Z_EPSILON)
        screen_x = center_x + (star.offset_x / z_safe) * focal
        screen_y = center_y + (star.offset_y / z_safe) * focal
        return screen_x, screen_y

    def _depth_gain(self, z: float) -> float:
        """
        compute normalized depth gain from z.

        z
            depth value
        """

        return float(np.clip((1.38 - z) / 1.16, 0.12, 1.0))

    def _estimate_radius(self, star: _StarSeed, depth_gain: float, settings: StarSettings) -> float:
        """
        estimate rendered star radius in pixels.

        star
            star seed
        depth_gain
            normalized depth gain
        settings
            star settings
        """

        size_norm = float(np.clip(star.size / _STAR_SIZE_MAX, 0.0, 1.0))
        spread = float(np.clip(settings.size_spread, 0.0, 1.0))
        # 0% keeps the original compact field; 100% lifts mid sizes and softens depth falloff.
        size_norm = size_norm ** (1.0 - 0.25 * spread)
        depth_factor = (0.20 + 0.10 * spread) + depth_gain * (0.80 - 0.10 * spread)
        blend = float(np.clip(size_norm * depth_factor, 0.0, 1.0))
        return settings.min_size + (settings.max_size - settings.min_size) * blend

    def _star_color(self, star: _StarSeed, settings: StarSettings) -> tuple[float, float, float]:
        """
        compute final star color from temperature and user intensity.

        star
            star seed
        settings
            star settings
        """

        return resolve_star_color(star.temperature, star.tint_strength, settings.color_intensity)

    def _star_colors(self, settings: StarSettings) -> list[tuple[float, float, float]]:
        """Return cached colors for the current color intensity."""

        if self._cached_color_intensity != settings.color_intensity:
            self._cached_star_colors = [self._star_color(star, settings) for star in self._stars]
            self._cached_color_intensity = settings.color_intensity
        return self._cached_star_colors

    def _visibility_margin(self, base_margin: float, radius: float, glow_intensity: float) -> float:
        """
        compute culling margin that includes star radius and glow.

        base_margin
            minimum margin in pixels
        radius
            estimated star radius
        glow_intensity
            user glow intensity from 0 to 1
        """

        # match star_renderer glow support: 3.5 sigmas at 2.1 * radius.
        core_extent = radius * 2.8 + 2.0
        if glow_intensity > 0.0:
            glow_extent = max(0.85, radius * 2.1) * 3.5
            core_extent = max(core_extent, glow_extent)
        return max(base_margin, core_extent)

    def _is_on_screen(self, screen_x: float, screen_y: float, margin: float) -> bool:
        """
        check whether a screen position is inside the visible frame.

        screen_x
            projected x position
        screen_y
            projected y position
        margin
            extra margin in pixels
        """

        return (
            screen_x >= -margin
            and screen_x <= self.width + margin
            and screen_y >= -margin
            and screen_y <= self.height + margin
        )

    def _is_star_visible_at_depth(
        self,
        star: _StarSeed,
        z: float,
        focal: float,
        center_x: float,
        center_y: float,
        base_margin: float,
        settings: StarSettings,
    ) -> bool:
        """
        check whether a star should be rendered at a given depth.

        star
            star seed
        z
            candidate depth
        focal
            projection focal length
        center_x
            screen center x
        center_y
            screen center y
        base_margin
            minimum culling margin
        settings
            star settings
        """

        depth_gain = self._depth_gain(z)
        radius = self._estimate_radius(star, depth_gain, settings)
        margin = self._visibility_margin(base_margin, radius, settings.glow_intensity)
        screen_x, screen_y = self._project_screen_position(
            star,
            z,
            focal,
            center_x,
            center_y,
        )
        return self._is_on_screen(screen_x, screen_y, margin)

    def _wrapped_depth(self, z_continuous: float) -> float:
        """
        wrap continuous depth into the valid far-depth band.

        z_continuous
            unconstrained depth from star.z - travel
        """

        z_range = self._z_range()
        wrapped_offset = (z_continuous - self._MIN_Z) % z_range
        return self._MIN_Z + wrapped_offset

    def _resolve_render_depth(
        self,
        star: _StarSeed,
        travel: float,
        focal: float,
        center_x: float,
        center_y: float,
        base_margin: float,
        settings: StarSettings,
        max_travel: float,
        duration_seconds: float,
    ) -> float | None:
        """
        resolve render depth without popping visible stars via z-wrapping.

        stars continue flying outward past min_z until they leave the frame.
        recycled stars only appear during animation as faint distant points.

        star
            star seed
        travel
            normalized travel distance
        focal
            projection focal length
        center_x
            screen center x
        center_y
            screen center y
        base_margin
            minimum culling margin
        settings
            star settings
        max_travel
            normalized travel at clip end
        duration_seconds
            clip duration in seconds

        Returns None when the star should not be rendered this frame.
        """

        z_continuous = star.z - travel

        if z_continuous >= self._MIN_Z:
            if self._is_star_visible_at_depth(
                star,
                z_continuous,
                focal,
                center_x,
                center_y,
                base_margin,
                settings,
            ):
                return z_continuous
            return None

        if self._is_star_visible_at_depth(
            star,
            z_continuous,
            focal,
            center_x,
            center_y,
            base_margin,
            settings,
        ):
            return z_continuous

        if travel <= 0.0:
            return None

        frame_travel = self._frame_travel(max_travel, duration_seconds)
        for lookback in range(1, self._RECYCLE_GRACE_FRAMES + 1):
            previous_travel = max(0.0, travel - lookback * frame_travel)
            z_previous = star.z - previous_travel
            if z_previous >= self._MIN_Z:
                if self._is_star_visible_at_depth(
                    star,
                    z_previous,
                    focal,
                    center_x,
                    center_y,
                    base_margin,
                    settings,
                ):
                    return None
            elif self._is_star_visible_at_depth(
                star,
                z_previous,
                focal,
                center_x,
                center_y,
                base_margin,
                settings,
            ):
                return None

        wrapped_z = self._wrapped_depth(z_continuous)
        if self._is_star_visible_at_depth(
            star,
            wrapped_z,
            focal,
            center_x,
            center_y,
            base_margin,
            settings,
        ):
            return wrapped_z

        return None

    def project_at_time(
        self,
        time_seconds: float,
        duration_seconds: float,
        view_center_at_progress: Callable[[float], tuple[float, float]] | None = None,
        quality: RenderQuality = RenderQuality.EXPORT,
    ) -> list[StarProjection]:
        """
        project stars for a specific time.

        time_seconds
            current animation time in seconds
        duration_seconds
            total clip duration in seconds
        view_center_at_progress
            optional callback returning the screen-space aim point
        quality
            preview or export quality
        """

        settings = self.settings
        progress = 0.0 if duration_seconds <= 0 else time_seconds / duration_seconds
        progress = float(np.clip(progress, 0.0, 1.0))
        max_travel = self._max_travel(settings, duration_seconds)
        travel = self._travel_at_time(settings, time_seconds)
        use_fade = quality == RenderQuality.EXPORT

        focal = min(self.width, self.height) * self._FOCAL_SCALE
        center_x, center_y = self._resolve_view_center(progress, view_center_at_progress)
        base_margin = settings.max_size * 6.0
        star_colors = self._star_colors(settings) if use_fade else None

        projections: list[StarProjection] = []
        rendered_now: set[int] = set()

        for index, star in enumerate(self._stars):
            z = self._resolve_render_depth(
                star,
                travel,
                focal,
                center_x,
                center_y,
                base_margin,
                settings,
                max_travel,
                duration_seconds,
            )
            if z is None:
                if use_fade:
                    self._fade_start_by_index.pop(index, None)
                continue

            screen_x, screen_y = self._project_screen_position(
                star,
                z,
                focal,
                center_x,
                center_y,
            )

            depth_gain = self._depth_gain(z)
            radius = self._estimate_radius(star, depth_gain, settings)
            margin = self._visibility_margin(base_margin, radius, settings.glow_intensity)

            if not self._is_on_screen(screen_x, screen_y, margin):
                if use_fade:
                    self._fade_start_by_index.pop(index, None)
                continue

            visibility = self._visibility_for_star(index, time_seconds, quality)
            if use_fade and visibility <= 0.0:
                continue

            if use_fade:
                rendered_now.add(index)
                radius *= visibility

            brightness = settings.brightness * star.brightness * (0.56 + depth_gain * 1.34)
            if use_fade:
                brightness *= visibility
            color = (
                star_colors[index]
                if star_colors is not None
                else self._star_color(star, settings)
            )

            spike_strength = 0.0
            spike_angle = star.spike_roll
            if use_fade and depth_gain > 0.82 and brightness > 0.55 and radius >= 2.5:
                spike_strength = float((depth_gain - 0.82) / 0.18) * visibility

            projections.append(
                StarProjection(
                    x=screen_x,
                    y=screen_y,
                    radius=float(radius),
                    brightness=float(brightness),
                    color=color,
                    spike_strength=spike_strength,
                    spike_angle=spike_angle,
                    depth_gain=depth_gain,
                )
            )

        if use_fade:
            if time_seconds <= 0.0:
                self._continuous_from_start = set(rendered_now)
            else:
                self._continuous_from_start &= rendered_now

        projections.sort(key=lambda item: item.radius)
        return projections
