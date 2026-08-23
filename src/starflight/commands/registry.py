"""Register application commands and keep their Qt actions in sync."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication

from starflight.commands.models import Command, CommandHandler
from starflight.services.error_service import ErrorService


class CommandRegistry(QObject):
    """stores commands, handlers and qaction bindings."""

    def __init__(self, error_service: ErrorService) -> None:
        super().__init__()
        self._error_service = error_service
        self._commands: dict[str, Command] = {}
        self._handlers: dict[str, CommandHandler] = {}
        self._actions: dict[str, list[QAction]] = {}

    def register(self, command: Command, handler: CommandHandler) -> None:
        """register a command and its handler."""

        if command.id in self._commands:
            raise ValueError(f"command '{command.id}' is already registered")
        self._commands[command.id] = command
        self._handlers[command.id] = handler

    def get(self, command_id: str) -> Command:
        """return a command by id."""

        try:
            return self._commands[command_id]
        except KeyError as exc:
            raise KeyError(f"unknown command: '{command_id}'") from exc

    def has(self, command_id: str) -> bool:
        """return whether a command is registered."""

        return command_id in self._commands

    def list(self) -> list[Command]:
        """return all commands in registration order."""

        return list(self._commands.values())

    def execute(self, command_id: str) -> None:
        """execute a registered command safely."""

        if command_id not in self._handlers:
            raise KeyError(f"unknown command: '{command_id}'")

        handler = self._handlers[command_id]
        try:
            handler()
        except Exception as exc:
            parent = None
            app = QApplication.instance()
            if app is not None:
                parent = app.activeWindow()
            self._error_service.show_crash_report(
                f"command '{command_id}' failed",
                exc,
                parent,
            )

    def bind_action(self, command_id: str, action: QAction) -> None:
        """bind a command to a qaction."""

        self._attach_action(command_id, action)

    def _attach_action(self, command_id: str, action: QAction) -> None:
        command = self.get(command_id)
        action.setEnabled(command.enabled)
        action.setObjectName(f"toolbar_{command_id}")
        action.triggered.connect(self._make_trigger_callback(command_id))
        self._actions.setdefault(command_id, []).append(action)

    def _make_trigger_callback(self, command_id: str) -> Callable[[bool], None]:
        def callback(_checked: bool = False) -> None:
            self.execute(command_id)

        return callback

    def action(self, command_id: str) -> QAction:
        """return the first bound qaction for a command."""

        try:
            return self._actions[command_id][0]
        except (KeyError, IndexError) as exc:
            raise KeyError(f"no qaction bound for command '{command_id}'") from exc

    def set_enabled(self, command_id: str, enabled: bool) -> None:
        """update enabled state for a command and its bound qactions."""

        command = self.get(command_id)
        self._commands[command_id] = Command(
            id=command.id,
            title=command.title,
            menu_path=command.menu_path,
            shortcut=command.shortcut,
            toolbar_visible=command.toolbar_visible,
            enabled=enabled,
        )
        for action in self._actions.get(command_id, []):
            action.setEnabled(enabled)

    def update_command(self, command_id: str, *, title: str | None = None) -> None:
        """
        update command metadata.

        command_id
            command identifier
        title
            optional new title
        """

        command = self.get(command_id)
        self._commands[command_id] = Command(
            id=command.id,
            title=title or command.title,
            menu_path=command.menu_path,
            shortcut=command.shortcut,
            toolbar_visible=command.toolbar_visible,
            enabled=command.enabled,
        )

    def connect_action(self, command_id: str, action: QAction) -> None:
        """connect a qaction to a command without replacing prior bindings."""

        command = self.get(command_id)
        action.setObjectName(f"action_{command_id}")
        action.setText(command.title)
        action.setEnabled(command.enabled)
        if command.shortcut:
            from PySide6.QtGui import QKeySequence

            action.setShortcut(QKeySequence(command.shortcut))
        action.triggered.connect(self._make_trigger_callback(command_id))
        self._actions.setdefault(command_id, []).append(action)


__all__ = ["CommandRegistry"]
