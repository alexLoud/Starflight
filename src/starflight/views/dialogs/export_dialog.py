"""Collect export options and show render progress."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from starflight.core.exporter import EXPORT_CANCELLED, ExportWorker
from starflight.i18n import tr_validation
from starflight.types.settings import ExportQuality, Project, export_crf_for_quality
from starflight.utils.validation import validate_project_for_export
from starflight.views.dialogs.video_save_dialog import VideoSaveDialog


class ExportDialog(QDialog):
    """modal export dialog."""

    def __init__(
        self,
        project: Project,
        project_path: Path | None,
        parent: QWidget | None = None,
        *,
        render_workers: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.project_path = project_path
        self._render_workers = render_workers
        self._worker: ExportWorker | None = None
        self._export_phase = "idle"

        self.setModal(True)
        self.resize(560, 260)
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)

        output_row = QHBoxLayout()
        self.output_edit = QLineEdit()
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self._choose_output_path)
        output_row.addWidget(self.output_edit, stretch=1)
        output_row.addWidget(self.browse_button)
        self._label_output = QLabel()
        form.addRow(self._label_output, output_row)

        self.quality_combo = QComboBox()
        for quality in (ExportQuality.HIGH, ExportQuality.STANDARD):
            self.quality_combo.addItem("", quality)
        self._label_quality = QLabel()
        form.addRow(self._label_quality, self.quality_combo)
        layout.addLayout(form)

        self.status_label = QLabel()
        self.status_label.setObjectName("section_hint")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        button_row = QHBoxLayout()
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        button_row.addStretch()
        button_row.addWidget(self.cancel_button)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.export_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.export_button.setObjectName("primary_button")
        self.button_box.accepted.connect(self._start_export)
        button_row.addWidget(self.button_box)
        layout.addLayout(button_row)

        default_name = f"{self.project.name}.mp4".replace(" ", "_")
        self.output_edit.setText(str(Path.home() / "Desktop" / default_name))

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self.setWindowTitle(self.tr("Export video"))
        self._label_output.setText(self.tr("Output file"))
        self._label_quality.setText(self.tr("Quality"))
        self.browse_button.setText(self.tr("Browse…"))
        self.cancel_button.setText(self.tr("Cancel"))
        self.export_button.setText(self.tr("Export"))
        self.status_label.setText(self.tr("Ready to export."))
        self.quality_combo.setItemText(0, self.tr("High"))
        self.quality_combo.setItemText(1, self.tr("Standard"))

    def _choose_output_path(self) -> None:
        dialog = VideoSaveDialog(initial_path=self.output_edit.text(), parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        path = dialog.selected_path()
        if path is not None:
            self.output_edit.setText(str(path))

    def _start_export(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            QMessageBox.warning(
                self,
                self.tr("Export unavailable"),
                self.tr("An export is already running."),
            )
            return

        validation = validate_project_for_export(self.project, self.project_path)
        if not validation.ok:
            QMessageBox.warning(
                self,
                self.tr("Export unavailable"),
                tr_validation(validation.message),
            )
            return

        output_path = Path(self.output_edit.text().strip())
        if not output_path:
            QMessageBox.warning(
                self,
                self.tr("Export unavailable"),
                self.tr("Please choose an output file."),
            )
            return

        quality = self.quality_combo.currentData()
        self.project.settings.export.quality = quality
        self.project.settings.export.crf = export_crf_for_quality(quality)

        self.export_button.setEnabled(False)
        self.export_button.setObjectName("")
        self.export_button.style().unpolish(self.export_button)
        self.export_button.style().polish(self.export_button)
        self.button_box.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.output_edit.setEnabled(False)
        self.quality_combo.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self._export_phase = "preparing"
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label.setText(self.tr("Preparing stars…"))

        self._worker = ExportWorker(
            self.project,
            output_path,
            self.project_path,
            render_workers=self._render_workers,
        )
        self._worker.progress_changed.connect(self._on_progress)
        self._worker.frame_progress.connect(self._on_frame_progress)
        self._worker.status_changed.connect(self._on_status)
        self._worker.finished_success.connect(self._on_success)
        self._worker.finished_error.connect(self._on_error)
        self._worker.start()

    def _on_progress(self, current: int, total: int) -> None:
        percent = int((current / max(1, total)) * 100)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)
        if self._export_phase == "preparing":
            self.status_label.setText(self.tr("Preparing stars…"))

    def _on_frame_progress(self, current: int, total: int) -> None:
        """
        update status text from rendered frame counts.

        current
            completed rendered frames
        total
            total export frames
        """

        self._export_phase = "rendering"
        self.status_label.setText(
            self.tr("Rendering frames… {current} of {total}").format(
                current=current,
                total=total,
            ),
        )

    def _on_status(self, phase: str) -> None:
        """
        update status for non-frame export phases.

        phase
            export phase key from ExportWorker
        """

        self._export_phase = phase
        if phase == "preparing":
            self.progress_bar.setRange(0, 100)
            self.status_label.setText(self.tr("Preparing stars…"))
            return
        if phase == "rendering":
            self.status_label.setText(self.tr("Rendering frames…"))

    def _on_success(self, output_path: str) -> None:
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self.status_label.setText(self.tr("Export completed."))
        QMessageBox.information(
            self,
            self.tr("Export successful"),
            self.tr("Video saved to:\n{path}").format(path=output_path),
        )
        self.accept()

    def _on_error(self, message: str) -> None:
        self._restore_export_controls()
        self.progress_bar.setRange(0, 100)
        if message == EXPORT_CANCELLED:
            self.status_label.setText(self.tr("Export cancelled."))
            return
        translated = tr_validation(message)
        self.status_label.setText(translated)
        QMessageBox.warning(self, self.tr("Export failed"), translated)

    def _restore_export_controls(self) -> None:
        """re-enable export controls after a failed or cancelled run."""

        self.browse_button.setEnabled(True)
        self.output_edit.setEnabled(True)
        self.quality_combo.setEnabled(True)
        self.button_box.setEnabled(True)
        self.export_button.setEnabled(True)
        self.export_button.setObjectName("primary_button")
        self.export_button.style().unpolish(self.export_button)
        self.export_button.style().polish(self.export_button)
        self.cancel_button.setEnabled(True)

    def _on_cancel_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.status_label.setText(self.tr("Cancelling export…"))
            self.cancel_button.setEnabled(False)
            return
        self.reject()

    def closeEvent(self, event) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        super().closeEvent(event)


__all__ = ["ExportDialog"]
