"""resolve the active monitor color profile for color-managed qt display."""

from __future__ import annotations

import ctypes
import ctypes.util
import sys
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, ClassVar

from PySide6.QtCore import QRect
from PySide6.QtGui import QColorSpace


class DisplayColorProfileError(RuntimeError):
    """raised when the active monitor profile cannot be resolved reliably."""


def display_color_space_for_geometry(screen_geometry: QRect | None) -> QColorSpace:
    """
    return the device color space for a screen.

    screen_geometry
        qt screen geometry used to pick the matching display, or none for the main display
    """

    if _running_on_macos():
        icc_profile = _macos_display_icc_profile(screen_geometry)
        if icc_profile is None:
            raise DisplayColorProfileError(
                "The active macOS display profile could not be read."
            )
        color_space = QColorSpace.fromIccProfile(icc_profile)
        if not color_space.isValid():
            raise DisplayColorProfileError(
                "The active macOS display profile is not supported by Qt."
            )
        return color_space
    return QColorSpace(QColorSpace.NamedColorSpace.SRgb)


def _running_on_macos() -> bool:
    """return true when running on macos."""

    return sys.platform == "darwin"


@dataclass(frozen=True, slots=True)
class _DisplayBounds:
    display_id: int
    x: float
    y: float
    width: float
    height: float


class _CGPoint(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("x", ctypes.c_double),
        ("y", ctypes.c_double),
    ]


class _CGSize(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("width", ctypes.c_double),
        ("height", ctypes.c_double),
    ]


class _CGRect(ctypes.Structure):
    _fields_: ClassVar[list[tuple[str, Any]]] = [
        ("origin", _CGPoint),
        ("size", _CGSize),
    ]


@dataclass(frozen=True, slots=True)
class _MacosFrameworks:
    core_graphics: ctypes.CDLL
    core_foundation: ctypes.CDLL


@lru_cache(maxsize=1)
def _macos_frameworks() -> _MacosFrameworks | None:
    """load coregraphics and corefoundation for display icc access."""

    core_graphics_library = ctypes.util.find_library("CoreGraphics")
    core_foundation_library = ctypes.util.find_library("CoreFoundation")
    if core_graphics_library is None or core_foundation_library is None:
        return None
    try:
        core_graphics = ctypes.CDLL(core_graphics_library)
        core_foundation = ctypes.CDLL(core_foundation_library)
    except OSError:
        return None

    core_graphics.CGMainDisplayID.argtypes = []
    core_graphics.CGMainDisplayID.restype = ctypes.c_uint32
    core_graphics.CGGetActiveDisplayList.argtypes = [
        ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32),
        ctypes.POINTER(ctypes.c_uint32),
    ]
    core_graphics.CGGetActiveDisplayList.restype = ctypes.c_int32
    core_graphics.CGDisplayBounds.argtypes = [ctypes.c_uint32]
    core_graphics.CGDisplayBounds.restype = _CGRect
    core_graphics.CGDisplayCopyColorSpace.argtypes = [ctypes.c_uint32]
    core_graphics.CGDisplayCopyColorSpace.restype = ctypes.c_void_p
    core_graphics.CGColorSpaceCopyICCData.argtypes = [ctypes.c_void_p]
    core_graphics.CGColorSpaceCopyICCData.restype = ctypes.c_void_p

    core_foundation.CFDataGetLength.argtypes = [ctypes.c_void_p]
    core_foundation.CFDataGetLength.restype = ctypes.c_long
    core_foundation.CFDataGetBytePtr.argtypes = [ctypes.c_void_p]
    core_foundation.CFDataGetBytePtr.restype = ctypes.POINTER(ctypes.c_ubyte)
    core_foundation.CFRelease.argtypes = [ctypes.c_void_p]
    core_foundation.CFRelease.restype = None
    return _MacosFrameworks(
        core_graphics=core_graphics,
        core_foundation=core_foundation,
    )


def _macos_display_icc_profile(screen_geometry: QRect | None) -> bytes | None:
    """
    read the icc profile bytes for the display matching the given geometry.

    screen_geometry
        qt screen geometry, or none to use the main display
    """

    frameworks = _macos_frameworks()
    if frameworks is None:
        return None
    display_id = _macos_display_id_for_geometry(
        frameworks.core_graphics,
        screen_geometry,
    )
    if display_id is None:
        return None

    color_space = frameworks.core_graphics.CGDisplayCopyColorSpace(display_id)
    if not color_space:
        return None
    try:
        icc_data = frameworks.core_graphics.CGColorSpaceCopyICCData(color_space)
        if not icc_data:
            return None
        try:
            length = int(frameworks.core_foundation.CFDataGetLength(icc_data))
            byte_pointer = frameworks.core_foundation.CFDataGetBytePtr(icc_data)
            if length <= 0 or not byte_pointer:
                return None
            return ctypes.string_at(byte_pointer, length)
        finally:
            frameworks.core_foundation.CFRelease(icc_data)
    finally:
        frameworks.core_foundation.CFRelease(color_space)


def _macos_display_id_for_geometry(
    core_graphics: ctypes.CDLL,
    screen_geometry: QRect | None,
) -> int | None:
    """
    pick the active display id that best matches the screen geometry.

    core_graphics
        loaded coregraphics library
    screen_geometry
        qt screen geometry, or none for the main display
    """

    displays = _active_macos_displays(core_graphics)
    if not displays:
        return None
    if screen_geometry is None:
        return int(core_graphics.CGMainDisplayID())

    target = _DisplayBounds(
        display_id=0,
        x=float(screen_geometry.x()),
        y=float(screen_geometry.y()),
        width=float(screen_geometry.width()),
        height=float(screen_geometry.height()),
    )
    best_display = max(displays, key=lambda display: _intersection_area(display, target))
    if _intersection_area(best_display, target) <= 0.0:
        return None
    return best_display.display_id


def _active_macos_displays(core_graphics: ctypes.CDLL) -> tuple[_DisplayBounds, ...]:
    """
    list bounds for all active macos displays.

    core_graphics
        loaded coregraphics library
    """

    maximum_display_count = 32
    display_ids = (ctypes.c_uint32 * maximum_display_count)()
    display_count = ctypes.c_uint32()
    error = core_graphics.CGGetActiveDisplayList(
        maximum_display_count,
        display_ids,
        ctypes.byref(display_count),
    )
    if error != 0:
        return ()

    displays: list[_DisplayBounds] = []
    for display_id in display_ids[: display_count.value]:
        bounds = core_graphics.CGDisplayBounds(display_id)
        displays.append(
            _DisplayBounds(
                display_id=int(display_id),
                x=float(bounds.origin.x),
                y=float(bounds.origin.y),
                width=float(bounds.size.width),
                height=float(bounds.size.height),
            )
        )
    return tuple(displays)


def _intersection_area(first: _DisplayBounds, second: _DisplayBounds) -> float:
    """
    return the intersection area of two display bounds.

    first
        first display bounds
    second
        second display bounds
    """

    width = max(
        0.0,
        min(first.x + first.width, second.x + second.width) - max(first.x, second.x),
    )
    height = max(
        0.0,
        min(first.y + first.height, second.y + second.height) - max(first.y, second.y),
    )
    return width * height


__all__ = ["DisplayColorProfileError", "display_color_space_for_geometry"]
