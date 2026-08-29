"""Repository checks for language and file level documentation rules."""

from __future__ import annotations

import ast
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON_FILES = [
    ROOT / "main.py",
    *(ROOT / "scripts").rglob("*.py"),
    *(ROOT / "src" / "starflight").rglob("*.py"),
    *(ROOT / "tests").glob("test_*.py"),
]
GERMAN_CHARACTERS = re.compile(r"[\u00c4\u00d6\u00dc\u00df\u00e4\u00f6\u00fc]")


class SourceQualityTests(unittest.TestCase):
    def test_python_modules_have_file_documentation(self) -> None:
        missing = [
            str(path.relative_to(ROOT))
            for path in PYTHON_FILES
            if ast.get_docstring(ast.parse(path.read_text(encoding="utf-8"))) is None
        ]
        self.assertEqual(missing, [])

    def test_python_source_contains_no_german_text(self) -> None:
        matches = [
            str(path.relative_to(ROOT))
            for path in PYTHON_FILES
            if GERMAN_CHARACTERS.search(path.read_text(encoding="utf-8"))
        ]
        self.assertEqual(matches, [])

    def test_old_infrastructure_package_is_removed(self) -> None:
        infra_directory = ROOT / "src" / "starflight" / "infra"
        self.assertFalse(any(infra_directory.glob("*.py")))

    def test_german_catalog_has_no_missing_or_stale_entries(self) -> None:
        catalog = ET.parse(ROOT / "src" / "starflight" / "i18n" / "starflight_de.ts")
        invalid: list[str] = []
        for context in catalog.getroot().findall("context"):
            context_name = context.findtext("name", default="")
            for message in context.findall("message"):
                translation = message.find("translation")
                translation_type = None if translation is None else translation.get("type")
                if (
                    translation is None
                    or translation_type in {"unfinished", "vanished", "obsolete"}
                    or not (translation.text or "").strip()
                ):
                    invalid.append(f"{context_name}: {message.findtext('source', default='')}")
        self.assertEqual(invalid, [])


if __name__ == "__main__":
    unittest.main()
