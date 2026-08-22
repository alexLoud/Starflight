"""Crop and scale logovorlage.png into platform app icons without altering pixels."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "logovorlage.png"
ICONS_DIR = ROOT / "src" / "starflight" / "assets" / "icons"
DEFAULT_SIZE = 1024
# only used to find the crop box; artwork pixels stay fully opaque.
BACKGROUND_COLOR_DISTANCE = 12.0
# pull in past the template frame and the dark padding outside the squircle.
CROP_INSET_RATIO = 0.09
# measured from Calculator/Notes/Safari icns: opaque body is 214/256 of the canvas.
MACOS_BODY_RATIO = 214 / 256
DESKTOP_BODY_RATIO = 1.0
# macOS-style continuous corner: ~22% of the icon body edge.
CORNER_RADIUS_RATIO = 0.22


def main(argv: list[str] | None = None) -> int:
    """
    generate platform app icons by cropping and scaling the logo template.

    argv
        optional cli arguments, defaults to sys.argv[1:]
    """

    parser = argparse.ArgumentParser(
        description="Crop logovorlage.png into Starflight app icons.",
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=DEFAULT_SOURCE,
        help=f"logo template path (default: {DEFAULT_SOURCE})",
    )
    parser.add_argument(
        "--size",
        type=int,
        default=DEFAULT_SIZE,
        help=f"output edge length in pixels (default: {DEFAULT_SIZE})",
    )
    args = parser.parse_args(argv)

    if args.size < 16:
        print("size must be at least 16", file=sys.stderr)
        return 1
    if not args.source.is_file():
        print(f"source missing: {args.source}", file=sys.stderr)
        return 1

    # crop only — keep every original pixel opaque.
    artwork = crop_logo(args.source)
    ICONS_DIR.mkdir(parents=True, exist_ok=True)

    outputs = {
        "app-icon.png": place_on_canvas(artwork, args.size, DESKTOP_BODY_RATIO),
        "app-icon-macos.png": place_on_canvas(artwork, args.size, MACOS_BODY_RATIO),
        "app-icon-windows.png": place_on_canvas(artwork, args.size, DESKTOP_BODY_RATIO),
        "app-icon-linux.png": place_on_canvas(artwork, args.size, DESKTOP_BODY_RATIO),
    }
    for name, image in outputs.items():
        dest = ICONS_DIR / name
        if not cv2.imwrite(str(dest), image):
            print(f"could not write icon: {dest}", file=sys.stderr)
            return 1
        print(f"wrote {dest}")
    return 0


def crop_logo(source: Path) -> np.ndarray:
    """
    crop the logo to its content box; all cropped pixels stay opaque.

    source
        path to logovorlage.png
    """

    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"could not read image: {source}")

    corner = image[0, 0].astype(np.float32)
    distance = np.linalg.norm(image.astype(np.float32) - corner, axis=2)
    content = distance >= BACKGROUND_COLOR_DISTANCE
    ys, xs = np.where(content)
    if len(xs) == 0:
        raise RuntimeError("no icon content detected in logo template")

    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    width = x1 - x0 + 1
    height = y1 - y0 + 1
    inset = max(1, round(min(width, height) * CROP_INSET_RATIO))
    x0 += inset
    y0 += inset
    x1 -= inset
    y1 -= inset
    if x1 <= x0 or y1 <= y0:
        raise RuntimeError("crop inset removed the entire logo")

    crop = image[y0 : y1 + 1, x0 : x1 + 1]
    # force opaque bgra — never punch holes into the artwork.
    rgba = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = 255
    return rgba


def place_on_canvas(artwork: np.ndarray, size: int, body_ratio: float) -> np.ndarray:
    """
    scale the opaque crop onto a square canvas.

    artwork
        opaque bgra crop of the original logo
    size
        output canvas edge length
    body_ratio
        fraction of the canvas used by the icon body
    """

    body = max(1, min(size, round(size * body_ratio)))
    scaled = _resize_rgba(artwork, body)
    # geometric round only — does not change rgb inside the shape.
    rounded = _apply_rounded_corners(scaled, CORNER_RADIUS_RATIO)

    if body_ratio >= 1.0 and rounded.shape[0] == size and rounded.shape[1] == size:
        return rounded

    canvas = np.zeros((size, size, 4), dtype=np.uint8)
    sh, sw = rounded.shape[:2]
    left = (size - sw) // 2
    top = (size - sh) // 2
    canvas[top : top + sh, left : left + sw] = rounded
    return canvas


def _apply_rounded_corners(image: np.ndarray, radius_ratio: float) -> np.ndarray:
    """
    set alpha outside a rounded rectangle; keep rgb pixels unchanged.

    image
        opaque bgra artwork
    radius_ratio
        corner radius as a fraction of the shorter edge
    """

    height, width = image.shape[:2]
    radius = max(1, round(min(width, height) * radius_ratio))
    # render mask at 2x for smoother edges, then downscale.
    scale = 2
    mask_hi = _rounded_rect_mask(width * scale, height * scale, radius * scale)
    mask = cv2.resize(mask_hi, (width, height), interpolation=cv2.INTER_AREA)
    result = image.copy()
    result[:, :, 3] = mask
    return result


def _rounded_rect_mask(width: int, height: int, radius: int) -> np.ndarray:
    """
    build a filled rounded-rectangle alpha mask.

    width
        mask width in pixels
    height
        mask height in pixels
    radius
        corner radius in pixels
    """

    mask = np.zeros((height, width), dtype=np.uint8)
    radius = min(radius, width // 2, height // 2)
    cv2.rectangle(mask, (radius, 0), (width - radius - 1, height - 1), 255, -1)
    cv2.rectangle(mask, (0, radius), (width - 1, height - radius - 1), 255, -1)
    for center in (
        (radius, radius),
        (width - radius - 1, radius),
        (radius, height - radius - 1),
        (width - radius - 1, height - radius - 1),
    ):
        cv2.circle(mask, center, radius, 255, -1)
    return mask


def _resize_rgba(image: np.ndarray, target_side: int) -> np.ndarray:
    """
    scale artwork to fit inside a square of target_side, preserving aspect.

    image
        bgra image
    target_side
        maximum width/height in pixels
    """

    height, width = image.shape[:2]
    scale = target_side / max(width, height)
    new_w = max(1, round(width * scale))
    new_h = max(1, round(height * scale))
    interpolation = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_LANCZOS4
    return cv2.resize(image, (new_w, new_h), interpolation=interpolation)


if __name__ == "__main__":
    raise SystemExit(main())
