"""Resolve preset paths and read or write look preset files."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication

from starflight.app.constants import APP_DISPLAY_NAME, APP_ID, package_dir
from starflight.types.preset import (
    LookPreset,
    look_preset_from_settings,
    look_settings_from_dict,
    look_settings_to_dict,
)
from starflight.types.settings import ProjectSettings


class PresetError(Exception):
    """raised when a preset operation fails."""


def _tr(text: str) -> str:
    """translate a preset persistence error."""

    translations = {
        "Preset could not be saved: {error}": QCoreApplication.translate(
            "PresetError",
            "Preset could not be saved: {error}",
        ),
        "Preset data could not be serialized: {error}": QCoreApplication.translate(
            "PresetError",
            "Preset data could not be serialized: {error}",
        ),
        "Preset file not found: {path}": QCoreApplication.translate(
            "PresetError",
            "Preset file not found: {path}",
        ),
        "Preset file could not be read: {error}": QCoreApplication.translate(
            "PresetError",
            "Preset file could not be read: {error}",
        ),
        "The preset file does not contain valid JSON.": QCoreApplication.translate(
            "PresetError",
            "The preset file does not contain valid JSON.",
        ),
        "The preset file has an invalid format.": QCoreApplication.translate(
            "PresetError",
            "The preset file has an invalid format.",
        ),
        "Built-in presets cannot be deleted.": QCoreApplication.translate(
            "PresetError",
            "Built-in presets cannot be deleted.",
        ),
        "Preset file could not be deleted: {error}": QCoreApplication.translate(
            "PresetError",
            "Preset file could not be deleted: {error}",
        ),
    }
    return translations.get(text, text)


def builtin_presets_directory() -> Path:
    """return the packaged built-in presets directory."""

    return package_dir() / "assets" / "presets"


def user_presets_directory() -> Path:
    """return the platform-specific user presets directory."""

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_DISPLAY_NAME / "presets"
    if sys.platform == "win32":
        local_app_data = os.getenv("LOCALAPPDATA")
        root = Path(local_app_data) if local_app_data else Path.home() / "AppData" / "Local"
        return root / APP_DISPLAY_NAME / "presets"
    data_home = os.getenv("XDG_DATA_HOME")
    root = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return root / APP_ID / "presets"


def load_preset(path: Path, *, builtin: bool) -> LookPreset:
    """
    load one look preset from a json file.

    path
        preset json path
    builtin
        true when the file is shipped with the app
    """

    if not path.exists():
        message = _tr("Preset file not found: {path}").format(path=path)
        raise PresetError(message)

    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        message = _tr("Preset file could not be read: {error}").format(error=exc)
        raise PresetError(message) from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PresetError(_tr("The preset file does not contain valid JSON.")) from exc

    if not isinstance(payload, dict):
        raise PresetError(_tr("The preset file has an invalid format."))

    try:
        settings_data = payload.get("settings", {})
        if not isinstance(settings_data, dict):
            raise TypeError("settings must be an object")
        name = str(payload.get("name", "")).strip()
        if not name:
            raise ValueError("name must not be empty")
        preset_id = _validated_preset_id(str(payload.get("id", path.stem)).strip() or path.stem)
        description = payload.get("description", "")
        if description is not None and not isinstance(description, str):
            raise TypeError("description must be a string")
        return LookPreset(
            id=preset_id,
            name=name,
            description=str(description or ""),
            settings=look_settings_from_dict(settings_data),
            source_settings=dict(settings_data),
            builtin=builtin,
            format_version=int(payload.get("format_version", 1)),
            path=path,
        )
    except (AttributeError, OverflowError, TypeError, ValueError) as exc:
        raise PresetError(_tr("The preset file has an invalid format.")) from exc


def load_library(*, user_directory: Path | None = None) -> list[LookPreset]:
    """
    load built-in presets and user presets.

    user_directory
        optional override for the user presets folder
    """

    presets: list[LookPreset] = []
    builtin_dir = builtin_presets_directory()
    if builtin_dir.is_dir():
        for path in sorted(builtin_dir.glob("*.json")):
            presets.append(load_preset(path, builtin=True))

    user_dir = user_directory if user_directory is not None else user_presets_directory()
    if user_dir.is_dir():
        for path in sorted(user_dir.glob("*.json")):
            try:
                presets.append(load_preset(path, builtin=False))
            except PresetError:
                continue
    return presets


def save_user_preset(preset: LookPreset, *, user_directory: Path | None = None) -> Path:
    """
    write a user look preset to disk.

    preset
        preset to store
    user_directory
        optional override for the user presets folder
    """

    target_dir = user_directory if user_directory is not None else user_presets_directory()
    preset_id = _validated_preset_id(preset.id)
    target = target_dir / f"{preset_id}.json"
    payload: dict[str, Any] = {
        "format_version": preset.format_version,
        "id": preset_id,
        "name": preset.name,
        "description": preset.description,
        "settings": look_settings_to_dict(preset.settings),
    }

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        message = _tr("Preset data could not be serialized: {error}").format(error=exc)
        raise PresetError(message) from exc

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.stem}_",
            suffix=target.suffix,
            delete=False,
        ) as handle:
            handle.write(serialized)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = Path(handle.name)
        temp_path.replace(target)
        temp_path = None
    except OSError as exc:
        message = _tr("Preset could not be saved: {error}").format(error=exc)
        raise PresetError(message) from exc
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass

    preset.id = preset_id
    preset.path = target
    preset.builtin = False
    preset.source_settings = dict(payload["settings"])
    return target


def save_look_from_settings(
    name: str,
    description: str,
    settings: ProjectSettings,
    *,
    preset_id: str,
    user_directory: Path | None = None,
) -> LookPreset:
    """
    create and save a user preset from current project settings.

    name
        preset display name
    description
        optional short description
    settings
        current project settings
    preset_id
        stable file identifier
    user_directory
        optional override for the user presets folder
    """

    preset = look_preset_from_settings(name, description, settings, preset_id=preset_id)
    save_user_preset(preset, user_directory=user_directory)
    return preset


def delete_user_preset(preset: LookPreset) -> None:
    """
    delete a user preset file.

    preset
        user preset to remove
    """

    if preset.builtin:
        raise PresetError(_tr("Built-in presets cannot be deleted."))
    if preset.path is None:
        raise PresetError(_tr("The preset file has an invalid format."))
    try:
        preset.path.unlink()
    except OSError as exc:
        message = _tr("Preset file could not be deleted: {error}").format(error=exc)
        raise PresetError(message) from exc


def find_user_preset_by_name(name: str, presets: list[LookPreset]) -> LookPreset | None:
    """
    return the first user preset with the same display name.

    name
        name to match
    presets
        loaded library
    """

    needle = name.strip().casefold()
    if not needle:
        return None
    for preset in presets:
        if not preset.builtin and preset.name.strip().casefold() == needle:
            return preset
    return None


def _validated_preset_id(value: str) -> str:
    """Accept only plain file ids that cannot escape the preset directory."""

    candidate = value.strip()
    if (
        not candidate
        or candidate in {".", ".."}
        or Path(candidate).name != candidate
        or any(separator in candidate for separator in ("/", "\\"))
    ):
        raise PresetError(_tr("The preset file has an invalid format."))
    return candidate
