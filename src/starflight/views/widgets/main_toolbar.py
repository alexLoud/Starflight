"""Show the main application actions in a mac-style top bar."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QSizePolicy, QToolButton, QWidget

from starflight.commands.registry import CommandRegistry
from starflight.views.icons import (
    TOOLBAR_ICON_FILES,
    load_icon_for_command,
    validate_toolbar_icon_mapping,
)

_BUTTON_ICON_SIZE = 24
_EXPORT_ICON_SIZE = 16


def _recolored_icon(icon: QIcon, size: int, color: str) -> QIcon:
    """
    recolor an icon to a solid color.

    icon
        source icon
    size
        logical icon size
    color
        target color
    """

    scale = 3
    source = icon.pixmap(size * scale, size * scale)
    tinted = QPixmap(source.size())
    tinted.setDevicePixelRatio(scale)
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    target = QRectF(0, 0, size, size)
    painter.drawPixmap(target, source, QRectF(source.rect()))
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(target, QColor(color))
    painter.end()
    result = QIcon()
    result.addPixmap(tinted)
    return result


class MainToolbar(QFrame):
    """mac-style top bar with icon-above-text buttons for primary actions."""

    def __init__(self, command_registry: CommandRegistry, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("toolbar_main")
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)

        validate_toolbar_icon_mapping(TOOLBAR_ICON_FILES)
        self._command_registry = command_registry
        self._buttons: dict[str, QToolButton] = {}
        self._build_actions()

    def _make_action(self, command_id: str) -> QAction:
        """
        create one bound action for a top bar button.

        command_id
            command identifier shown in the top bar
        """

        action = QAction(load_icon_for_command(command_id), "", self)
        action.setObjectName(f"toolbar_action_{command_id.replace('.', '_')}")
        self._command_registry.bind_action(command_id, action)
        return action

    def _make_button(self, command_id: str) -> QToolButton:
        """
        create an icon-above-text button bound to a command.

        command_id
            command identifier shown in the top bar
        """

        button = QToolButton()
        button.setObjectName("toolbar_button")
        button.setAutoRaise(False)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        button.setIconSize(QSize(_BUTTON_ICON_SIZE, _BUTTON_ICON_SIZE))
        button.setDefaultAction(self._make_action(command_id))
        return button

    def _add_command_button(self, command_id: str) -> QToolButton:
        """
        create and remember one toolbar button.

        command_id
            command identifier shown in the top bar
        """

        button = self._make_button(command_id)
        self._buttons[command_id] = button
        return button

    def button_for_command(self, command_id: str) -> QToolButton | None:
        """
        return the toolbar button bound to a command.

        command_id
            command identifier shown in the top bar
        """

        return self._buttons.get(command_id)

    def _build_actions(self) -> None:
        file_commands = (
            "app.file.new",
            "app.file.open",
            "app.file.save",
            "app.file.save_as",
        )
        look_commands = (
            "app.project.presets",
            "app.project.reset_settings",
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(4)

        for command_id in file_commands:
            layout.addWidget(self._add_command_button(command_id))

        layout.addStretch(1)

        for command_id in look_commands:
            layout.addWidget(self._add_command_button(command_id))

        layout.addStretch(1)

        export_action = self._make_action("app.project.export")
        export_icon = load_icon_for_command("app.project.export")
        export_action.setIcon(_recolored_icon(export_icon, _EXPORT_ICON_SIZE, "#FFFFFF"))
        export_button = QToolButton()
        export_button.setObjectName("toolbar_export_button")
        export_button.setAutoRaise(False)
        export_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        export_button.setIconSize(QSize(_EXPORT_ICON_SIZE, _EXPORT_ICON_SIZE))
        export_button.setDefaultAction(export_action)
        layout.addWidget(export_button)

    def minimumSizeHint(self) -> QSize:
        """allow the window to shrink below the full button-row width."""

        return QSize(0, super().minimumSizeHint().height())

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
