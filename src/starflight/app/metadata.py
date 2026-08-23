"""Application metadata shown in the about dialog and welcome splash."""

from __future__ import annotations

from starflight import __version__
from starflight.app.constants import APP_AUTHOR, APP_DESCRIPTION, APP_GITHUB_URL, APP_ICON_FILE, package_dir


def app_version() -> str:
    """return the application version from the package module."""

    return __version__


def app_icon_path() -> str:
    """return the path to the application icon png."""

    return str(package_dir() / "assets" / "icons" / APP_ICON_FILE)


__all__ = [
    "APP_AUTHOR",
    "APP_DESCRIPTION",
    "APP_GITHUB_URL",
    "app_icon_path",
    "app_version",
]
