# Starflight

<img src="src/starflight/assets/icons/app-icon.png" width="88" alt="Starflight">

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/UI-PySide6-41CD52?logo=qt&logoColor=white)](https://doc.qt.io/qtforpython/)
[![FFmpeg](https://img.shields.io/badge/export-FFmpeg%20libx264-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org/)

**Starflight** turns a starless deep-sky image into a short fly-through video
with a rendered starfield. Cross-platform desktop app for macOS, Windows, and Linux.

## Download

Pre-built apps for **macOS (Intel + Apple Silicon), Windows, and Linux** are published on
[GitHub Releases](https://github.com/alexLoud/Starflight/releases/latest).

## Install (from source)

```bash
poetry install
poetry run starflight
```

Also:

```bash
poetry run python main.py
poetry run python -m starflight
```

## Dependencies

- [Python](https://www.python.org/) 3.12 (`>=3.12,<3.13`)
- [Poetry](https://python-poetry.org/)
- [PySide6](https://doc.qt.io/qtforpython/) — UI
- [NumPy](https://numpy.org/) / [OpenCV](https://opencv.org/) — image pipeline
- [FFmpeg](https://ffmpeg.org/) — export (`libx264`); bundled in packaged builds

For development (`poetry run`), FFmpeg must be on `PATH`. On macOS:

```bash
brew install ffmpeg
```

## How to build

PyInstaller packaging. Native builds only — no cross-compilation.

```bash
poetry run build              # current host
poetry run build macos-intel
poetry run build macos-arm
poetry run build windows
poetry run build linux
```

Outputs in `dist/`:

- `Starflight-<version>-macos-intel.dmg`
- `Starflight-<version>-macos-arm.dmg`
- `Starflight-<version>-windows.zip`
- `Starflight-<version>-linux.tar.gz`

Packaged builds include a pinned, redistributable GPL FFmpeg binary with
libx264 (no `--enable-nonfree`). See `src/starflight/assets/legal/ffmpeg-bundle.json`.

## Translation

German (default) and English.

```bash
poetry run python scripts/update_i18n.py
```

Updates `src/starflight/i18n/starflight_de.ts` from the Python sources and
compiles `starflight_de.qm`.

## Development

```bash
poetry run ruff check src
poetry run python -m unittest discover -s tests
```
