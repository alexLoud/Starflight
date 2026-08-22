"""Display a setting label with an optional help tooltip."""

from __future__ import annotations

import html

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QColor, QEnterEvent, QFont, QIcon, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolTip, QWidget

from starflight.views.icons import load_icon_asset
from starflight.views.theme import TEXT_FORM_LABEL, TEXT_FORM_LABEL_DISABLED, TEXT_GROUP_TITLE

_HINT_ICON_SIZE = 16
_TOOLTIP_MAX_WIDTH_PX = 280


def apply_form_label_palette(label: QLabel, *, enabled: bool = True) -> None:
    """
    apply readable foreground color to a sidebar form label.

    label
        label widget to style
    enabled
        whether the label should use the primary text color
    """

    color = QColor(TEXT_FORM_LABEL if enabled else TEXT_FORM_LABEL_DISABLED)
    palette = label.palette()
    palette.setColor(QPalette.ColorRole.WindowText, color)
    palette.setColor(QPalette.ColorRole.Text, color)
    label.setPalette(palette)

    font = label.font()
    font.setWeight(QFont.Weight.Medium)
    label.setFont(font)


def apply_settings_group_title_style(label: QLabel) -> None:
    """
    apply bright heading style for grouped settings sections.

    label
        group title label to style
    """

    color = QColor(TEXT_GROUP_TITLE)
    palette = label.palette()
    palette.setColor(QPalette.ColorRole.WindowText, color)
    palette.setColor(QPalette.ColorRole.Text, color)
    label.setPalette(palette)

    font = label.font()
    font.setPixelSize(12)
    font.setWeight(QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
    label.setFont(font)


def format_setting_hint_tooltip(text: str) -> str:
    """
    format help text for a multi-line tooltip.

    text
        plain help text shown on hover
    """

    cleaned = text.strip()
    if not cleaned:
        return ""
    escaped = html.escape(cleaned)
    return (
        "<html><head/><body style="
        f"'white-space:pre-wrap; max-width:{_TOOLTIP_MAX_WIDTH_PX}px; "
        "margin:0; line-height:1.4;'>"
        f"{escaped}</body></html>"
    )


class SettingHintIcon(QLabel):
    """small info icon that shows its tooltip immediately on hover."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("setting_hint_icon")
        self.setFixedSize(_HINT_ICON_SIZE, _HINT_ICON_SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCursor(Qt.CursorShape.WhatsThisCursor)
        self._hint_raw = ""
        icon = load_icon_asset("info.svg")
        self.setPixmap(
            icon.pixmap(_HINT_ICON_SIZE, _HINT_ICON_SIZE, QIcon.Mode.Normal, QIcon.State.Off),
        )
        self.setVisible(False)

    def set_hint(self, text: str) -> None:
        """
        update help text shown on hover.

        text
            plain help text
        """

        self._hint_raw = text.strip()
        super().setToolTip(format_setting_hint_tooltip(self._hint_raw))
        self.setVisible(bool(self._hint_raw))

    def enterEvent(self, event: QEnterEvent) -> None:
        if self._hint_raw:
            anchor = self.mapToGlobal(QPoint(self.width() // 2, self.height()))
            QToolTip.showText(anchor, format_setting_hint_tooltip(self._hint_raw), self)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        QToolTip.hideText()
        super().leaveEvent(event)


class SettingLabel(QWidget):
    """form label with trailing info icon for setting help text."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("setting_label")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._text_label = QLabel(self)
        self._text_label.setObjectName("form_label")
        self._hint_icon = SettingHintIcon(self)

        layout.addWidget(self._text_label)
        layout.addWidget(self._hint_icon)
        layout.addStretch(1)
        self._apply_text_color()

    def changeEvent(self, event: QEvent) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.Type.EnabledChange:
            self._apply_text_color()

    def _apply_text_color(self) -> None:
        """sync label text color with enabled state."""

        apply_form_label_palette(self._text_label, enabled=self.isEnabled())

    def set_text(self, text: str) -> None:
        """
        update visible label text.

        text
            setting name shown in the form
        """

        self._text_label.setText(text)

    def set_hint(self, hint: str) -> None:
        """
        update help text shown by the info icon.

        hint
            explanatory tooltip text
        """

        self._hint_icon.set_hint(hint)


__all__ = [
    "SettingHintIcon",
    "SettingLabel",
    "apply_form_label_palette",
    "apply_settings_group_title_style",
]
