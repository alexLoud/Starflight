"""Choose the destination for an exported video."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QWidget

VIDEO_FILTER = "MP4 Video (*.mp4)"


class VideoSaveDialog(QFileDialog):
    """non-native save dialog for mp4 export."""

    def __init__(self, *, initial_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Save video"))
        self.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        self.setFileMode(QFileDialog.FileMode.AnyFile)
        self.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        self.setNameFilter(self.tr("MP4 Video (*.mp4)"))
        self.setDefaultSuffix("mp4")
        self.selectFile(initial_path)
        self.setLabelText(QFileDialog.DialogLabel.Accept, self.tr("Save"))
        self.setLabelText(QFileDialog.DialogLabel.Reject, self.tr("Cancel"))

    def selected_path(self) -> Path | None:
        """return selected output path."""

        paths = self.selectedFiles()
        if not paths:
            return None
        path = Path(paths[0]).expanduser()
        if path.suffix.lower() != ".mp4":
            path = path.with_suffix(".mp4")
        return path


__all__ = ["VIDEO_FILTER", "VideoSaveDialog"]
