"""Display a copyable report after an internal application failure."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from starflight.app.crash_reporting import CrashReport


class CrashReportDialog(QDialog):
    """modal crash-report dialog with copy and log-folder actions."""

    def __init__(
        self,
        report: CrashReport,
        log_directory: Path,
        parent: QWidget | None = None,
        *,
        fatal: bool = True,
    ) -> None:
        super().__init__(parent)
        self._report = report
        self._log_directory = log_directory
        self._fatal = fatal

        self.setModal(True)
        self.setMinimumWidth(620)
        self._build_ui()
        self.retranslate_ui()
        self.resize(620, self.height())
        self._fit_header_height()
        self.adjustSize()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(12)

        self._header_widget = QWidget()
        self._header_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        header_layout = QHBoxLayout(self._header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(16)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        critical_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxCritical)
        self.setWindowIcon(critical_icon)
        icon_label = QLabel()
        icon_label.setFixedSize(40, 40)
        icon_label.setPixmap(critical_icon.pixmap(36, 36))
        icon_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        header_layout.addWidget(icon_label)
        header_layout.setAlignment(icon_label, Qt.AlignmentFlag.AlignTop)

        message_layout = QVBoxLayout()
        message_layout.setSpacing(5)
        message_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._header_title_label = QLabel()
        self._header_title_label.setObjectName("crash_title")
        self._header_title_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self._header_title_label.setWordWrap(True)
        message_layout.addWidget(self._header_title_label)
        self._summary_label = QLabel()
        self._summary_label.setObjectName("crash_summary")
        self._summary_label.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        self._summary_label.setWordWrap(True)
        message_layout.addWidget(self._summary_label)
        header_layout.addLayout(message_layout, stretch=1)
        layout.addWidget(self._header_widget)

        separator = QFrame()
        separator.setObjectName("crash_separator")
        separator.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(separator)

        self.details_button = QToolButton()
        self.details_button.setObjectName("crash_details_toggle")
        self.details_button.setCheckable(True)
        self.details_button.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.details_button.setArrowType(Qt.ArrowType.RightArrow)
        self.details_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.details_button.toggled.connect(self._set_details_visible)
        layout.addWidget(self.details_button)

        self.report_edit = QPlainTextEdit()
        self.report_edit.setObjectName("crash_report_details")
        self.report_edit.setReadOnly(True)
        self.report_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        details_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        details_font.setPointSize(11)
        self.report_edit.setFont(details_font)
        self.report_edit.setPlainText(self._report.text)
        self.report_edit.hide()
        layout.addWidget(self.report_edit, stretch=1)

        self._button_box = QDialogButtonBox()
        self.copy_button = self._button_box.addButton(
            "",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.open_logs_button = self._button_box.addButton(
            "",
            QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.close_button = self._button_box.addButton(
            QDialogButtonBox.StandardButton.Close,
        )
        self.close_button.setObjectName("primary_button")
        self.close_button.setDefault(True)
        self.copy_button.clicked.connect(self._copy_report)
        self.open_logs_button.clicked.connect(self._open_log_directory)
        self._button_box.rejected.connect(self.reject)
        layout.addWidget(self._button_box)

        self.setStyleSheet(
            """
            QLabel#crash_title {
                color: #F5F8FC;
                font-size: 17px;
                font-weight: 600;
            }
            QLabel#crash_summary {
                color: #A3B0C0;
                font-size: 13px;
            }
            QFrame#crash_separator {
                color: #2B3544;
            }
            QToolButton#crash_details_toggle {
                background: transparent;
                border: none;
                color: #E4EBF4;
                font-weight: 600;
                padding: 3px 0;
                text-align: left;
            }
            QToolButton#crash_details_toggle:hover {
                color: #FFFFFF;
            }
            QPlainTextEdit#crash_report_details {
                background-color: #10151C;
                border: 1px solid #2B3544;
                border-radius: 5px;
                padding: 8px;
            }
            """
        )

    def retranslate_ui(self) -> None:
        """refresh all user-visible text."""

        self.setWindowTitle(self.tr("Starflight Error"))
        self._header_title_label.setText(self.tr("An application error occurred"))
        if self._fatal:
            self._summary_label.setText(
                self.tr(
                    "Starflight cannot continue safely and must be closed. Your project "
                    "files were not changed. You can copy the diagnostic report for "
                    "troubleshooting. The report is stored locally and is not sent "
                    "automatically."
                )
            )
        else:
            self._summary_label.setText(
                self.tr(
                    "The affected operation could not be completed. You can copy the "
                    "diagnostic report and continue using Starflight. The report is "
                    "stored locally and is not sent automatically."
                )
            )
        self._update_details_button_text()
        self.copy_button.setText(self.tr("Copy report"))
        self.open_logs_button.setText(self.tr("Open log folder"))
        self.close_button.setText(
            self.tr("Quit Starflight") if self._fatal else self.tr("Close message")
        )

    def _set_details_visible(self, visible: bool) -> None:
        self.report_edit.setVisible(visible)
        self.details_button.setArrowType(
            Qt.ArrowType.DownArrow if visible else Qt.ArrowType.RightArrow
        )
        self._update_details_button_text()
        if visible:
            self.resize(760, 560)
            self._fit_header_height()
        else:
            self.resize(620, self.height())
            self._fit_header_height()
            self.adjustSize()

    def _fit_header_height(self) -> None:
        self.ensurePolished()
        message_width = max(1, self.width() - 24 * 2 - 40 - 16)
        title_height = self._header_title_label.heightForWidth(message_width)
        summary_height = self._summary_label.heightForWidth(message_width)
        self._header_widget.setFixedHeight(max(40, title_height + 5 + summary_height))

    def _update_details_button_text(self) -> None:
        if self.details_button.isChecked():
            self.details_button.setText(
                QCoreApplication.translate(
                    "CrashReportDialog",
                    "Hide technical details",
                )
            )
        else:
            self.details_button.setText(
                QCoreApplication.translate(
                    "CrashReportDialog",
                    "Show technical details",
                )
            )

    def _copy_report(self) -> None:
        clipboard = QApplication.clipboard()
        clipboard.setText(self._report.text)
        self.copy_button.setText(QCoreApplication.translate("CrashReportDialog", "Report copied"))

    def _open_log_directory(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._log_directory)))


class RecoveredCrashReportDialog(CrashReportDialog):
    """show a recovered report without implying that the new session must exit."""

    def __init__(
        self,
        report: CrashReport,
        log_directory: Path,
        parent: QWidget | None = None,
        *,
        fatal: bool = True,
        pending_count: int = 1,
    ) -> None:
        self._pending_count = max(1, pending_count)
        super().__init__(report, log_directory, parent, fatal=fatal)

    def retranslate_ui(self) -> None:
        """refresh all user-visible text."""

        self.setWindowTitle(self.tr("Previous Starflight Crash"))
        self._header_title_label.setText(
            self.tr("Starflight closed unexpectedly during the previous session")
        )
        if self._pending_count > 1:
            self._summary_label.setText(
                self.tr(
                    "The most recent of {count} recovered diagnostic reports is shown. "
                    "You can copy it for troubleshooting and then continue using "
                    "Starflight. Additional reports remain in the log folder. The "
                    "report is stored locally and is not sent automatically."
                ).format(count=self._pending_count)
            )
        else:
            self._summary_label.setText(
                self.tr(
                    "A diagnostic report was recovered. You can copy it for "
                    "troubleshooting and then continue using Starflight. The report "
                    "is stored locally and is not sent automatically."
                )
            )
        self._update_details_button_text()
        self.copy_button.setText(QCoreApplication.translate("CrashReportDialog", "Copy report"))
        self.open_logs_button.setText(
            QCoreApplication.translate("CrashReportDialog", "Open log folder")
        )
        self.close_button.setText(QCoreApplication.translate("CrashReportDialog", "Close message"))


__all__ = ["CrashReportDialog", "RecoveredCrashReportDialog"]
