"""Create the shared Qt settings store."""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings

from starflight.app.constants import (
    APP_ID,
    APP_ORGANIZATION,
    SETTINGS_KEY_BACKGROUND_PREVIEW_UPDATE,
    SETTINGS_KEY_PLAYBACK_PREVIEW_FPS,
    SETTINGS_KEY_RENDER_WORKERS,
)

DEFAULT_RENDER_WORKER_COUNT = 4
DEFAULT_PLAYBACK_PREVIEW_FPS = 6
PLAYBACK_PREVIEW_FPS_OPTIONS = (3, 6, 9, 12)

BACKGROUND_PREVIEW_UPDATE_DISABLED = "disabled"
BACKGROUND_PREVIEW_UPDATE_PARTIAL = "partial"
BACKGROUND_PREVIEW_UPDATE_FULL = "full"
DEFAULT_BACKGROUND_PREVIEW_UPDATE = BACKGROUND_PREVIEW_UPDATE_PARTIAL
PARTIAL_BACKGROUND_PRELOAD_FRACTION = 0.4
BACKGROUND_PREVIEW_UPDATE_OPTIONS = (
    BACKGROUND_PREVIEW_UPDATE_DISABLED,
    BACKGROUND_PREVIEW_UPDATE_PARTIAL,
    BACKGROUND_PREVIEW_UPDATE_FULL,
)


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


def available_playback_preview_fps_options() -> tuple[int, ...]:
    """return selectable timeline preview frame rates."""

    return PLAYBACK_PREVIEW_FPS_OPTIONS


def playback_preview_fps_from_settings(settings: QSettings) -> int:
    """
    read configured timeline preview frame rate from application settings.

    settings
        central application settings store
    """

    configured = int(
        settings.value(SETTINGS_KEY_PLAYBACK_PREVIEW_FPS, DEFAULT_PLAYBACK_PREVIEW_FPS),
    )
    if configured in PLAYBACK_PREVIEW_FPS_OPTIONS:
        return configured
    return DEFAULT_PLAYBACK_PREVIEW_FPS


def background_preview_update_from_settings(settings: QSettings) -> str:
    """
    read configured background playback preview update mode.

    settings
        central application settings store
    """

    configured = str(
        settings.value(
            SETTINGS_KEY_BACKGROUND_PREVIEW_UPDATE,
            DEFAULT_BACKGROUND_PREVIEW_UPDATE,
        ),
    )
    if configured in BACKGROUND_PREVIEW_UPDATE_OPTIONS:
        return configured
    return DEFAULT_BACKGROUND_PREVIEW_UPDATE


def background_preview_preload_fraction(update_mode: str) -> float:
    """map a background update mode to the fraction of frames to preload."""

    if update_mode == BACKGROUND_PREVIEW_UPDATE_DISABLED:
        return 0.0
    if update_mode == BACKGROUND_PREVIEW_UPDATE_FULL:
        return 1.0
    return PARTIAL_BACKGROUND_PRELOAD_FRACTION


def background_preview_preload_fraction_from_settings(settings: QSettings) -> float:
    """return the configured background preload fraction for timeline playback."""

    return background_preview_preload_fraction(
        background_preview_update_from_settings(settings),
    )


__all__ = [
    "BACKGROUND_PREVIEW_UPDATE_DISABLED",
    "BACKGROUND_PREVIEW_UPDATE_FULL",
    "BACKGROUND_PREVIEW_UPDATE_OPTIONS",
    "BACKGROUND_PREVIEW_UPDATE_PARTIAL",
    "DEFAULT_BACKGROUND_PREVIEW_UPDATE",
    "DEFAULT_PLAYBACK_PREVIEW_FPS",
    "DEFAULT_RENDER_WORKER_COUNT",
    "PARTIAL_BACKGROUND_PRELOAD_FRACTION",
    "PLAYBACK_PREVIEW_FPS_OPTIONS",
    "available_playback_preview_fps_options",
    "available_render_worker_counts",
    "background_preview_preload_fraction",
    "background_preview_preload_fraction_from_settings",
    "background_preview_update_from_settings",
    "create_settings",
    "default_render_worker_count",
    "max_available_render_workers",
    "playback_preview_fps_from_settings",
    "render_worker_count_from_settings",
]
