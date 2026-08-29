"""Render the source image with camera movement.

The renderer builds an inverse affine transform for each frame. Extra zoom to cover empty
corners is applied only when fill-frame is enabled.
"""

from __future__ import annotations

import math

import cv2
import numpy as np

from starflight.core.camera_motion import camera_motion_progress
from starflight.core.crop import framing_base_scale, map_look_at_to_source
from starflight.core.parallax import parallax_coordinate_maps
from starflight.types.settings import (
    MAX_BACKGROUND_SCALE_PERCENT,
    MIN_BACKGROUND_SCALE_PERCENT,
    BackgroundSettings,
    CropSettings,
)

_SCALE_SAMPLE_COUNT = 64


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


def resolve_camera_path(
    settings: BackgroundSettings,
) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    resolve normalized start and end look-at points for the camera path.

    unset points fall back to the image center so only-start or only-end
    matches the requested defaults.

    settings
        background camera settings
    """

    image_center = (0.5, 0.5)
    start = (
        (_clamp(settings.start_focus_x, 0.0, 1.0), _clamp(settings.start_focus_y, 0.0, 1.0))
        if settings.start_focus_enabled
        else image_center
    )
    end = (
        (_clamp(settings.end_focus_x, 0.0, 1.0), _clamp(settings.end_focus_y, 0.0, 1.0))
        if settings.end_focus_enabled
        else image_center
    )
    return start, end


def interpolate_camera_look_at(
    settings: BackgroundSettings,
    progress: float,
) -> tuple[float, float]:
    """
    interpolate the normalized look-at point along the camera path.

    settings
        background camera settings
    progress
        normalized animation progress 0..1
    """

    (start_x, start_y), (end_x, end_y) = resolve_camera_path(settings)
    amount = _clamp(progress, 0.0, 1.0)
    return (
        start_x + (end_x - start_x) * amount,
        start_y + (end_y - start_y) * amount,
    )


class BackgroundRenderer:
    """cached background renderer for a source image."""

    def __init__(
        self,
        source_image: np.ndarray,
        width: int,
        height: int,
        parallax_depth: np.ndarray | None = None,
        parallax_iterations: int = 24,
        crop: CropSettings | None = None,
        crop_target_size: tuple[int, int] | None = None,
    ) -> None:
        """
        prepare background renderer using the full source image.

        source_image
            loaded bgr source image
        width
            target frame width
        height
            target frame height
        crop
            optional framing window on the full source image
        crop_target_size
            optional full-output size whose aspect ratio defines the crop window
        """

        self.width = width
        self.height = height
        self.source_image = source_image
        self.source_h, self.source_w = source_image.shape[:2]
        self.parallax_depth = parallax_depth
        self.parallax_iterations = max(1, int(parallax_iterations))
        self.crop = crop if crop is not None else CropSettings()
        crop_width, crop_height = crop_target_size or (width, height)
        self.crop_target_width = max(1, int(crop_width))
        self.crop_target_height = max(1, int(crop_height))
        self._x_coords = np.arange(width, dtype=np.float32)[np.newaxis, :]
        self._y_coords = np.arange(height, dtype=np.float32)[:, np.newaxis]
        self._scale_envelope_cache_key: tuple[object, ...] | None = None
        self._scale_start = 0.0
        self._scale_slope = 0.0

    def render(
        self,
        time_seconds: float,
        duration_seconds: float,
        settings: BackgroundSettings,
        flight_speed: float = 1.0,
        parallax_travel: float = 0.0,
        parallax_lateral_percent: float = 0.0,
    ) -> np.ndarray:
        """
        render background frame at a given time.

        time_seconds
            current time in seconds
        duration_seconds
            total clip duration in seconds
        settings
            background movement settings
        flight_speed
            star flight speed used to size easing ramps
        """

        progress = camera_motion_progress(
            time_seconds,
            duration_seconds,
            settings,
            flight_speed,
        )
        matrix = self._build_transform_matrix(progress, settings)
        if self.parallax_depth is not None and parallax_travel > 0.0 and progress > 0.0:
            return self._remap_parallax(
                matrix,
                progress,
                parallax_travel,
                parallax_lateral_percent,
            )
        return self._remap(matrix)

    def has_empty_edges(
        self,
        duration_seconds: float,
        fps: int,
        settings: BackgroundSettings,
        flight_speed: float,
    ) -> bool:
        """Return whether any exported frame samples outside the source image."""

        frame_count = max(1, round(duration_seconds * fps))
        for frame_index in range(frame_count):
            progress = camera_motion_progress(
                frame_index / fps,
                duration_seconds,
                settings,
                flight_speed,
            )
            matrix = self._build_transform_matrix(progress, settings)
            if self._matrix_samples_outside_source(matrix):
                return True
        return False

    def _matrix_samples_outside_source(self, matrix: np.ndarray) -> bool:
        """Return whether any output corner maps outside the source image."""

        corners = np.array(
            [
                [0.0, 0.0],
                [self.width - 1.0, 0.0],
                [0.0, self.height - 1.0],
                [self.width - 1.0, self.height - 1.0],
            ],
            dtype=np.float32,
        )
        source_x = matrix[0, 0] * corners[:, 0] + matrix[0, 1] * corners[:, 1] + matrix[0, 2]
        source_y = matrix[1, 0] * corners[:, 0] + matrix[1, 1] * corners[:, 1] + matrix[1, 2]
        # Match cv2.remap: valid source coordinates are in [0, width) and [0, height).
        tolerance = 1e-4
        return bool(
            np.any(source_x < -tolerance)
            or np.any(source_x >= self.source_w)
            or np.any(source_y < -tolerance)
            or np.any(source_y >= self.source_h)
        )

    def _coordinate_maps(self, matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Build source-space coordinate maps from one inverse affine matrix."""

        map_x = np.asarray(
            matrix[0, 0] * self._x_coords + matrix[0, 1] * self._y_coords + matrix[0, 2],
            dtype=np.float32,
        )
        map_y = np.asarray(
            matrix[1, 0] * self._x_coords + matrix[1, 1] * self._y_coords + matrix[1, 2],
            dtype=np.float32,
        )
        return map_x, map_y

    def _remap(self, matrix: np.ndarray) -> np.ndarray:
        """
        remap source image using an affine coordinate map.

        matrix
            2x3 affine matrix mapping output pixels to source coordinates
        """

        map_x, map_y = self._coordinate_maps(matrix)

        return cv2.remap(
            self.source_image,
            map_x,
            map_y,
            interpolation=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

    def _remap_parallax(
        self,
        matrix: np.ndarray,
        progress: float,
        travel: float,
        lateral_percent: float,
    ) -> np.ndarray:
        """Apply continuous parallax after the complete background camera transform."""

        if self.parallax_depth is None:
            return self._remap(matrix)
        base_map_x, base_map_y = self._coordinate_maps(matrix)
        output_center_x = self.width / 2.0
        output_center_y = self.height / 2.0
        center_x = matrix[0, 0] * output_center_x + matrix[0, 1] * output_center_y + matrix[0, 2]
        center_y = matrix[1, 0] * output_center_x + matrix[1, 1] * output_center_y + matrix[1, 2]
        map_x, map_y = parallax_coordinate_maps(
            self.parallax_depth,
            base_map_x,
            base_map_y,
            (self.source_w, self.source_h),
            (float(center_x), float(center_y)),
            progress,
            travel,
            lateral_percent,
            iterations=self.parallax_iterations,
        )
        return cv2.remap(
            self.source_image,
            map_x,
            map_y,
            interpolation=cv2.INTER_LANCZOS4,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(0, 0, 0),
        )

    def _desired_source_center(
        self,
        progress: float,
        settings: BackgroundSettings,
    ) -> tuple[float, float]:
        """
        compute animated source center along the start/end camera path.

        progress
            normalized animation progress 0..1
        settings
            background settings
        """

        look_x, look_y = interpolate_camera_look_at(settings, progress)
        source_x, source_y = map_look_at_to_source(
            look_x,
            look_y,
            self.crop,
            self.source_w,
            self.source_h,
            self.crop_target_width,
            self.crop_target_height,
        )
        return source_x * self.source_w, source_y * self.source_h

    def _scale_factor(self, settings: BackgroundSettings) -> float:
        """
        return clamped user scale factor from settings.

        settings
            background settings
        """

        return _clamp(
            settings.scale_percent / 100.0,
            MIN_BACKGROUND_SCALE_PERCENT / 100.0,
            MAX_BACKGROUND_SCALE_PERCENT / 100.0,
        )

    def _required_scale(
        self,
        progress: float,
        settings: BackgroundSettings,
        cos_a: float,
        sin_a: float,
        center_x: float,
        center_y: float,
    ) -> float:
        """
        compute the per-frame minimum scale before linearization.

        progress
            normalized animation progress 0..1
        settings
            background settings
        cos_a
            cosine of the current rotation angle
        sin_a
            sine of the current rotation angle
        center_x
            source-space look-at x coordinate
        center_y
            source-space look-at y coordinate
        """

        scale_factor = self._scale_factor(settings)
        base_scale = framing_base_scale(
            self.crop,
            self.source_w,
            self.source_h,
            self.width,
            self.height,
            self.crop_target_width,
            self.crop_target_height,
        )
        zoom = 1.0 + (settings.zoom_percent / 100.0) * progress
        requested_scale = base_scale * scale_factor * zoom
        if not settings.fill_frame:
            return requested_scale

        rotated_width = abs(cos_a) * self.width + abs(sin_a) * self.height
        rotated_height = abs(sin_a) * self.width + abs(cos_a) * self.height
        centered_rotation_scale = (
            max(rotated_width / self.source_w, rotated_height / self.source_h) * scale_factor
        )
        scale = max(requested_scale, centered_rotation_scale)
        edge_x = max(1e-6, min(center_x, self.source_w - center_x))
        edge_y = max(1e-6, min(center_y, self.source_h - center_y))
        focus_safe_scale = (
            max(rotated_width / (2.0 * edge_x), rotated_height / (2.0 * edge_y)) * scale_factor
        )
        return max(scale, focus_safe_scale)

    def _scale_envelope_key(self, settings: BackgroundSettings) -> tuple[object, ...]:
        """
        build a cache key for scale-envelope settings.

        settings
            background settings
        """

        return (
            settings.scale_percent,
            settings.zoom_percent,
            settings.rotation_degrees,
            settings.fill_frame,
            settings.start_focus_enabled,
            settings.start_focus_x,
            settings.start_focus_y,
            settings.end_focus_enabled,
            settings.end_focus_x,
            settings.end_focus_y,
            self.crop.center_x,
            self.crop.center_y,
            self.crop.scale,
            self.crop_target_width,
            self.crop_target_height,
        )

    def _compute_scale_envelope(self, settings: BackgroundSettings) -> tuple[float, float]:
        """
        derive a constant-rate linear scale curve that covers every sampled frame.

        settings
            background settings
        """

        start = self._required_scale(
            0.0,
            settings,
            1.0,
            0.0,
            *self._desired_source_center(0.0, settings),
        )
        max_slope = 0.0
        for index in range(1, _SCALE_SAMPLE_COUNT + 1):
            progress = index / _SCALE_SAMPLE_COUNT
            angle = math.radians(settings.rotation_degrees * progress)
            cos_a = math.cos(angle)
            sin_a = math.sin(angle)
            center_x, center_y = self._desired_source_center(progress, settings)
            required = self._required_scale(progress, settings, cos_a, sin_a, center_x, center_y)
            max_slope = max(max_slope, (required - start) / progress)

        return start, max_slope

    def _linear_scale(self, progress: float, settings: BackgroundSettings) -> float:
        """
        return linearly interpolated scale from frame 1 through the last frame.

        progress
            normalized animation progress 0..1
        settings
            background settings
        """

        cache_key = self._scale_envelope_key(settings)
        if cache_key != self._scale_envelope_cache_key:
            self._scale_start, self._scale_slope = self._compute_scale_envelope(settings)
            self._scale_envelope_cache_key = cache_key

        amount = _clamp(progress, 0.0, 1.0)
        return self._scale_start + self._scale_slope * amount

    def _build_transform_matrix(self, progress: float, settings: BackgroundSettings) -> np.ndarray:
        """
        build affine matrix mapping output pixels to source coordinates.

        progress
            normalized animation progress 0..1
        settings
            background settings
        """

        angle = math.radians(settings.rotation_degrees * progress)
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        center_x, center_y = self._desired_source_center(progress, settings)
        scale = self._linear_scale(progress, settings)

        rotated_width = abs(cos_a) * self.width + abs(sin_a) * self.height
        rotated_height = abs(sin_a) * self.width + abs(cos_a) * self.height

        if settings.fill_frame:
            half_x = rotated_width / (2.0 * scale)
            half_y = rotated_height / (2.0 * scale)
            render_center_x = _clamp(center_x, half_x, self.source_w - half_x)
            render_center_y = _clamp(center_y, half_y, self.source_h - half_y)
        else:
            render_center_x = center_x
            render_center_y = center_y

        output_center_x = self.width / 2.0
        output_center_y = self.height / 2.0

        a = cos_a / scale
        b = sin_a / scale
        d = -sin_a / scale
        e = cos_a / scale
        c = render_center_x - a * output_center_x - b * output_center_y
        f = render_center_y - d * output_center_x - e * output_center_y

        return np.array([[a, b, c], [d, e, f]], dtype=np.float32)

    def focus_screen_position(
        self,
        progress: float,
        settings: BackgroundSettings,
    ) -> tuple[float, float]:
        """
        return where the path end point appears on the output frame.

        progress
            normalized animation progress 0..1
        settings
            background movement settings
        """

        matrix = self._build_transform_matrix(progress, settings)
        a, b, c = matrix[0]
        d, e, f = matrix[1]
        _, (end_x, end_y) = resolve_camera_path(settings)
        source_x, source_y = map_look_at_to_source(
            end_x,
            end_y,
            self.crop,
            self.source_w,
            self.source_h,
            self.crop_target_width,
            self.crop_target_height,
        )
        focus_x = source_x * self.source_w
        focus_y = source_y * self.source_h
        determinant = a * e - b * d
        if abs(determinant) < 1e-8:
            return self.width / 2.0, self.height / 2.0

        screen_x = (e * (focus_x - c) - b * (focus_y - f)) / determinant
        screen_y = (-d * (focus_x - c) + a * (focus_y - f)) / determinant
        return float(screen_x), float(screen_y)
