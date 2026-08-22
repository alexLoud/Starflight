"""Expose project persistence operations through the services package."""

from __future__ import annotations

from starflight.core.project import (
    ProjectError,
    load_project,
    make_relative_image_path,
    new_project,
    normalize_project_path,
    resolve_source_image_path,
    save_project,
)
from starflight.types.settings import Project

__all__ = [
    "Project",
    "ProjectError",
    "load_project",
    "make_relative_image_path",
    "new_project",
    "normalize_project_path",
    "resolve_source_image_path",
    "save_project",
]
