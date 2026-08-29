"""Collect export options and show render progress."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QLocale, QStandardPaths, Qt, QUrl
from PySide6.QtGui import QDesktopServices
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
        self._last_output_path: Path | None = None

        self.setModal(True)
        self.setMinimumWidth(520)
        self._build_ui()
        self.retranslate_ui()
        default_name = f"{self.project.name}.mp4".replace(" ", "_")
        self.output_edit.setText(str(default_export_output_path(default_name)))
        self._update_summary()
        self._update_export_state()

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

        self._summary_card = QFrame(self._options_page)
        self._summary_card.setObjectName("export_summary_card")
        summary_layout = QVBoxLayout(self._summary_card)
        summary_layout.setContentsMargins(14, 12, 14, 12)
        summary_layout.setSpacing(4)
        self._summary_primary = QLabel(self._summary_card)
        self._summary_primary.setObjectName("export_summary_primary")
        self._summary_secondary = QLabel(self._summary_card)
        self._summary_secondary.setObjectName("export_summary_secondary")
        summary_layout.addWidget(self._summary_primary)
        summary_layout.addWidget(self._summary_secondary)
        options_layout.addWidget(self._summary_card)

        form = QFormLayout()
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(12)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.FieldsStayAtSizeHint)

        output_row = QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        self.output_edit = QLineEdit()
        self.output_edit.setMinimumWidth(240)
        self.output_edit.setReadOnly(True)
        self.output_edit.textChanged.connect(self._update_export_state)
        self.browse_button = QPushButton()
        self.browse_button.clicked.connect(self._choose_output_path)
        output_row.addWidget(self.output_edit)
        output_row.addWidget(self.browse_button)
        self._label_output = QLabel()
        self._label_output.setObjectName("form_label")
        form.addRow(self._label_output, output_row)

        self.quality_combo = QComboBox()
        for quality in (ExportQuality.HIGH, ExportQuality.STANDARD):
            self.quality_combo.addItem("", quality)
        self.quality_combo.currentIndexChanged.connect(self._update_summary)
        self._label_quality = QLabel()
        self._label_quality.setObjectName("form_label")
        form.addRow(self._label_quality, self.quality_combo)
        options_layout.addLayout(form)

        self.status_label = QLabel()
        self.status_label.setObjectName("section_hint")
        self.status_label.setWordWrap(True)
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

        self._progress_cancel_row = QWidget(page)
        cancel_row = QHBoxLayout(self._progress_cancel_row)
        cancel_row.setContentsMargins(0, 0, 0, 0)
        self.progress_cancel_button = QPushButton()
        self.progress_cancel_button.clicked.connect(self._on_cancel_clicked)
        cancel_row.addStretch(1)
        cancel_row.addWidget(self.progress_cancel_button)
        cancel_row.addStretch(1)
        content_layout.addWidget(self._progress_cancel_row)

        self._progress_complete_row = QWidget(page)
        complete_row = QHBoxLayout(self._progress_complete_row)
        complete_row.setContentsMargins(0, 0, 0, 0)
        complete_row.setSpacing(10)
        self.show_in_folder_button = QPushButton()
        self.show_in_folder_button.clicked.connect(self._show_in_folder)
        self.done_button = QPushButton()
        self.done_button.setObjectName("primary_button")
        self.done_button.clicked.connect(self.accept)
        complete_row.addStretch(1)
        complete_row.addWidget(self.show_in_folder_button)
        complete_row.addWidget(self.done_button)
        self._progress_complete_row.setVisible(False)
        content_layout.addWidget(self._progress_complete_row)
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
        self.quality_combo.setItemText(0, self.tr("High"))
        self.quality_combo.setItemText(1, self.tr("Standard"))
        self._header_title.setText(self.tr("Export video"))
        self._header_subtitle.setText(
            self.tr("Review the summary and choose where to save the video."),
        )
        self.progress_cancel_button.setText(self.tr("Cancel"))
        self.show_in_folder_button.setText(self.tr("Show in folder"))
        self.done_button.setText(self.tr("Done"))
        self._update_summary()
        self._update_export_state()

    def _output_path(self) -> Path:
        """return the current export destination path."""

        return Path(self.output_edit.text().strip()).expanduser()

    def _format_duration(self, seconds: float) -> str:
        """
        format clip duration for the export summary.

        seconds
            clip duration in seconds
        """

        if abs(seconds - round(seconds)) < 0.05:
            return self.tr("{seconds} s").format(seconds=int(round(seconds)))
        return self.tr("{seconds} s").format(
            seconds=QLocale().toString(seconds, "f", 1),
        )

    def _update_summary(self) -> None:
        """refresh the pre-export video summary."""

        settings = self.project.settings
        resolution = self.tr("{width} × {height}").format(
            width=settings.resolution.width,
            height=settings.resolution.height,
        )
        duration = self._format_duration(settings.duration_seconds)
        frame_rate = self.tr("{fps} fps").format(fps=settings.fps)
        self._summary_primary.setText(f"{resolution}  ·  {duration}  ·  {frame_rate}")

        quality = self.quality_combo.currentText()
        self._summary_secondary.setText(f"MP4  ·  {quality}")

    def _output_path_error(self) -> str | None:
        """return a translated path validation message or none when valid."""

        output_text = self.output_edit.text().strip()
        if not output_text:
            return self.tr("Please choose an output file.")
        output_path = self._output_path()
        if not output_path.parent.is_dir():
            return self.tr("The output folder does not exist:\n{path}").format(
                path=output_path.parent,
            )
        return None

    def _update_export_state(self) -> None:
        """refresh validation feedback and export button state."""

        path_error = self._output_path_error()
        project_validation = validate_project_for_export(self.project, self.project_path)
        output_text = self.output_edit.text().strip()
        self.output_edit.setToolTip(output_text)

        if path_error is not None:
            self.status_label.setText(path_error)
            self.status_label.setVisible(True)
            self.export_button.setEnabled(False)
            return
        if not project_validation.ok:
            self.status_label.setText(tr_validation(project_validation.message))
            self.status_label.setVisible(True)
            self.export_button.setEnabled(False)
            return

        self.status_label.clear()
        self.status_label.setVisible(False)
        self.export_button.setEnabled(True)

    def _choose_output_path(self) -> None:
        dialog = VideoSaveDialog(initial_path=self.output_edit.text(), parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        path = dialog.selected_path()
        if path is not None:
            self.output_edit.setText(str(path))

    def _confirm_overwrite(self, output_path: Path) -> bool:
        """
        ask whether to replace an existing export file.

        output_path
            destination path that already exists
        """

        answer = QMessageBox.question(
            self,
            self.tr("Overwrite file?"),
            self.tr(
                'A file named "{name}" already exists in this folder. Overwrite it?',
            ).format(name=output_path.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

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

        path_error = self._output_path_error()
        if path_error is not None:
            QMessageBox.warning(self, self.tr("Export unavailable"), path_error)
            return

        output_path = self._output_path()
        if output_path.exists() and not self._confirm_overwrite(output_path):
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
        self._last_output_path = None
        self._header_title.setText(self.tr("Exporting…"))
        self._header_subtitle.setText(self.tr("File: {name}").format(name=output_path.name))
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self._percent_label.setText("0%")
        if self._export_phase == "parallax":
            self.progress_status_label.setText(self.tr("Preparing parallax…"))
        else:
            self.progress_status_label.setText(self.tr("Preparing export…"))
        self.progress_cancel_button.setEnabled(True)
        self._progress_cancel_row.setVisible(True)
        self._progress_complete_row.setVisible(False)
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
        percent = round((current / max(1, total)) * 100)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(percent)
        self._percent_label.setText(f"{percent}%")
        if self._export_phase == "preparing":
            self.progress_status_label.setText(self.tr("Preparing export…"))

    def _on_frame_progress(self, current: int, total: int) -> None:
        """
        update status text from rendered frame counts.

        current
            completed rendered frames
        total
            total export frames
        """

        if current <= 0:
            return
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
            if self._export_phase == "parallax":
                self.progress_status_label.setText(self.tr("Preparing export…"))
            self._export_phase = "preparing"
            return
        if phase == "rendering":
            return
        if phase == "rendering_workers":
            self.progress_status_label.setText(self.tr("Starting render workers…"))
            return
        if phase == "encoding":
            self.progress_status_label.setText(self.tr("Encoding video…"))

    def _release_worker(self) -> None:
        """wait for the export worker thread to finish and drop the reference."""

        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.wait()

    def _show_in_folder(self) -> None:
        """reveal the exported video in the system file manager."""

        if self._last_output_path is None:
            return
        QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(self._last_output_path.parent)),
        )

    def _on_success(self, output_path: str) -> None:
        self._export_finished = True
        self._release_worker()
        self._last_output_path = Path(output_path)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)
        self._percent_label.setText("100%")
        self.progress_status_label.setText(self.tr("Export completed."))
        self._header_title.setText(self.tr("Export video"))
        self._header_subtitle.setText(self.tr("File: {name}").format(name=Path(output_path).name))
        self._progress_cancel_row.setVisible(False)
        self._progress_complete_row.setVisible(True)
        self.adjustSize()

    def _on_error(self, failure: object) -> None:
        self._release_worker()
        self._restore_export_controls()
        self.progress_bar.setRange(0, 100)
        if failure == EXPORT_CANCELLED:
            self.status_label.setText(self.tr("Export cancelled."))
            self.status_label.setVisible(True)
            return
        if isinstance(failure, RuntimeError) and "FFmpeg" in str(failure):
            message = str(failure)
            self.status_label.setText(message)
            self.status_label.setVisible(True)
            QMessageBox.warning(self, self.tr("Export failed"), message)
            return
        if isinstance(failure, BaseException):
            self.status_label.setText(self.tr("Export failed due to an internal error."))
            self.status_label.setVisible(True)
            self._error_service.show_crash_report(
                "video export failed",
                failure,
                self,
            )
            return

        translated = tr_validation(str(failure))
        self.status_label.setText(translated)
        self.status_label.setVisible(True)
        QMessageBox.warning(self, self.tr("Export failed"), translated)

    def _restore_export_controls(self) -> None:
        """return to the options state after a failed or cancelled run."""

        self.progress_cancel_button.setEnabled(True)
        self._progress_cancel_row.setVisible(True)
        self._progress_complete_row.setVisible(False)
        self._header_title.setText(self.tr("Export video"))
        self._header_subtitle.setText(
            self.tr("Review the summary and choose where to save the video."),
        )
        self._progress_page.setVisible(False)
        self._options_page.setVisible(True)
        self.adjustSize()
        self._update_export_state()

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
