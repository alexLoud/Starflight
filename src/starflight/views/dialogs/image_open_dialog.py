"""Choose a source image with the native Qt file dialog."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QFileDialog, QWidget

IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.tif *.tiff);;All files (*)"


class ImageOpenDialog:
    """non-native open dialog for source images."""

    @staticmethod
    def tr(text: str) -> str:
        """Translate a message owned by the image open dialog."""

        return QCoreApplication.translate("ImageOpenDialog", text)

    @staticmethod
    def run(parent: QWidget) -> Path | None:
        """
        show image open dialog and return selected path.

        parent
            parent widget
        """

        start_dir = str(Path.cwd())
        file_path, _selected_filter = QFileDialog.getOpenFileName(
            parent,
            ImageOpenDialog.tr("Load image"),
            start_dir,
            ImageOpenDialog.tr("Images (*.jpg *.jpeg *.png *.tif *.tiff);;All files (*)"),
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not file_path:
            return None
        return Path(file_path).expanduser()


__all__ = ["IMAGE_FILTER", "ImageOpenDialog"]
