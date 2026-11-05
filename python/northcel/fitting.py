"""Offline vector authoring, never a renderer or a visual acceptance judge.

Images are quantised and traced to closed contours; no pixels, filenames or
textures survive in the emitted document. Install `northcel[fit]` for tracing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from .rings import encode_ring_b63_q25


def trace_mask(mask: np.ndarray, tolerance: float = 0.6, min_area: float = 2.0,
               cell_edges: bool = False) -> list[str]:
    try:
        import cv2
        from skimage.measure import find_contours
    except ImportError as exc:
        raise RuntimeError('Tracing requires pip install "northcel[fit]"') from exc
    rings = []
    for contour in find_contours(np.pad(mask.astype(np.float32), 1), 0.5, fully_connected="high"):
        points = (contour[:, ::-1] - 0.5).astype(np.float32).reshape(-1, 1, 2)
        if cell_edges:
            # Marching squares chamfers isolated pixel corners into diamonds.
            # Restore the *vector boundary of the union of pixel cells*, not
            # one rectangle per pixel or an embedded sample/lookup array.
            p = points[:, 0, :]
            q = np.roll(p, -1, axis=0)
            diagonal = (p[:, 0] != q[:, 0]) & (p[:, 1] != q[:, 1])
            expanded = np.empty((len(p)*2, 2), dtype=np.float32)
            expanded[0::2] = p
            integer_x = p[:, 0] == np.floor(p[:, 0])
            expanded[1::2, 0] = np.where(integer_x, p[:, 0], q[:, 0])
            expanded[1::2, 1] = np.where(integer_x, q[:, 1], p[:, 1])
            keep = np.ones(len(p)*2, dtype=bool)
            keep[1::2] = diagonal
            points = expanded[keep].reshape(-1, 1, 2)
        if abs(cv2.contourArea(points)) < min_area:
            continue
        points = cv2.approxPolyDP(points, tolerance, True).reshape(-1, 2)
        if len(points) >= 3:
            rings.append(encode_ring_b63_q25(points.tolist()))
    return rings


def fit_image(image: Image.Image, colors: int = 32, tolerance: float = 0.6,
              min_area: float = 2.0, palette: list[tuple[int, int, int]] | None = None,
              name: str = "FittedDrawing", cell_edges: bool = False,
              mask: np.ndarray | None = None) -> tuple[str, dict]:
    """Return complete ordinary .ncel source plus a reproducible fitting receipt.

    Palette override is useful for a sequence: colour meaning is then the
    author's choice rather than per-frame quantiser drift. Alpha is flattened
    onto white. No semantic segmentation, optical flow or learned model runs.
    """
    if not 2 <= colors <= 256 or tolerance < 0 or min_area < 0:
        raise ValueError("colors must be 2..256; tolerance/min_area must be nonnegative")
    image = image.convert("RGBA")
    base = Image.new("RGBA", image.size, "white")
    base.alpha_composite(image)
    image = base.convert("RGB")
    if mask is not None:
        mask = np.asarray(mask, dtype=bool)
        if mask.shape != (image.height, image.width) or not mask.any():
            raise ValueError("mask must be nonempty and match the input image size")
    t0 = time.monotonic()
    if palette:
        if not 2 <= len(palette) <= 256:
            raise ValueError("palette must have 2..256 RGB colours")
        pal = Image.new("P", (1, 1))
        flat = [c for rgb in palette for c in rgb]
        pal.putpalette(flat + flat[-3:] * (256-len(palette)))
        quant = image.quantize(palette=pal, dither=Image.Dither.NONE)
    else:
        if mask is None:
            quant = image.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
        else:
            training = Image.fromarray(np.asarray(image)[mask][None, :, :])
            pal = training.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
            quant = image.quantize(palette=pal, dither=Image.Dither.NONE)
    indices = np.asarray(quant)
    rgb_palette = np.asarray(quant.getpalette(), dtype=np.uint8).reshape(-1, 3)
    counts = np.bincount(indices.ravel() if mask is None else indices[mask], minlength=len(rgb_palette))
    order = sorted(np.flatnonzero(counts), key=lambda k: (-int(counts[k]), int(k)))
    # Use the colour nearest the image median as the underpaint. Picking the
    # largest *single* bin made a white cloud win over a sky spread across many
    # bins; discarded subpixel sky islands then became white pinholes.
    median = np.median(np.asarray(image).reshape(-1, 3), axis=0)
    bg = int(min(order, key=lambda k: float(np.sum((rgb_palette[k].astype(float)-median)**2)))) if mask is None else -1
    palette_line = ", ".join(f"c{k}: #{''.join(f'{c:02X}' for c in rgb_palette[k])}" for k in order)
    body = [f"  palette {{ {palette_line} }}",
            f"  paper {{ color: {'$c'+str(bg) if bg >= 0 else '#FFFFFF'}, antialias_grid: 4 }}"]
    ring_count = 0
    for k in (k for k in order if k != bg):
        field = indices == k
        if mask is not None:
            field &= mask
        rings = trace_mask(field, tolerance, min_area, cell_edges)
        if rings:
            body.append(f'  layer color_{k}(color: $c{k}, rings: {len(rings)}) {{ "{"|".join(rings)}" }}')
            ring_count += len(rings)
    width, height = image.size
    source = ('northcel "0.3.0-draft"\n\n'
              f'scene {name}(width: {width}, height: {height}, fps: 24, precision: 0.25px-b63) {{\n'
              + '\n'.join(body) + '\n}\n')
    receipt = {"tool": "northcel-fit/1", "input_rgb_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
               "underpaint_rgb": rgb_palette[bg].tolist() if bg >= 0 else [255, 255, 255],
               "libraries": {name: getattr(sys.modules.get(name), "__version__", "not loaded") for name in ("numpy", "PIL", "cv2", "skimage")},
               "colors": len(order), "tolerance_px": tolerance, "min_area_px2": min_area,
               "cell_edges": cell_edges,
               "masked": mask is not None,
               "rings": ring_count, "bytes": len(source.encode()), "seconds": time.monotonic()-t0,
               "raster_embedded": False, "quality": "unreviewed"}
    return source, receipt


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="northcel fit", description=__doc__)
    p.add_argument("image")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--colors", type=int, default=32)
    p.add_argument("--tolerance", type=float, default=0.6)
    p.add_argument("--min-area", type=float, default=2.0)
    p.add_argument("--cell-edges", action="store_true", help="preserve quantised pixel-cell contour corners (larger source)")
    p.add_argument("--palette", help="JSON file containing [[r,g,b], ...]")
    p.add_argument("--mask", help="author-supplied nonzero grayscale matte (one intact cel)")
    p.add_argument("--receipt", help="write JSON fitting receipt")
    a = p.parse_args(argv)
    try:
        palette = json.loads(Path(a.palette).read_text()) if a.palette else None
        mask = np.asarray(Image.open(a.mask).convert("L")) > 0 if a.mask else None
        source, receipt = fit_image(Image.open(a.image), a.colors, a.tolerance, a.min_area, palette, cell_edges=a.cell_edges, mask=mask)
        Path(a.out).write_text(source, encoding="utf-8")
        if a.receipt:
            Path(a.receipt).write_text(json.dumps(receipt, indent=2)+"\n")
        print(json.dumps(receipt))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        p.error(str(exc))
