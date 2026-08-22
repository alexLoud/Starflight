"""Store and retrieve the list of recently opened project files."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from starflight.app.constants import SETTINGS_KEY_RECENT_PROJECTS

MAX_RECENT_PROJECTS = 10


def read_recent_project_paths(settings: QSettings) -> list[Path]:
    """
    return existing recent project paths in most-recent-first order.

    settings
        application settings store
    """

    raw = settings.value(SETTINGS_KEY_RECENT_PROJECTS, [])
    if raw is None:
        return []

    if isinstance(raw, str):
        candidates = [raw]
    else:
        candidates = list(raw)

    recent: list[Path] = []
    seen: set[str] = set()
    for entry in candidates:
        text = str(entry).strip()
        if not text or text in seen:
            continue
        path = Path(text)
        if not path.is_file():
            continue
        seen.add(text)
        recent.append(path)
    return recent


def remember_recent_project(settings: QSettings, path: Path) -> None:
    """
    store a project path at the top of the recent list.

    settings
        application settings store
    path
        project file path to remember
    """

    normalized = str(path.expanduser().resolve())
    existing = [
        str(item.expanduser().resolve())
        for item in read_recent_project_paths(settings)
        if str(item.expanduser().resolve()) != normalized
    ]
    updated = [normalized, *existing][:MAX_RECENT_PROJECTS]
    settings.setValue(SETTINGS_KEY_RECENT_PROJECTS, updated)


def remove_recent_project(settings: QSettings, path: Path) -> None:
    """
    remove a missing or invalid project from the recent list.

    settings
        application settings store
    path
        project file path to remove
    """

    normalized = str(path.expanduser().resolve())
    updated = [
        str(item.expanduser().resolve())
        for item in read_recent_project_paths(settings)
        if str(item.expanduser().resolve()) != normalized
    ]
    settings.setValue(SETTINGS_KEY_RECENT_PROJECTS, updated)


__all__ = [
    "MAX_RECENT_PROJECTS",
    "read_recent_project_paths",
    "remember_recent_project",
    "remove_recent_project",
]
