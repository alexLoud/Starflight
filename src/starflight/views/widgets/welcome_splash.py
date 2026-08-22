"""welcome splash overlay shown until the first preview frame loads."""

from __future__ import annotations

import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtWidgets import QLabel, QToolButton, QWidget

from starflight import __version__ as package_version
from starflight.app.constants import WELCOME_LOGO_FILE, package_dir

_AUTO_HIDE_MS = 20_000
_META_BAR_HEIGHT = 32
_META_RIGHT_MARGIN = 12
_CLOSE_MARGIN = 8


def resolve_app_version() -> str:
    """
    return the application version from the package module.

    """

    return package_version


def resolve_build_id() -> str:
    """
    return the short git commit hash when available.

    """

    repo_root = package_dir().parents[1]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"

    build_id = result.stdout.strip()
    if result.returncode != 0 or not build_id:
        return "unknown"
    return build_id


def welcome_logo_path() -> Path:
    """
    return the path to the welcome splash logo asset.

    """

    return package_dir() / "assets" / WELCOME_LOGO_FILE


class WelcomeSplash(QWidget):
    """centered original-size logo splash with meta and close overlay."""

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcome_splash")

        self._logo_pixmap = QPixmap(str(welcome_logo_path()))
        self._dismissed = False

        self._logo_frame = QWidget(self)
        self._logo_frame.setObjectName("welcome_splash_frame")

        self._logo_label = QLabel(self._logo_frame)
        self._logo_label.setObjectName("welcome_splash_logo")
        self._logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if not self._logo_pixmap.isNull():
            self._logo_label.setPixmap(self._logo_pixmap)
            self._logo_label.setFixedSize(self._logo_pixmap.size())
            self._logo_frame.setFixedSize(self._logo_pixmap.size())
            self._logo_label.move(0, 0)

        self._meta_bar = QWidget(self._logo_frame)
        self._meta_bar.setObjectName("welcome_splash_meta_bar")
        self._meta_bar.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._meta_label = QLabel(self._meta_bar)
        self._meta_label.setObjectName("welcome_splash_meta")
        self._meta_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self._meta_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._close_button = QToolButton(self._logo_frame)
        self._close_button.setObjectName("welcome_splash_close")
        self._close_button.setText("X")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.clicked.connect(self.dismiss)

        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setSingleShot(True)
        self._auto_hide_timer.setInterval(_AUTO_HIDE_MS)
        self._auto_hide_timer.timeout.connect(self.dismiss)

        self.retranslate_ui()
        self._auto_hide_timer.start()

    def dismiss(self) -> None:
        """hide the splash and stop the auto-hide timer."""

        if self._dismissed:
            return
        self._dismissed = True
        self._auto_hide_timer.stop()
        self.hide()
        self.dismissed.emit()

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self._close_button.setToolTip(self.tr("Close"))
        self._meta_label.setText(
            self.tr("Version {version} · Build {build}").format(
                version=resolve_app_version(),
                build=resolve_build_id(),
            )
        )
        self._meta_label.adjustSize()
        self._position_overlays()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._center_logo_frame()
        self._position_overlays()

    def _center_logo_frame(self) -> None:
        """
        center the original-size logo in the splash host.

        """

        frame_width = self._logo_frame.width()
        frame_height = self._logo_frame.height()
        self._logo_frame.move(
            max(0, (self.width() - frame_width) // 2),
            max(0, (self.height() - frame_height) // 2),
        )

    def _position_overlays(self) -> None:
        """
        place meta bar and close button on the logo.

        """

        frame_width = self._logo_frame.width()
        frame_height = self._logo_frame.height()

        self._meta_bar.setGeometry(
            0,
            frame_height - _META_BAR_HEIGHT,
            frame_width,
            _META_BAR_HEIGHT,
        )
        meta_width = max(self._meta_label.sizeHint().width(), 1)
        meta_height = self._meta_label.sizeHint().height()
        self._meta_label.setGeometry(
            frame_width - meta_width - _META_RIGHT_MARGIN,
            (_META_BAR_HEIGHT - meta_height) // 2,
            meta_width,
            meta_height,
        )
        self._meta_bar.raise_()

        close_size = self._close_button.sizeHint()
        self._close_button.setGeometry(
            frame_width - close_size.width() - _CLOSE_MARGIN,
            _CLOSE_MARGIN,
            close_size.width(),
            close_size.height(),
        )
        self._close_button.raise_()


__all__ = [
    "WelcomeSplash",
    "resolve_app_version",
    "resolve_build_id",
    "welcome_logo_path",
]
