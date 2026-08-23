"""Update and compile the Qt translation files."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N_DIR = ROOT / "src" / "starflight" / "i18n"
SOURCE_TS = I18N_DIR / "starflight_de.ts"


def main() -> int:
    """run pylupdate6 and lrelease for project translations."""

    environment_bin = Path(sys.executable).parent
    pylupdate = environment_bin / "pyside6-lupdate"
    lrelease = environment_bin / "pyside6-lrelease"
    if not pylupdate.exists() or not lrelease.exists():
        print("pyside6 lupdate/lrelease not found in the active environment", file=sys.stderr)
        return 1

    sources = list((ROOT / "src" / "starflight").rglob("*.py"))
    # Both tools are fixed executables from the project environment.
    subprocess.run(
        [
            str(pylupdate),
            *map(str, sources),
            "-no-obsolete",
            "-ts",
            str(SOURCE_TS),
        ],
        check=True,
    )
    subprocess.run(
        [str(lrelease), str(SOURCE_TS), "-qm", str(I18N_DIR / "starflight_de.qm")],
        check=True,
    )
    print("translations updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
