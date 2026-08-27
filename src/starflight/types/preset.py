"""Define look presets and apply them to project settings."""

from __future__ import annotations

import re
import unicodedata
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from starflight.types.settings import (
    DensityPreset,
    EasingMode,
    ImageMotionMode,
    ParallaxSettings,
    ProjectSettings,
    StarSettings,
    coerce_easing_mode,
    coerce_image_motion_mode,
    coerce_parallax_strength,
)

PRESET_FORMAT_VERSION = 1

_STAR_FIELDS = (
    "density_preset",
    "star_count",
    "min_size",
    "max_size",
    "brightness",
    "glow_intensity",
    "glow_depth_boost",
    "color_intensity",
    "speed",
    "magnitude_realism",
    "size_spread",
    "seed",
)

_BACKGROUND_LOOK_FIELDS = (
    "motion_mode",
    "zoom_percent",
    "rotation_degrees",
    "easing",
    "fill_frame",
)


@dataclass
class LookBackgroundSettings:
    """camera look fields stored in a preset."""

    motion_mode: ImageMotionMode = ImageMotionMode.MANUAL
    zoom_percent: float = 0.0
    rotation_degrees: float = 0.0
    easing: EasingMode = EasingMode.LINEAR
    fill_frame: bool = False


@dataclass
class LookSettings:
    """look subset of project settings."""

    stars: StarSettings
    background: LookBackgroundSettings
    parallax: ParallaxSettings


@dataclass
class LookPreset:
    """a named look preset loaded from json."""

    id: str
    name: str
    description: str
    settings: LookSettings
    source_settings: dict[str, Any]
    builtin: bool = False
    format_version: int = PRESET_FORMAT_VERSION
    path: Path | None = None


def look_from_project_settings(settings: ProjectSettings) -> LookSettings:
    """
    copy the look fields from project settings.

    settings
        current project settings
    """

    background = settings.background
    return LookSettings(
        stars=deepcopy(settings.stars),
        background=LookBackgroundSettings(
            motion_mode=background.motion_mode,
            zoom_percent=background.zoom_percent,
            rotation_degrees=background.rotation_degrees,
            easing=background.easing,
            fill_frame=background.fill_frame,
        ),
        parallax=deepcopy(settings.parallax),
    )


def look_settings_to_dict(look: LookSettings) -> dict[str, Any]:
    """
    serialize look settings to a json-compatible dict.

    look
        look subset to store
    """

    return {
        "stars": {
            "density_preset": look.stars.density_preset.value,
            "star_count": look.stars.star_count,
            "min_size": look.stars.min_size,
            "max_size": look.stars.max_size,
            "brightness": look.stars.brightness,
            "glow_intensity": look.stars.glow_intensity,
            "glow_depth_boost": look.stars.glow_depth_boost,
            "color_intensity": look.stars.color_intensity,
            "speed": look.stars.speed,
            "magnitude_realism": look.stars.magnitude_realism,
            "size_spread": look.stars.size_spread,
            "seed": look.stars.seed,
        },
        "background": {
            "motion_mode": look.background.motion_mode.value,
            "zoom_percent": look.background.zoom_percent,
            "rotation_degrees": look.background.rotation_degrees,
            "easing": look.background.easing.value,
            "fill_frame": look.background.fill_frame,
        },
        "parallax": {
            "strength": look.parallax.strength.value,
        },
    }


def look_settings_from_dict(data: dict[str, Any]) -> LookSettings:
    """
    deserialize look settings from a dict, using defaults for missing fields.

    data
        settings object from preset json
    """

    stars_data = data.get("stars")
    if not isinstance(stars_data, dict):
        stars_data = {}
    background_data = data.get("background")
    if not isinstance(background_data, dict):
        background_data = {}
    parallax_data = data.get("parallax")
    if not isinstance(parallax_data, dict):
        parallax_data = {}

    star_defaults = StarSettings()
    background_defaults = LookBackgroundSettings()
    parallax_defaults = ParallaxSettings()

    density_value = stars_data.get("density_preset", star_defaults.density_preset.value)
    stars = StarSettings(
        density_preset=DensityPreset(density_value),
        star_count=int(stars_data.get("star_count", star_defaults.star_count)),
        min_size=float(stars_data.get("min_size", star_defaults.min_size)),
        max_size=float(stars_data.get("max_size", star_defaults.max_size)),
        brightness=float(stars_data.get("brightness", star_defaults.brightness)),
        glow_intensity=float(stars_data.get("glow_intensity", star_defaults.glow_intensity)),
        glow_depth_boost=float(stars_data.get("glow_depth_boost", star_defaults.glow_depth_boost)),
        color_intensity=float(stars_data.get("color_intensity", star_defaults.color_intensity)),
        speed=float(stars_data.get("speed", star_defaults.speed)),
        magnitude_realism=float(
            stars_data.get("magnitude_realism", star_defaults.magnitude_realism)
        ),
        size_spread=float(stars_data.get("size_spread", star_defaults.size_spread)),
        seed=int(stars_data.get("seed", star_defaults.seed)),
    )

    return LookSettings(
        stars=stars,
        background=LookBackgroundSettings(
            motion_mode=coerce_image_motion_mode(
                background_data.get("motion_mode", background_defaults.motion_mode),
            ),
            zoom_percent=float(
                background_data.get("zoom_percent", background_defaults.zoom_percent),
            ),
            rotation_degrees=float(
                background_data.get(
                    "rotation_degrees",
                    background_defaults.rotation_degrees,
                ),
            ),
            easing=coerce_easing_mode(background_data.get("easing", background_defaults.easing)),
            fill_frame=bool(background_data.get("fill_frame", background_defaults.fill_frame)),
        ),
        parallax=ParallaxSettings(
            strength=coerce_parallax_strength(
                parallax_data.get("strength", parallax_defaults.strength),
            ),
        ),
    )


def look_preset_from_settings(
    name: str,
    description: str,
    settings: ProjectSettings,
    *,
    preset_id: str,
) -> LookPreset:
    """
    build a user preset from the current project look.

    name
        preset display name
    description
        optional short description
    settings
        current project settings
    preset_id
        stable file identifier
    """

    look = look_from_project_settings(settings)
    source_settings = look_settings_to_dict(look)
    return LookPreset(
        id=preset_id,
        name=name.strip(),
        description=description.strip(),
        settings=look,
        source_settings=source_settings,
        builtin=False,
        format_version=PRESET_FORMAT_VERSION,
    )


def apply_look(project_settings: ProjectSettings, preset: LookPreset) -> None:
    """
    merge present look fields into project settings.

    project_settings
        project settings to update
    preset
        look preset to apply
    """

    stars_data = preset.source_settings.get("stars")
    if isinstance(stars_data, dict):
        for field_name in _STAR_FIELDS:
            if field_name in stars_data:
                setattr(
                    project_settings.stars,
                    field_name,
                    getattr(preset.settings.stars, field_name),
                )

    background_data = preset.source_settings.get("background")
    if isinstance(background_data, dict):
        for field_name in _BACKGROUND_LOOK_FIELDS:
            if field_name in background_data:
                setattr(
                    project_settings.background,
                    field_name,
                    getattr(preset.settings.background, field_name),
                )

    parallax_data = preset.source_settings.get("parallax")
    if isinstance(parallax_data, dict) and "strength" in parallax_data:
        project_settings.parallax.strength = preset.settings.parallax.strength


def preset_id_from_name(name: str) -> str:
    """
    build a filesystem-safe preset id from a display name.

    name
        preset display name
    """

    normalized = unicodedata.normalize("NFKD", name.strip())
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")
    return slug or "preset"


def unique_preset_id(base_id: str, existing_ids: set[str]) -> str:
    """
    return a preset id that does not collide with existing ids.

    base_id
        preferred identifier
    existing_ids
        ids already in use
    """

    if base_id not in existing_ids:
        return base_id
    index = 2
    candidate = f"{base_id}-{index}"
    while candidate in existing_ids:
        index += 1
        candidate = f"{base_id}-{index}"
    return candidate
