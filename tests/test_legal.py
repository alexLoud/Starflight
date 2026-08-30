"""Tests for bundled license notice loading."""

from __future__ import annotations

import unittest

from starflight.app.legal import (
    combined_legal_text,
    license_texts_dir,
    starflight_license_path,
    third_party_notices_path,
)


class LegalNoticesTests(unittest.TestCase):
    """verify license files resolve and combine for the about dialog."""

    def test_starflight_license_exists(self) -> None:
        path = starflight_license_path()
        self.assertTrue(path.is_file(), msg=f"missing license: {path}")
        text = path.read_text(encoding="utf-8")
        self.assertIn("PolyForm Noncommercial License 1.0.0", text)

    def test_third_party_notices_exist(self) -> None:
        path = third_party_notices_path()
        self.assertTrue(path.is_file(), msg=f"missing notices: {path}")
        text = path.read_text(encoding="utf-8")
        self.assertIn("PySide6", text)
        self.assertIn("FFmpeg", text)
        self.assertIn("BtbN", text)
        self.assertNotIn("imageio-ffmpeg vendor", text)

    def test_full_license_texts_present(self) -> None:
        licenses = license_texts_dir()
        self.assertTrue(licenses.is_dir())
        required = {
            "LGPL-3.0.txt",
            "GPL-3.0.txt",
            "GPL-2.0.txt",
            "Apache-2.0.txt",
            "BSD-3-Clause.txt",
            "BSD-2-Clause.txt",
            "PSF-2.0.txt",
            "PyInstaller-bootloader-exception.txt",
        }
        names = {path.name for path in licenses.glob("*.txt")}
        self.assertTrue(required.issubset(names), msg=f"missing: {required - names}")

    def test_combined_legal_text_includes_sections(self) -> None:
        text = combined_legal_text()
        self.assertIn("STARFLIGHT LICENSE", text)
        self.assertIn("THIRD-PARTY NOTICES", text)
        self.assertIn("LGPL-3.0.txt", text)
        self.assertIn("PolyForm Noncommercial License 1.0.0", text)


if __name__ == "__main__":
    unittest.main()
