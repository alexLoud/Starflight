"""Resolve project paths and read or write project files safely."""

from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from starflight.types.settings import Project, settings_from_dict, settings_to_dict


class ProjectError(Exception):
    """Raised when a project operation fails."""


def _tr(text: str) -> str:
    """Translate a project persistence error."""

    translations = {
        "Project could not be saved: {error}": QCoreApplication.translate(
            "ProjectError", "Project could not be saved: {error}"
        ),
        "Project data could not be serialized: {error}": QCoreApplication.translate(
            "ProjectError", "Project data could not be serialized: {error}"
        ),
        "Project file not found: {path}": QCoreApplication.translate(
            "ProjectError", "Project file not found: {path}"
        ),
        "Project file could not be read: {error}": QCoreApplication.translate(
            "ProjectError", "Project file could not be read: {error}"
        ),
        "The project file does not contain valid JSON.": QCoreApplication.translate(
            "ProjectError", "The project file does not contain valid JSON."
        ),
        "The project file has an invalid format.": QCoreApplication.translate(
            "ProjectError", "The project file has an invalid format."
        ),
    }
    return translations.get(text, text)


def resolve_source_image_path(project_path: Path | None, source_image: str | None) -> Path | None:
    """
    resolve source image path relative to project file.

    project_path
        path to the .sf project file
    source_image
        stored relative or absolute image path
    """

    if not source_image:
        return None

    image_path = Path(source_image)
    if image_path.is_absolute():
        return image_path

    if project_path is None:
        return image_path

    return (project_path.parent / image_path).resolve()


def make_relative_image_path(project_path: Path, image_path: Path) -> str:
    """
    store image path relative to project directory when possible.

    project_path
        path to the .sf project file
    image_path
        absolute path to the source image
    """

    image_path = image_path.resolve()
    try:
        return str(image_path.relative_to(project_path.parent.resolve()))
    except ValueError:
        return str(image_path)


def normalize_project_path(path: str | Path) -> Path:
    """
    normalize a user-selected path to a .sf project file.

    path
        raw path from a file dialog or user input
    """

    target = Path(path).expanduser()
    if target.suffix.lower() == ".sf":
        return target
    return target.with_suffix(".sf")


def save_project(project: Project, project_path: Path) -> None:
    """
    save project to a .sf file (json content).

    project
        project state to persist
    project_path
        destination .sf path
    """

    target = normalize_project_path(project_path)
    payload = {
        "version": project.version,
        "name": project.name,
        "source_image": project.source_image,
        "settings": settings_to_dict(project.settings),
    }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
    except OSError as exc:
        message = _tr("Project could not be saved: {error}").format(error=exc)
        raise ProjectError(message) from exc
    except (TypeError, ValueError) as exc:
        message = _tr("Project data could not be serialized: {error}").format(error=exc)
        raise ProjectError(message) from exc


def load_project(project_path: Path) -> Project:
    """
    load project from a .sf file (json content).

    project_path
        path to the project file
    """

    if not project_path.exists():
        message = _tr("Project file not found: {path}").format(path=project_path)
        raise ProjectError(message)

    try:
        with project_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        message = _tr("Project file could not be read: {error}").format(error=exc)
        raise ProjectError(message) from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ProjectError(_tr("The project file does not contain valid JSON.")) from exc

    if not isinstance(payload, dict):
        raise ProjectError(_tr("The project file has an invalid format."))

    try:
        settings = settings_from_dict(payload.get("settings", {}))
        source_image = payload.get("source_image")
        if source_image is not None and not isinstance(source_image, str):
            raise TypeError("source_image must be a string or null")
        return Project(
            version=int(payload.get("version", 1)),
            name=str(payload.get("name", project_path.stem)),
            source_image=source_image,
            settings=settings,
        )
    except (AttributeError, OverflowError, TypeError, ValueError) as exc:
        raise ProjectError(_tr("The project file has an invalid format.")) from exc


def new_project(name: str = "Untitled Project") -> Project:
    """
    create a new empty project.

    name
        default project name
    """

    return Project(name=name)
