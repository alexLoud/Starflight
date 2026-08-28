"""Collect export options and show render progress."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
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
from starflight.services.error_service import ErrorService
from starflight.types.settings import (
    ExportQuality,
    ImageMotionMode,
    Project,
    export_crf_for_quality,
)
from starflight.utils.validation import validate_project_for_export
from starflight.views.dialogs.video_save_dialog import VideoSaveDialog
from starflight.views.icons import load_icon_asset


def default_export_output_path(filename: str) -> Path:
    """
    return a writable default mp4 path, preferring the real desktop folder.

    filename
        destination file name including the .mp4 suffix
    """

    locations = (
        QStandardPaths.StandardLocation.DesktopLocation,
        QStandardPaths.StandardLocation.DocumentsLocation,
        QStandardPaths.StandardLocation.HomeLocation,
    )
    for location in locations:
        candidate = QStandardPaths.writableLocation(location)
        if not candidate:
            continue
        directory = Path(candidate)
        if directory.is_dir():
            return directory / filename
    return Path.home() / filename


class ExportDialog(QDialog):
    """modal export dialog."""

    def __init__(
        self,
        project: Project,
        project_path: Path | None,
        parent: QWidget | None = None,
        *,
        render_workers: int | None = None,
        error_service: ErrorService,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.project_path = project_path
        self._render_workers = render_workers
        self._error_service = error_service
        self._worker: ExportWorker | None = None
        self._export_phase = "idle"
        self._export_finished = False

        self.setModal(True)
        self.setMinimumWidth(500)
        self._build_ui()
        self.retranslate_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._header_frame = QFrame(self)
        self._header_frame.setObjectName("export_header")
        header = QHBoxLayout(self._header_frame)
        header.setContentsMargins(22, 16, 16, 16)
        header.setSpacing(14)

        header_icon = QLabel(self._header_frame)
        header_icon.setObjectName("export_header_icon")
        header_icon.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        header_icon.setFixedSize(44, 44)
        header_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_icon.setPixmap(load_icon_asset("export-video.svg").pixmap(24, 24))
        header.addWidget(header_icon, 0, Qt.AlignmentFlag.AlignVCenter)

        title_column = QVBoxLayout()
        title_column.setContentsMargins(0, 0, 0, 0)
        title_column.setSpacing(2)
        self._header_title = QLabel(self._header_frame)
        self._header_title.setObjectName("export_title")
        title_column.addWidget(self._header_title)
        self._header_subtitle = QLabel(self._header_frame)
        self._header_subtitle.setObjectName("export_subtitle")
        title_column.addWidget(self._header_subtitle)
        header.addLayout(title_column, stretch=1)
        layout.addWidget(self._header_frame)

        self._options_page = QWidget(self)
        options_layout = QVBoxLayout(self._options_page)
        options_layout.setContentsMargins(22, 16, 22, 16)
        options_layout.setSpacing(14)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        self.output_edit = QLineEdit()
        self.output_edit.setMinimumWidth(240)
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self._choose_output_path)
        output_row.addWidget(self.output_edit)
        output_row.addWidget(self.browse_button)
        self._label_output = QLabel()
        form.addRow(self._label_output, output_row)

        self.quality_combo = QComboBox()
        for quality in (ExportQuality.HIGH, ExportQuality.STANDARD):
            self.quality_combo.addItem("", quality)
        self._label_quality = QLabel()
        form.addRow(self._label_quality, self.quality_combo)
        options_layout.addLayout(form)

        self.status_label = QLabel()
        self.status_label.setObjectName("section_hint")
        self.status_label.setVisible(False)
        options_layout.addWidget(self.status_label)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        self.cancel_button = QPushButton()
        self.cancel_button.clicked.connect(self._on_cancel_clicked)
        self.export_button = QPushButton()
        self.export_button.setObjectName("primary_button")
        self.export_button.setDefault(True)
        self.export_button.clicked.connect(self._start_export)
        button_row.addStretch(1)
        button_row.addWidget(self.cancel_button)
        button_row.addWidget(self.export_button)
        options_layout.addLayout(button_row)
        layout.addWidget(self._options_page)

        self._progress_page = self._build_progress_page()
        self._progress_page.setVisible(False)
        layout.addWidget(self._progress_page)

        default_name = f"{self.project.name}.mp4".replace(" ", "_")
        self.output_edit.setText(str(default_export_output_path(default_name)))

    def _build_progress_page(self) -> QWidget:
        """build the progress content shown while an export runs."""

        page = QWidget(self)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        page_layout.setSpacing(0)

        content = QWidget(page)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(22, 16, 22, 16)
        content_layout.setSpacing(12)

        progress_row = QHBoxLayout()
        progress_row.setContentsMargins(0, 0, 0, 0)
        progress_row.setSpacing(10)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        progress_row.addWidget(self.progress_bar, stretch=1)
        self._percent_label = QLabel("0%")
        self._percent_label.setObjectName("export_percent_label")
        progress_row.addWidget(self._percent_label)
        content_layout.addLayout(progress_row)

        self.progress_status_label = QLabel()
        self.progress_status_label.setObjectName("section_hint")
        content_layout.addWidget(self.progress_status_label)

        cancel_row = QHBoxLayout()
        cancel_row.setContentsMargins(0, 0, 0, 0)
        self.progress_cancel_button = QPushButton()
        self.progress_cancel_button.clicked.connect(self._on_cancel_clicked)
        cancel_row.addStretch(1)
        cancel_row.addWidget(self.progress_cancel_button)
        cancel_row.addStretch(1)
        content_layout.addLayout(cancel_row)
        page_layout.addWidget(content, stretch=1)
        return page

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
        self._header_title.setText(self.tr("Export video"))
        self._header_subtitle.setText(self.tr("Choose the output file and quality."))
        self.progress_cancel_button.setText(self.tr("Cancel"))

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

        output_text = self.output_edit.text().strip()
        if not output_text:
            QMessageBox.warning(
                self,
                self.tr("Export unavailable"),
                self.tr("Please choose an output file."),
            )
            return
        output_path = Path(output_text).expanduser()
        if not output_path.parent.is_dir():
            QMessageBox.warning(
                self,
                self.tr("Export unavailable"),
                self.tr("The output folder does not exist:\n{path}").format(
                    path=output_path.parent
                ),
            )
            return

        quality = self.quality_combo.currentData()
        self.project.settings.export.quality = quality
        self.project.settings.export.crf = export_crf_for_quality(quality)

        self._export_phase = (
            "parallax"
            if self.project.settings.background.motion_mode == ImageMotionMode.PARALLAX
            else "preparing"
        )
        self._export_finished = False
        self._header_title.setText(self.tr("Exporting…"))
        self._header_subtitle.setText(self.tr("File: {name}").format(name=output_path.name))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._percent_label.setText("0%")
        if self._export_phase == "parallax":
            self.progress_status_label.setText(self.tr("Preparing parallax…"))
        else:
            self.progress_status_label.setText(self.tr("Preparing stars…"))
        self.progress_cancel_button.setEnabled(True)
        self._options_page.setVisible(False)
        self._progress_page.setVisible(True)
        self.adjustSize()

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
        self._percent_label.setText(f"{percent}%")
        if self._export_phase == "preparing":
            self.progress_status_label.setText(self.tr("Preparing stars…"))

    def _on_frame_progress(self, current: int, total: int) -> None:
        """
        update status text from rendered frame counts.

        current
            completed rendered frames
        total
            total export frames
        """

        self._export_phase = "rendering"
        self.progress_status_label.setText(
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
        if phase == "parallax":
            self.progress_bar.setRange(0, 100)
            self.progress_status_label.setText(self.tr("Preparing parallax…"))
            return
        if phase == "preparing":
            self.progress_bar.setRange(0, 100)
            self.progress_status_label.setText(self.tr("Preparing stars…"))
            return
        if phase == "rendering":
            self.progress_status_label.setText(self.tr("Rendering frames…"))

    def _release_worker(self) -> None:
        """wait for the export worker thread to finish and drop the reference."""

        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.wait()

    def _on_success(self, output_path: str) -> None:
        self._export_finished = True
        self._release_worker()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._percent_label.setText("100%")
        self.progress_status_label.setText(self.tr("Export completed."))
        QMessageBox.information(
            self,
            self.tr("Export successful"),
            self.tr("Video saved to:\n{path}").format(path=output_path),
        )
        self.accept()

    def _on_error(self, failure: object) -> None:
        self._release_worker()
        self._restore_export_controls()
        self.progress_bar.setRange(0, 100)
        if failure == EXPORT_CANCELLED:
            self.status_label.setText(self.tr("Export cancelled."))
            return
        if isinstance(failure, RuntimeError) and "FFmpeg" in str(failure):
            message = str(failure)
            self.status_label.setText(message)
            QMessageBox.warning(self, self.tr("Export failed"), message)
            return
        if isinstance(failure, BaseException):
            self.status_label.setText(self.tr("Export failed due to an internal error."))
            self._error_service.show_crash_report(
                "video export failed",
                failure,
                self,
            )
            return

        translated = tr_validation(str(failure))
        self.status_label.setText(translated)
        QMessageBox.warning(self, self.tr("Export failed"), translated)

    def _restore_export_controls(self) -> None:
        """return to the options state after a failed or cancelled run."""

        self.progress_cancel_button.setEnabled(True)
        self.status_label.setVisible(True)
        self._header_title.setText(self.tr("Export video"))
        self._header_subtitle.setText(self.tr("Choose the output file and quality."))
        self._progress_page.setVisible(False)
        self._options_page.setVisible(True)
        self.adjustSize()

    def _on_cancel_clicked(self) -> None:
        if self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
            self.progress_status_label.setText(self.tr("Cancelling export…"))
            self.progress_cancel_button.setEnabled(False)
            return
        self.reject()

    def closeEvent(self, event) -> None:
        if not self._export_finished and self._worker is not None and self._worker.isRunning():
            self._worker.cancel()
        super().closeEvent(event)


__all__ = ["ExportDialog", "default_export_output_path"]
