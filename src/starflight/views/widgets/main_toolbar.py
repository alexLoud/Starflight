"""Show the main application actions as icons with text labels."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QToolBar, QWidget

from starflight.commands.registry import CommandRegistry
from starflight.views.icons import (
    TOOLBAR_ICON_FILES,
    load_icon_for_command,
    validate_toolbar_icon_mapping,
)


class MainToolbar(QToolBar):
    """icon and text toolbar for primary file actions."""

    def __init__(self, command_registry: CommandRegistry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolbar_main")
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QSize(16, 16))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

        validate_toolbar_icon_mapping(TOOLBAR_ICON_FILES)
        self._command_registry = command_registry
        self._build_actions()

    def _build_actions(self) -> None:
        for index, command_id in enumerate(TOOLBAR_ICON_FILES):
            action = self.addAction(load_icon_for_command(command_id), "")
            action.setObjectName(f"toolbar_action_{command_id.replace('.', '_')}")
            self._command_registry.bind_action(command_id, action)
            if index == 3:
                self.addSeparator()

    def refresh_action_texts(self) -> None:
        """update action labels from command registry."""

        for command in self._command_registry.list():
            if not command.toolbar_visible:
                continue
            try:
                action = self._command_registry.action(command.id)
            except KeyError:
                continue
            action.setText(command.title)
            action.setToolTip(command.title)
            if command.shortcut:
                action.setShortcut(command.shortcut)


__all__ = ["MainToolbar"]
