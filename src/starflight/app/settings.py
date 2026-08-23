"""Create the shared Qt settings store."""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings

from starflight.app.constants import APP_ID, APP_ORGANIZATION, SETTINGS_KEY_RENDER_WORKERS

DEFAULT_RENDER_WORKER_COUNT = 4


def create_settings() -> QSettings:
    """create central application settings."""

    settings = QSettings(APP_ORGANIZATION, APP_ID)
    settings.setFallbacksEnabled(False)
    return settings


def max_available_render_workers() -> int:
    """
    return the highest render worker count allowed on this machine.

    one logical core is kept free for the ui, ffmpeg, and coordination.
    """

    cpu_count = os.cpu_count() or 4
    return max(1, cpu_count - 1)


def available_render_worker_counts() -> list[int]:
    """return selectable render worker counts from 1 up to the machine limit."""

    return list(range(1, max_available_render_workers() + 1))


def default_render_worker_count() -> int:
    """return the default render worker count capped by available cores."""

    return min(DEFAULT_RENDER_WORKER_COUNT, max_available_render_workers())


def render_worker_count_from_settings(settings: QSettings) -> int:
    """
    read configured render worker count from application settings.

    settings
        central application settings store
    """

    configured = int(settings.value(SETTINGS_KEY_RENDER_WORKERS, default_render_worker_count()))
    return min(max(1, configured), max_available_render_workers())


__all__ = [
    "DEFAULT_RENDER_WORKER_COUNT",
    "available_render_worker_counts",
    "create_settings",
    "default_render_worker_count",
    "max_available_render_workers",
    "render_worker_count_from_settings",
]
