"""Application metadata shown in the about dialog and welcome splash."""

from __future__ import annotations

import sys
import tomllib
from functools import lru_cache
from pathlib import Path

from starflight.app.constants import (
    APP_AUTHOR,
    APP_DESCRIPTION,
    APP_GITHUB_URL,
    APP_ICON_FILE,
    package_dir,
)


def _repo_root() -> Path:
    """return the repository root for editable development runs."""

    return Path(__file__).resolve().parents[3]


def _read_pyproject_version() -> str | None:
    """
    read the canonical project version from pyproject.toml when available.

    """

    if getattr(sys, "frozen", False):
        return None

    pyproject_path = _repo_root() / "pyproject.toml"
    if not pyproject_path.is_file():
        return None

    with pyproject_path.open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


@lru_cache(maxsize=1)
def app_version() -> str:
    """return the application version from pyproject.toml or the bundled package."""

    pyproject_version = _read_pyproject_version()
    if pyproject_version is not None:
        return pyproject_version

    from starflight import __version__

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
