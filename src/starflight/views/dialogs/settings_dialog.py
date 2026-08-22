"""Edit settings that apply to the whole application."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from starflight.app.constants import SETTINGS_KEY_LANGUAGE
from starflight.i18n import available_languages, normalize_language_code


class SettingsDialog(QDialog):
    """modal dialog for application preferences."""

    def __init__(
        self,
        settings: QSettings,
        parent: QWidget | None = None,
        *,
        on_language_changed: Callable[[str], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._on_language_changed = on_language_changed
        self._initial_language = normalize_language_code(
            str(settings.value(SETTINGS_KEY_LANGUAGE, "de")),
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        form = QFormLayout()
        self._language_label = QLabel()
        self.language_combo = QComboBox()
        for code, name in available_languages().items():
            self.language_combo.addItem(name, code)
        index = self.language_combo.findData(self._initial_language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)
        form.addRow(self._language_label, self.language_combo)
        layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.resize(420, 180)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Settings"))
        self._language_label.setText(self.tr("Language"))

    def _on_accept(self) -> None:
        language = normalize_language_code(str(self.language_combo.currentData()))
        self._settings.setValue(SETTINGS_KEY_LANGUAGE, language)
        if language != self._initial_language and self._on_language_changed is not None:
            self._on_language_changed(language)
        self.accept()


__all__ = ["SettingsDialog"]
