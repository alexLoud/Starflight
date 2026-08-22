"""Read image metadata and convert image data used by Qt and OpenCV."""

from __future__ import annotations

import struct
from collections.abc import Callable
from pathlib import Path
from typing import cast

import cv2
import numpy as np
from PySide6.QtCore import QCoreApplication, QRect
from PySide6.QtGui import QColorSpace, QGuiApplication, QImage, QScreen, QWindow

DisplayColorSpaceResolver = Callable[[QRect | None], QColorSpace]
_display_color_space_resolver: DisplayColorSpaceResolver | None = None


def configure_display_color_space_resolver(
    resolver: DisplayColorSpaceResolver | None,
) -> None:
    """
    bind the platform display-profile resolver at the composition root.

    resolver
        callable that maps screen geometry to a qcolorspace, or none to disable
    """

    global _display_color_space_resolver
    _display_color_space_resolver = resolver


def _image_load_error(path: str) -> ValueError:
    """Build the translated image loading error used by existing callers."""

    message = QCoreApplication.translate(
        "ImageError",
        "Image could not be loaded: {path}",
    ).format(path=path)
    return ValueError(message)


def read_image_dimensions(path: str) -> tuple[int, int]:
    """
    read image width and height without decoding full pixel data when possible.

    path
        image file path
    """

    suffix = Path(path).suffix.lower()
    if suffix == ".png":
        return _read_png_dimensions(path)
    if suffix in {".jpg", ".jpeg"}:
        return _read_jpeg_dimensions(path)

    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise _image_load_error(path)
    source_h, source_w = image.shape[:2]
    return source_w, source_h


def _read_png_dimensions(path: str) -> tuple[int, int]:
    with Path(path).open("rb") as handle:
        header = handle.read(24)
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise _image_load_error(path)
    width, height = struct.unpack(">II", header[16:24])
    return int(width), int(height)


def _read_jpeg_dimensions(path: str) -> tuple[int, int]:
    data = Path(path).read_bytes()
    if len(data) < 4 or data[0:2] != b"\xff\xd8":
        raise _image_load_error(path)

    index = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue

        marker = data[index + 1]
        if marker in sof_markers:
            height = (data[index + 5] << 8) | data[index + 6]
            width = (data[index + 7] << 8) | data[index + 8]
            return int(width), int(height)

        if marker in {0xD8, 0x01} or 0xD0 <= marker <= 0xD7:
            index += 2
            continue

        segment_length = (data[index + 2] << 8) | data[index + 3]
        if segment_length < 2:
            break
        index += 2 + segment_length

    raise _image_load_error(path)


def load_image_bgr(path: str) -> np.ndarray:
    """
    load an image file as a bgr numpy array.

    path
        image file path
    """

    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None:
        raise _image_load_error(path)
    return image


def cover_resize_bgr(image: np.ndarray, width: int, height: int) -> np.ndarray:
    """Resize an image to cover the target size and crop it around the center."""

    source_h, source_w = image.shape[:2]
    scale = max(width / source_w, height / source_h)
    resized_w = max(1, round(source_w * scale))
    resized_h = max(1, round(source_h * scale))
    resized = cv2.resize(image, (resized_w, resized_h), interpolation=cv2.INTER_LANCZOS4)

    start_x = max(0, (resized_w - width) // 2)
    start_y = max(0, (resized_h - height) // 2)
    return resized[start_y : start_y + height, start_x : start_x + width].copy()


def bgr_to_rgb(image: np.ndarray) -> np.ndarray:
    """
    convert bgr image to rgb.

    image
        bgr numpy array
    """

    return cv2.cvtColor(image, cv2.COLOR_BGR2RGB)


def numpy_rgb_to_qimage(image: np.ndarray, *, screen: QScreen | None = None) -> QImage:
    """
    convert rgb uint8 numpy array to a color-managed qimage for display.

    image
        rgb image array with shape (h, w, 3), treated as encoded srgb
    screen
        optional screen used to resolve the monitor profile
    """

    if image.dtype != np.uint8:
        image = np.clip(image, 0, 255).astype(np.uint8)

    height, width, channels = image.shape
    if channels != 3:
        raise ValueError("Expected an RGB image with 3 channels.")

    rgb = np.ascontiguousarray(image)
    bytes_per_line = 3 * width
    qimage = QImage(rgb.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)
    qimage = qimage.copy()
    qimage.setColorSpace(QColorSpace(QColorSpace.NamedColorSpace.SRgb))
    if _display_color_space_resolver is None:
        return qimage

    target_color_space = _display_color_space_resolver(_screen_geometry(screen))
    if not target_color_space.isValid():
        raise RuntimeError("The active display profile is not a valid RGB color space.")
    transformed = qimage.convertedToColorSpace(
        target_color_space,
        QImage.Format.Format_RGB32,
    )
    if transformed.isNull():
        raise RuntimeError("Conversion to the active display profile failed.")
    return transformed


def _screen_geometry(screen: QScreen | None) -> QRect | None:
    """
    resolve qt screen geometry for display-profile lookup.

    screen
        preferred screen, or none to fall back to the focused or primary screen
    """

    if screen is not None:
        return QRect(screen.geometry())
    active_window = cast(QWindow | None, QGuiApplication.focusWindow())
    if active_window is not None:
        return QRect(active_window.screen().geometry())
    primary_screen = QGuiApplication.primaryScreen()
    return None if primary_screen is None else QRect(primary_screen.geometry())


def compute_preview_size(
    width: int,
    height: int,
    available_width: int,
    available_height: int,
) -> tuple[int, int]:
    """
    Compute preview dimensions that fit the available space.

    width
        target render width
    height
        target render height
    available_width
        available preview widget width
    available_height
        available preview widget height
    """

    target_w = max(2, width)
    target_h = max(2, height)
    aspect = target_w / target_h

    max_w = max(240, min(available_width, 960))
    max_h = max(180, min(available_height, 820))

    render_w = max_w
    render_h = max(2, round(render_w / aspect))
    if render_h > max_h:
        render_h = max_h
        render_w = max(2, round(render_h * aspect))

    if render_w % 2 != 0:
        render_w += 1
    if render_h % 2 != 0:
        render_h += 1

    return render_w, render_h
