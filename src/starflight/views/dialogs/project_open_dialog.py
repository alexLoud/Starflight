"""Choose an existing project file."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QFileDialog, QWidget

PROJECT_FILTER = "Starflight project (*.sf);;All files (*)"


class ProjectOpenDialog:
    """non-native open dialog for project files."""

    @staticmethod
    def tr(text: str) -> str:
        """Translate a message owned by the project open dialog."""

        return QCoreApplication.translate("ProjectOpenDialog", text)

    @staticmethod
    def run(*, initial_dir: str, parent: QWidget) -> Path | None:
        """
        show project open dialog and return selected path.

        initial_dir
            starting directory
        parent
            parent widget
        """

        file_path, _selected_filter = QFileDialog.getOpenFileName(
            parent,
            ProjectOpenDialog.tr("Open project"),
            initial_dir,
            ProjectOpenDialog.tr("Starflight project (*.sf);;All files (*)"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not file_path:
            return None
        return Path(file_path).expanduser()


__all__ = ["PROJECT_FILTER", "ProjectOpenDialog"]
