"""Register the commands exposed by the main window."""

from __future__ import annotations

from starflight.commands.models import Command
from starflight.commands.registry import CommandRegistry
from starflight.views.main_window import MainWindow


def register_core_commands(registry: CommandRegistry, window: MainWindow) -> None:
    """
    register main window commands.

    registry
        command registry
    window
        main application window
    """

    commands = [
        Command("app.file.new", "New", ("File",), "Ctrl+N", True),
        Command("app.file.open", "Open", ("File",), "Ctrl+O", True),
        Command("app.file.save", "Save", ("File",), "Ctrl+S", True),
        Command("app.file.save_as", "Save As", ("File",), "Ctrl+Shift+S", True),
        Command("app.file.quit", "Quit", ("File",), "Ctrl+Q", False),
        Command("app.project.load_image", "Load Image", ("Project",), None, False),
        Command("app.project.presets", "Presets", ("Project",), None, True),
        Command("app.project.reset_settings", "Reset all settings", ("Project",), None, True),
        Command("app.project.export", "Export", ("Project",), None, True),
        Command("app.settings.open", "Settings", ("Settings",), None, False),
        Command("app.help.about", "About Starflight", ("Help",), None, False),
    ]

    handlers = {
        "app.file.new": window.new_project_action,
        "app.file.open": window.open_project,
        "app.file.save": window.save_project,
        "app.file.save_as": window.save_project_as,
        "app.file.quit": window.close,
        "app.project.load_image": window.load_image,
        "app.project.presets": window.open_presets,
        "app.project.reset_settings": window.reset_settings_keep_image,
        "app.project.export": window.export_video,
        "app.settings.open": window.open_settings,
        "app.help.about": window.open_about,
    }

    for command in commands:
        registry.register(command, handlers[command.id])


__all__ = ["register_core_commands"]
