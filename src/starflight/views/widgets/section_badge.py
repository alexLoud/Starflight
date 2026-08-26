"""Paint a compact pill badge for section headers."""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

from starflight.views.theme import ACCENT, TEXT_PRIMARY

_BADGE_HEIGHT = 16
_HORIZONTAL_PADDING = 7


class SectionBadge(QWidget):
    """small rounded pill label drawn with explicit geometry."""

    def __init__(self, text: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(_BADGE_HEIGHT)
        self._text = text.upper()

    def set_text(self, text: str) -> None:
        """
        update badge label.

        text
            badge caption such as beta
        """

        self._text = text.upper()
        size = self.sizeHint()
        self.setFixedSize(size.width(), size.height())
        self.update()

    def sizeHint(self) -> QSize:
        """return pill width from the current label text."""

        metrics = QFontMetrics(self._badge_font())
        width = metrics.horizontalAdvance(self._text) + _HORIZONTAL_PADDING * 2
        return QSize(width, _BADGE_HEIGHT)

    def minimumSizeHint(self) -> QSize:
        """keep the badge compact while fitting the label."""

        return self.sizeHint()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().toRectF()
        radius = rect.height() / 2.0
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(ACCENT))
        painter.drawRoundedRect(rect, radius, radius)

        painter.setPen(QColor(TEXT_PRIMARY))
        painter.setFont(self._badge_font())
        painter.drawText(self.rect(), int(Qt.AlignmentFlag.AlignCenter), self._text)

    @staticmethod
    def _badge_font() -> QFont:
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.4)
        return font


__all__ = ["SectionBadge"]
