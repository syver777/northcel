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


def _rgb_array(image) -> np.ndarray:
    """Flatten alpha onto white, exactly as `_quantize` does, as int32 RGB."""
    if not isinstance(image, Image.Image):
        image = Image.fromarray(np.asarray(image, dtype=np.uint8))
    base = Image.new("RGBA", image.size, "white")
    base.alpha_composite(image.convert("RGBA"))
    return np.asarray(base.convert("RGB"), dtype=np.int32)


def _palette_array(palette) -> np.ndarray:
    pal = np.asarray(palette)
    if pal.ndim != 2 or pal.shape[1] != 3 or not len(pal):
        raise ValueError("palette must be a nonempty list of [r,g,b] colours")
    if not np.issubdtype(pal.dtype, np.integer):
        rounded = np.rint(pal)
        if not np.allclose(pal, rounded):
            raise ValueError("palette colours must be integer 8-bit RGB")
        pal = rounded
    pal = pal.astype(np.int32)
    if np.any(pal < 0) or np.any(pal > 255):
        raise ValueError("palette colours must be 8-bit RGB in 0..255")
    return pal


def _nearest_distances(rgb: np.ndarray, palette: np.ndarray) -> np.ndarray:
    """Euclidean distance from every pixel to its nearest palette colour."""
    best = None
    for colour in palette:
        delta = rgb - colour
        distance2 = np.sum(delta * delta, axis=2)
        if best is None:
            best = distance2
        else:
            np.minimum(best, distance2, out=best)
    return np.sqrt(best)


def _nearest_colour(rgb, palette: np.ndarray) -> tuple[list[int], float]:
    delta = palette - np.asarray(rgb, dtype=np.int32)
    distance2 = np.sum(delta * delta, axis=1)
    index = int(np.argmin(distance2))
    return palette[index].tolist(), float(np.sqrt(float(distance2[index])))


def _erode_3x3(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    padded = np.pad(mask, 1, constant_values=False)
    out = np.ones((height, width), dtype=bool)
    for y in range(3):
        for x in range(3):
            out &= padded[y:y+height, x:x+width]
    return out


def _dilate_3x3(mask: np.ndarray) -> np.ndarray:
    height, width = mask.shape
    padded = np.pad(mask, 1, constant_values=False)
    out = np.zeros((height, width), dtype=bool)
    for y in range(3):
        for x in range(3):
            out |= padded[y:y+height, x:x+width]
    return out


def _open_3x3_twice(mask: np.ndarray) -> np.ndarray:
    """Remove lines up to 4 px wide (the blended colour at an ink edge).

    Two erosion iterations followed by two dilations are equivalent to a 5x5
    opening: a 4 px line vanishes, while a real fill five pixels wide survives.
    """
    return _dilate_3x3(_dilate_3x3(_erode_3x3(_erode_3x3(mask))))


def _components_numpy(mask: np.ndarray, min_area: float):
    """8-connected components, pure NumPy fallback when cv2 is unavailable."""
    height, width = mask.shape
    visited = np.zeros((height, width), dtype=bool)
    components = []
    for y0, x0 in np.argwhere(mask):
        y0, x0 = int(y0), int(x0)
        if visited[y0, x0]:
            continue
        visited[y0, x0] = True
        stack = [(y0, x0)]
        ys: list[int] = []
        xs: list[int] = []
        while stack:
            y, x = stack.pop()
            ys.append(y)
            xs.append(x)
            for ny in (y - 1, y, y + 1):
                if ny < 0 or ny >= height:
                    continue
                for nx in (x - 1, x, x + 1):
                    if 0 <= nx < width and mask[ny, nx] and not visited[ny, nx]:
                        visited[ny, nx] = True
                        stack.append((ny, nx))
        if len(ys) < min_area:
            continue
        components.append((len(ys), [min(xs), min(ys), max(xs) + 1, max(ys) + 1],
                           np.asarray(ys), np.asarray(xs)))
    return components


def _components_8(mask: np.ndarray, min_area: float):
    """Return (area, bbox, ys, xs) for 8-connected components at least min_area."""
    try:
        import cv2
    except ImportError:
        return _components_numpy(mask, min_area)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    components = []
    for label in range(1, count):
        area = int(stats[label, 4])
        if area < min_area:
            continue
        x, y, w, h = (int(v) for v in stats[label, :4])
        ys, xs = np.where(labels[y:y+h, x:x+w] == label)
        components.append((area, [x, y, x+w, y+h], ys + y, xs + x))
    return components


def palette_gaps(image, palette, threshold: float = 60.0, min_area: float = 150,
                 limit: int = 20) -> dict:
    """Report drawing regions with no suitable colour in a shared palette.

    A pixel is a gap when its Euclidean distance in 8-bit RGB to the nearest
    palette colour is greater than ``threshold``. Two 3x3 erosion/dilation
    passes remove anti-aliased lines up to 4 px wide before 8-connected
    components of at least ``min_area`` source pixels are measured. Each region
    carries its median RGB,
    the nearest palette colour and its distance, area and half-open bbox; the
    largest ``limit`` are returned. ``suggested`` keeps the median of the largest
    region from each group closer than ``threshold``.

    This is a report only; it does not quantise, trace or change a fitted shape.
    """
    if threshold < 0 or min_area < 0 or limit < 0:
        raise ValueError("palette gap threshold/min_area/limit must be nonnegative")
    rgb = _rgb_array(image)
    pal = _palette_array(palette)
    mask = _nearest_distances(rgb, pal) > threshold
    mask = _open_3x3_twice(mask)
    components = _components_8(mask, min_area)
    components.sort(key=lambda row: (-row[0], row[1][1], row[1][0]))
    regions = []
    for area, bbox, ys, xs in components[:limit]:
        median = np.rint(np.median(rgb[ys, xs], axis=0)).astype(np.int32)
        nearest, distance = _nearest_colour(median, pal)
        regions.append({"rgb": median.tolist(), "nearest": nearest,
                        "distance": distance, "area_px2": area, "bbox": bbox})
    # Merge suggestions closer than the threshold, transitively, and keep the
    # largest region's median as each cluster's representative.
    parent = list(range(len(regions)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            delta = np.asarray(regions[i]["rgb"], dtype=np.int32) \
                - np.asarray(regions[j]["rgb"], dtype=np.int32)
            if float(np.sum(delta * delta)) < threshold * threshold:
                parent[find(j)] = find(i)
    clusters: dict[int, list[int]] = {}
    for index in range(len(regions)):
        clusters.setdefault(find(index), []).append(index)
    suggested = [regions[min(members)]["rgb"]
                 for _, members in sorted(clusters.items(), key=lambda item: min(item[1]))]
    return {"threshold": threshold, "min_area_px2": min_area,
            "count": len(regions), "regions": regions, "suggested": suggested}


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


def _quantize(image: Image.Image, colors: int, tolerance: float, min_area: float,
              palette: list[tuple[int, int, int]] | None, mask: np.ndarray | None):
    """Flatten alpha, quantise to a palette and pick the underpaint colour.

    Returns (rgb image, palette indices per pixel, rgb palette, colour order,
    underpaint index or -1 for a masked fit, mask).
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
    return image, indices, rgb_palette, order, bg, mask, t0


def fit_image(image: Image.Image, colors: int = 32, tolerance: float = 0.6,
              min_area: float = 2.0, palette: list[tuple[int, int, int]] | None = None,
              name: str = "FittedDrawing", cell_edges: bool = False,
              mask: np.ndarray | None = None) -> tuple[str, dict]:
    """Return complete ordinary .ncel source plus a reproducible fitting receipt.

    Palette override is useful for a sequence: colour meaning is then the
    author's choice rather than per-frame quantiser drift. Alpha is flattened
    onto white. No semantic segmentation, optical flow or learned model runs.
    The output is a planar map; see `fit_stacked` for painter's-order shapes.
    """
    image, indices, rgb_palette, order, bg, mask, t0 = _quantize(image, colors, tolerance, min_area, palette, mask)
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


def fit_stacked(image: Image.Image, colors: int = 32, tolerance: float = 0.6,
                min_area: float = 2.0, palette: list[tuple[int, int, int]] | None = None,
                name: str = "StackedDrawing", cell_edges: bool = False,
                mask: np.ndarray | None = None, *, gap_fraction: float = 0.5,
                underpaint_min_area: float = 300.0, ink: tuple[int, int, int] | None = None,
                hole_min_area: float = 30.0, min_shape_area: float = 4.0):
    """Fit `image` and stack it: painter's-order solid shapes, biggest first.

    Returns (StackedDrawing, receipt). Tracing is exactly `fit_image`'s; the
    planar map is then stacked by `northcel.shapes.stack_planar`, with the
    see-through-gap test made on this image's own palette labels (the pixels the
    contours were traced from). `ink` defaults to the darkest fitted colour.
    Use `northcel.shapes.stacked_source` to write the drawing as `.ncel`.
    """
    from .rings import decode_ring_b63_q25
    from .shapes import shape_manifest, shape_summary, stack_planar

    image, indices, rgb_palette, order, bg, mask, t0 = _quantize(image, colors, tolerance, min_area, palette, mask)
    labels = indices.astype(np.int32)
    label_colors = [tuple(int(v) for v in c) for c in rgb_palette]
    if bg >= 0:
        paper = label_colors[bg]
    else:
        paper = (255, 255, 255)
        labels = labels.copy()
        labels[~mask] = len(label_colors)
        label_colors.append(paper)
    layers = []
    for k in (k for k in order if k != bg):
        field = indices == k
        if mask is not None:
            field &= mask
        rings = [np.asarray(decode_ring_b63_q25(r), dtype=np.float64)
                 for r in trace_mask(field, tolerance, min_area, cell_edges)]
        if rings:
            layers.append((label_colors[k], rings))
    width, height = image.size
    drawing = stack_planar(layers, paper, width, height, labels, label_colors,
                           gap_fraction=gap_fraction, underpaint_min_area=underpaint_min_area,
                           ink=ink, hole_min_area=hole_min_area, min_shape_area=min_shape_area, name=name)
    receipt = {"tool": "northcel-fit/1", "mode": "stacked",
               "input_rgb_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
               "paper_rgb": list(paper),
               "libraries": {n: getattr(sys.modules.get(n), "__version__", "not loaded") for n in ("numpy", "PIL", "cv2", "skimage")},
               "colors": len(order), "tolerance_px": tolerance, "min_area_px2": min_area,
               "cell_edges": cell_edges, "masked": mask is not None,
               "gap_fraction": gap_fraction, "underpaint_min_area_px2": underpaint_min_area,
               "ink_rgb": list(ink) if ink else None, "hole_min_area_px2": hole_min_area,
               **shape_summary(drawing),
               "shape_manifest": shape_manifest(drawing),
               "seconds": time.monotonic()-t0, "raster_embedded": False, "quality": "unreviewed"}
    return drawing, receipt


def _report_palette_gaps(receipt: dict, image_path, palette, threshold: float,
                         min_area: float) -> None:
    """Attach the palette-gap report to a fit receipt and warn once on stderr."""
    if not palette:
        return
    with Image.open(image_path) as image:
        gaps = palette_gaps(image, palette, threshold=threshold, min_area=min_area)
    receipt["palette_gaps"] = gaps
    if gaps["count"]:
        suggested = ", ".join("#" + "".join(f"{c:02X}" for c in rgb)
                              for rgb in gaps["suggested"])
        print(f"northcel fit: palette_gaps: {gaps['count']} region(s) >= "
              f"{gaps['min_area_px2']:g} px^2 have no palette colour within "
              f"{gaps['threshold']:g}; suggested {suggested}", file=sys.stderr)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="northcel fit", description=__doc__)
    p.add_argument("image")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--colors", type=int, default=32)
    p.add_argument("--tolerance", type=float, default=0.6)
    p.add_argument("--min-area", type=float, default=2.0)
    p.add_argument("--cell-edges", action="store_true", help="preserve quantised pixel-cell contour corners (larger source)")
    p.add_argument("--palette", help="JSON file containing [[r,g,b], ...]")
    p.add_argument("--palette-threshold", type=float, default=60.0,
                   help="--palette: report regions farther than this RGB distance from every palette colour (default: 60)")
    p.add_argument("--palette-min-area", type=float, default=150.0,
                   help="--palette: report gap regions at least this many source pixels (default: 150)")
    p.add_argument("--mask", help="author-supplied nonzero grayscale matte (one intact cel)")
    p.add_argument("--receipt", help="write JSON fitting receipt")
    p.add_argument("--stacked", action="store_true",
                   help="emit painter's-order solid shapes (biggest first) instead of a planar map")
    p.add_argument("--figure", action="store_true",
                   help="--stacked: fit the measured figure only (mask), with an ink outline backing")
    p.add_argument("--figure-mask", help="--figure: author-supplied figure matte (one intact cel)")
    p.add_argument("--backing", type=float, default=4.0,
                   help="--figure: outline backing width in px (0 disables, default 4)")
    p.add_argument("--gap-fraction", type=float, default=0.5,
                   help="--stacked: a hole whose source pixels are more than this fraction paper stays as a paper-coloured shape")
    p.add_argument("--underpaint-min-area", type=float, default=300.0,
                   help="--stacked: fill ink holes larger than this (px^2) with their dominant colour; 0 disables")
    p.add_argument("--ink", help="--stacked: ink colour #RRGGBB for underpaint (default: darkest fitted colour)")
    a = p.parse_args(argv)
    try:
        palette = json.loads(Path(a.palette).read_text()) if a.palette else None
        if a.palette_threshold < 0 or a.palette_min_area < 0:
            raise ValueError("--palette-threshold and --palette-min-area must be nonnegative")
        mask = np.asarray(Image.open(a.mask).convert("L")) > 0 if a.mask else None
        if a.stacked:
            from .shapes import stacked_source
            ink = None
            if a.ink:
                h = a.ink.lstrip("#")
                if len(h) != 6:
                    raise ValueError("--ink must be #RRGGBB")
                ink = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
            if not 0.0 <= a.gap_fraction <= 1.0 or a.underpaint_min_area < 0:
                raise ValueError("--gap-fraction must be 0..1 and --underpaint-min-area nonnegative")
            if a.figure:
                from .keys import prepare_key
                figure_mask = None
                if a.figure_mask:
                    figure_mask = np.asarray(Image.open(a.figure_mask).convert("L")) > 0
                drawing, receipt = prepare_key(
                    Image.open(a.image), palette=palette, colors=a.colors,
                    tolerance=a.tolerance, min_area=a.min_area,
                    gap_fraction=a.gap_fraction, underpaint_min_area=a.underpaint_min_area,
                    backing=int(a.backing), mask=figure_mask)
            else:
                drawing, receipt = fit_stacked(Image.open(a.image), a.colors, a.tolerance, a.min_area, palette,
                                               cell_edges=a.cell_edges, mask=mask, gap_fraction=a.gap_fraction,
                                               underpaint_min_area=a.underpaint_min_area, ink=ink)
            source = stacked_source(drawing)
            receipt["bytes"] = len(source.encode())
            _report_palette_gaps(receipt, a.image, palette, a.palette_threshold, a.palette_min_area)
            Path(a.out).write_text(source, encoding="utf-8")
            if a.receipt:
                Path(a.receipt).write_text(json.dumps(receipt, indent=2)+"\n")
            print(json.dumps(receipt))
            return 0
        source, receipt = fit_image(Image.open(a.image), a.colors, a.tolerance, a.min_area, palette, cell_edges=a.cell_edges, mask=mask)
        _report_palette_gaps(receipt, a.image, palette, a.palette_threshold, a.palette_min_area)
        Path(a.out).write_text(source, encoding="utf-8")
        if a.receipt:
            Path(a.receipt).write_text(json.dumps(receipt, indent=2)+"\n")
        print(json.dumps(receipt))
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        p.error(str(exc))
