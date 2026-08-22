"""Create stable colors and brightness values for synthetic stars."""

from __future__ import annotations

import math

import numpy as np

# Approximate main sequence mix ordered as blue, white, yellow, orange, and red.
SPECTRAL_CLASS_WEIGHTS: tuple[float, ...] = (0.08, 0.20, 0.34, 0.27, 0.11)
SPECTRAL_TEMPERATURE_RANGES: tuple[tuple[float, float], ...] = (
    (9000.0, 18000.0),
    (6800.0, 9400.0),
    (5400.0, 6800.0),
    (3900.0, 5400.0),
    (2800.0, 3900.0),
)


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


def temperature_to_rgb(kelvin: float) -> np.ndarray:
    """
    approximate visible star color from color temperature.

    kelvin
        color temperature in kelvin
    """

    temperature = _clamp(kelvin, 1000.0, 40000.0) / 100.0

    if temperature <= 66.0:
        red = 255.0
        green = 99.4708025861 * math.log(temperature) - 161.1195681661
        if temperature <= 19.0:
            blue = 0.0
        else:
            blue = 138.5177312231 * math.log(temperature - 10.0) - 305.0447927307
    else:
        red = 329.698727446 * ((temperature - 60.0) ** -0.1332047592)
        green = 288.1221695283 * ((temperature - 60.0) ** -0.0755148492)
        blue = 255.0

    rgb = np.array(
        [
            _clamp(red, 0.0, 255.0),
            _clamp(green, 0.0, 255.0),
            _clamp(blue, 0.0, 255.0),
        ],
        dtype=np.float32,
    )
    rgb /= 255.0
    peak = max(float(rgb.max()), 1e-6)
    rgb /= peak
    return np.clip(rgb, 0.0, 1.0)


def _boost_saturation(color: np.ndarray, amount: float) -> np.ndarray:
    """
    boost color saturation around the luminance center.

    color
        normalized rgb color
    amount
        saturation multiplier
    """

    color = np.asarray(color, dtype=np.float32)
    luminance = float(color.mean())
    boosted = luminance + (color - luminance) * amount
    return np.clip(boosted, 0.0, 1.0)


def _map_color_intensity(intensity: float) -> float:
    """
    map ui color intensity to effective spectral strength.

    intensity
        user color intensity from 0 to 1
    """

    intensity = _clamp(intensity, 0.0, 1.0)
    if intensity <= 0.0:
        return 0.0
    # A value near 30 percent gives a subtle tint. Full strength makes colors clear.
    return _clamp((intensity / 0.30) ** 0.82, 0.0, 4.0)


def sample_star_brightness(rng: np.random.Generator, realism: float) -> float:
    """
    sample star brightness with optional magnitude realism.

    rng
        random number generator
    realism
        realism strength from 0 to 1
    """

    uniform = float(rng.uniform(0.35, 1.0))
    realism = _clamp(realism, 0.0, 1.0)
    if realism <= 0.0:
        return uniform

    exponent = 1.0 + realism * 3.8
    skewed = 0.12 + float(rng.uniform(0.0, 1.0) ** exponent) * 0.88
    return uniform * (1.0 - realism) + skewed * realism


def bias_temperature_for_star_strength(
    temperature: float,
    brightness: float,
    size: float,
    *,
    size_min: float = 0.35,
    size_max: float = 2.6,
) -> float:
    """
    bias temperature so large bright stars run hotter and bluer.

    mid-strength stars keep their sampled class so yellow/white stay common.
    faint small stars lean slightly cooler.

    temperature
        base color temperature in kelvin
    brightness
        normalized star brightness
    size
        sampled star size seed
    size_min
        lower size seed bound
    size_max
        upper size seed bound
    """

    brightness = _clamp(brightness, 0.0, 1.0)
    # Treat the common large seeds near 1.0 as strong without requiring the rare maximum.
    size_norm = _clamp((_clamp(size, size_min, size_max) - size_min) / 1.25, 0.0, 1.0)
    strength = _clamp(0.40 * brightness + 0.60 * size_norm, 0.0, 1.0)

    mid = 0.40
    if strength <= mid:
        t = strength / mid
        factor = 0.88 + t * 0.12
    else:
        t = (strength - mid) / (1.0 - mid)
        t = t * t * (3.0 - 2.0 * t)
        factor = 1.0 + t * 0.55

    adjusted = temperature * factor
    if strength > mid:
        # Move strong stars toward blue white even when the sampled base is yellow.
        blue_floor = 6200.0 + t * 4200.0
        adjusted = max(adjusted, temperature * (1.0 - t) + blue_floor * t)

    return _clamp(adjusted, 2800.0, 18000.0)


def sample_star_temperatures(rng: np.random.Generator, count: int) -> np.ndarray:
    """
    sample color temperatures using realistic spectral class distribution.

    rng
        random number generator
    count
        number of stars
    """

    class_index = rng.choice(len(SPECTRAL_CLASS_WEIGHTS), size=count, p=SPECTRAL_CLASS_WEIGHTS)
    temperatures = np.empty(count, dtype=np.float32)
    for index, (low, high) in enumerate(SPECTRAL_TEMPERATURE_RANGES):
        mask = class_index == index
        if int(mask.sum()) > 0:
            temperatures[mask] = rng.uniform(low, high, int(mask.sum()))
    return temperatures


def resolve_star_color(
    temperature: float,
    tint_strength: float,
    intensity: float,
) -> tuple[float, float, float]:
    """
    resolve final star color from temperature and user intensity.

    temperature
        color temperature in kelvin
    tint_strength
        per-star tint blend strength
    intensity
        user color intensity from 0 to 1
    """

    base_color = temperature_to_rgb(temperature)
    strength = _map_color_intensity(intensity)
    tint = _clamp(tint_strength, 0.0, 1.0) * strength
    tinted = 1.0 - (1.0 - base_color) * tint
    saturation = 1.0 + strength * 0.95
    final_color = _boost_saturation(tinted, saturation)
    return float(final_color[0]), float(final_color[1]), float(final_color[2])


def star_rgb_from_temperature(temperature: float, tint_strength: float) -> np.ndarray:
    """Build a normalized RGB color for one star."""

    color = temperature_to_rgb(temperature)
    tint = _clamp(tint_strength, 0.0, 1.0)
    return 1.0 - (1.0 - color) * tint


def apply_color_intensity(color: np.ndarray, intensity: float) -> tuple[float, float, float]:
    """Blend a star color toward neutral white according to the selected intensity."""

    intensity = _clamp(intensity, 0.0, 1.0)
    strength = _map_color_intensity(intensity)
    tinted = 1.0 - (1.0 - np.asarray(color, dtype=np.float32)) * strength
    final_color = _boost_saturation(tinted, 1.0 + strength * 0.95)
    return float(final_color[0]), float(final_color[1]), float(final_color[2])
