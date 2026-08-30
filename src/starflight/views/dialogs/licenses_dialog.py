"""Show Starflight and third-party license texts."""

from __future__ import annotations

from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
    QWidget,
)

from starflight.app.legal import combined_legal_text


class LicensesDialog(QDialog):
    """modal dialog listing bundled open-source license texts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("licenses_dialog")
        self.setModal(True)
        self.setMinimumSize(640, 480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(12)

        self._intro_label = QLabel(self)
        self._intro_label.setObjectName("licenses_dialog_intro")
        self._intro_label.setWordWrap(True)
        layout.addWidget(self._intro_label)

        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setObjectName("licenses_dialog_text")
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        mono.setPointSize(11)
        self._text_edit.setFont(mono)
        self._text_edit.setPlainText(combined_legal_text())
        layout.addWidget(self._text_edit, stretch=1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        self.button_box.accepted.connect(self.accept)
        close_button = self.button_box.button(QDialogButtonBox.StandardButton.Close)
        if close_button is not None:
            close_button.clicked.connect(self.accept)
        layout.addWidget(self.button_box)

        self.resize(720, 560)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self.setWindowTitle(self.tr("Open-Source Licenses"))
        self._intro_label.setText(
            self.tr(
                "Starflight and the third-party components bundled with this "
                "application are provided under the following license terms."
            ),
        )


__all__ = ["LicensesDialog"]
