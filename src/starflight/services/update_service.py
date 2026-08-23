"""Check GitHub releases for application updates."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request

from starflight.app.constants import APP_GITHUB_REPO, APP_GITHUB_URL
from starflight.types.update import UpdateInfo

_GITHUB_API_BASE = "https://api.github.com"
_USER_AGENT = "Starflight"
_REQUEST_TIMEOUT_S = 8.0
_VERSION_SEGMENT_RE = re.compile(r"(\d+)")


def normalize_version(value: str) -> tuple[int, ...]:
    """
    parse a dotted version or release tag into comparable integer parts.

    value
        version string such as 1.0.1 or v1.0.1
    """

    text = value.strip().removeprefix("v").removeprefix("V")
    parts: list[int] = []
    for segment in text.split("."):
        match = _VERSION_SEGMENT_RE.match(segment)
        parts.append(int(match.group(1)) if match else 0)
    return tuple(parts)


def is_newer_version(latest: str, current: str) -> bool:
    """
    return whether latest is strictly newer than current.

    latest
        remote release version
    current
        installed application version
    """

    return normalize_version(latest) > normalize_version(current)


def release_page_url(version: str) -> str:
    """
    build the github release page url for a version.

    version
        release version without a leading v
    """

    return f"{APP_GITHUB_URL}/releases/tag/v{version}"


def fetch_latest_release(repo: str = APP_GITHUB_REPO) -> UpdateInfo | None:
    """
    fetch the latest published github release for the configured repository.

    repo
        github owner/repo slug used for the releases api
    """

    request = urllib.request.Request(
        f"{_GITHUB_API_BASE}/repos/{repo}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": _USER_AGENT,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_S) as response:
            payload = json.load(response)
    except (TimeoutError, urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
        return None

    tag_name = payload.get("tag_name")
    if not isinstance(tag_name, str) or not tag_name.strip():
        return None

    version = tag_name.strip().removeprefix("v").removeprefix("V")
    release_url = payload.get("html_url")
    if not isinstance(release_url, str) or not release_url.strip():
        release_url = release_page_url(version)

    return UpdateInfo(version=version, release_url=release_url)


def check_for_update(current_version: str) -> UpdateInfo | None:
    """
    return update info when a newer github release is available.

    current_version
        installed application version
    """

    latest = fetch_latest_release()
    if latest is None:
        return None
    if not is_newer_version(latest.version, current_version):
        return None
    return latest


__all__ = [
    "check_for_update",
    "fetch_latest_release",
    "is_newer_version",
    "normalize_version",
    "release_page_url",
]
