"""full-window start screen with the existing splash artwork and project actions."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QDateTime, QLocale, QSize, Qt, QUrl, Signal
from PySide6.QtGui import QKeyEvent, QMouseEvent, QPixmap, QResizeEvent, QShowEvent
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from starflight.app.constants import WELCOME_LOGO_FILE, package_dir
from starflight.app.metadata import app_version
from starflight.services.update_service import (
    is_newer_version,
    latest_release_api_url,
    parse_latest_release,
)
from starflight.types.update import UpdateInfo
from starflight.views.icons import load_icon_asset

_META_BAR_HEIGHT = 32
_META_LEFT_MARGIN = 12
_META_RIGHT_MARGIN = 12
_MAX_RECENT = 5
_ACTION_ICON_SIZE = 26
_RECENT_ICON_SIZE = 18
_CONTENT_GAP = 28
_OUTER_MARGIN = 48
_ACTION_WIDTH = 264
_ACTION_HEIGHT = 96
_ACTION_GAP = 16
_ACTION_ROW_MAX_WIDTH = _ACTION_WIDTH * 2 + _ACTION_GAP
_RECENT_ROW_HEIGHT = 58
_RECENT_ROW_SPACING = 2
_RECENT_PANEL_MARGIN = 12
_MIN_LOGO_HEIGHT = 240


def welcome_logo_path() -> Path:
    """
    return the path to the welcome splash logo asset.

    """

    return package_dir() / "assets" / WELCOME_LOGO_FILE


class _WelcomeActionButton(QFrame):
    """compact start-screen action card with icon, title, and subtitle."""

    clicked = Signal()

    def __init__(self, icon_file: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcome_action_button")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedSize(_ACTION_WIDTH, _ACTION_HEIGHT)

        icon_label = QLabel(self)
        icon_label.setObjectName("welcome_action_icon")
        icon_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon_label.setFixedSize(44, 44)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon = load_icon_asset(icon_file)
        icon_label.setPixmap(icon.pixmap(_ACTION_ICON_SIZE, _ACTION_ICON_SIZE))

        self._title_label = QLabel(self)
        self._title_label.setObjectName("welcome_action_title")

        self._subtitle_label = QLabel(self)
        self._subtitle_label.setObjectName("welcome_action_subtitle")
        self._subtitle_label.setWordWrap(True)

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(3)
        text_column.addWidget(self._title_label)
        text_column.addWidget(self._subtitle_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(14)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_column, stretch=1)

        for child in (icon_label, self._title_label, self._subtitle_label):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.rect().contains(event.position().toPoint())
        ):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
            Qt.Key.Key_Space,
        ):
            self.clicked.emit()
            return
        super().keyPressEvent(event)

    def set_texts(self, title: str, subtitle: str) -> None:
        """
        update title and subtitle.

        title
            primary action label
        subtitle
            supporting description
        """

        self._title_label.setText(title)
        self._subtitle_label.setText(subtitle)


class _RecentProjectButton(QPushButton):
    """one recent project row on the start screen."""

    def __init__(self, path: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcome_recent_row")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAutoDefault(False)
        self.setFlat(True)
        self.setMinimumHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(str(path))
        self.path = path
        self._full_location = str(path.parent)

        icon_label = QLabel(self)
        icon_label.setObjectName("welcome_recent_icon")
        icon_label.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        icon_label.setFixedSize(36, 36)
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setPixmap(
            load_icon_asset("file-open.svg").pixmap(_RECENT_ICON_SIZE, _RECENT_ICON_SIZE),
        )

        self._name_label = QLabel(path.stem, self)
        self._name_label.setObjectName("welcome_recent_name")

        self._location_label = QLabel(self)
        self._location_label.setObjectName("welcome_recent_location")

        self._date_label = QLabel(self._modified_text(path), self)
        self._date_label.setObjectName("welcome_recent_date")
        self._date_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )

        text_column = QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(2)
        text_column.addWidget(self._name_label)
        text_column.addWidget(self._location_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 16, 10)
        layout.setSpacing(14)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(text_column, stretch=1)
        layout.addWidget(self._date_label, 0, Qt.AlignmentFlag.AlignVCenter)

        for child in (
            icon_label,
            self._name_label,
            self._location_label,
            self._date_label,
        ):
            child.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        metrics = self._location_label.fontMetrics()
        self._location_label.setText(
            metrics.elidedText(
                self._full_location,
                Qt.TextElideMode.ElideMiddle,
                max(self._location_label.width(), 40),
            ),
        )

    @staticmethod
    def _modified_text(path: Path) -> str:
        """
        format the project file modification date.

        path
            project file path
        """

        try:
            modified = QDateTime.fromSecsSinceEpoch(int(path.stat().st_mtime))
        except OSError:
            return ""
        return QLocale().toString(modified, QLocale.FormatType.ShortFormat)


class WelcomeSplash(QWidget):
    """existing splash artwork with version overlay, plus project actions."""

    new_project_requested = Signal()
    open_project_requested = Signal()
    recent_project_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("welcome_splash")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        self._logo_pixmap = QPixmap(str(welcome_logo_path()))
        self._update_info: UpdateInfo | None = None
        self._is_up_to_date = False
        self._recent_paths: list[Path] = []
        self._shown_recent_count = -1
        self._fitted_logical_size: tuple[int, int] | None = None
        self._fitting_logo = False

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

        self._new_button = _WelcomeActionButton("file-new.svg", self)
        self._open_button = _WelcomeActionButton("file-open.svg", self)
        self._new_button.clicked.connect(self.new_project_requested.emit)
        self._open_button.clicked.connect(self.open_project_requested.emit)

        self._actions_host = QWidget(self)
        self._actions_host.setObjectName("welcome_actions_host")
        actions = QHBoxLayout(self._actions_host)
        actions.setContentsMargins(0, 0, 0, 0)
        actions.setSpacing(_ACTION_GAP)
        actions.addWidget(self._new_button)
        actions.addWidget(self._open_button)

        self._recent_heading = QLabel(self)
        self._recent_heading.setObjectName("welcome_recent_heading")

        self._recent_list = QWidget(self)
        self._recent_list.setObjectName("welcome_recent_list")
        self._recent_list_layout = QVBoxLayout(self._recent_list)
        self._recent_list_layout.setContentsMargins(0, 0, 0, 0)
        self._recent_list_layout.setSpacing(2)

        self._recent_panel = QFrame(self)
        self._recent_panel.setObjectName("welcome_recent_panel")
        self._recent_panel.setFrameShape(QFrame.Shape.NoFrame)
        self._recent_panel.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        recent_layout = QVBoxLayout(self._recent_panel)
        recent_layout.setContentsMargins(6, 6, 6, 6)
        recent_layout.setSpacing(0)
        recent_layout.addWidget(self._recent_list)

        self._recent_section = QWidget(self)
        self._recent_section.setObjectName("welcome_recent_section")
        recent_section_layout = QVBoxLayout(self._recent_section)
        recent_section_layout.setContentsMargins(0, 0, 0, 0)
        recent_section_layout.setSpacing(10)
        recent_section_layout.addWidget(self._recent_heading)
        recent_section_layout.addWidget(self._recent_panel)
        self._recent_section.hide()

        root = QVBoxLayout(self)
        root.setContentsMargins(_OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN, _OUTER_MARGIN)
        root.setSpacing(_CONTENT_GAP)
        root.addStretch(1)
        root.addWidget(self._logo_frame, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self._actions_host, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addWidget(self._recent_section, 0, Qt.AlignmentFlag.AlignHCenter)
        root.addStretch(1)

        self._network_manager = QNetworkAccessManager(self)
        request = QNetworkRequest(QUrl(latest_release_api_url()))
        request.setRawHeader(b"Accept", b"application/vnd.github+json")
        request.setRawHeader(b"User-Agent", b"Starflight")
        request.setTransferTimeout(8_000)
        reply = self._network_manager.get(request)
        reply.finished.connect(lambda current_reply=reply: self._on_update_reply(current_reply))

        self.retranslate_ui()
        self._new_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def set_recent_projects(self, paths: list[Path]) -> None:
        """
        replace the recent-project list on the start screen.

        paths
            existing project files, most recent first
        """

        self._recent_paths = paths[:_MAX_RECENT]
        self._shown_recent_count = -1
        self._rebuild_recent_rows()

    def retranslate_ui(self) -> None:
        """refresh translatable texts."""

        self._new_button.set_texts(
            self.tr("New Project"),
            self.tr("Start a new fly-through"),
        )
        self._open_button.set_texts(
            self.tr("Load Project"),
            self.tr("Open a saved project"),
        )
        self._recent_heading.setText(self.tr("Recent Projects"))
        self._refresh_version_label()
        self._refresh_update_label()
        self._shown_recent_count = -1
        self._rebuild_recent_rows()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        self._rebuild_recent_rows()
        self._fit_logo()
        self._position_overlays()
        self._new_button.setFocus(Qt.FocusReason.OtherFocusReason)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._rebuild_recent_rows()
        self._fit_logo()
        self._position_overlays()

    def _fit_logo(self) -> None:
        """
        scale the splash artwork to the current window while keeping its aspect ratio.

        """

        if self._fitting_logo or self._logo_pixmap.isNull():
            return

        available = self._available_logo_size()
        native = self._native_logo_size()
        scale = min(
            available.width() / native.width(),
            available.height() / native.height(),
            1.0,
        )
        target_width = max(int(native.width() * scale), 1)
        target_height = max(int(native.height() * scale), 1)
        if self._fitted_logical_size == (target_width, target_height):
            return

        self._fitting_logo = True
        try:
            self._fitted_logical_size = (target_width, target_height)
            self._logo_label.setPixmap(self._scaled_logo_pixmap(target_width, target_height))
            self._logo_label.setFixedSize(target_width, target_height)
            self._logo_frame.setFixedSize(target_width, target_height)
            row_width = min(_ACTION_ROW_MAX_WIDTH, target_width)
            button_width = max((row_width - _ACTION_GAP) // 2, 200)
            self._new_button.setFixedSize(button_width, _ACTION_HEIGHT)
            self._open_button.setFixedSize(button_width, _ACTION_HEIGHT)
            actions_width = button_width * 2 + _ACTION_GAP
            self._actions_host.setFixedWidth(actions_width)
            self._recent_section.setFixedWidth(actions_width)
            self._logo_label.move(0, 0)
            self._position_overlays()
        finally:
            self._fitting_logo = False

    def _available_logo_size(self) -> QSize:
        """
        return the largest box the splash artwork may occupy.

        """

        if self.layout() is not None:
            margins = self.layout().contentsMargins()
            margin_x = margins.left() + margins.right()
            margin_y = margins.top() + margins.bottom()
            spacing = self.layout().spacing()
        else:
            margin_x = 2 * _OUTER_MARGIN
            margin_y = 2 * _OUTER_MARGIN
            spacing = _CONTENT_GAP
        gap_count = 4 if self._recent_section.isVisible() else 3

        reserved_height = margin_y + (gap_count * spacing) + _ACTION_HEIGHT
        if self._recent_section.isVisible():
            reserved_height += (
                self._recent_section.height() or self._recent_section.sizeHint().height()
            )

        return QSize(
            max(self.width() - margin_x, 240),
            max(self.height() - reserved_height, 160),
        )

    def _native_logo_size(self) -> QSize:
        """
        return the splash artwork size in logical pixels.

        """

        pixel_ratio = max(self._logo_pixmap.devicePixelRatio(), 1.0)
        return QSize(
            max(int(self._logo_pixmap.width() / pixel_ratio), 1),
            max(int(self._logo_pixmap.height() / pixel_ratio), 1),
        )

    def _scaled_logo_pixmap(self, width: int, height: int) -> QPixmap:
        """
        create a sharp pixmap for the requested logical size.

        width
            target width in logical pixels
        height
            target height in logical pixels
        """

        native = self._native_logo_size()
        if width >= native.width() and height >= native.height():
            return self._logo_pixmap

        pixel_ratio = max(self.devicePixelRatioF(), 1.0)
        scaled = self._logo_pixmap.scaled(
            max(int(width * pixel_ratio), 1),
            max(int(height * pixel_ratio), 1),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        scaled.setDevicePixelRatio(pixel_ratio)
        return scaled

    def _position_overlays(self) -> None:
        """place version and update text on the splash artwork."""

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

    def _rebuild_recent_rows(self) -> None:
        """rebuild recent project buttons that fit the current window."""

        visible_paths = self._recent_paths[: self._recent_capacity()]
        if len(visible_paths) == self._shown_recent_count and (
            bool(visible_paths) == self._recent_section.isVisible()
        ):
            return

        while self._recent_list_layout.count():
            item = self._recent_list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not visible_paths:
            self._shown_recent_count = 0
            self._recent_section.hide()
            self._fitted_logical_size = None
            self._fit_logo()
            return

        for path in visible_paths:
            row = _RecentProjectButton(path, self._recent_list)
            row.clicked.connect(
                lambda _checked=False, project_path=path: self.recent_project_requested.emit(
                    str(project_path),
                ),
            )
            self._recent_list_layout.addWidget(row)

        self._shown_recent_count = len(visible_paths)
        self._recent_section.show()
        self._fitted_logical_size = None
        self._fit_logo()

    def _recent_capacity(self) -> int:
        """
        return how many recent rows fit under a reasonably sized splash image.

        """

        stored = min(len(self._recent_paths), _MAX_RECENT)
        if stored == 0:
            return 0
        if self.width() < 200 or self.height() < 200:
            return stored

        if self.layout() is not None:
            margins = self.layout().contentsMargins()
            margin_x = margins.left() + margins.right()
            margin_y = margins.top() + margins.bottom()
            spacing = self.layout().spacing()
        else:
            margin_x = 2 * _OUTER_MARGIN
            margin_y = 2 * _OUTER_MARGIN
            spacing = _CONTENT_GAP

        native = self._native_logo_size()
        available_width = max(self.width() - margin_x, 240)
        available_height = max(self.height() - margin_y, 160)
        width_scale = min(available_width / native.width(), 1.0)
        scaled_native_height = int(native.height() * width_scale)
        min_logo_height = min(
            scaled_native_height,
            max(int(scaled_native_height * 0.45), _MIN_LOGO_HEIGHT),
        )

        leftover = available_height - (4 * spacing) - _ACTION_HEIGHT - min_logo_height
        leftover -= max(self._recent_heading.sizeHint().height(), 16) + 10
        leftover -= _RECENT_PANEL_MARGIN
        if leftover < _RECENT_ROW_HEIGHT:
            return 0

        count = 1 + (leftover - _RECENT_ROW_HEIGHT) // (
            _RECENT_ROW_HEIGHT + _RECENT_ROW_SPACING
        )
        return max(0, min(stored, count))

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


__all__ = [
    "WelcomeSplash",
    "welcome_logo_path",
]
