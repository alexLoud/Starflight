"""Types for remote update checks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class UpdateInfo:
    """available release newer than the installed application version."""

    version: str
    release_url: str


__all__ = ["UpdateInfo"]
