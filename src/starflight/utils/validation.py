"""Validate project settings before rendering or exporting."""

from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

from starflight.app.constants import package_dir
from starflight.core.project import resolve_source_image_path
from starflight.types.settings import MAX_STAR_COUNT, MIN_STAR_COUNT, Project


@dataclass
class ValidationResult:
    """validation result with optional error message."""

    ok: bool
    message: str = ""


def ffmpeg_executable() -> str | None:
    """return path to bundled ffmpeg, or system ffmpeg on path."""

    name = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    bundled = package_dir() / "bin" / name
    if bundled.is_file():
        return str(bundled)
    return shutil.which("ffmpeg")


def is_ffmpeg_available() -> bool:
    """check whether a usable ffmpeg binary is available."""

    return ffmpeg_executable() is not None


def validate_project_for_render(
    project: Project,
    project_path: Path | None = None,
) -> ValidationResult:
    """
    validate project before preview or export.

    project
        project to validate
    project_path
        optional path to project file for resolving relative image paths
    """

    if not project.source_image:
        return ValidationResult(False, "Please load an image first.")

    image_path = resolve_source_image_path(project_path, project.source_image)
    if image_path is None or not image_path.exists():
        return ValidationResult(False, "The image was not found. Please load it again.")

    width = project.settings.resolution.width
    height = project.settings.resolution.height
    if width < 480 or height < 480:
        return ValidationResult(False, "Target resolution must be at least 480 pixels.")
    if width % 2 != 0 or height % 2 != 0:
        return ValidationResult(False, "Width and height must be even numbers.")

    duration = project.settings.duration_seconds
    if duration < 3 or duration > 60:
        return ValidationResult(False, "Video length must be between 3 and 60 seconds.")

    fps = project.settings.fps
    if fps not in (24, 30, 60):
        return ValidationResult(False, "Frame rate must be 24, 30, or 60 fps.")

    stars = project.settings.stars
    if stars.star_count < MIN_STAR_COUNT or stars.star_count > MAX_STAR_COUNT:
        return ValidationResult(
            False,
            f"Star count must be between {MIN_STAR_COUNT} and {MAX_STAR_COUNT}.",
        )
    if stars.min_size >= stars.max_size:
        return ValidationResult(False, "The smallest star size must be below the largest.")

    return ValidationResult(True)


def validate_project_for_export(
    project: Project,
    project_path: Path | None = None,
) -> ValidationResult:
    """
    validate project before export including ffmpeg availability.

    project
        project to validate
    project_path
        optional path to project file
    """

    render_result = validate_project_for_render(project, project_path)
    if not render_result.ok:
        return render_result

    if not is_ffmpeg_available():
        return ValidationResult(
            False,
            "FFmpeg was not found. Install FFmpeg and make sure it is available on PATH.",
        )

    return ValidationResult(True)
