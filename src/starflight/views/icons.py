"""Map application actions to SVG icon files."""

from __future__ import annotations

from PySide6.QtGui import QIcon

from starflight.app.constants import package_dir

ICON_DIRECTORY = package_dir() / "assets" / "icons"

COMMAND_ICON_FILES: dict[str, str] = {
    "app.file.new": "file-new.svg",
    "app.file.open": "file-open.svg",
    "app.file.save": "file-save.svg",
    "app.file.save_as": "file-save-as.svg",
    "app.file.quit": "file-quit.svg",
    "app.project.presets": "presets.svg",
    "app.project.reset_settings": "reset-all.svg",
    "app.project.export": "export-video.svg",
}

TOOLBAR_ICON_FILES: list[str] = [
    "app.file.new",
    "app.file.open",
    "app.file.save",
    "app.file.save_as",
    "app.project.presets",
    "app.project.reset_settings",
    "app.project.export",
]


def validate_toolbar_icon_mapping(command_ids: list[str]) -> None:
    """
    ensure every toolbar command has a valid svg icon.

    command_ids
        command identifiers shown in toolbar
    """

    missing = sorted(
        command_id for command_id in command_ids if command_id not in COMMAND_ICON_FILES
    )
    if missing:
        joined = ", ".join(missing)
        raise RuntimeError(f"missing toolbar icon mapping for commands: {joined}")

    missing_files: list[str] = []
    for command_id in command_ids:
        icon_file = COMMAND_ICON_FILES[command_id]
        icon_path = ICON_DIRECTORY / icon_file
        if not icon_path.exists():
            missing_files.append(f"{command_id} -> {icon_file}")

    if missing_files:
        joined = ", ".join(sorted(missing_files))
        raise RuntimeError(f"missing toolbar svg files: {joined}")


def load_icon_for_command(command_id: str) -> QIcon:
    """
    load svg icon for a command.

    command_id
        command identifier
    """

    try:
        icon_file = COMMAND_ICON_FILES[command_id]
    except KeyError as exc:
        raise KeyError(f"no icon defined for command '{command_id}'") from exc
    return load_icon_asset(icon_file)


def load_icon_asset(icon_file: str) -> QIcon:
    """
    load named svg icon from assets.

    icon_file
        svg file name
    """

    cleaned = icon_file.strip()
    if not cleaned:
        raise ValueError("icon file name must not be empty")

    icon_path = ICON_DIRECTORY / cleaned
    if not icon_path.exists():
        raise FileNotFoundError(f"icon file missing: {icon_path}")

    icon = QIcon(str(icon_path))
    if icon.isNull():
        raise RuntimeError(f"icon could not be loaded: {icon_path}")
    return icon


__all__ = [
    "COMMAND_ICON_FILES",
    "ICON_DIRECTORY",
    "TOOLBAR_ICON_FILES",
    "load_icon_asset",
    "load_icon_for_command",
    "validate_toolbar_icon_mapping",
]
