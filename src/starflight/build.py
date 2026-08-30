"""Package Starflight for desktop distribution."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import plistlib
import shutil
import struct
import subprocess
import sys
import tarfile
import tomllib
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
ICON_DIR = SRC / "starflight" / "assets" / "icons"
ICON_PNG = ICON_DIR / "app-icon.png"
ICON_MACOS_PNG = ICON_DIR / "app-icon-macos.png"
ICON_WINDOWS_PNG = ICON_DIR / "app-icon-windows.png"
ICON_LINUX_PNG = ICON_DIR / "app-icon-linux.png"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
APP_NAME = "Starflight"
BUNDLE_IDENTIFIER = "local.starflight"
TARGETS = ("macos-intel", "macos-arm", "windows", "linux")

MACOS_ICON_SIZES = (
    (16, "icon_16x16.png"),
    (32, "icon_16x16@2x.png"),
    (32, "icon_32x32.png"),
    (64, "icon_32x32@2x.png"),
    (128, "icon_128x128.png"),
    (256, "icon_128x128@2x.png"),
    (256, "icon_256x256.png"),
    (512, "icon_256x256@2x.png"),
    (512, "icon_512x512.png"),
    (1024, "icon_512x512@2x.png"),
)
WINDOWS_ICON_SIZES = (16, 32, 48, 64, 128, 256)
LINUX_ICON_SIZE = 256
FFMPEG_BUNDLE_MANIFEST = SRC / "starflight" / "assets" / "legal" / "ffmpeg-bundle.json"
FFMPEG_DOWNLOAD_UA = "Starflight-packaging/1.0 (+https://github.com/alexLoud/Starflight)"


def main(argv: list[str] | None = None) -> int:
    """
    build a desktop package for one target platform.

    argv
        optional cli arguments, defaults to sys.argv[1:]
    """

    parser = argparse.ArgumentParser(
        prog="build",
        description="Build a desktop package for macOS, Windows, or Linux.",
    )
    parser.add_argument(
        "target",
        nargs="?",
        choices=TARGETS,
        help="build target (default: current platform)",
    )
    args = parser.parse_args(argv)
    target = args.target or _current_target()
    _require_native(target)
    icon_source = _icon_source_for_target(target)
    if not icon_source.exists():
        print(f"app icon missing: {icon_source}", file=sys.stderr)
        return 1

    version = _read_version()
    _sync_package_version(version)
    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    work_dir = BUILD_DIR / "pyinstaller" / target
    dist_dir = work_dir / "dist"
    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    print(f"rendering app icon for {target}...", flush=True)
    icon_path = _render_icon(target, icon_source, work_dir)

    print(f"building {target}...", flush=True)
    _run_pyinstaller(target, icon_path, work_dir, dist_dir)
    artifact = _package_artifact(target, version, dist_dir)
    _cleanup_intermediates(artifact)
    print(f"created {artifact}", flush=True)
    return 0


def _current_target() -> str:
    """return the build target for this machine."""

    system = sys.platform
    machine = platform.machine().lower()
    if system == "darwin":
        if machine in {"arm64", "aarch64"}:
            return "macos-arm"
        return "macos-intel"
    if system == "win32":
        return "windows"
    if system.startswith("linux"):
        return "linux"
    raise RuntimeError(f"unsupported platform: {system}")


def _require_native(target: str) -> None:
    """
    exit if this machine cannot build the requested target.

    target
        requested build target
    """

    current = _current_target()
    if target != current:
        print(
            f"cannot build {target} on this machine ({current}). "
            "run this command on the matching os/arch; pyinstaller cannot cross-compile.",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _read_version() -> str:
    """read the project version from pyproject.toml."""

    with (ROOT / "pyproject.toml").open("rb") as handle:
        return str(tomllib.load(handle)["project"]["version"])


def _sync_package_version(version: str) -> None:
    """
    mirror pyproject.toml version into the package module for frozen builds.

    version
        project version string
    """

    init_path = SRC / "starflight" / "__init__.py"
    lines = init_path.read_text(encoding="utf-8").splitlines(keepends=True)
    updated: list[str] = []
    replaced = False
    for line in lines:
        if line.startswith('__version__ = "'):
            updated.append(f'__version__ = "{version}"\n')
            replaced = True
        else:
            updated.append(line)
    if not replaced:
        raise RuntimeError(f"could not update __version__ in {init_path}")
    init_path.write_text("".join(updated), encoding="utf-8")


def _icon_source_for_target(target: str) -> Path:
    """
    return the platform-specific master icon png.

    target
        build target
    """

    if target.startswith("macos-"):
        return ICON_MACOS_PNG
    if target == "windows":
        return ICON_WINDOWS_PNG
    if target == "linux":
        return ICON_LINUX_PNG
    return ICON_PNG


def _render_icon(target: str, icon_source: Path, work_dir: Path) -> Path:
    """
    resize the png app icon into the native format for a target.

    target
        build target
    icon_source
        platform master png
    work_dir
        working directory for generated icon files
    """

    import cv2

    source = cv2.imread(str(icon_source), cv2.IMREAD_UNCHANGED)
    if source is None:
        raise RuntimeError(f"could not read app icon: {icon_source}")

    if target.startswith("macos-"):
        iconset_dir = work_dir / "AppIcon.iconset"
        iconset_dir.mkdir(parents=True)
        for size, filename in MACOS_ICON_SIZES:
            _write_icon_png(source, size, iconset_dir / filename)
        icns_path = work_dir / "AppIcon.icns"
        subprocess.run(
            ["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)],
            check=True,
        )
        return icns_path

    if target == "windows":
        png_by_size: dict[int, bytes] = {}
        for size in WINDOWS_ICON_SIZES:
            png_path = work_dir / f"icon_{size}.png"
            _write_icon_png(source, size, png_path)
            png_by_size[size] = png_path.read_bytes()
        ico_path = work_dir / "AppIcon.ico"
        _write_ico(png_by_size, ico_path)
        return ico_path

    png_path = work_dir / "AppIcon.png"
    _write_icon_png(source, LINUX_ICON_SIZE, png_path)
    return png_path


def _write_icon_png(source: object, size: int, dest: Path) -> None:
    """
    resize the app icon png to a square png file.

    source
        loaded bgr or bgra icon array
    size
        output size in pixels
    dest
        destination png path
    """

    import cv2
    import numpy as np

    if not isinstance(source, np.ndarray):
        raise TypeError("source must be a numpy image array")
    interpolation = cv2.INTER_AREA if size < source.shape[0] else cv2.INTER_LANCZOS4
    resized = cv2.resize(source, (size, size), interpolation=interpolation)
    if not cv2.imwrite(str(dest), resized):
        raise RuntimeError(f"could not write icon png: {dest}")


def _write_ico(png_by_size: dict[int, bytes], dest: Path) -> None:
    """
    write a png-based windows ico file.

    png_by_size
        png bytes keyed by pixel size
    dest
        destination ico path
    """

    sizes = sorted(png_by_size)
    count = len(sizes)
    offset = 6 + 16 * count
    header = struct.pack("<HHH", 0, 1, count)
    directory = bytearray()
    images = bytearray()
    for size in sizes:
        data = png_by_size[size]
        width = 0 if size >= 256 else size
        directory.extend(struct.pack("<BBBBHHII", width, width, 0, 0, 1, 32, len(data), offset))
        images.extend(data)
        offset += len(data)
    dest.write_bytes(header + directory + images)


def _ffmpeg_bundle_key(target: str) -> str:
    """
    return the ffmpeg-bundle.json key for a packaging target.

    target
        packaging target name
    """

    if target != "linux":
        return target
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "linux-arm64"
    if machine in {"x86_64", "amd64"}:
        return "linux-amd64"
    raise RuntimeError(f"unsupported linux architecture for ffmpeg bundle: {machine}")


def _assert_ffmpeg_redistributable(version_text: str) -> None:
    """
    reject ffmpeg builds that are not redistributable or lack libx264.

    version_text
        output of ffmpeg -version
    """

    lowered = version_text.lower()
    if "--enable-nonfree" in lowered:
        raise RuntimeError(
            "refusing to bundle FFmpeg: this binary was built with --enable-nonfree "
            "and cannot be redistributed"
        )
    if "--enable-libx264" not in lowered and "libx264" not in lowered:
        raise RuntimeError("refusing to bundle FFmpeg: libx264 is required for export")
    if "--enable-gpl" not in lowered:
        raise RuntimeError("refusing to bundle FFmpeg: expected a GPL build with libx264")


def _copy_vendor_ffmpeg(dest: Path, target: str) -> Path:
    """
    download a pinned redistributable ffmpeg build and copy it to dest.

    dest
        destination path (ffmpeg or ffmpeg.exe)
    target
        packaging target name
    """

    spec = _ffmpeg_bundle_spec(target)
    archive_dir = dest.parent / "download"
    archive_dir.mkdir(parents=True, exist_ok=True)
    url = str(spec["url"])
    archive_path = archive_dir / Path(url).name
    _download_verified_file(url, str(spec["sha256"]), archive_path)

    extract_dir = dest.parent / "extract"
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True)
    _extract_archive(archive_path, extract_dir, str(spec["format"]))
    binary = _find_ffmpeg_binary(extract_dir, dest.name)
    _assert_ffmpeg_redistributable(_ffmpeg_version_output(binary))

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, dest)
    mode = dest.stat().st_mode
    dest.chmod(mode | 0o111)
    return dest


def _ffmpeg_bundle_spec(target: str) -> dict[str, object]:
    """
    return the pinned ffmpeg download spec for a target.

    target
        packaging target name
    """

    key = _ffmpeg_bundle_key(target)
    manifest = json.loads(FFMPEG_BUNDLE_MANIFEST.read_text(encoding="utf-8"))
    spec = manifest["targets"].get(key)
    if not isinstance(spec, dict):
        raise RuntimeError(f"no ffmpeg bundle spec for {key}")
    return spec


def _download_verified_file(url: str, expected_sha256: str, dest: Path) -> None:
    """
    download url to dest and verify the sha-256 digest.

    url
        download url
    expected_sha256
        expected lowercase hex digest
    dest
        destination file
    """

    if dest.is_file() and hashlib.sha256(dest.read_bytes()).hexdigest() == expected_sha256:
        return

    dest.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": FFMPEG_DOWNLOAD_UA})
    print(f"downloading ffmpeg from {url}...", flush=True)
    with urllib.request.urlopen(request) as response, dest.open("wb") as handle:
        shutil.copyfileobj(response, handle)

    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    if digest != expected_sha256:
        dest.unlink(missing_ok=True)
        raise RuntimeError(
            f"ffmpeg download hash mismatch for {url}: got {digest}, expected {expected_sha256}"
        )


def _extract_archive(archive_path: Path, dest_dir: Path, archive_format: str) -> None:
    """
    extract a zip or tar.xz archive into dest_dir.

    archive_path
        downloaded archive
    dest_dir
        extraction directory
    archive_format
        zip or tar.xz
    """

    if archive_format == "zip":
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(dest_dir)
        return
    if archive_format == "tar.xz":
        with tarfile.open(archive_path, "r:xz") as archive:
            archive.extractall(dest_dir, filter="data")
        return
    raise RuntimeError(f"unsupported ffmpeg archive format: {archive_format}")


def _find_ffmpeg_binary(root: Path, expected_name: str) -> Path:
    """
    return the ffmpeg executable inside an extracted archive.

    root
        extracted archive directory
    expected_name
        ffmpeg or ffmpeg.exe
    """

    matches = [
        path for path in root.rglob(expected_name) if path.is_file() and path.name == expected_name
    ]
    if not matches:
        raise RuntimeError(f"extracted ffmpeg archive does not contain {expected_name}")
    matches.sort(key=lambda path: len(path.parts))
    return matches[0]


def _ffmpeg_version_output(binary: Path) -> str:
    """
    return ffmpeg -version output for license checks.

    binary
        ffmpeg executable
    """

    completed = subprocess.run(
        [str(binary), "-hide_banner", "-version"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = (completed.stdout or "") + (completed.stderr or "")
    if completed.returncode != 0 and not output:
        raise RuntimeError(f"could not run bundled ffmpeg: {binary}")
    return output


def _run_pyinstaller(target: str, icon_path: Path, work_dir: Path, dist_dir: Path) -> None:
    """
    run pyinstaller for one target.

    target
        build target
    icon_path
        native icon file
    work_dir
        pyinstaller work directory
    dist_dir
        pyinstaller output directory
    """

    import PyInstaller.__main__

    data_sep = os.pathsep
    ffmpeg_name = "ffmpeg.exe" if target == "windows" else "ffmpeg"
    ffmpeg_src = work_dir / "ffmpeg_bundle" / ffmpeg_name
    print("bundling ffmpeg...", flush=True)
    _copy_vendor_ffmpeg(ffmpeg_src, target)

    args = [
        str(ROOT / "main.py"),
        f"--name={APP_NAME}",
        "--windowed",
        "--noconfirm",
        "--clean",
        f"--icon={icon_path}",
        f"--paths={SRC}",
        f"--specpath={work_dir}",
        f"--workpath={work_dir / 'work'}",
        f"--distpath={dist_dir}",
        f"--add-data={SRC / 'starflight' / 'assets'}{data_sep}starflight/assets",
        f"--add-data={SRC / 'starflight' / 'i18n'}{data_sep}starflight/i18n",
        f"--add-data={ROOT / 'LICENSE'}{data_sep}starflight/assets/legal",
        f"--add-binary={ffmpeg_src}{data_sep}starflight/bin",
        "--hidden-import=PySide6.QtSvg",
        "--hidden-import=PySide6.QtXml",
        "--collect-submodules=starflight",
        "--exclude-module=starflight.build",
    ]
    if target.startswith("macos-"):
        args.append(f"--osx-bundle-identifier={BUNDLE_IDENTIFIER}")
        args.append(f"--target-arch={'arm64' if target == 'macos-arm' else 'x86_64'}")
    PyInstaller.__main__.run(args)


def _package_artifact(target: str, version: str, dist_dir: Path) -> Path:
    """
    wrap pyinstaller output into the distributable archive.

    target
        build target
    version
        project version
    dist_dir
        pyinstaller output directory
    """

    if target.startswith("macos-"):
        app_path = dist_dir / f"{APP_NAME}.app"
        if not app_path.exists():
            raise RuntimeError(f"app bundle was not created: {app_path}")
        _set_bundle_version(app_path, version)
        dmg_path = DIST_DIR / f"Starflight-{version}-{target}.dmg"
        _create_dmg(app_path, dmg_path)
        return dmg_path

    payload = dist_dir / APP_NAME
    if not payload.exists():
        raise RuntimeError(f"application folder was not created: {payload}")
    if target == "windows":
        zip_path = DIST_DIR / f"Starflight-{version}-{target}.zip"
        _zip_directory(payload, zip_path)
        return zip_path
    tar_path = DIST_DIR / f"Starflight-{version}-{target}.tar.gz"
    _tar_directory(payload, tar_path)
    return tar_path


def _set_bundle_version(app_path: Path, version: str) -> None:
    """
    write the project version into the macos app bundle.

    app_path
        built .app bundle
    version
        project version string
    """

    plist_path = app_path / "Contents" / "Info.plist"
    with plist_path.open("rb") as handle:
        data = plistlib.load(handle)
    data["CFBundleShortVersionString"] = version
    data["CFBundleVersion"] = version
    with plist_path.open("wb") as handle:
        plistlib.dump(data, handle)
    subprocess.run(
        ["codesign", "--force", "--deep", "--sign", "-", str(app_path)],
        check=True,
    )


def _create_dmg(app_path: Path, dmg_path: Path) -> None:
    """
    wrap the app bundle in a compressed disk image.

    app_path
        built .app bundle
    dmg_path
        destination dmg path
    """

    staging = app_path.parent / "dmg_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    shutil.copytree(app_path, staging / app_path.name, symlinks=True)
    (staging / "Applications").symlink_to("/Applications")
    if dmg_path.exists():
        dmg_path.unlink()
    subprocess.run(
        [
            "hdiutil",
            "create",
            "-volname",
            APP_NAME,
            "-srcfolder",
            str(staging),
            "-ov",
            "-format",
            "UDZO",
            str(dmg_path),
        ],
        check=True,
    )


def _zip_directory(source: Path, dest: Path) -> None:
    """
    zip an application folder.

    source
        folder to archive
    dest
        destination zip path
    """

    if dest.exists():
        dest.unlink()
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in source.rglob("*"):
            if path.is_file():
                archive.write(path, Path(source.name) / path.relative_to(source))


def _is_final_artifact(path: Path) -> bool:
    """
    return whether a dist file is a finished package.

    path
        candidate file in dist
    """

    name = path.name
    if not path.is_file() or not name.startswith("Starflight-"):
        return False
    return name.endswith(".dmg") or name.endswith(".zip") or name.endswith(".tar.gz")


def _cleanup_intermediates(artifact: Path) -> None:
    """
    remove build leftovers so dist only keeps finished packages.

    artifact
        package created by this build
    """

    if BUILD_DIR.exists():
        shutil.rmtree(BUILD_DIR)
    if not DIST_DIR.exists():
        return
    for path in DIST_DIR.iterdir():
        if path.resolve() == artifact.resolve() or _is_final_artifact(path):
            continue
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()


def _tar_directory(source: Path, dest: Path) -> None:
    """
    create a gzip compressed tar archive of an application folder.

    source
        folder to archive
    dest
        destination tar.gz path
    """

    if dest.exists():
        dest.unlink()
    with tarfile.open(dest, "w:gz") as archive:
        archive.add(source, arcname=source.name)


if __name__ == "__main__":
    raise SystemExit(main())
