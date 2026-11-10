"""Measured raster masks for key drawings: figure extraction and outline backing.

This is offline authoring arithmetic, not a renderer and not an acceptance judge.
A "measured raster mask" is the set of pixels a drawing actually covers: the
figure is separated from its paper/sky by colour distance to the border colour,
then solidified (small enclosed holes filled, white shoes/socks re-attached).
The mask can be handed to :func:`northcel.fitting.fit_stacked` so a generated
in-between is fitted as the *figure*, not as a whole new page (which is how blue
background specks and black gaps between the legs got into a film).

:func:`add_outline_backing` paints the measured silhouette, expanded by a few
pixels, in the ink colour underneath every fitted shape. Thin anti-aliasing
cracks in the stack then show ink instead of exposing the background colour.
"""
from __future__ import annotations


import numpy as np
from PIL import Image

__all__ = [
    "border_background",
    "measure_figure",
    "figure_box",
    "dilate_mask",
    "outline_rings",
    "add_outline_backing",
    "prepare_key",
]


def _rgb(image: Image.Image) -> np.ndarray:
    return np.asarray(image.convert("RGB"), dtype=np.int16)


def border_background(image: Image.Image) -> np.ndarray:
    """Median colour of the image border (the paper or sky the drawing sits on)."""
    rgb = _rgb(image)
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    return np.median(border, axis=0)


def _components(mask: np.ndarray):
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover - exercised by install hints
        raise RuntimeError('Measuring a figure mask requires pip install "northcel[fit]"') from exc
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    return count, labels, stats


def _open_mask(mask: np.ndarray, pixels: int = 2) -> np.ndarray:
    """Opening that removes thin anti-aliasing rings (a cloud/sky edge is not a fill)."""
    if pixels <= 0:
        return mask
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('Measuring a figure mask requires pip install "northcel[fit]"') from exc
    size = int(pixels) * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return cv2.morphologyEx(mask.astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)


def measure_figure(image: Image.Image, *, background=None, tolerance: float = 42.0,
                   min_component: int = 1200, attach_px: int = 14,
                   max_hole: int = 18000, white_min: int = 400,
                   white_max: int = 26000, with_core: bool = False):
    """Boolean mask of the drawing's figure, without its paper or sky.

    ``tolerance`` is the per-channel distance that still counts as background.
    The figure is every material fill (skin, cloth, hair) with its ink outline,
    small detached pieces and the white garments between them. A cloud the ink
    touches stays out: it has no material colour inside.

    With ``with_core=True`` returns ``(mask, core)`` where ``core`` is the
    material fill without outlines or thin edges; its box is the accurate
    figure extent for scale/position checks.
    """
    rgb = _rgb(image)
    bg = border_background(image) if background is None else np.asarray(background, dtype=np.int16)
    distance = np.abs(rgb - bg).max(axis=2)
    luma = (0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2])
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    # Paper, sky and cloud white are all background: near the border colour, or
    # light and neutral. Material colours (skin, cloth, hair) and dark ink are
    # the drawing itself.
    neutral = (luma > 222) & (chroma < 16)
    dark = (luma < 140) & (chroma < 40)
    material = (distance > tolerance) & ~neutral & ~dark
    ink = dark & (distance > tolerance)

    count, labels, stats = _components(material)
    if count > 1 and int(stats[1:, 4].max()) >= min_component:
        # Only fills count: anti-aliasing rings between sky and cloud are thin.
        core = _open_mask(material, 2)
        count, labels, stats = _components(core)
        if count <= 1:
            empty = np.zeros((image.height, image.width), bool)
            return (empty, empty) if with_core else empty
        h, w = material.shape
        canvas = float(w * h)
        candidates = []
        for i in range(1, count):
            area = float(stats[i, 4])
            if area < min_component:
                continue
            by = int(stats[i, 1])
            bw, bh = float(stats[i, 2]), float(stats[i, 3])
            big = area > 0.05 * canvas
            # A full-width field (grass, a painted wall) or a ground band is
            # scenery, not the figure.
            field = big and ((bw > 0.85 * w) or (bh > 0.9 * h)
                             or (by + bh >= h - 2 and bw > 0.5 * w))
            candidates.append((field, area, i))
        if not candidates:
            empty = np.zeros((image.height, image.width), bool)
            return (empty, empty) if with_core else empty
        figure_candidates = [c for c in candidates if not c[0]] or candidates
        biggest = max(figure_candidates, key=lambda c: c[1])[2]
        field_ids = {c[2] for c in candidates if c[0]}
        keep = labels == biggest
        near = dilate_mask(keep, attach_px * 2)
        for i in range(1, count):
            if i in field_ids or i == biggest:
                continue
            if int(stats[i, 4]) >= max(80, min_component // 8) and (labels == i)[near].any():
                keep |= labels == i
        keep |= material & near
        # White garments (shirts, socks) sit *between* material colours: skin
        # above, trousers below. A cloud lobe beside or under the figure does
        # not have material on both sides.
        ys, xs = np.where(keep)
        x0, y0, x1, y1 = xs.min(), ys.min(), xs.max(), ys.max()
        white = neutral & (distance > tolerance)
        wcount, wlabels, wstats = _components(white)
        for i in range(1, wcount):
            area = int(wstats[i, 4])
            if not (white_min <= area <= max(white_max, 30000)):
                continue
            wx0, wy0 = int(wstats[i, 0]), int(wstats[i, 1])
            wx1, wy1 = wx0 + int(wstats[i, 2]), wy0 + int(wstats[i, 3])
            if wx1 <= x0 or wx0 >= x1 or wy1 <= y0 or wy0 >= y1:
                continue
            above = core[:wy0, max(0, wx0):wx1].any()
            below = core[wy1:, max(0, wx0):wx1].any()
            if above and below:
                keep |= wlabels == i
    else:
        # A black-and-white drawing has no material colour: its dark strokes
        # are the drawing. Keep strokes near the largest one.
        count, labels, stats = _components(ink)
        if count <= 1:
            empty = np.zeros((image.height, image.width), bool)
            return (empty, empty) if with_core else empty
        areas = stats[1:, 4]
        biggest = int(np.argmax(areas)) + 1
        keep = labels == biggest
        near = dilate_mask(keep, attach_px * 2)
        for i in range(1, count):
            if i != biggest and int(stats[i, 4]) >= max(80, min_component // 20) \
                    and (labels == i)[near].any():
                keep |= labels == i
        core = ink

    # Grow over the ink outline and detached material pieces directly on the
    # figure (hands, props), never over a cloud further away. Ink is clipped
    # per pixel, not per connected component: an outline that touches a cloud
    # must not drag the whole cloud in.
    reach = dilate_mask(keep, attach_px)
    keep |= ink & reach
    near = dilate_mask(keep, attach_px * 2)
    # Thick dark fills (black trousers, hair masses) are part of the figure;
    # thin dark lines are its outline. Opening separates the two, so a black
    # garment joins the figure while a cloud's thin outline does not.
    ink_core = _open_mask(ink, 2)
    fcount, flabels, fstats = _components(ink_core if ink_core.any() else core)
    for i in range(1, fcount):
        if int(fstats[i, 4]) < max(80, min_component // 8):
            continue
        if (flabels == i)[near].any():
            keep |= (flabels == i) & near

    # Fill only small enclosed holes (shoes, socks, paper gaps inside a body).
    hole_filled = _fill_holes(keep)
    holes = hole_filled & ~keep
    if holes.any():
        hcount, hlabels, hstats = _components(holes)
        for i in range(1, hcount):
            if int(hstats[i, 4]) <= max_hole:
                keep |= hlabels == i
    # Background colour is never figure: a see-through gap between the legs
    # stays paper/sky instead of becoming a fitted blue shape.
    keep &= distance > tolerance
    if with_core:
        return keep, core & keep
    return keep


def _fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill zero-regions that are not reachable from the image border."""
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('Measuring a figure mask requires pip install "northcel[fit]"') from exc
    m = mask.astype(np.uint8)
    h, w = m.shape
    flooded = m.copy()
    scratch = np.zeros((h + 2, w + 2), np.uint8)
    # Seed from every border pixel that is background, so a drawing touching one
    # corner cannot make the rest of the page look like a hole.
    for x in range(w):
        if flooded[0, x] == 0:
            cv2.floodFill(flooded, scratch, (x, 0), 1)
        if flooded[h - 1, x] == 0:
            cv2.floodFill(flooded, scratch, (x, h - 1), 1)
    for y in range(h):
        if flooded[y, 0] == 0:
            cv2.floodFill(flooded, scratch, (0, y), 1)
        if flooded[y, w - 1] == 0:
            cv2.floodFill(flooded, scratch, (w - 1, y), 1)
    holes = (flooded == 0)
    return mask | holes


def figure_box(mask: np.ndarray) -> list[float]:
    """Bounding box of a mask as ``[x0, y0, x1, y1]`` (empty -> the whole frame)."""
    ys, xs = np.where(mask)
    if not len(xs):
        return [0.0, 0.0, float(mask.shape[1]), float(mask.shape[0])]
    return [float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)]


def dilate_mask(mask: np.ndarray, pixels: int) -> np.ndarray:
    if pixels <= 0:
        return mask.astype(bool).copy()
    try:
        import cv2
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError('Dilating a figure mask requires pip install "northcel[fit]"') from exc
    size = int(pixels) * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size))
    return cv2.dilate(mask.astype(np.uint8), kernel).astype(bool)


def outline_rings(mask: np.ndarray, *, width: int = 4, tolerance: float = 0.6,
                  min_area: float = 2.0) -> list[str]:
    """Encoded (0.25px-b63) rings of the mask expanded by ``width`` pixels."""
    from .fitting import trace_mask

    if width > 0:
        mask = dilate_mask(mask, width)
    return trace_mask(mask, tolerance=tolerance, min_area=min_area)


def add_outline_backing(drawing, mask: np.ndarray, *, width: int = 4,
                        color=None, name: str = "backing"):
    """Return a copy of ``drawing`` painting an ink silhouette under its shapes.

    ``mask`` is in the drawing's own pixel coordinates. The silhouette is the
    mask expanded by ``width``; it is painted first, so every anti-aliased crack
    between fitted shapes exposes ink rather than the background colour.
    """
    from .rings import decode_ring_b63_q25
    from .shapes import Shape, StackedDrawing

    if mask.shape != (drawing.height, drawing.width):
        raise ValueError("mask must match the drawing's width and height")
    rings = outline_rings(mask, width=width)
    if not rings:
        return drawing
    ink = tuple(color) if color is not None else _darkest(drawing)
    shapes = list(drawing.shapes)
    min_area = min((s.area for s in shapes), default=0.0)
    z = min((s.z if s.z is not None else s.area for s in shapes), default=0.0)
    for n, text in enumerate(rings):
        ring = np.asarray(decode_ring_b63_q25(text), dtype=np.float64)
        if len(ring) < 3:
            continue
        shapes.insert(0, Shape(ink, ring, min_area - 0.01 * (n + 1), "backing",
                               id=f"{name}{n}", z=z + 0.01 * (len(rings) - n)))
    return StackedDrawing(drawing.width, drawing.height, drawing.paper, shapes, drawing.name)


def _darkest(drawing) -> tuple[int, int, int]:
    from .shapes import darkest

    return darkest(drawing.colors()) or (17, 20, 22)


def prepare_key(image: Image.Image, *, palette=None, colors: int = 32,
                tolerance: float = 0.6, min_area: float = 2.0,
                gap_fraction: float = 0.5, underpaint_min_area: float = 300.0,
                backing: int = 4, mask: np.ndarray | None = None,
                name: str = "Key") -> tuple[object, dict]:
    """Fit one key drawing as a clean figure: measured mask + outline backing.

    Returns the :class:`~northcel.shapes.StackedDrawing` and a receipt with the
    measured figure box and backing width, so a plan can record why a key looks
    the way it does.
    """
    from .fitting import fit_stacked

    if mask is None:
        measured, core = measure_figure(image, with_core=True)
    else:
        measured = np.asarray(mask, dtype=bool)
        core = measured
    if not measured.any():
        raise ValueError("no figure pixels were measured; check the drawing's border/background")
    drawing, receipt = fit_stacked(
        image, colors=colors, tolerance=tolerance, min_area=min_area, palette=palette,
        name=name, gap_fraction=gap_fraction, underpaint_min_area=underpaint_min_area,
        mask=measured)
    box = figure_box(measured)
    material_box = figure_box(core) if core.any() else box
    if backing:
        drawing = add_outline_backing(drawing, measured, width=backing)
        from .shapes import shape_manifest, shape_summary
        receipt.update(shape_summary(drawing))
        receipt["shape_manifest"] = shape_manifest(drawing)
    receipt = dict(receipt, figure_mask={"box": box,
                                         "material_box": material_box,
                                         "pixels": int(measured.sum()),
                                         "backing_px": int(backing),
                                         "source": "measured" if mask is None else "supplied"})
    return drawing, receipt
