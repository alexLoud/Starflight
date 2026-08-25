"""Map clip time onto shared camera and star-flight progress.

Easing uses a trapezoidal velocity profile: a short ramp at the start and/or end,
then a constant cruise. The ramp length scales with clip duration and flight speed.
Motion runs from the first frame to the last. Stars use the same eased clock.
"""

from __future__ import annotations

from starflight.types.settings import BackgroundSettings, EasingMode

# ramp length at flight speed 1.0, as a fraction of clip duration
_EASE_FRACTION_AT_SPEED_ONE = 0.22
_MAX_EASE_FRACTION = 0.33
_MIN_EASE_SECONDS = 0.35
# start/end speed as a fraction of linear 1/duration, so the first frames move
_MIN_VELOCITY_RATIO = 0.45


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


def _ease_window_seconds(duration_seconds: float, flight_speed: float) -> float:
    """
    return the start/end ramp length in seconds.

    duration_seconds
        total clip duration
    flight_speed
        star flight speed; faster flight shortens the ramp
    """

    if duration_seconds <= 0.0:
        return 0.0
    speed_scale = _clamp(flight_speed, 0.5, 2.0)
    window = duration_seconds * _EASE_FRACTION_AT_SPEED_ONE / speed_scale
    minimum = min(_MIN_EASE_SECONDS, duration_seconds * 0.12)
    maximum = duration_seconds * _MAX_EASE_FRACTION
    return _clamp(window, minimum, maximum)


def _ramp_windows(
    duration_seconds: float,
    flight_speed: float,
    mode: EasingMode,
) -> tuple[float, float]:
    """
    return ease-in and ease-out window lengths in seconds.

    duration_seconds
        total clip duration
    flight_speed
        star flight speed
    mode
        selected easing curve
    """

    if duration_seconds <= 0.0 or mode == EasingMode.LINEAR:
        return 0.0, 0.0
    window = _ease_window_seconds(duration_seconds, flight_speed)
    ease_in = window if mode in (EasingMode.EASE_IN, EasingMode.EASE_IN_OUT) else 0.0
    ease_out = window if mode in (EasingMode.EASE_OUT, EasingMode.EASE_IN_OUT) else 0.0
    total = ease_in + ease_out
    if total > duration_seconds > 0.0:
        scale = duration_seconds / total
        ease_in *= scale
        ease_out *= scale
    return ease_in, ease_out


def camera_motion_progress(
    time_seconds: float,
    duration_seconds: float,
    settings: BackgroundSettings,
    flight_speed: float = 1.0,
) -> float:
    """
    return eased progress for zoom, rotation, look-at, and star flight.

    time_seconds
        current clip time
    duration_seconds
        total clip duration
    settings
        background camera settings including easing
    flight_speed
        star flight speed; faster flight shortens ease ramps
    """

    if duration_seconds <= 0.0:
        return 0.0
    time_seconds = _clamp(time_seconds, 0.0, duration_seconds)
    ease_in, ease_out = _ramp_windows(duration_seconds, flight_speed, settings.easing)
    if ease_in <= 0.0 and ease_out <= 0.0:
        return time_seconds / duration_seconds

    v_min = _MIN_VELOCITY_RATIO / duration_seconds
    cruise_span = duration_seconds - (ease_in / 2.0) - (ease_out / 2.0)
    v_cruise = (1.0 - v_min * (ease_in + ease_out) / 2.0) / cruise_span
    if v_cruise < v_min:
        return time_seconds / duration_seconds

    if ease_in > 0.0 and time_seconds <= ease_in:
        acceleration = (v_cruise - v_min) / ease_in
        return _clamp(
            v_min * time_seconds + 0.5 * acceleration * time_seconds * time_seconds,
            0.0,
            1.0,
        )

    distance_in = ease_in * (v_min + v_cruise) / 2.0 if ease_in > 0.0 else 0.0
    cruise_end = duration_seconds - ease_out
    if time_seconds <= cruise_end or ease_out <= 0.0:
        return _clamp(distance_in + v_cruise * (time_seconds - ease_in), 0.0, 1.0)

    distance_before_out = distance_in + v_cruise * (cruise_end - ease_in)
    out_time = time_seconds - cruise_end
    deceleration = (v_min - v_cruise) / ease_out
    return _clamp(
        distance_before_out + v_cruise * out_time + 0.5 * deceleration * out_time * out_time,
        0.0,
        1.0,
    )
