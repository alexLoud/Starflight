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

from starflight.app.constants import (
    SETTINGS_KEY_BACKGROUND_PREVIEW_UPDATE,
    SETTINGS_KEY_LANGUAGE,
    SETTINGS_KEY_PLAYBACK_PREVIEW_FPS,
    SETTINGS_KEY_RENDER_WORKERS,
)
from starflight.app.settings import (
    BACKGROUND_PREVIEW_UPDATE_OPTIONS,
    PLAYBACK_PREVIEW_FPS_OPTIONS,
    available_render_worker_counts,
    background_preview_update_from_settings,
    playback_preview_fps_from_settings,
    render_worker_count_from_settings,
)
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
        self._initial_render_workers = render_worker_count_from_settings(settings)
        self._initial_preview_fps = playback_preview_fps_from_settings(settings)
        self._initial_background_update = background_preview_update_from_settings(settings)

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

        self._render_workers_label = QLabel()
        self.render_workers_combo = QComboBox()
        for worker_count in available_render_worker_counts():
            self.render_workers_combo.addItem("", worker_count)
        render_index = self.render_workers_combo.findData(self._initial_render_workers)
        if render_index >= 0:
            self.render_workers_combo.setCurrentIndex(render_index)
        form.addRow(self._render_workers_label, self.render_workers_combo)

        self._preview_fps_label = QLabel()
        self.preview_fps_combo = QComboBox()
        for preview_fps in PLAYBACK_PREVIEW_FPS_OPTIONS:
            self.preview_fps_combo.addItem("", preview_fps)
        preview_fps_index = self.preview_fps_combo.findData(self._initial_preview_fps)
        if preview_fps_index >= 0:
            self.preview_fps_combo.setCurrentIndex(preview_fps_index)
        form.addRow(self._preview_fps_label, self.preview_fps_combo)

        self._background_update_label = QLabel()
        self.background_update_combo = QComboBox()
        for update_mode in BACKGROUND_PREVIEW_UPDATE_OPTIONS:
            self.background_update_combo.addItem("", update_mode)
        background_index = self.background_update_combo.findData(self._initial_background_update)
        if background_index >= 0:
            self.background_update_combo.setCurrentIndex(background_index)
        form.addRow(self._background_update_label, self.background_update_combo)
        layout.addLayout(form)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        )
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.resize(460, 300)
        self.retranslate_ui()

    def retranslate_ui(self) -> None:
        self.setWindowTitle(self.tr("Settings"))
        self._language_label.setText(self.tr("Language"))
        self._render_workers_label.setText(self.tr("CPU cores for rendering"))
        self._preview_fps_label.setText(self.tr("Preview frame rate"))
        self._background_update_label.setText(self.tr("Update preview in background"))
        for index in range(self.render_workers_combo.count()):
            worker_count = int(self.render_workers_combo.itemData(index))
            if worker_count == 1:
                label = self.tr("{count} core").format(count=worker_count)
            else:
                label = self.tr("{count} cores").format(count=worker_count)
            self.render_workers_combo.setItemText(index, label)
        for index in range(self.preview_fps_combo.count()):
            preview_fps = int(self.preview_fps_combo.itemData(index))
            label = self._preview_fps_label_for_rate(preview_fps)
            self.preview_fps_combo.setItemText(index, label)
        for index in range(self.background_update_combo.count()):
            update_mode = str(self.background_update_combo.itemData(index))
            self.background_update_combo.setItemText(
                index,
                self._background_update_label_for_mode(update_mode),
            )

    def _preview_fps_label_for_rate(self, preview_fps: int) -> str:
        if preview_fps <= 3:
            quality = self.tr("Low")
        elif preview_fps <= 6:
            quality = self.tr("Medium")
        elif preview_fps <= 9:
            quality = self.tr("High")
        else:
            quality = self.tr("Very high")
        return self.tr("{quality} ({fps} fps)").format(quality=quality, fps=preview_fps)

    def _background_update_label_for_mode(self, update_mode: str) -> str:
        if update_mode == "disabled":
            return self.tr("Disabled")
        if update_mode == "full":
            return self.tr("Update fully")
        return self.tr("Update partially")

    def _on_accept(self) -> None:
        language = normalize_language_code(str(self.language_combo.currentData()))
        self._settings.setValue(SETTINGS_KEY_LANGUAGE, language)
        render_workers = int(self.render_workers_combo.currentData())
        self._settings.setValue(SETTINGS_KEY_RENDER_WORKERS, render_workers)
        preview_fps = int(self.preview_fps_combo.currentData())
        self._settings.setValue(SETTINGS_KEY_PLAYBACK_PREVIEW_FPS, preview_fps)
        background_update = str(self.background_update_combo.currentData())
        self._settings.setValue(SETTINGS_KEY_BACKGROUND_PREVIEW_UPDATE, background_update)
        if language != self._initial_language and self._on_language_changed is not None:
            self._on_language_changed(language)
        self.accept()


__all__ = ["SettingsDialog"]
