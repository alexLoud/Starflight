"""Create the shared Qt settings store."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from starflight.app.constants import APP_ID, APP_ORGANIZATION


def create_settings() -> QSettings:
    """create central application settings."""

    settings = QSettings(APP_ORGANIZATION, APP_ID)
    settings.setFallbacksEnabled(False)
    return settings


__all__ = ["create_settings"]
