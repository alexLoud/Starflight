"""Show a titled settings section that can be collapsed."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from starflight.views.widgets.section_badge import SectionBadge
from starflight.views.widgets.setting_label import SettingHintIcon

_ICON_SIZE = 16
_ARROW_SIZE = 20


class CollapsibleSection(QWidget):
    """expandable settings section with toggle header."""

    expanded_changed = Signal(bool)

    def __init__(
        self,
        title: str,
        *,
        icon: QIcon | None = None,
        expanded: bool = True,
        nested: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        """
        create collapsible section.

        title
            section header text
        icon
            optional section icon
        expanded
            initial expanded state
        nested
            compact sub-section styling for use inside another section
        parent
            optional parent widget
        """

        super().__init__(parent)
        self.setObjectName("collapsible_section_nested" if nested else "collapsible_section")
        self._title = title
        self._icon = icon
        self._expanded = expanded
        self._nested = nested
        self._available = True
        self.setProperty("available", True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0 if nested else 12)
        layout.setSpacing(0)

        self._header = QWidget(self)
        self._header.setObjectName(
            "collapsible_section_header_nested" if nested else "collapsible_section_header",
        )
        self._header.setCursor(Qt.CursorShape.PointingHandCursor)
        self._header.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._header.setMinimumHeight(30 if nested else 36)

        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(12, 0, 10, 0)
        header_layout.setSpacing(0)

        self._icon_label = QLabel(self._header)
        self._icon_label.setObjectName("collapsible_section_icon")
        self._icon_label.setFixedSize(_ICON_SIZE, _ICON_SIZE)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if nested:
            self._icon_label.setVisible(False)

        self._title_label = QLabel(title, self._header)
        self._title_label.setObjectName(
            "collapsible_section_title_nested" if nested else "collapsible_section_title",
        )

        self._badge = SectionBadge("", self._header)
        self._badge.setVisible(False)

        self._hint_icon = SettingHintIcon(self._header)
        self._hint_icon.setVisible(False)

        self._arrow_label = QLabel(self._header)
        self._arrow_label.setObjectName("collapsible_section_arrow")
        self._arrow_label.setFixedSize(_ARROW_SIZE, _ARROW_SIZE)
        self._arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if not nested:
            header_layout.addWidget(self._icon_label)
            header_layout.addSpacing(10)
        header_layout.addWidget(self._title_label)
        header_layout.addSpacing(8)
        header_layout.addWidget(self._badge, 0, Qt.AlignmentFlag.AlignVCenter)
        header_layout.addStretch(1)
        header_layout.addWidget(self._hint_icon)
        header_layout.addSpacing(6)
        header_layout.addWidget(self._arrow_label)
        layout.addWidget(self._header)

        self._content = QWidget(self)
        self._content.setObjectName("collapsible_section_content")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(14, 10 if nested else 12, 14, 10 if nested else 14)
        self._content_layout.setSpacing(10)
        layout.addWidget(self._content)

        self._set_icon(None if nested else icon)
        self._set_expanded(expanded, notify=False)

    @property
    def content_layout(self) -> QVBoxLayout:
        """return inner content layout."""

        return self._content_layout

    @property
    def is_expanded(self) -> bool:
        """return whether section content is visible."""

        return self._expanded

    def set_expanded(self, expanded: bool) -> None:
        """
        set expanded state.

        expanded
            whether section is expanded
        """

        self._set_expanded(expanded, notify=False)

    def set_title(self, title: str) -> None:
        """
        update section title.

        title
            new header text
        """

        self._title = title
        self._title_label.setText(title)

    def set_hint(self, hint: str) -> None:
        """
        update optional help text for the section header info icon.

        hint
            explanatory tooltip text
        """

        self._hint_icon.set_hint(hint)

    def set_badge(self, badge: str | None) -> None:
        """
        update optional badge text shown beside the section title.

        badge
            short badge label such as beta, or none to hide
        """

        if badge:
            self._badge.set_text(badge)
            self._badge.setVisible(True)
            return
        self._badge.set_text("")
        self._badge.setVisible(False)

    def set_icon(self, icon: QIcon) -> None:
        """
        update section icon.

        icon
            new section icon
        """

        self._icon = icon
        self._set_icon(icon)

    def set_available(self, available: bool) -> None:
        """Dim the header and disable content when the section does not apply."""

        available = bool(available)
        if self._available == available:
            return
        self._available = available
        self.setProperty("available", available)
        self._content.setEnabled(available)
        for widget in (self, self._header, self._title_label, self._arrow_label, self._icon_label):
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            header_rect = self._header.geometry()
            if header_rect.contains(event.position().toPoint()):
                self._set_expanded(not self._expanded, notify=True)
                event.accept()
                return
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._header.setFixedWidth(self.width())

    def _set_icon(self, icon: QIcon | None) -> None:
        if icon is not None and not icon.isNull():
            pixmap = icon.pixmap(_ICON_SIZE, _ICON_SIZE, QIcon.Mode.Normal, QIcon.State.Off)
            self._icon_label.setPixmap(pixmap)
            self._icon_label.setVisible(True)
            return
        self._icon_label.clear()
        self._icon_label.setVisible(False)

    def _set_expanded(self, expanded: bool, *, notify: bool) -> None:
        changed = self._expanded != expanded
        self._expanded = expanded
        self._arrow_label.setText("▾" if expanded else "▸")
        self._content.setVisible(expanded)
        if notify and changed:
            self.expanded_changed.emit(expanded)


__all__ = ["CollapsibleSection"]
