"""Names and settings keys shared during application startup."""

from __future__ import annotations

import sys
from pathlib import Path

APP_ID = "starflight"
APP_DISPLAY_NAME = "Starflight"
APP_ORGANIZATION = "starflight"
APP_ORGANIZATION_DOMAIN = "starflight.local"
APP_AUTHOR = "Alexander Lauterbach"
APP_DESCRIPTION = (
    "Turns a starless deep-sky image into a short fly-through video with a rendered starfield."
)
APP_GITHUB_URL = "https://github.com/alexLoud/Starflight"
APP_GITHUB_REPO = "alexLoud/Starflight"
APP_ICON_FILE = "app-icon.png"
APP_ICON_MACOS_FILE = "app-icon-macos.png"
WELCOME_LOGO_FILE = "welcome-logo.jpg"

SETTINGS_KEY_LANGUAGE = "ui/language"
SETTINGS_KEY_RENDER_WORKERS = "render/worker_count"
SETTINGS_KEY_PLAYBACK_PREVIEW_FPS = "preview/playback_fps"
SETTINGS_KEY_BACKGROUND_PREVIEW_UPDATE = "preview/background_update"
SETTINGS_KEY_WINDOW_GEOMETRY = "ui/window_geometry"
SETTINGS_KEY_SPLITTER_STATE = "ui/splitter_state"
SETTINGS_KEY_RECENT_PROJECTS = "projects/recent"

DEFAULT_LANGUAGE = "de"


def package_dir() -> Path:
    """return the starflight package directory, including frozen builds."""

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / "starflight"
    return Path(__file__).resolve().parents[1]


__all__ = [
    "APP_AUTHOR",
    "APP_DESCRIPTION",
    "APP_DISPLAY_NAME",
    "APP_GITHUB_REPO",
    "APP_GITHUB_URL",
    "APP_ICON_FILE",
    "APP_ICON_MACOS_FILE",
    "APP_ID",
    "APP_ORGANIZATION",
    "APP_ORGANIZATION_DOMAIN",
    "DEFAULT_LANGUAGE",
    "SETTINGS_KEY_BACKGROUND_PREVIEW_UPDATE",
    "SETTINGS_KEY_LANGUAGE",
    "SETTINGS_KEY_PLAYBACK_PREVIEW_FPS",
    "SETTINGS_KEY_RECENT_PROJECTS",
    "SETTINGS_KEY_RENDER_WORKERS",
    "SETTINGS_KEY_SPLITTER_STATE",
    "SETTINGS_KEY_WINDOW_GEOMETRY",
    "WELCOME_LOGO_FILE",
    "package_dir",
]
