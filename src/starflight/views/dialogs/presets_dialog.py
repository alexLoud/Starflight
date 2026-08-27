"""Browse look presets, apply one, and save the current look."""

from __future__ import annotations

import math
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLayoutItem,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from starflight.services.preset_service import (
    PresetError,
    delete_user_preset,
    find_user_preset_by_name,
    load_library,
    save_look_from_settings,
)
from starflight.types.preset import LookPreset, preset_id_from_name, unique_preset_id
from starflight.types.settings import ProjectSettings
from starflight.views.icons import load_icon_asset

_CARD_WIDTH = 260
_CARD_HEIGHT = 108
_CARD_GAP = 12
_PRESET_COLUMNS = 3
_CONTENT_MARGIN_LEFT = 22
_CONTENT_MARGIN_RIGHT = 14
_CONTENT_WIDTH = _PRESET_COLUMNS * _CARD_WIDTH + (_PRESET_COLUMNS - 1) * _CARD_GAP
_DIALOG_WIDTH = _CONTENT_MARGIN_LEFT + _CONTENT_MARGIN_RIGHT + 12 + _CONTENT_WIDTH
_DIALOG_MIN_HEIGHT = 480
_DIALOG_MAX_HEIGHT = 740
_ACTION_WIDTH = (_CONTENT_WIDTH - _CARD_GAP) // 2
_ACTION_HEIGHT = 72
_HEADER_ICON_SIZE = 24
_CREATE_ICON_SIZE = 22


def _elide_description(label: QLabel, text: str) -> None:
    """
    set label text wrapped to at most two lines with elision.

    label
        target description label
    text
        full description text
    """

    width = _CARD_WIDTH - 24
    metrics = label.fontMetrics()
    if metrics.horizontalAdvance(text) <= width:
        label.setText(text)
        return

    words = text.split()
    first_line = ""
    index = 0
    while index < len(words):
        candidate = f"{first_line} {words[index]}".strip()
        if metrics.horizontalAdvance(candidate) > width:
            break
        first_line = candidate
        index += 1

    if not first_line:
        label.setText(metrics.elidedText(text, Qt.TextElideMode.ElideRight, width))
        return

    remainder = " ".join(words[index:])
    second_line = metrics.elidedText(remainder, Qt.TextElideMode.ElideRight, width)
    label.setText(f"{first_line}\n{second_line}")


class _FlowLayout(QLayout):
    """wrap child widgets onto following rows when the width is exceeded."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 10) -> None:
        super().__init__(parent)
        self._items: list[QLayoutItem] = []
        self.setContentsMargins(0, 0, 0, 0)
        self.setSpacing(spacing)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem | None:
        if 0 <= index < len(self._items):
            return self._items.pop(index)
        return None

    def expandingDirections(self) -> Qt.Orientation:
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._do_layout(QRect(0, 0, width, 0), True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._do_layout(rect, False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        left, top, right, bottom = self.getContentsMargins()
        size += QSize(left + right, top + bottom)
        return size

    def _do_layout(self, rect: QRect, test_only: bool) -> int:
        left, top, right, bottom = self.getContentsMargins()
        effective = rect.adjusted(left, top, -right, -bottom)
        x = effective.x()
        y = effective.y()
        line_height = 0
        space = self.spacing()

        for item in self._items:
            item_size = item.sizeHint()
            next_x = x + item_size.width() + space
            if next_x - space > effective.right() + 1 and line_height > 0:
                x = effective.x()
                y = y + line_height + space
                next_x = x + item_size.width() + space
                line_height = 0
            if not test_only:
                item.setGeometry(QRect(x, y, item_size.width(), item_size.height()))
            x = next_x
            line_height = max(line_height, item_size.height())

        return y + line_height - rect.y() + bottom


class _PresetCard(QFrame):
    """clickable look preset card with parameter summary chips."""

    clicked = Signal()
    delete_requested = Signal()

    def __init__(self, preset: LookPreset, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preset = preset
        self.setObjectName("preset_card")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(_CARD_WIDTH, _CARD_HEIGHT)
        self.setProperty("selected", False)

        self._title_label = QLabel(self)
        self._title_label.setObjectName("preset_card_title")

        self._delete_button = QToolButton(self)
        self._delete_button.setObjectName("preset_card_delete")
        self._delete_button.setCursor(Qt.CursorShape.ArrowCursor)
        self._delete_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._delete_button.setFixedSize(22, 22)
        self._delete_button.setVisible(not preset.builtin)
        self._delete_button.clicked.connect(self.delete_requested.emit)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)
        header.addWidget(self._title_label, stretch=1)
        header.addWidget(self._delete_button, 0, Qt.AlignmentFlag.AlignTop)

        self._description_label = QLabel(self)
        self._description_label.setObjectName("preset_card_description")
        self._description_label.setWordWrap(True)
        self._description_label.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(6)
        layout.addLayout(header)
        layout.addWidget(self._description_label)
        layout.addStretch(1)

        for child in (self._title_label, self._description_label):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)

    def set_selected(self, selected: bool) -> None:
        """
        update the selected highlight.

        selected
            true when this card is the active look
        """

        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_texts(self, title: str, description: str, delete_tooltip: str) -> None:
        """
        update visible card strings.

        title
            preset name
        description
            short summary
        delete_tooltip
            delete button tooltip
        """

        title_metrics = self._title_label.fontMetrics()
        self._title_label.setText(
            title_metrics.elidedText(title, Qt.TextElideMode.ElideRight, _CARD_WIDTH - 52)
        )
        _elide_description(self._description_label, description)
        self._delete_button.setToolTip(delete_tooltip)
        self._delete_button.setText("✕")


class _PresetFooterAction(QFrame):
    """compact footer action with icon, title, and hint."""

    clicked = Signal()

    def __init__(self, icon_file: str, parent: QWidget | None = None) -> None:
        """
        build a compact footer action.

        icon_file
            svg file name for the leading icon
        parent
            optional parent widget
        """

        super().__init__(parent)
        self.setObjectName("preset_create_action")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(_ACTION_WIDTH, _ACTION_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        icon_label = QLabel(self)
        icon_label.setObjectName("preset_create_icon")
        icon_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon_label.setFixedSize(42, 42)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(
            load_icon_asset(icon_file).pixmap(_CREATE_ICON_SIZE, _CREATE_ICON_SIZE),
        )

        self._title_label = QLabel(self)
        self._title_label.setObjectName("preset_create_title")

        self._hint_label = QLabel(self)
        self._hint_label.setObjectName("preset_create_hint")
        self._hint_label.setWordWrap(True)
        self._hint_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        text_column.addWidget(self._title_label)
        text_column.addWidget(self._hint_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_column)

        for child in (icon_label, self._title_label, self._hint_label):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(
            event.position().toPoint()
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)

    def set_texts(self, title: str, hint: str) -> None:
        """
        update title and supporting hint.

        title
            action label
        hint
            explanation under the title
        """

        self._title_label.setText(title)
        self._hint_label.setText(hint)


class _SavePresetDialog(QDialog):
    """ask for a name and optional description for a new user preset."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("save_preset_dialog")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        form = QFormLayout()
        self._name_label = QLabel()
        self.name_edit = QLineEdit()
        self.name_edit.setMaxLength(80)
        form.addRow(self._name_label, self.name_edit)

        self._description_label = QLabel()
        self.description_edit = QLineEdit()
        self.description_edit.setMaxLength(160)
        form.addRow(self._description_label, self.description_edit)
        layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel,
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.resize(420, 180)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self.setWindowTitle(self.tr("Create new preset"))
        self._name_label.setText(self.tr("Name"))
        self._description_label.setText(self.tr("Description"))
        self.name_edit.setPlaceholderText(self.tr("Required"))
        self.description_edit.setPlaceholderText(self.tr("Optional"))

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip():
            QMessageBox.warning(
                self,
                self.tr("Create new preset"),
                self.tr("Please enter a name."),
            )
            return
        self.accept()


class PresetsDialog(QDialog):
    """modal library of built-in and user look presets."""

    preset_applied = Signal(object)

    def __init__(
        self,
        get_settings: Callable[[], ProjectSettings],
        parent: QWidget | None = None,
        *,
        user_directory: Path | None = None,
        selected_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("presets_dialog")
        self.setModal(True)
        self._get_settings = get_settings
        self._user_directory = user_directory
        self._selected_id = selected_id
        self._cards: list[_PresetCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header_frame = QFrame(self)
        self._header_frame.setObjectName("presets_header")
        header = QHBoxLayout(self._header_frame)
        header.setContentsMargins(22, 16, 16, 16)
        header.setSpacing(14)

        header_icon = QLabel(self._header_frame)
        header_icon.setObjectName("presets_header_icon")
        header_icon.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_icon.setFixedSize(44, 44)
        header_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_icon.setPixmap(
            load_icon_asset("presets.svg").pixmap(_HEADER_ICON_SIZE, _HEADER_ICON_SIZE),
        )
        header.addWidget(header_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(2)
        self._title_label = QLabel(self._header_frame)
        self._title_label.setObjectName("presets_title")
        title_column.addWidget(self._title_label)
        self._subtitle_label = QLabel(self._header_frame)
        self._subtitle_label.setObjectName("presets_subtitle")
        title_column.addWidget(self._subtitle_label)
        header.addLayout(title_column, stretch=1)

        self._close_button = QPushButton(self._header_frame)
        self._close_button.setAutoDefault(False)
        self._close_button.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self._close_button.clicked.connect(self.accept)
        header.addWidget(self._close_button, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self._header_frame)

        scroll = QScrollArea(self)
        scroll.setObjectName("presets_scroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._content = QWidget()
        self._content.setObjectName("presets_content")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(
            _CONTENT_MARGIN_LEFT,
            12,
            _CONTENT_MARGIN_RIGHT,
            18,
        )
        self._content_layout.setSpacing(10)

        self._builtin_heading = QLabel()
        self._builtin_heading.setObjectName("preset_section_title")
        self._content_layout.addWidget(self._builtin_heading)

        self._builtin_host = QWidget()
        self._builtin_flow = _FlowLayout(self._builtin_host, spacing=_CARD_GAP)
        self._content_layout.addWidget(self._builtin_host)

        self._user_heading = QLabel()
        self._user_heading.setObjectName("preset_section_title")
        self._content_layout.addWidget(self._user_heading)

        self._user_host = QWidget()
        self._user_flow = _FlowLayout(self._user_host, spacing=_CARD_GAP)
        self._content_layout.addWidget(self._user_host)

        self._empty_user_label = QLabel()
        self._empty_user_label.setObjectName("preset_empty_label")
        self._empty_user_label.setWordWrap(True)
        self._content_layout.addWidget(self._empty_user_label)
        self._content_layout.addStretch(1)

        scroll.setWidget(self._content)
        layout.addWidget(scroll, stretch=1)

        self._footer_frame = QFrame(self)
        self._footer_frame.setObjectName("presets_footer")
        footer = QHBoxLayout(self._footer_frame)
        footer.setContentsMargins(22, 12, 22, 14)
        footer.setSpacing(_CARD_GAP)
        self._create_action = _PresetFooterAction("file-new.svg", self._footer_frame)
        self._create_action.clicked.connect(self._on_save_current)
        footer.addWidget(self._create_action, 0, Qt.AlignmentFlag.AlignLeft)
        self._overwrite_action = _PresetFooterAction("file-save.svg", self._footer_frame)
        self._overwrite_action.clicked.connect(self._on_overwrite_current)
        footer.addWidget(self._overwrite_action, 0, Qt.AlignmentFlag.AlignLeft)
        footer.addStretch(1)
        layout.addWidget(self._footer_frame)

        self.setMinimumSize(560, 400)
        self.retranslate_ui()
        self._reload_library()
        self._fit_height_to_content()

    @property
    def selected_id(self) -> str | None:
        """return the currently selected preset id."""

        return self._selected_id

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self.setWindowTitle(self.tr("Presets"))
        self._title_label.setText(self.tr("Presets"))
        self._subtitle_label.setText(
            self.tr("Apply a look or save the current settings as a preset.")
        )
        self._builtin_heading.setText(self.tr("Built-in"))
        self._user_heading.setText(self.tr("Saved"))
        self._empty_user_label.setText(self.tr("No saved presets yet."))
        self._create_action.set_texts(
            self.tr("Create new preset"),
            self.tr("Create a new preset from the current settings."),
        )
        self._overwrite_action.set_texts(
            self.tr("Overwrite template"),
            self.tr("Save the current settings into this template."),
        )
        self._close_button.setText(self.tr("Close"))
        for card in self._cards:
            self._apply_card_texts(card)

    def _builtin_texts(self, preset: LookPreset) -> tuple[str, str]:
        if preset.id == "soft-drift":
            return (
                self.tr("Soft Drift"),
                self.tr("Sparse, slow stars with a gentle zoom"),
            )
        if preset.id == "deep-glow":
            return (
                self.tr("Deep Glow"),
                self.tr("Dense glowing stars with a cinematic sweep"),
            )
        return preset.name, preset.description

    def _apply_card_texts(self, card: _PresetCard) -> None:
        preset = card.preset
        if preset.builtin:
            title, description = self._builtin_texts(preset)
        else:
            title, description = preset.name, preset.description
        card.set_texts(title, description, self.tr("Delete"))

    def _fit_height_to_content(self) -> None:
        """size the dialog so the current content fits without scrolling."""

        builtin_count = sum(1 for card in self._cards if card.preset.builtin)
        user_count = len(self._cards) - builtin_count

        builtin_rows = max(1, math.ceil(builtin_count / _PRESET_COLUMNS))
        content = 12 + 18
        content += 32 + builtin_rows * _CARD_HEIGHT + (builtin_rows - 1) * _CARD_GAP
        content += 10 + 32
        if user_count:
            user_rows = math.ceil(user_count / _PRESET_COLUMNS)
            content += user_rows * _CARD_HEIGHT + (user_rows - 1) * _CARD_GAP
        else:
            content += 48

        frame = self._header_frame.sizeHint().height() + self._footer_frame.sizeHint().height()
        target = frame + content + 8
        height = min(max(target, _DIALOG_MIN_HEIGHT), _DIALOG_MAX_HEIGHT)
        self.resize(_DIALOG_WIDTH, height)

    def _reload_library(self) -> None:
        self._clear_flow(self._builtin_flow)
        self._clear_flow(self._user_flow)
        self._cards.clear()

        presets = load_library(user_directory=self._user_directory)
        builtin = [preset for preset in presets if preset.builtin]
        user = [preset for preset in presets if not preset.builtin]

        for preset in builtin:
            self._builtin_flow.addWidget(self._make_card(preset))
        for preset in user:
            self._user_flow.addWidget(self._make_card(preset))

        has_user = bool(user)
        self._user_host.setVisible(has_user)
        self._empty_user_label.setVisible(not has_user)
        known_ids = {card.preset.id for card in self._cards}
        if self._selected_id and self._selected_id not in known_ids:
            self._selected_id = None
        self._sync_selection()

    def _make_card(self, preset: LookPreset) -> _PresetCard:
        card = _PresetCard(preset, self._content)
        self._apply_card_texts(card)
        card.clicked.connect(lambda: self._on_card_clicked(card))
        card.delete_requested.connect(lambda: self._on_delete_card(card))
        self._cards.append(card)
        return card

    def _clear_flow(self, layout: _FlowLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                break
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _sync_selection(self) -> None:
        for card in self._cards:
            card.set_selected(card.preset.id == self._selected_id)
        self._overwrite_action.setVisible(self._selected_user_preset() is not None)

    def _selected_user_preset(self) -> LookPreset | None:
        """
        return the selected user preset, if any.

        """

        for card in self._cards:
            if card.preset.id == self._selected_id and not card.preset.builtin:
                return card.preset
        return None

    def _on_card_clicked(self, card: _PresetCard) -> None:
        self._selected_id = card.preset.id
        self._sync_selection()
        self.preset_applied.emit(card.preset)

    def _on_delete_card(self, card: _PresetCard) -> None:
        preset = card.preset
        answer = QMessageBox.question(
            self,
            self.tr("Delete preset"),
            self.tr('Delete "{name}"? This cannot be undone.').format(name=preset.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            delete_user_preset(preset)
        except PresetError as exc:
            QMessageBox.warning(self, self.tr("Could not delete preset"), str(exc))
            return
        if self._selected_id == preset.id:
            self._selected_id = None
        self._reload_library()

    def _on_save_current(self) -> None:
        dialog = _SavePresetDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        name = dialog.name_edit.text().strip()
        description = dialog.description_edit.text().strip()
        presets = load_library(user_directory=self._user_directory)
        existing = find_user_preset_by_name(name, presets)
        if existing is not None:
            answer = QMessageBox.question(
                self,
                self.tr("Replace preset"),
                self.tr('A preset named "{name}" already exists. Replace it?').format(name=name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            preset_id = existing.id
        else:
            existing_ids = {preset.id for preset in presets}
            preset_id = unique_preset_id(preset_id_from_name(name), existing_ids)

        try:
            saved = save_look_from_settings(
                name,
                description,
                self._get_settings(),
                preset_id=preset_id,
                user_directory=self._user_directory,
            )
        except PresetError as exc:
            QMessageBox.warning(self, self.tr("Could not save preset"), str(exc))
            return

        self._selected_id = saved.id
        self._reload_library()

    def _on_overwrite_current(self) -> None:
        """write the current look into the selected user template."""

        preset = self._selected_user_preset()
        if preset is None:
            return
        try:
            saved = save_look_from_settings(
                preset.name,
                preset.description,
                self._get_settings(),
                preset_id=preset.id,
                user_directory=self._user_directory,
            )
        except PresetError as exc:
            QMessageBox.warning(self, self.tr("Could not save preset"), str(exc))
            return
        self._selected_id = saved.id
        self._reload_library()


__all__ = ["PresetsDialog"]
