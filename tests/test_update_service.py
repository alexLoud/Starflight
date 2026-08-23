"""Tests for github release update checks."""

from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from starflight.services.update_service import (
    check_for_update,
    fetch_latest_release,
    is_newer_version,
    normalize_version,
    release_page_url,
)
from starflight.types.update import UpdateInfo


class UpdateVersionTests(unittest.TestCase):
    def test_normalize_version_strips_release_prefix(self) -> None:
        self.assertEqual(normalize_version("v1.0.2"), (1, 0, 2))

    def test_is_newer_version_compares_numeric_parts(self) -> None:
        self.assertTrue(is_newer_version("1.0.2", "1.0.1"))
        self.assertFalse(is_newer_version("1.0.1", "1.0.1"))
        self.assertFalse(is_newer_version("1.0.0", "1.0.1"))


class UpdateServiceTests(unittest.TestCase):
    def test_release_page_url_uses_configured_repo(self) -> None:
        self.assertEqual(
            release_page_url("1.0.2"),
            "https://github.com/alexLoud/Starflight/releases/tag/v1.0.2",
        )

    def test_fetch_latest_release_parses_github_response(self) -> None:
        payload = {
            "tag_name": "v1.0.2",
            "html_url": "https://github.com/alexLoud/Starflight/releases/tag/v1.0.2",
        }
        response = io.BytesIO(json.dumps(payload).encode("utf-8"))

        with patch(
            "starflight.services.update_service.urllib.request.urlopen",
            return_value=response,
        ):
            update = fetch_latest_release()

        self.assertEqual(
            update,
            UpdateInfo(
                version="1.0.2",
                release_url="https://github.com/alexLoud/Starflight/releases/tag/v1.0.2",
            ),
        )

    def test_check_for_update_returns_none_when_current_is_latest(self) -> None:
        update = UpdateInfo(
            version="1.0.1",
            release_url="https://github.com/alexLoud/Starflight/releases/tag/v1.0.1",
        )

        with patch("starflight.services.update_service.fetch_latest_release", return_value=update):
            self.assertIsNone(check_for_update("1.0.1"))

    def test_check_for_update_returns_info_for_newer_release(self) -> None:
        update = UpdateInfo(
            version="1.0.2",
            release_url="https://github.com/alexLoud/Starflight/releases/tag/v1.0.2",
        )

        with patch("starflight.services.update_service.fetch_latest_release", return_value=update):
            self.assertEqual(check_for_update("1.0.1"), update)


if __name__ == "__main__":
    unittest.main()
