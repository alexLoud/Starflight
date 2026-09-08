"""tests for linux qt runtime library bundling during packaging."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from starflight.build import (
    LINUX_QT_RUNTIME_LIBS,
    LINUX_QT_RUNTIME_LIBS_REQUIRED,
    _find_system_library,
    _linux_qt_runtime_binaries,
)


class LinuxQtRuntimeLibTests(unittest.TestCase):
    """verify soname discovery and required-lib enforcement."""

    def test_required_libs_are_listed_for_bundling(self) -> None:
        for soname in LINUX_QT_RUNTIME_LIBS_REQUIRED:
            self.assertIn(soname, LINUX_QT_RUNTIME_LIBS)

    def test_find_system_library_returns_soname_path(self) -> None:
        with patch(
            "starflight.build._linux_lib_search_dirs",
            return_value=(Path("/usr/lib/x86_64-linux-gnu"),),
        ):
            with patch.object(Path, "is_file", return_value=True):
                found = _find_system_library("libxcb-cursor.so.0")
        self.assertEqual(found, Path("/usr/lib/x86_64-linux-gnu/libxcb-cursor.so.0"))

    def test_runtime_binaries_fail_when_required_lib_missing(self) -> None:
        def fake_find(soname: str) -> Path | None:
            if soname in LINUX_QT_RUNTIME_LIBS_REQUIRED:
                return None
            return Path("/usr/lib") / soname

        with patch("starflight.build._find_system_library", side_effect=fake_find):
            with self.assertRaises(RuntimeError) as raised:
                _linux_qt_runtime_binaries()
        message = str(raised.exception)
        self.assertIn("libEGL.so.1", message)
        self.assertIn("libxcb-cursor.so.0", message)

    def test_runtime_binaries_collect_found_libs(self) -> None:
        def fake_find(soname: str) -> Path | None:
            return Path("/usr/lib/x86_64-linux-gnu") / soname

        with patch("starflight.build._find_system_library", side_effect=fake_find):
            binaries = _linux_qt_runtime_binaries()

        self.assertEqual(len(binaries), len(LINUX_QT_RUNTIME_LIBS))
        sources = [src.name for src, dest in binaries]
        destinations = {dest for _src, dest in binaries}
        self.assertIn("libEGL.so.1", sources)
        self.assertIn("libxcb-cursor.so.0", sources)
        self.assertEqual(destinations, {"."})


if __name__ == "__main__":
    unittest.main()
