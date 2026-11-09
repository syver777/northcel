"""Stacked shapes: painter's-order solid contours made from a fitted planar map.

`northcel fit` emits a *planar map*: one layer per palette colour, each with
outer rings and the holes the other colours sit in (even-odd). That is exact for
one still frame, but as soon as two maps are interpolated every gap between
regions shows paper. A *stacked* drawing instead paints every region as its
solid outer contour, biggest first, so a smaller region that drifts uncovers
the region underneath it rather than the paper.

Two kinds of hole survive stacking as shapes of their own:

* a **see-through gap** — a hole whose source pixels are mostly paper (sky
  between an arm and the body) becomes a paper-coloured shape, so the stack
  still shows the paper there;
* an optional **underpaint** — a large hole in the ink colour is filled with the
  dominant other colour inside it, so a drifting fill exposes skin or shirt
  rather than black ink.

Which pixels a hole covers is decided by the source image's palette labels
when one is given ("checked against the source pixels"), otherwise by the
planar map itself. This is offline authoring arithmetic. It does not segment
characters, infer depth or judge the result.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

RGB = tuple[int, int, int]


# ---------------------------------------------------------------- geometry
def ring_area(ring: np.ndarray) -> float:
    """Signed shoelace area (positive when the ring runs clockwise on screen, y down)."""
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def ring_centroid(ring: np.ndarray) -> np.ndarray:
    a = ring_area(ring)
    if abs(a) < 1e-6:
        return ring.mean(axis=0)
    x, y = ring[:, 0], ring[:, 1]
    cr = x * np.roll(y, -1) - np.roll(x, -1) * y
    return np.array([((x + np.roll(x, -1)) * cr).sum(), ((y + np.roll(y, -1)) * cr).sum()]) / (6.0 * a)


def ring_perimeter(ring: np.ndarray) -> float:
    return float(np.linalg.norm(np.diff(np.vstack([ring, ring[:1]]), axis=0), axis=1).sum())


def point_in_ring(pt: Sequence[float], ring: np.ndarray) -> bool:
    """Even-odd point test with the renderer's half-open crossing rule."""
    x, y = float(pt[0]), float(pt[1])
    xs, ys = ring[:, 0], ring[:, 1]
    xs2, ys2 = np.roll(xs, -1), np.roll(ys, -1)
    cond = (ys > y) != (ys2 > y)
    with np.errstate(divide="ignore", invalid="ignore"):
        xint = xs + (y - ys) * (xs2 - xs) / (ys2 - ys)
    return bool(np.count_nonzero(cond & (x < xint)) % 2)


def ring_pixel_spans(ring: np.ndarray, width: int, height: int):
    """(rows, x0, x1) pixel spans whose centres lie inside `ring` (renderer rule, aa=1)."""
    from .renderer import _layer_spans

    pts = [(float(x), float(y)) for x, y in ring]
    return _layer_spans([pts], 1, height, width)


def colour_fractions(labels: np.ndarray, ring: np.ndarray) -> dict[int, float]:
    """Fraction of each label among the pixels whose centres are inside `ring`."""
    spans = ring_pixel_spans(ring, labels.shape[1], labels.shape[0])
    if spans is None:
        return {}
    rows, a, b = spans
    counts: dict[int, int] = {}
    total = 0
    for r, x0, x1 in zip(rows.tolist(), a.tolist(), b.tolist()):
        values, n = np.unique(labels[r, x0:x1], return_counts=True)
        for v, c in zip(values.tolist(), n.tolist()):
            counts[v] = counts.get(v, 0) + c
        total += x1 - x0
    if not total:
        return {}
    return {k: v / total for k, v in sorted(counts.items())}


# ------------------------------------------------------------------- model
@dataclass
class Shape:
    """One solid painter's shape: a colour and one closed ring (pixel units)."""

    color: RGB
    ring: np.ndarray
    area: float
    kind: str = "region"  # "region", "gap" (paper seen through) or "underpaint"

    @property
    def centroid(self) -> np.ndarray:
        return ring_centroid(self.ring)

    @property
    def perimeter(self) -> float:
        return ring_perimeter(self.ring)


@dataclass
class StackedDrawing:
    """A drawing as painter's-order solid shapes over a paper colour."""

    width: int
    height: int
    paper: RGB
    shapes: list[Shape] = field(default_factory=list)
    name: str = "Drawing"

    def colors(self) -> list[RGB]:
        seen: list[RGB] = [self.paper]
        for s in self.shapes:
            if s.color not in seen:
                seen.append(s.color)
        return seen


def darkest(colors: Iterable[RGB]) -> RGB | None:
    """The lowest-luma colour (Rec. 601 weights); the default 'ink' for underpaint."""
    best = None
    for c in colors:
        luma = 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
        if best is None or luma < best[0]:
            best = (luma, c)
    return best[1] if best else None


# ---------------------------------------------------------------- stacking
def stack_planar(
    layers: Sequence[tuple[RGB, Sequence[np.ndarray]]],
    paper: RGB,
    width: int,
    height: int,
    labels: np.ndarray | None = None,
    label_colors: Sequence[RGB] | None = None,
    *,
    gap_fraction: float = 0.5,
    underpaint_min_area: float = 300.0,
    ink: RGB | None = None,
    min_shape_area: float = 4.0,
    hole_min_area: float = 30.0,
    name: str = "Drawing",
) -> StackedDrawing:
    """Planar map -> painter's-order solid shapes, biggest first.

    `layers` is the planar map in paint order: (colour, rings). Within one layer
    a ring nested inside an odd number of larger same-layer rings is a hole; the
    rest are outer contours and become solid shapes. A hole bigger than
    `hole_min_area` px^2 becomes:

    * a paper-coloured "gap" shape when more than `gap_fraction` of its pixels
      are paper in `labels`;
    * otherwise, if its layer is the ink colour and it is bigger than
      `underpaint_min_area` (0 disables), an "underpaint" shape in the most
      frequent non-ink label inside it.

    `labels` is an (H, W) integer array of indices into `label_colors`. When it
    is omitted, the planar map itself is rasterised to make it. Shapes are sorted
    by decreasing area (stable); gap/underpaint shapes sort just after an outer
    shape of the same area.
    """
    if labels is None:
        labels, label_colors = planar_labels(layers, paper, width, height)
    assert label_colors is not None
    label_colors = [tuple(int(v) for v in c) for c in label_colors]
    paper = tuple(paper)
    if ink is None:
        ink = darkest(tuple(c) for c, _ in layers)
    ink = tuple(ink) if ink is not None else None

    outers: list[tuple[RGB, np.ndarray, float]] = []
    holes: list[tuple[RGB, np.ndarray, float]] = []
    for color, rings in layers:
        info = []
        for r in rings:
            arr = np.asarray(r, dtype=np.float64)
            if len(arr) < 3:
                continue
            a = abs(ring_area(arr))
            if a > min_shape_area:
                info.append((arr, a, arr.min(axis=0), arr.max(axis=0)))
        for i, (r, a, lo, hi) in enumerate(info):
            depth = 0
            for j, (r2, a2, lo2, hi2) in enumerate(info):
                if j != i and a2 > a and (lo >= lo2).all() and (hi <= hi2).all() and point_in_ring(r[0], r2):
                    depth += 1
            (outers if depth % 2 == 0 else holes).append((tuple(color), r, a))

    shapes = [Shape(c, r, a, "region") for c, r, a in outers]
    for c, r, a in holes:
        if a <= hole_min_area:
            continue
        # Fractions per colour (a palette may list a colour twice).
        frac: dict[RGB, float] = {}
        for k, v in colour_fractions(labels, r).items():
            if 0 <= k < len(label_colors):
                frac[label_colors[k]] = frac.get(label_colors[k], 0.0) + v
        if frac.get(paper, 0.0) > gap_fraction:
            shapes.append(Shape(paper, r, a - 0.5, "gap"))
        elif underpaint_min_area > 0 and c == ink and a > underpaint_min_area:
            others = {k: v for k, v in frac.items() if k != ink}
            if others:
                dom = max((v, k) for k, v in others.items())[1]
                shapes.append(Shape(dom, r, a - 0.5, "underpaint"))
    shapes.sort(key=lambda s: -s.area)
    return StackedDrawing(width, height, paper, shapes, name)


def planar_labels(layers, paper: RGB, width: int, height: int):
    """Rasterise a planar map to an (H, W) label array (pixel centres, paint order)."""
    from .renderer import _layer_spans

    colors: list[RGB] = [tuple(paper)]
    labels = np.zeros((height, width), dtype=np.int32)
    for color, rings in layers:
        color = tuple(color)
        if color not in colors:
            colors.append(color)
        spans = _layer_spans([[(float(x), float(y)) for x, y in r] for r in rings], 1, height, width)
        if spans is None:
            continue
        idx = colors.index(color)
        for row, x0, x1 in zip(*(s.tolist() for s in spans)):
            labels[row, x0:x1] = idx
    return labels, colors


def image_labels(image, colors: Sequence[RGB]) -> np.ndarray:
    """Nearest-colour (RGB squared distance, lowest index on ties) label per pixel."""
    from PIL import Image

    if isinstance(image, Image.Image):
        image = image.convert("RGB")
    rgb = np.asarray(image, dtype=np.int32)[:, :, :3]
    pal = np.asarray(colors, dtype=np.int32)
    out = np.empty(rgb.shape[:2], dtype=np.int32)
    step = max(1, (1 << 22) // max(1, rgb.shape[1] * len(pal)))
    for y0 in range(0, rgb.shape[0], step):
        block = rgb[y0:y0 + step]
        d = ((block[:, :, None, :] - pal[None, None]) ** 2).sum(axis=-1)
        out[y0:y0 + step] = d.argmin(axis=-1)
    return out


# --------------------------------------------------------- source <-> model
def drawing_from_source(
    source: str,
    image=None,
    *,
    stack: str = "auto",
    gap_fraction: float = 0.5,
    underpaint_min_area: float = 300.0,
    ink: RGB | None = None,
) -> StackedDrawing:
    """Read a plain `.ncel` scene (fitted planar or already stacked) as a StackedDrawing.

    The scene is expanded at frame 0 (outlines, transforms and `use` included).
    `stack="auto"` keeps the document's own paint order when every painted layer
    has exactly one ring and no hole (a stacked document); otherwise the planar
    map is stacked with `stack_planar`. `stack="never"`/`"always"` force it.
    `image` (a PIL image or path), when given, supplies the source pixels for
    the gap test; colours are labelled by nearest palette colour.
    """
    from .ast_nodes import SceneNode
    from .parser import parse_ncel
    from .renderer import frame_paint_list

    doc = parse_ncel(source)
    if not isinstance(doc.root, SceneNode):
        raise ValueError("expected a scene (one drawing), not a film")
    _paper, paper_color, paints = frame_paint_list(doc, 0)
    root = doc.root
    if any(p.opacity < 1.0 or p.groups for p in paints):
        raise ValueError("a drawing with opacity cannot be read as solid shapes")
    layers = [(p.color.as_rgb_tuple(), [np.asarray(r, dtype=np.float64) for r in p.rings if len(r) >= 3])
              for p in paints]
    layers = [(c, rs) for c, rs in layers if rs]
    paper = paper_color.as_rgb_tuple()
    if stack not in ("auto", "always", "never"):
        raise ValueError("stack must be auto, always or never")
    already = all(len(rs) == 1 for _c, rs in layers)
    if stack == "never" or (stack == "auto" and already):
        shapes = [Shape(c, r, abs(ring_area(r))) for c, rs in layers for r in rs]
        return StackedDrawing(root.width, root.height, paper, shapes, root.name)
    labels = colors = None
    if image is not None:
        from PIL import Image

        img = Image.open(image) if isinstance(image, (str, bytes)) or hasattr(image, "__fspath__") else image
        if img.size != (root.width, root.height):
            raise ValueError(f"image is {img.size[0]}x{img.size[1]}, drawing is {root.width}x{root.height}")
        colors = [paper] + [c for c, _ in layers if c != paper]
        colors = list(dict.fromkeys(colors))
        labels = image_labels(img, colors)
    return stack_planar(layers, paper, root.width, root.height, labels, colors,
                        gap_fraction=gap_fraction, underpaint_min_area=underpaint_min_area, ink=ink,
                        name=root.name)


def _hex(c: RGB) -> str:
    return "#" + "".join(f"{v:02X}" for v in c)


def palette_names(colors: Iterable[RGB]) -> dict[RGB, str]:
    names: dict[RGB, str] = {}
    for c in colors:
        if tuple(c) not in names:
            names[tuple(c)] = f"c{len(names)}"
    return names


def encode_ring(ring: np.ndarray) -> str | None:
    """Quarter-pixel Base-63 ring text, or None when it collapses below 3 vertices."""
    from .rings import RingEncodingError, encode_ring_b63_q25

    try:
        return encode_ring_b63_q25([(float(x), float(y)) for x, y in ring])
    except RingEncodingError:
        return None


def stacked_source(drawing: StackedDrawing, *, spec: str = "0.3.0-draft", antialias_grid: int = 4,
                   fps: int = 24) -> str:
    """A plain scene: palette, paper and one `layer` per shape in paint order.

    Only spec 0.3 constructs are used, so the result also renders natively.
    """
    names = palette_names(drawing.colors())
    width = max(3, len(str(max(0, len(drawing.shapes) - 1))))
    lines = [
        f'northcel "{spec}"',
        "",
        f"scene {drawing.name}(width: {drawing.width}, height: {drawing.height}, fps: {fps}, precision: 0.25px-b63) {{",
        "  palette { " + ", ".join(f"{n}: {_hex(c)}" for c, n in names.items()) + " }",
        f"  paper {{ color: ${names[drawing.paper]}, antialias_grid: {antialias_grid} }}",
    ]
    for n, shape in enumerate(drawing.shapes):
        text = encode_ring(shape.ring)
        if text:
            lines.append(f'  layer s{n:0{width}d}(color: ${names[shape.color]}) {{ "{text}" }}')
    lines.append("}")
    return "\n".join(lines) + "\n"


def shape_summary(drawing: StackedDrawing) -> dict:
    kinds: dict[str, int] = {}
    for s in drawing.shapes:
        kinds[s.kind] = kinds.get(s.kind, 0) + 1
    return {"shapes": len(drawing.shapes), "kinds": kinds,
            "largest_area_px2": round(drawing.shapes[0].area, 1) if drawing.shapes else 0.0,
            "canvas_area_px2": drawing.width * drawing.height}
