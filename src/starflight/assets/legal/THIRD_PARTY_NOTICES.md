# Third-Party Notices

This document lists third-party software included with Starflight source
releases and packaged desktop builds. Full license texts are in the
`licenses/` directory next to this file and are also shown in the app under
**Help → About Starflight → Open-Source Licenses**.

Starflight itself is licensed under the **GNU General Public License v3**
(or later; see `LICENSE` at the repository root; packaged builds include the
same file under `assets/legal/LICENSE`).

---

## Written offer for source code (LGPL / GPL components)

Packaged Starflight builds dynamically ship LGPL-licensed Qt libraries
(via PySide6) and a separate GPL-licensed FFmpeg executable used only as an
external process for video export.

For at least three years after you receive a packaged Starflight build, the
copyright holders of Starflight will, on request, provide a copy of the
corresponding source code for the LGPL/GPL components distributed with that
build, on a durable physical medium at cost or by equivalent electronic means.

Contact: see the author listed in **Help → About Starflight**, or open an
issue on the Starflight GitHub repository.

You may also obtain upstream sources from:

- Qt / PySide6: https://code.qt.io/ and https://pyside.org/
- FFmpeg: see the pinned source URLs in `ffmpeg-bundle.json` in this folder

---

## Python

- **Component:** CPython runtime (when using a packaged build that embeds Python)
- **License:** Python Software Foundation License Version 2 (`licenses/PSF-2.0.txt`)
- **Homepage:** https://www.python.org/

---

## PySide6 / Qt

- **Component:** PySide6 and the Qt libraries shipped with it
- **License:** LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only  
  Starflight uses the LGPL-3.0 option for Qt/PySide6 (`licenses/LGPL-3.0.txt`,
  which incorporates terms from `licenses/GPL-3.0.txt`).
- **Homepage:** https://pyside.org/ · https://www.qt.io/
- **Notes:** Packaged builds include Qt shared libraries collected by
  PyInstaller. You may replace those LGPL libraries with compatible modified
  versions in accordance with the LGPL.

---

## NumPy

- **Component:** NumPy
- **License:** BSD-3-Clause (and additional permissive notices for bundled
  components; see the NumPy distribution). Primary terms:
  `licenses/BSD-3-Clause.txt`
- **Homepage:** https://numpy.org/

---

## OpenCV (opencv-python-headless)

- **Component:** OpenCV Python wheels (headless)
- **License:** Apache License 2.0 (`licenses/Apache-2.0.txt`)
- **Homepage:** https://opencv.org/ · https://github.com/opencv/opencv-python

---

## FFmpeg (bundled executable)

- **Component:** `ffmpeg` / `ffmpeg.exe` bundled into packaged builds under
  `starflight/bin/`
- **License:** GNU GPL (FFmpeg is built with `--enable-gpl` and libx264).
  See `licenses/GPL-2.0.txt` and `licenses/GPL-3.0.txt`. Packaged binaries are
  **not** `--enable-nonfree` builds (those cannot be redistributed).
- **Homepage:** https://ffmpeg.org/
- **Pinned builds:** `ffmpeg-bundle.json` in this folder (checksums, download
  URLs, and corresponding source). macOS uses Martin Riedl 9.0.1 GPL static
  builds; Windows and Linux use BtbN FFmpeg-Builds `gpl` (not `nonfree`)
  from tag `autobuild-2026-08-30-13-12`.
- **Notes:** Starflight invokes FFmpeg as a separate process for H.264 export.
  The FFmpeg binary remains under GPL. Redistributors must keep these notices
  and provide corresponding source (or honor the written offer above).

---

## PyInstaller bootloader

- **Component:** PyInstaller bootloader embedded in packaged executables
- **License:** GPL-2.0-or-later with the PyInstaller bootloader exception  
  Full text: `licenses/PyInstaller-bootloader-exception.txt`
- **Homepage:** https://pyinstaller.org/
- **Notes:** The bootloader exception allows bundling applications under terms
  other than the GPL, provided the exception conditions are met. This notice is
  included to satisfy that requirement.

---

## Additional permissive components

Some dependencies may include small amounts of code under MIT, 0BSD, Zlib,
CC0, or similar permissive terms (for example within NumPy). Where those terms
apply, the corresponding SPDX texts are provided under `licenses/`
(including `licenses/MIT.txt`).
