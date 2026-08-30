"""Show application version, author, and project links."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from starflight.app.constants import APP_AUTHOR, APP_DESCRIPTION, APP_DISPLAY_NAME, APP_GITHUB_URL
from starflight.app.metadata import app_icon_path, app_version
from starflight.views.dialogs.licenses_dialog import LicensesDialog


class AboutDialog(QDialog):
    """classic about dialog for starflight."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("about_dialog")
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 16)
        layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(16)

        self._icon_label = QLabel(self)
        self._icon_label.setObjectName("about_dialog_icon")
        icon_pixmap = QPixmap(app_icon_path())
        if not icon_pixmap.isNull():
            self._icon_label.setPixmap(
                icon_pixmap.scaled(
                    64,
                    64,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            )
        self._icon_label.setFixedSize(64, 64)
        header.addWidget(self._icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_column = QVBoxLayout()
        text_column.setSpacing(6)

        self._title_label = QLabel(self)
        self._title_label.setObjectName("about_dialog_title")
        text_column.addWidget(self._title_label)

        self._version_label = QLabel(self)
        self._version_label.setObjectName("about_dialog_version")
        text_column.addWidget(self._version_label)

        self._description_label = QLabel(self)
        self._description_label.setObjectName("about_dialog_description")
        self._description_label.setWordWrap(True)
        text_column.addWidget(self._description_label)

        self._author_label = QLabel(self)
        self._author_label.setObjectName("about_dialog_author")
        text_column.addWidget(self._author_label)

        self._license_label = QLabel(self)
        self._license_label.setObjectName("about_dialog_author")
        self._license_label.setWordWrap(True)
        text_column.addWidget(self._license_label)

        self._github_label = QLabel(self)
        self._github_label.setObjectName("about_dialog_link")
        self._github_label.setOpenExternalLinks(True)
        self._github_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard,
        )
        text_column.addWidget(self._github_label)

        self._licenses_link = QLabel(self)
        self._licenses_link.setObjectName("about_dialog_link")
        self._licenses_link.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard,
        )
        self._licenses_link.linkActivated.connect(self._open_licenses)
        text_column.addWidget(self._licenses_link)

        header.addLayout(text_column, stretch=1)
        layout.addLayout(header)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.button_box.accepted.connect(self.accept)
        layout.addWidget(self.button_box)

        self.resize(440, 300)
        self.retranslate_ui()

    def _open_licenses(self, _link: str = "") -> None:
        """
        open the bundled open-source licenses dialog.

        _link
            unused link target from qlabel
        """

        dialog = LicensesDialog(self)
        dialog.exec()

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self.setWindowTitle(self.tr("About Starflight"))
        self._title_label.setText(f"<b>{APP_DISPLAY_NAME}</b>")
        self._version_label.setText(
            self.tr("Version {version}").format(version=app_version()),
        )
        self._description_label.setText(self.tr(APP_DESCRIPTION))
        self._author_label.setText(
            self.tr("Author: {author}").format(author=APP_AUTHOR),
        )
        self._license_label.setText(
            self.tr("License: PolyForm Noncommercial 1.0.0"),
        )
        self._github_label.setText(
            self.tr('<a href="{url}">GitHub</a>').format(url=APP_GITHUB_URL),
        )
        self._licenses_link.setText(
            self.tr('<a href="licenses">Open-Source Licenses</a>'),
        )


__all__ = ["AboutDialog"]
