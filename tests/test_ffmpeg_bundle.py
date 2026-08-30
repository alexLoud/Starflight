"""Tests for redistributable FFmpeg bundle selection."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from starflight.app.constants import package_dir
from starflight.build import _assert_ffmpeg_redistributable, _ffmpeg_bundle_key


class FfmpegBundleTests(unittest.TestCase):
    """verify pinned ffmpeg specs and license checks."""

    def test_manifest_covers_packaging_targets(self) -> None:
        path = package_dir() / "assets" / "legal" / "ffmpeg-bundle.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        targets = manifest["targets"]
        required = {
            "macos-arm",
            "macos-intel",
            "windows",
            "linux-amd64",
            "linux-arm64",
        }
        self.assertEqual(required, set(targets))
        for spec in targets.values():
            self.assertEqual(len(spec["sha256"]), 64)
            self.assertTrue(spec["url"].startswith("https://"))
            self.assertTrue(spec["sources"])

    def test_linux_bundle_key_uses_machine(self) -> None:
        with patch("starflight.build.platform.machine", return_value="arm64"):
            self.assertEqual(_ffmpeg_bundle_key("linux"), "linux-arm64")
        with patch("starflight.build.platform.machine", return_value="x86_64"):
            self.assertEqual(_ffmpeg_bundle_key("linux"), "linux-amd64")

    def test_rejects_nonfree_ffmpeg(self) -> None:
        with self.assertRaises(RuntimeError):
            _assert_ffmpeg_redistributable(
                "configuration: --enable-gpl --enable-nonfree --enable-libx264"
            )

    def test_rejects_ffmpeg_without_x264(self) -> None:
        with self.assertRaises(RuntimeError):
            _assert_ffmpeg_redistributable("configuration: --enable-gpl --enable-libvpx")

    def test_accepts_gpl_libx264_build(self) -> None:
        _assert_ffmpeg_redistributable(
            "configuration: --enable-gpl --enable-version3 --enable-libx264"
        )


if __name__ == "__main__":
    unittest.main()
