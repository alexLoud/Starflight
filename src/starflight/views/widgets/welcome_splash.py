"""welcome splash overlay shown until the first preview frame loads."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QPixmap, QResizeEvent
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import QLabel, QToolButton, QWidget

from starflight.app.constants import WELCOME_LOGO_FILE, package_dir
from starflight.app.metadata import app_version
from starflight.services.update_service import (
    is_newer_version,
    latest_release_api_url,
    parse_latest_release,
)
from starflight.types.update import UpdateInfo

_META_BAR_HEIGHT = 32
_META_LEFT_MARGIN = 12
_META_RIGHT_MARGIN = 12
_CLOSE_MARGIN = 8


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
        self._update_info: UpdateInfo | None = None
        self._is_up_to_date = False

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

        self._meta_label = QLabel(self._meta_bar)
        self._meta_label.setObjectName("welcome_splash_meta")
        self._meta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._meta_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        self._update_label = QLabel(self._meta_bar)
        self._update_label.setObjectName("welcome_splash_update")
        self._update_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self._update_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self._update_label.setTextFormat(Qt.TextFormat.RichText)
        self._update_label.setOpenExternalLinks(True)
        self._update_label.hide()

        self._close_button = QToolButton(self._logo_frame)
        self._close_button.setObjectName("welcome_splash_close")
        self._close_button.setText("X")
        self._close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_button.clicked.connect(self.dismiss)

        self._network_manager = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(latest_release_api_url()))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", b"Starflight")
        request.setTransferTimeout(8_000)
        reply = self._network_manager.get(request)
        reply.finished.connect(lambda current_reply=reply: self._on_update_reply(current_reply))

        self.retranslate_ui()

    def dismiss(self) -> None:
        """hide the splash."""

        if self._dismissed:
            return
        self._dismissed = True
        self.hide()
        self.dismissed.emit()

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self._close_button.setToolTip(self.tr("Close"))
        self._refresh_version_label()
        self._refresh_update_label()

    def _on_update_available(self, update: UpdateInfo) -> None:
        """
        show an update hint when a newer release was found.

        update
            remote release information
        """

        self._update_info = update
        self._is_up_to_date = False
        self._refresh_version_label()
        self._refresh_update_label()

    def _on_update_reply(self, reply: QNetworkReply) -> None:
        """consume the asynchronous latest-release response."""

        try:
            if reply.error() != QNetworkReply.NetworkError.NoError:
                return
            latest = parse_latest_release(bytes(reply.readAll()))
            if latest is None:
                return
            if is_newer_version(latest.version, app_version()):
                self._on_update_available(latest)
            else:
                self._on_up_to_date()
        finally:
            reply.deleteLater()

    def _on_up_to_date(self) -> None:
        """mark the installed version as current after a successful release check."""

        self._update_info = None
        self._is_up_to_date = True
        self._refresh_version_label()
        self._refresh_update_label()

    def _refresh_version_label(self) -> None:
        """refresh the version text on the right side of the splash."""

        version = app_version()
        if self._is_up_to_date:
            text = self.tr("Version {version} (current)").format(version=version)
        else:
            text = self.tr("Version {version}").format(version=version)
        self._meta_label.setText(text)
        self._position_overlays()

    def _refresh_update_label(self) -> None:
        """refresh the optional update hint text."""

        if self._update_info is None:
            self._update_label.hide()
            self._position_overlays()
            return

        self._update_label.setText(
            self.tr(
                '<a href="{url}">Update available: Version {version}</a>',
            ).format(
                url=self._update_info.release_url,
                version=self._update_info.version,
            ),
        )
        self._update_label.show()
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

        meta_height = max(self._meta_label.sizeHint().height(), 1)
        meta_y = (_META_BAR_HEIGHT - meta_height) // 2
        meta_left = _META_LEFT_MARGIN

        if self._update_info is not None and self._update_label.isVisible():
            update_width = max(self._update_label.sizeHint().width(), 1)
            update_height = max(self._update_label.sizeHint().height(), 1)
            self._update_label.setGeometry(
                _META_LEFT_MARGIN,
                meta_y,
                update_width,
                update_height,
            )
            self._update_label.raise_()
            meta_left = _META_LEFT_MARGIN + update_width + 8

        meta_width = max(frame_width - meta_left - _META_RIGHT_MARGIN, 1)
        self._meta_label.setGeometry(
            meta_left,
            meta_y,
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
    "welcome_logo_path",
]
