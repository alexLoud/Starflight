"""shared helpers for qt-backed unit tests."""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

from PySide6.QtCore import QSettings
from PySide6.QtNetwork import QNetworkReply

from starflight.app.constants import SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED


def suppress_welcome_tour(settings: QSettings) -> None:
    """prevent modal welcome dialogs from blocking headless test runs."""

    settings.setValue(SETTINGS_KEY_WELCOME_TOUR_SUPPRESSED, True)


def welcome_splash_network_patch() -> patch:
    """avoid blocking github release checks while constructing main windows in tests."""

    mock_reply = MagicMock()
    mock_reply.error.return_value = QNetworkReply.NetworkError.ConnectionRefusedError
    mock_reply.readAll.return_value = MagicMock(return_value=b"")
    mock_reply.deleteLater = Mock()
    mock_reply.finished.connect = Mock(side_effect=lambda slot: slot(mock_reply))
    mock_manager = MagicMock()
    mock_manager.get.return_value = mock_reply
    return patch(
        "starflight.views.widgets.welcome_splash.QNetworkAccessManager",
        return_value=mock_manager,
    )
