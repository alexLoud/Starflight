"""Choose the destination for a project file."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget


class ProjectSaveDialog(QFileDialog):
    """non-native save dialog for project files."""

    def __init__(self, *, initial_target: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Save project"))
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        self.setFileMode(QFileDialog.FileMode.AnyFile)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.setNameFilter(self.tr("Starflight project (*.sf);;All files (*)"))
        self.setDefaultSuffix("sf")
        self.selectFile(str(initial_target))
        self.setLabelText(QFileDialog.DialogLabel.Accept, self.tr("Save"))
        self.setLabelText(QFileDialog.DialogLabel.Reject, self.tr("Cancel"))

    def selected_path(self) -> Path | None:
        """return selected save path."""

        paths = self.selectedFiles()
        if not paths:
            return None
        return Path(paths[0]).expanduser()


__all__ = ["ProjectSaveDialog"]
