"""Tests for display color-profile resolution and preview conversion."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

import numpy as np

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QRect
from PySide6.QtGui import QColorSpace, QImage
from PySide6.QtWidgets import QApplication

from starflight.platform import display_color_profile
from starflight.utils.image import (
    configure_display_color_space_resolver,
    numpy_rgb_to_qimage,
)


class DisplayColorProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self) -> None:
        configure_display_color_space_resolver(None)

    def test_macos_display_profile_is_returned_without_substitution(self) -> None:
        expected = QColorSpace(
            QColorSpace.Primaries.SRgb,
            QColorSpace.TransferFunction.Gamma,
            2.2,
        )
        icc_profile = bytes(expected.iccProfile())

        with (
            patch.object(display_color_profile, "_running_on_macos", return_value=True),
            patch.object(
                display_color_profile,
                "_macos_display_icc_profile",
                return_value=icc_profile,
            ),
        ):
            resolved = display_color_profile.display_color_space_for_geometry(None)

        self.assertTrue(resolved.isValid())
        self.assertEqual(bytes(resolved.iccProfile()), icc_profile)

    def test_missing_macos_display_profile_is_an_error(self) -> None:
        with (
            patch.object(display_color_profile, "_running_on_macos", return_value=True),
            patch.object(
                display_color_profile,
                "_macos_display_icc_profile",
                return_value=None,
            ),
        ):
            with self.assertRaises(display_color_profile.DisplayColorProfileError):
                display_color_profile.display_color_space_for_geometry(None)

    def test_non_macos_display_contract_is_srgb(self) -> None:
        with patch.object(display_color_profile, "_running_on_macos", return_value=False):
            resolved = display_color_profile.display_color_space_for_geometry(None)

        self.assertEqual(resolved, QColorSpace(QColorSpace.NamedColorSpace.SRgb))

    def test_preview_rgb_converts_srgb_to_monitor_profile(self) -> None:
        pixels = np.array([[[20, 80, 180]]], dtype=np.uint8)
        monitor_color_space = QColorSpace(
            QColorSpace.Primaries.SRgb,
            QColorSpace.TransferFunction.Gamma,
            1.8,
        )
        resolved_geometries: list[QRect | None] = []

        def resolve_monitor(screen_geometry: QRect | None) -> QColorSpace:
            resolved_geometries.append(screen_geometry)
            return monitor_color_space

        configure_display_color_space_resolver(resolve_monitor)
        image = numpy_rgb_to_qimage(pixels)

        self.assertEqual(image.format(), QImage.Format.Format_RGB32)
        self.assertEqual(image.colorSpace(), monitor_color_space)
        self.assertEqual(len(resolved_geometries), 1)
        transformed = image.pixelColor(0, 0)
        self.assertNotEqual(
            (transformed.red(), transformed.green(), transformed.blue()),
            (20, 80, 180),
        )

    def test_preview_rgb_keeps_srgb_when_resolver_is_unbound(self) -> None:
        pixels = np.array([[[10, 20, 30]]], dtype=np.uint8)

        image = numpy_rgb_to_qimage(pixels)

        self.assertEqual(image.format(), QImage.Format.Format_RGB888)
        self.assertEqual(image.colorSpace(), QColorSpace(QColorSpace.NamedColorSpace.SRgb))
        color = image.pixelColor(0, 0)
        self.assertEqual((color.red(), color.green(), color.blue()), (10, 20, 30))


if __name__ == "__main__":
    unittest.main()
