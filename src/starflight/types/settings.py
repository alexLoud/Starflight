"""Define project data and convert settings to and from saved JSON data."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

MAX_BACKGROUND_ZOOM_PERCENT = 50.0
MAX_BACKGROUND_ROTATION_DEGREES = 45.0
MIN_BACKGROUND_SCALE_PERCENT = 10.0
MAX_BACKGROUND_SCALE_PERCENT = 200.0
MIN_STAR_COUNT = 50
MAX_STAR_COUNT = 3000


class DensityPreset(str, Enum):
    """star density presets."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CUSTOM = "custom"


class EasingMode(str, Enum):
    """camera motion easing over the clip."""

    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"


class ImageMotionMode(str, Enum):
    """movement mode for the source image."""

    MANUAL = "manual"
    PARALLAX = "parallax"


class ExportQuality(str, Enum):
    """export quality presets."""

    STANDARD = "standard"
    HIGH = "high"


class RenderQuality(str, Enum):
    """render quality for preview vs export."""

    PREVIEW = "preview"
    EXPORT = "export"


DENSITY_STAR_COUNTS: dict[DensityPreset, int] = {
    DensityPreset.LOW: 500,
    DensityPreset.MEDIUM: 1500,
    DensityPreset.HIGH: 2500,
}

DENSITY_LABELS: dict[DensityPreset, str] = {
    DensityPreset.LOW: "Low",
    DensityPreset.MEDIUM: "Medium",
    DensityPreset.HIGH: "High",
    DensityPreset.CUSTOM: "Custom",
}

EXPORT_QUALITY_LABELS: dict[ExportQuality, str] = {
    ExportQuality.STANDARD: "Standard",
    ExportQuality.HIGH: "High",
}

RESOLUTION_PRESETS: dict[str, tuple[int, int]] = {
    "1920 x 1080 (1080p Landscape)": (1920, 1080),
    "2560 x 1440 (1440p Landscape)": (2560, 1440),
    "3840 x 2160 (4K Landscape)": (3840, 2160),
    "1080 x 1920 (1080p Portrait)": (1080, 1920),
    "1440 x 2560 (1440p Portrait)": (1440, 2560),
    "2160 x 3840 (4K Portrait)": (2160, 3840),
    "1080 x 1080 (1080p Square)": (1080, 1080),
    "1440 x 1440 (1440p Square)": (1440, 1440),
    "2160 x 2160 (4K Square)": (2160, 2160),
}

PORTRAIT_1080_RESOLUTION = (1080, 1920)
LANDSCAPE_1080_RESOLUTION = (1920, 1080)
SQUARE_1080_RESOLUTION = (1080, 1080)


def resolution_for_image_orientation(width: int, height: int) -> tuple[int, int]:
    """
    pick default target resolution from source image orientation.

    width
        source image width in pixels
    height
        source image height in pixels
    """

    if width == height:
        return SQUARE_1080_RESOLUTION
    if width > height:
        return LANDSCAPE_1080_RESOLUTION
    return PORTRAIT_1080_RESOLUTION


@dataclass
class ResolutionSettings:
    """target video resolution."""

    width: int = 1920
    height: int = 1080


@dataclass
class CropSettings:
    """normalized fixed-aspect source-image crop."""

    center_x: float = 0.5
    center_y: float = 0.5
    scale: float = 1.0


@dataclass
class BackgroundSettings:
    """background camera movement settings."""

    motion_mode: ImageMotionMode = ImageMotionMode.MANUAL
    scale_percent: float = 100.0
    zoom_percent: float = 0.0
    rotation_degrees: float = 0.0
    easing: EasingMode = EasingMode.LINEAR
    start_focus_enabled: bool = False
    start_focus_x: float = 0.5
    start_focus_y: float = 0.5
    end_focus_enabled: bool = False
    end_focus_x: float = 0.5
    end_focus_y: float = 0.5
    fill_frame: bool = False


@dataclass
class ParallaxSettings:
    """parallax export settings."""

    strength: int = 4


@dataclass
class StarSettings:
    """star appearance and animation settings."""

    density_preset: DensityPreset = DensityPreset.MEDIUM
    star_count: int = 1500
    min_size: float = 1.0
    max_size: float = 5.0
    brightness: float = 0.8
    glow_intensity: float = 0.0
    glow_depth_boost: float = 0.0
    color_intensity: float = 0.0
    speed: float = 1.0
    magnitude_realism: float = 0.0
    size_spread: float = 0.25
    seed: int = 42


@dataclass
class ExportSettings:
    """export quality settings."""

    quality: ExportQuality = ExportQuality.HIGH
    crf: int = 18


@dataclass
class SidebarUiSettings:
    """persisted expand/collapse state for settings sidebar sections."""

    project_section_expanded: bool = True
    image_motion_section_expanded: bool = True
    crop_section_expanded: bool = False
    focus_section_expanded: bool = False
    star_appearance_section_expanded: bool = True
    star_effects_section_expanded: bool = True
    star_animation_section_expanded: bool = True


@dataclass
class ProjectSettings:
    """all project settings combined."""

    resolution: ResolutionSettings = field(default_factory=ResolutionSettings)
    duration_seconds: float = 10.0
    fps: int = 30
    crop: CropSettings = field(default_factory=CropSettings)
    background: BackgroundSettings = field(default_factory=BackgroundSettings)
    parallax: ParallaxSettings = field(default_factory=ParallaxSettings)
    stars: StarSettings = field(default_factory=StarSettings)
    export: ExportSettings = field(default_factory=ExportSettings)
    ui: SidebarUiSettings = field(default_factory=SidebarUiSettings)

    def clone(self) -> ProjectSettings:
        """return a deep copy of settings."""

        return deepcopy(self)


@dataclass
class Project:
    """full project state."""

    name: str = "Untitled Project"
    source_image: str | None = None
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    version: int = 1

    def clone(self) -> Project:
        """return a deep copy of the project."""

        return deepcopy(self)


def density_preset_from_count(star_count: int) -> DensityPreset:
    """map star count back to a density preset if it matches."""

    for preset, count in DENSITY_STAR_COUNTS.items():
        if star_count == count:
            return preset
    return DensityPreset.CUSTOM


def apply_density_preset(settings: StarSettings, preset: DensityPreset) -> None:
    """Apply a density preset to the star count."""

    settings.density_preset = preset
    if preset != DensityPreset.CUSTOM:
        settings.star_count = DENSITY_STAR_COUNTS[preset]


def export_crf_for_quality(quality: ExportQuality) -> int:
    """return crf value for export quality preset."""

    if quality == ExportQuality.STANDARD:
        return 23
    return 18


def _enum_to_json_value(value: Enum | str) -> str:
    """
    convert enum or plain string to a json-safe enum value.

    value
        enum member or raw string value
    """

    if isinstance(value, Enum):
        return value.value
    return str(value)


def coerce_density_preset(value: DensityPreset | str | None) -> DensityPreset:
    """
    normalize density preset from enum or qt user data.

    value
        density preset enum or string value
    """

    if value is None:
        return DensityPreset.MEDIUM
    if isinstance(value, DensityPreset):
        return value
    return DensityPreset(value)


def coerce_export_quality(value: ExportQuality | str | None) -> ExportQuality:
    """Normalize export quality from enum or Qt user data."""

    if value is None:
        return ExportQuality.HIGH
    if isinstance(value, ExportQuality):
        return value
    return ExportQuality(value)


def coerce_easing_mode(value: EasingMode | str | None) -> EasingMode:
    """
    normalize easing mode from enum or qt user data.

    value
        easing enum or string value
    """

    if value is None:
        return EasingMode.LINEAR
    if isinstance(value, EasingMode):
        return value
    return EasingMode(value)


def coerce_image_motion_mode(value: ImageMotionMode | str | None) -> ImageMotionMode:
    """Normalize an image movement mode from enum or stored string."""

    if value is None or value == "none":
        return ImageMotionMode.MANUAL
    if isinstance(value, ImageMotionMode):
        return value
    return ImageMotionMode(value)


def _load_color_intensity(stars_data: dict[str, Any]) -> float:
    """
    load color intensity with backward compatibility for older projects.

    stars_data
        stars section from project json
    """

    if "color_intensity" in stars_data:
        return float(stars_data["color_intensity"])
    if "color_variation" in stars_data:
        legacy = float(stars_data["color_variation"])
        return min(1.0, legacy * 10.0 + 0.15)
    return 0.0


def _load_easing_mode(background_data: dict[str, Any]) -> EasingMode:
    """
    load easing with linear fallback for older projects.

    background_data
        background section from project json
    """

    if "easing" not in background_data:
        return EasingMode.LINEAR
    return EasingMode(background_data["easing"])


def _load_image_motion_mode(
    background_data: dict[str, Any],
    parallax_data: dict[str, Any],
) -> ImageMotionMode:
    """Load the movement mode and migrate projects saved before modes existed."""

    if "motion_mode" in background_data:
        return coerce_image_motion_mode(background_data["motion_mode"])
    if bool(parallax_data.get("enabled", False)):
        return ImageMotionMode.PARALLAX
    return ImageMotionMode.MANUAL


def _load_focus_points(background_data: dict[str, Any]) -> dict[str, float | bool]:
    """
    load start/end focus points with migration from legacy focus box fields.

    background_data
        background section from project json
    """

    has_new_fields = any(
        key in background_data
        for key in (
            "start_focus_enabled",
            "end_focus_enabled",
            "start_focus_x",
            "start_focus_y",
            "end_focus_x",
            "end_focus_y",
        )
    )
    if has_new_fields:
        return {
            "start_focus_enabled": bool(background_data.get("start_focus_enabled", False)),
            "start_focus_x": float(background_data.get("start_focus_x", 0.5)),
            "start_focus_y": float(background_data.get("start_focus_y", 0.5)),
            "end_focus_enabled": bool(background_data.get("end_focus_enabled", False)),
            "end_focus_x": float(background_data.get("end_focus_x", 0.5)),
            "end_focus_y": float(background_data.get("end_focus_y", 0.5)),
        }

    # Older projects stored one target point as focus_x and focus_y.
    return {
        "start_focus_enabled": False,
        "start_focus_x": 0.5,
        "start_focus_y": 0.5,
        "end_focus_enabled": True,
        "end_focus_x": float(background_data.get("focus_x", 0.5)),
        "end_focus_y": float(background_data.get("focus_y", 0.5)),
    }


def _load_crop_settings(data: dict[str, Any]) -> CropSettings:
    """Load crop values. Missing crop data uses the largest centered fit."""

    crop_data = data.get("crop")
    if crop_data is None:
        return CropSettings()
    return CropSettings(
        center_x=float(crop_data.get("center_x", 0.5)),
        center_y=float(crop_data.get("center_y", 0.5)),
        scale=float(crop_data.get("scale", 1.0)),
    )


def settings_to_dict(settings: ProjectSettings) -> dict[str, Any]:
    """serialize settings to a json-compatible dict."""

    data = asdict(settings)
    data["stars"]["density_preset"] = _enum_to_json_value(settings.stars.density_preset)
    data["export"]["quality"] = _enum_to_json_value(settings.export.quality)
    data["background"]["easing"] = _enum_to_json_value(settings.background.easing)
    data["background"]["motion_mode"] = _enum_to_json_value(settings.background.motion_mode)
    return json.loads(json.dumps(data, ensure_ascii=False))


def settings_from_dict(data: dict[str, Any]) -> ProjectSettings:
    """deserialize settings from dict."""

    stars_data = data.get("stars", {})
    export_data = data.get("export", {})
    resolution_data = data.get("resolution", {})
    background_data = data.get("background", {})
    parallax_data = data.get("parallax", {})
    ui_data = data.get("ui", {})

    stars = StarSettings(
        density_preset=DensityPreset(stars_data.get("density_preset", "medium")),
        star_count=int(stars_data.get("star_count", 1500)),
        min_size=float(stars_data.get("min_size", 1.0)),
        max_size=float(stars_data.get("max_size", 5.0)),
        brightness=float(stars_data.get("brightness", 0.8)),
        glow_intensity=float(stars_data.get("glow_intensity", 0.0)),
        glow_depth_boost=float(stars_data.get("glow_depth_boost", 0.0)),
        color_intensity=_load_color_intensity(stars_data),
        speed=float(stars_data.get("speed", 1.0)),
        magnitude_realism=float(stars_data.get("magnitude_realism", 0.0)),
        size_spread=float(stars_data.get("size_spread", 0.25)),
        seed=int(stars_data.get("seed", 42)),
    )

    export_quality = ExportQuality(export_data.get("quality", "high"))
    export_settings = ExportSettings(
        quality=export_quality,
        crf=int(export_data.get("crf", export_crf_for_quality(export_quality))),
    )

    ui_settings = SidebarUiSettings(
        project_section_expanded=bool(ui_data.get("project_section_expanded", True)),
        image_motion_section_expanded=bool(
            ui_data.get(
                "image_motion_section_expanded",
                ui_data.get("background_section_expanded", True),
            )
        ),
        crop_section_expanded=bool(ui_data.get("crop_section_expanded", False)),
        focus_section_expanded=bool(ui_data.get("focus_section_expanded", False)),
        star_appearance_section_expanded=bool(
            ui_data.get("star_appearance_section_expanded", True)
        ),
        star_effects_section_expanded=bool(ui_data.get("star_effects_section_expanded", True)),
        star_animation_section_expanded=bool(ui_data.get("star_animation_section_expanded", True)),
    )

    return ProjectSettings(
        resolution=ResolutionSettings(
            width=int(resolution_data.get("width", 1920)),
            height=int(resolution_data.get("height", 1080)),
        ),
        duration_seconds=float(data.get("duration_seconds", 10.0)),
        fps=int(data.get("fps", 30)),
        crop=_load_crop_settings(data),
        background=BackgroundSettings(
            motion_mode=_load_image_motion_mode(background_data, parallax_data),
            scale_percent=float(background_data.get("scale_percent", 100.0)),
            zoom_percent=float(background_data.get("zoom_percent", 0.0)),
            rotation_degrees=float(background_data.get("rotation_degrees", 0.0)),
            easing=_load_easing_mode(background_data),
            **_load_focus_points(background_data),
            fill_frame=bool(background_data.get("fill_frame", False)),
        ),
        parallax=ParallaxSettings(
            strength=int(parallax_data.get("strength", 4)),
        ),
        stars=stars,
        export=export_settings,
        ui=ui_settings,
    )
