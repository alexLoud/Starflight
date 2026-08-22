"""Validate a project and open its video export dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QWidget

from starflight.i18n import tr_validation
from starflight.services.error_service import ErrorService
from starflight.types.settings import Project
from starflight.utils.validation import validate_project_for_export
from starflight.views.dialogs.export_dialog import ExportDialog


class ExportController:
    """handles export dialog flow."""

    @staticmethod
    def tr(text: str) -> str:
        """Translate a message owned by the export controller."""

        return QCoreApplication.translate("ExportController", text)

    def __init__(self, error_service: ErrorService) -> None:
        self._error_service = error_service

    def open_export_dialog(
        self,
        project: Project,
        project_path: Path | None,
        parent: QWidget,
    ) -> None:
        """
        open export dialog when project is valid.

        project
            project to export
        project_path
            optional project path
        parent
            parent widget
        """

        validation = validate_project_for_export(project, project_path)
        if not validation.ok:
            self._error_service.show_user_warning(
                self.tr("Export unavailable"),
                tr_validation(validation.message),
                parent,
            )
            return

        dialog = ExportDialog(project, project_path, parent)
        dialog.exec()


__all__ = ["ExportController"]
