"""locate and load license texts shipped with starflight."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

from starflight.app.constants import package_dir


def _repo_root() -> Path:
    """return the repository root for editable development runs."""

    return Path(__file__).resolve().parents[3]


def legal_dir() -> Path:
    """
    return the directory that contains bundled legal documents.

    """

    return package_dir() / "assets" / "legal"


def starflight_license_path() -> Path:
    """
    return the path to the starflight license file.

    """

    bundled = legal_dir() / "LICENSE"
    if bundled.is_file():
        return bundled
    if not getattr(sys, "frozen", False):
        root_license = _repo_root() / "LICENSE"
        if root_license.is_file():
            return root_license
    return bundled


def third_party_notices_path() -> Path:
    """
    return the path to the third-party notices file.

    """

    return legal_dir() / "THIRD_PARTY_NOTICES.md"


def license_texts_dir() -> Path:
    """
    return the directory of full third-party license texts.

    """

    return legal_dir() / "licenses"


def _read_text(path: Path) -> str:
    """
    read utf-8 text from path, or a short missing-file message.

    path
        file to read
    """

    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return f"[missing license file: {path.name}]\n"


@lru_cache(maxsize=1)
def combined_legal_text() -> str:
    """
    return starflight license, notices, and full third-party license texts.

    """

    sections: list[str] = [
        "========== STARFLIGHT LICENSE ==========\n\n" + _read_text(starflight_license_path()),
        "========== THIRD-PARTY NOTICES ==========\n\n" + _read_text(third_party_notices_path()),
    ]
    licenses = license_texts_dir()
    if licenses.is_dir():
        for path in sorted(licenses.glob("*.txt")):
            sections.append(
                f"========== {path.name} ==========\n\n" + _read_text(path),
            )
    return "\n\n".join(sections)


__all__ = [
    "combined_legal_text",
    "legal_dir",
    "license_texts_dir",
    "starflight_license_path",
    "third_party_notices_path",
]
