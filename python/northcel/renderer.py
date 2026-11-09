"""Pure-Python + NumPy 4x4 subpixel reference renderer for NorthCel (.ncel).

Implements the exact rendering semantics of the NorthCel 0.1.0-draft specification:
1. Each frame `f` is a pure function of `(doc, frame_index, seed)`.
2. Paint order:
   - Paper fill (`paper.color` + optional deterministic lattice grain).
   - Ordered `layer` / `wash`, `stroke`, `ribbon`, `use`, and `bend_swarm` primitives.
   - Backward-compatibility rule for `water_droplets` / `beard_and_chest_bristles` swarms
     on standard 4-layer scenes: water droplets merge into `tile_wall` (even-odd aperture
     cutouts + bright spray on tile), and bristles merge into `ink_contours`, matching
     the MoonBit + Bend + GLSL pipeline byte-for-byte.
3. Fill rule: Even-Odd winding parity (`fill-rule="evenodd"`) evaluated at `N x N`
   subpixel centers `(x + (sx + 0.5)/N, y + (sy + 0.5)/N)` where `N = paper.antialias_grid`
   (default 4).
4. Deterministic Line Boil: Pure stateless 32-bit integer hash of `(seed, frame_index,
   layer_id, ring_id, vertex_id)` — zero sequential RNG state.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from .ast_nodes import (
    BoilSpec,
    ColorMix,
    ColorValue,
    DefBlock,
    DocumentNode,
    DropNode,
    FilmNode,
    LayerNode,
    MorphNode,
    PaperSpec,
    RibbonNode,
    SceneItem,
    SceneNode,
    StrokeNode,
    SwarmNode,
    TransformNode,
    UseNode,
)
from .parser import ExprValue
from .rings import decode_rings_payload


class NorthCelEvaluationError(ValueError):
    """A located semantic error, also consumable by the CLI without a traceback."""

    def __init__(self, message: str, line: int, column: int):
        self.message, self.line, self.column = message, line, column
        super().__init__(f"{line}:{column}: {message}")


def _hash_u32(x: int) -> int:
    x = (x & 0xFFFFFFFF) ^ 61
    x = (x ^ (x >> 16)) & 0xFFFFFFFF
    x = (x + ((x << 3) & 0xFFFFFFFF)) & 0xFFFFFFFF
    x = (x ^ (x >> 4)) & 0xFFFFFFFF
    x = (x * 0x27D4EB2D) & 0xFFFFFFFF
    x = (x ^ (x >> 15)) & 0xFFFFFFFF
    return x


def boil_offset(
    seed: int,
    frame_idx: int,
    item_idx: int,
    ring_idx: int,
    vert_idx: int,
    boil: BoilSpec | None,
) -> tuple[float, float]:
    """Computes a pure stateless (dx, dy) line-boil offset for a vertex."""
    if boil is None or boil.amplitude_px <= 0.0:
        return (0.0, 0.0)
    phase_frame = int(math.floor(frame_idx * max(0.01, boil.frequency)))
    h1 = _hash_u32(
        seed * 73856093
        ^ phase_frame * 19349663
        ^ item_idx * 83492791
        ^ ring_idx * 2654435761
        ^ vert_idx * 374761393
    )
    h2 = _hash_u32(h1 ^ 0x9E3779B9)
    nx = (h1 / 4294967295.0) * 2.0 - 1.0
    ny = (h2 / 4294967295.0) * 2.0 - 1.0
    return (nx * boil.amplitude_px, ny * boil.amplitude_px)


def _eval_num(val: Any, env: dict[str, float]) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, ExprValue):
        return val.eval(env)
    return float(val)


def _stroke_to_ring(
    pts: list[tuple[float, float]], w_start: float, w_end: float
) -> list[tuple[float, float]]:
    """Converts a polyline with start/end taper widths into a closed polygon ribbon."""
    n = len(pts)
    if n < 2:
        return []
    left_pts: list[tuple[float, float]] = []
    right_pts: list[tuple[float, float]] = []
    for i, (px, py) in enumerate(pts):
        u = i / float(n - 1)
        half_w = 0.5 * (w_start + (w_end - w_start) * u)
        if i == 0:
            dx = pts[1][0] - pts[0][0]
            dy = pts[1][1] - pts[0][1]
        elif i == n - 1:
            dx = pts[-1][0] - pts[-2][0]
            dy = pts[-1][1] - pts[-2][1]
        else:
            dx = pts[i + 1][0] - pts[i - 1][0]
            dy = pts[i + 1][1] - pts[i - 1][1]
        length = math.hypot(dx, dy) or 1.0
        nx = -dy / length
        ny = dx / length
        left_pts.append((px + nx * half_w, py + ny * half_w))
        right_pts.append((px - nx * half_w, py - ny * half_w))
    return left_pts + list(reversed(right_pts))


def _ribbon_to_ring(pts_w: list[tuple[float, float, float]]) -> list[tuple[float, float]]:
    """Converts a polyline with per-vertex widths (x, y, w) into a closed polygon ribbon."""
    n = len(pts_w)
    if n < 2:
        return []
    left_pts: list[tuple[float, float]] = []
    right_pts: list[tuple[float, float]] = []
    for i, (px, py, w) in enumerate(pts_w):
        half_w = 0.5 * max(0.25, w)
        if i == 0:
            dx = pts_w[1][0] - pts_w[0][0]
            dy = pts_w[1][1] - pts_w[0][1]
        elif i == n - 1:
            dx = pts_w[-1][0] - pts_w[-2][0]
            dy = pts_w[-1][1] - pts_w[-2][1]
        else:
            dx = pts_w[i + 1][0] - pts_w[i - 1][0]
            dy = pts_w[i + 1][1] - pts_w[i - 1][1]
        length = math.hypot(dx, dy) or 1.0
        nx = -dy / length
        ny = dx / length
        left_pts.append((px + nx * half_w, py + ny * half_w))
        right_pts.append((px - nx * half_w, py - ny * half_w))
    return left_pts + list(reversed(right_pts))


def _clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def resolve_color(spec: ColorValue | ColorMix, env: dict[str, float]) -> ColorValue:
    """Evaluate a colour attribute for one frame (spec 0.4 `mix` in sRGB, u clamped)."""
    if isinstance(spec, ColorValue):
        return spec
    a = resolve_color(spec.a, env)
    b = resolve_color(spec.b, env)
    u = _clamp01(_eval_num(spec.u, env))
    r, g, bl = (
        int(math.floor(x + (y - x) * u + 0.5)) for x, y in zip(a.as_rgb_tuple(), b.as_rgb_tuple())
    )
    return ColorValue.from_rgb(r, g, bl)


# ------------------------------------------------------------------- morph
def _signed_area(ring: np.ndarray) -> float:
    x, y = ring[:, 0], ring[:, 1]
    return 0.5 * float(np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y))


def resample_closed(ring: np.ndarray, samples: int) -> np.ndarray:
    """`samples` points at uniform arclength k*L/samples from vertex 0 (spec 0.4 morph)."""
    pts = np.asarray(ring, dtype=np.float64)
    edges = np.roll(pts, -1, axis=0) - pts
    lengths = np.sqrt(np.sum(edges * edges, axis=1))
    cum = np.concatenate(([0.0], np.cumsum(lengths)))
    total = cum[-1]
    if total <= 0.0:
        return np.repeat(pts[:1], samples, axis=0)
    at = np.arange(samples, dtype=np.float64) * (total / samples)
    ix = np.minimum(np.searchsorted(cum, at, side="right") - 1, len(pts) - 1)
    u = (at - cum[ix]) / np.maximum(lengths[ix], 1e-300)
    return pts[ix] + edges[ix] * u[:, None]


def align_cyclic(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Roll `b` by the shift k minimising sum |(a_j - mean a) - (b_(j+k) - mean b)|^2; ties -> smallest k."""
    m = len(a)
    ca = a - a.mean(axis=0)
    cb = b - b.mean(axis=0)
    idx = (np.arange(m)[None, :] + np.arange(m)[:, None]) % m
    cross = np.einsum("kjc,jc->k", cb[idx], ca)
    cost = float(np.sum(ca * ca)) + float(np.sum(cb * cb)) - 2.0 * cross
    k = int(np.argmin(cost))
    return np.roll(b, -k, axis=0)


_MORPH_CACHE: dict[tuple[str, str, str, int | None], list[tuple[np.ndarray, np.ndarray]]] = {}


def morph_pairs(payload_a: str, payload_b: str, precision: str, samples: int | None):
    """Decoded, winding-normalised, resampled and start-aligned ring pairs (pure, cached)."""
    key = (payload_a, payload_b, precision, samples)
    hit = _MORPH_CACHE.get(key)
    if hit is not None:
        return hit
    rings_a = decode_rings_payload(payload_a, precision=precision)
    rings_b = decode_rings_payload(payload_b, precision=precision)
    pairs = []
    for ra, rb in zip(rings_a, rings_b):
        pa = np.asarray(ra, dtype=np.float64)
        pb = np.asarray(rb, dtype=np.float64)
        if _signed_area(pa) < 0.0:
            pa = pa[::-1]
        if _signed_area(pb) < 0.0:
            pb = pb[::-1]
        m = samples if samples is not None else min(1024, max(8, len(pa), len(pb)))
        sa = resample_closed(pa, m)
        sb = align_cyclic(sa, resample_closed(pb, m))
        pairs.append((sa, sb))
    if len(_MORPH_CACHE) > 4096:
        _MORPH_CACHE.clear()
    _MORPH_CACHE[key] = pairs
    return pairs


def morph_rings(item: MorphNode, precision: str, env: dict[str, float]) -> list[list[tuple[float, float]]]:
    u = _clamp01(_eval_num(item.u, env))
    if u <= 0.0:
        return decode_rings_payload(item.payload_a, precision=precision)
    if u >= 1.0:
        return decode_rings_payload(item.payload_b, precision=precision)
    out = []
    for sa, sb in morph_pairs(item.payload_a, item.payload_b, precision, item.samples):
        ring = sa + (sb - sa) * u
        out.append([(float(x), float(y)) for x, y in ring])
    return out


# ------------------------------------------------------------- paint list
class _Paint:
    """One paint-list entry: a named layer with an evaluated colour, rings and opacity.

    `groups` is the tuple of enclosing group-opacity scopes `(group_id, opacity)`
    opened by `use ...(opacity: ...)` in spec 0.4 documents.
    """

    __slots__ = ("name", "color", "rings", "opacity", "groups")

    def __init__(self, name, color, rings, opacity=1.0, groups=()):
        self.name = name
        self.color = color
        self.rings = rings
        self.opacity = opacity
        self.groups = groups

    def as_tuple(self):
        return (self.name, self.color, self.rings)


def _expand_paint(
    items: list[SceneItem],
    defs: dict[str, DefBlock],
    precision: str,
    env: dict[str, float],
    seed: int,
    frame_idx: int,
    spec04: bool = True,
) -> list[_Paint]:
    """Expands scene items and `use` blocks into the ordered paint list."""
    layers_out: list[_Paint] = []
    named_index: dict[str, int] = {}
    group_counter = [0]

    def upsert_layer(name, color, rings, opacity, groups) -> None:
        paint = _Paint(name, color, rings, opacity, groups)
        if name in named_index:
            layers_out[named_index[name]] = paint
        else:
            named_index[name] = len(layers_out)
            layers_out.append(paint)

    def opacity_of(item, local_env) -> float:
        expr = getattr(item, "opacity", None)
        if expr is None or not spec04:
            return 1.0
        return _clamp01(_eval_num(expr, local_env))

    def add_outline(name, rings, outline_color, outline_width, opacity, groups, local_env) -> None:
        if outline_color is None or outline_width <= 0.0:
            return
        stroke_rings: list[list[tuple[float, float]]] = []
        for r in rings:
            if len(r) >= 3:
                closed = list(r) + [r[0]]
                sr = _stroke_to_ring(closed, outline_width, outline_width)
                if len(sr) >= 3:
                    stroke_rings.append(sr)
        if stroke_rings:
            upsert_layer(f"{name}__outline", resolve_color(outline_color, local_env), stroke_rings, opacity, groups)

    def process_list(seq: list[SceneItem], local_env: dict[str, float], groups: tuple) -> None:
        for item_idx, item in enumerate(seq):
            if isinstance(item, TransformNode):
                sx, sy = (_eval_num(v, local_env) for v in item.scale)
                ax, ay = (_eval_num(v, local_env) for v in item.anchor)
                dx, dy = (_eval_num(v, local_env) for v in item.translate)
                angle = _eval_num(item.rotate, local_env) * math.pi / 180.0
                c, s = math.cos(angle), math.sin(angle)
                found = item.target_name == "all"
                for paint in layers_out:
                    nm = paint.name
                    if item.target_name != "all" and nm not in (item.target_name, item.target_name+"__outline"):
                        continue
                    found = True
                    transformed = []
                    for ring in paint.rings:
                        pts = []
                        for x, y in ring:
                            u, v = (x-ax)*sx, (y-ay)*sy
                            pts.append((ax+u*c-v*s+dx, ay+u*s+v*c+dy))
                        transformed.append(pts)
                    paint.rings = transformed
                if not found:
                    raise NorthCelEvaluationError(f"Transform target '{item.target_name}' has not been painted", item.span.line, item.span.column)
                continue
            if isinstance(item, DropNode):
                if item.target_name in named_index:
                    layers_out[named_index[item.target_name]] = _Paint(item.target_name, ColorValue.from_tone(0), [])
                out_key = f"{item.target_name}__outline"
                if out_key in named_index:
                    layers_out[named_index[out_key]] = _Paint(out_key, ColorValue.from_tone(0), [])
                continue

            if isinstance(item, UseNode):
                d = defs[item.def_name]
                child_env = dict(local_env)
                child_env.update(d.params)
                for k, v in item.args.items():
                    child_env[k] = _eval_num(v, local_env)
                dx = float(child_env.get("dx", 0.0))
                dy = float(child_env.get("dy", 0.0))
                child_groups = groups
                if spec04 and "opacity" in item.args:
                    group_opacity = _clamp01(child_env["opacity"])
                    if group_opacity < 1.0:
                        group_counter[0] += 1
                        child_groups = groups + ((group_counter[0], group_opacity),)
                before_len = len(layers_out)
                process_list(list(d.items), child_env, child_groups)
                if abs(dx) > 1e-9 or abs(dy) > 1e-9:
                    for paint in layers_out[before_len:]:
                        paint.rings = [[(x + dx, y + dy) for x, y in r] for r in paint.rings]
                continue

            if isinstance(item, LayerNode):
                raw_rings = decode_rings_payload(item.payload, precision=precision)
                tx = _eval_num(item.translate_expr[0], local_env)
                ty = _eval_num(item.translate_expr[1], local_env)
                final_rings: list[list[tuple[float, float]]] = []
                for ri, r in enumerate(raw_rings):
                    pts: list[tuple[float, float]] = []
                    for vi, (x, y) in enumerate(r):
                        bx, by = boil_offset(seed, frame_idx, item_idx, ri, vi, item.boil)
                        pts.append((x + tx + bx, y + ty + by))
                    final_rings.append(pts)
                opacity = opacity_of(item, local_env)
                upsert_layer(item.name, resolve_color(item.color, local_env), final_rings, opacity, groups)
                add_outline(item.name, final_rings, item.outline_color, item.outline_width, opacity, groups, local_env)

            elif isinstance(item, MorphNode):
                rings = morph_rings(item, precision, local_env)
                opacity = opacity_of(item, local_env)
                upsert_layer(item.name, resolve_color(item.color, local_env), rings, opacity, groups)
                add_outline(item.name, rings, item.outline_color, item.outline_width, opacity, groups, local_env)

            elif isinstance(item, SwarmNode):
                raw_rings = decode_rings_payload(item.payload, precision=precision)
                tx = _eval_num(item.translate_expr[0], local_env)
                ty = _eval_num(item.translate_expr[1], local_env)
                final_rings = []
                for ri, r in enumerate(raw_rings):
                    pts = []
                    for vi, (x, y) in enumerate(r):
                        bx, by = boil_offset(seed, frame_idx, item_idx + 1000, ri, vi, item.boil)
                        pts.append((x + tx + bx, y + ty + by))
                    final_rings.append(pts)

                # If this is a shower-style `water_droplets` or `beard_and_chest_bristles`
                # swarm and the matching host layer exists, merge into it so even-odd
                # aperture cutouts match the MoonBit + Bend + GLSL pipeline identically!
                if item.name == "water_droplets" and "tile_wall" in named_index:
                    layers_out[named_index["tile_wall"]].rings.extend(final_rings)
                elif item.name == "beard_and_chest_bristles" and "ink_contours" in named_index:
                    layers_out[named_index["ink_contours"]].rings.extend(final_rings)
                else:
                    layers_out.append(_Paint(item.name, resolve_color(item.color, local_env), final_rings,
                                             opacity_of(item, local_env), groups))

            elif isinstance(item, StrokeNode):
                pts_eval: list[tuple[float, float]] = []
                for vi, (xe, ye) in enumerate(item.points):
                    x = _eval_num(xe, local_env)
                    y = _eval_num(ye, local_env)
                    bx, by = boil_offset(seed, frame_idx, item_idx + 2000, 0, vi, item.boil)
                    pts_eval.append((x + bx, y + by))
                ring = _stroke_to_ring(pts_eval, item.width_start, item.width_end)
                if len(ring) >= 3:
                    layers_out.append(_Paint(item.name, resolve_color(item.color, local_env), [ring],
                                             opacity_of(item, local_env), groups))

            elif isinstance(item, RibbonNode):
                pts_w: list[tuple[float, float, float]] = []
                for vi, (xe, ye, w) in enumerate(item.points):
                    x = _eval_num(xe, local_env)
                    y = _eval_num(ye, local_env)
                    bx, by = boil_offset(seed, frame_idx, item_idx + 3000, 0, vi, item.boil)
                    pts_w.append((x + bx, y + by, w))
                ring = _ribbon_to_ring(pts_w)
                if len(ring) >= 3:
                    layers_out.append(_Paint(item.name, resolve_color(item.color, local_env), [ring],
                                             opacity_of(item, local_env), groups))

    process_list(items, env, ())
    return layers_out


def _expand_items(
    items: list[SceneItem],
    defs: dict[str, DefBlock],
    precision: str,
    env: dict[str, float],
    seed: int,
    frame_idx: int,
) -> list[tuple[str, ColorValue, list[list[tuple[float, float]]]]]:
    """Expands scene items into ordered (name, color, rings) layers.

    Kept for callers written against tools 0.4. Opacity and group opacity are
    not represented in this view; use `_expand_paint` for the full paint list.
    """
    return [p.as_tuple() for p in _expand_paint(items, defs, precision, env, seed, frame_idx)]


# ------------------------------------------------------------ rasteriser
_CHUNK = 1 << 22  # subpixels written per vectorised batch


def _layer_spans(
    rings: list[list[tuple[float, float]]], aa: int, sh: int, sw: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    """Even-odd spans (row, ix0, ix1) for one layer on the subpixel grid.

    Exactly the rule of spec 0.1 §6: a subpixel row `sy` samples `py = sy + 0.5`;
    an edge is active when `(y0 > py) != (y1 > py)`; crossings
    `x0 + (py - y0) * (x1 - x0) / (y1 - y0)` are sorted, mapped to
    `clip(ceil(x - 0.5), 0, sw)` and paired. Vectorised over all rows at once; the
    arithmetic and the pairing are the same as the per-row loop it replaces, so the
    covered subpixels are identical.
    """
    ys0: list[float] = []
    xs0: list[float] = []
    ys1: list[float] = []
    xs1: list[float] = []
    for ring in rings:
        if len(ring) < 3:
            continue
        for (ax, ay), (bx, by) in zip(ring, ring[1:] + ring[:1]):
            if ay != by:
                ys0.append(ay * aa)
                xs0.append(ax * aa)
                ys1.append(by * aa)
                xs1.append(bx * aa)
    if not ys0:
        return None
    y0 = np.asarray(ys0, dtype=np.float64)
    x0 = np.asarray(xs0, dtype=np.float64)
    y1 = np.asarray(ys1, dtype=np.float64)
    x1 = np.asarray(xs1, dtype=np.float64)
    inv_dy = (x1 - x0) / (y1 - y0)
    ymin = np.minimum(y0, y1)
    ymax = np.maximum(y0, y1)
    # Candidate rows: ymin <= sy + 0.5 < ymax, clipped to the canvas.
    lo = np.clip(np.ceil(ymin - 0.5), 0, sh).astype(np.int64)
    hi = np.clip(np.ceil(ymax - 0.5), 0, sh).astype(np.int64)
    counts = np.maximum(hi - lo, 0)
    total = int(counts.sum())
    if total == 0:
        return None
    edge = np.repeat(np.arange(len(y0)), counts)
    row = np.arange(total, dtype=np.int64) - np.repeat(np.cumsum(counts) - counts, counts) + np.repeat(lo, counts)
    py = row + 0.5
    ey0 = y0[edge]
    active = (ey0 > py) != (y1[edge] > py)
    if not active.all():
        edge, row, py, ey0 = edge[active], row[active], py[active], ey0[active]
    cross = x0[edge] + (py - ey0) * inv_dy[edge]
    order = np.lexsort((cross, row))
    row = row[order]
    ix = np.clip(np.ceil(cross[order] - 0.5).astype(np.int64), 0, sw)
    if len(row) % 2 or np.any(row[0::2] != row[1::2]):
        # A row with an odd crossing count cannot come from closed rings; keep the
        # per-row rule (the unmatched last crossing of a row is ignored).
        rows_out, a_out, b_out = [], [], []
        start = 0
        n = len(row)
        while start < n:
            end = start
            while end < n and row[end] == row[start]:
                end += 1
            for k in range(start, end - 1, 2):
                rows_out.append(row[start])
                a_out.append(ix[k])
                b_out.append(ix[k + 1])
            start = end
        rows = np.asarray(rows_out, dtype=np.int64)
        a = np.asarray(a_out, dtype=np.int64)
        b = np.asarray(b_out, dtype=np.int64)
    else:
        rows, a, b = row[0::2], ix[0::2], ix[1::2]
    keep = a < b
    return rows[keep], a[keep], b[keep]


def _span_indices(rows: np.ndarray, a: np.ndarray, b: np.ndarray, sw: int):
    """Yield flat subpixel indices covered by the spans, in bounded batches."""
    lengths = b - a
    starts = rows * sw + a
    n = len(lengths)
    i = 0
    while i < n:
        csum = np.cumsum(lengths[i:])
        j = i + max(1, int(np.searchsorted(csum, _CHUNK, side="right")))
        ln = lengths[i:j]
        st = starts[i:j]
        tot = int(ln.sum())
        offs = np.repeat(st - (np.cumsum(ln) - ln), ln)
        yield offs + np.arange(tot, dtype=np.int64)
        i = j


def _paint_spans(flat: np.ndarray, spans, color: ColorValue, opacity: float, grey: bool, sw: int) -> None:
    rows, a, b = spans
    if grey:
        if opacity >= 1.0:
            if len(rows) < 64 or int((b - a).sum()) > 48 * len(rows):
                for r, x0, x1 in zip(rows.tolist(), a.tolist(), b.tolist()):
                    flat[r * sw + x0 : r * sw + x1] = color.r
                return
            for idx in _span_indices(rows, a, b, sw):
                flat[idx] = color.r
            return
        for idx in _span_indices(rows, a, b, sw):
            dst = flat[idx].astype(np.float64)
            flat[idx] = np.floor(dst + (color.r - dst) * opacity + 0.5).astype(np.uint8)
        return
    col = np.asarray(color.as_rgb_tuple(), dtype=np.uint8)
    if opacity >= 1.0:
        # Long spans: a slice per span beats building a large index array.
        if len(rows) < 64 or int((b - a).sum()) > 48 * len(rows):
            for r, x0, x1 in zip(rows.tolist(), a.tolist(), b.tolist()):
                flat[r * sw + x0 : r * sw + x1] = col
            return
        for idx in _span_indices(rows, a, b, sw):
            flat[idx] = col
        return
    colf = col.astype(np.float64)
    for idx in _span_indices(rows, a, b, sw):
        dst = flat[idx].astype(np.float64)
        flat[idx] = np.floor(dst + (colf - dst) * opacity + 0.5).astype(np.uint8)


def _box_mean(canvas: np.ndarray, aa: int) -> np.ndarray:
    """Mean of each aa x aa subpixel block, as float64.

    The sum of at most 64 8-bit values is exact in uint16 and the float mean of
    integers is exact too, so this equals `reshape(...).mean(axis=(1, 3))` bit for
    bit; it is just several times faster.
    """
    rows = np.zeros(canvas[::aa].shape, dtype=np.uint16)
    for i in range(aa):
        rows += canvas[i::aa]          # whole rows: contiguous adds
    acc = np.zeros(canvas[::aa, ::aa].shape, dtype=np.uint16)
    for j in range(aa):
        acc += rows[:, j::aa]
    return acc / float(aa * aa)


def _rasterize_paint(
    width: int,
    height: int,
    paper: PaperSpec,
    paper_color: ColorValue,
    paints: list[_Paint],
    seed: int,
) -> np.ndarray:
    """Rasterizes the paint list at `N x N` subpixel resolution with exact even-odd parity.

    Opaque layers overwrite covered subpixels (spec 0.1). Spec 0.4 opacity blends
    each covered subpixel channel as `floor(c + (s - c) * a + 0.5)` on the 8-bit
    subpixel canvas; a group (`use ...(opacity: a)`) paints its layers onto the
    canvas, then every subpixel is blended back towards the pre-group canvas with
    the same formula.
    """
    aa = max(1, int(paper.antialias_grid))
    sh = height * aa
    sw = width * aa

    all_grey = paper_color.is_grey and all(p.color.is_grey for p in paints)
    if all_grey:
        canvas = np.full((sh, sw), paper_color.r, dtype=np.uint8)
        flat = canvas.reshape(-1)
    else:
        canvas = np.empty((sh, sw, 3), dtype=np.uint8)
        canvas[:, :, 0] = paper_color.r
        canvas[:, :, 1] = paper_color.g
        canvas[:, :, 2] = paper_color.b
        flat = canvas.reshape(-1, 3)

    # Open group-opacity scopes: (group_id, opacity, snapshot of the canvas).
    stack: list[tuple[int, float, np.ndarray]] = []

    def close_group() -> None:
        _gid, gop, snap = stack.pop()
        changed = canvas != snap
        if changed.ndim == 3:
            changed = changed.any(axis=2)
        if not changed.any():
            return
        rows = np.flatnonzero(changed.any(axis=1))
        r0, r1 = int(rows[0]), int(rows[-1]) + 1
        src = snap[r0:r1].astype(np.float64)
        dst = canvas[r0:r1].astype(np.float64)
        canvas[r0:r1] = np.floor(src + (dst - src) * gop + 0.5).astype(np.uint8)

    for paint in paints:
        groups = paint.groups
        # A paint that cannot change a subpixel is not an event: it neither opens
        # nor closes a group scope.
        if not paint.rings or paint.opacity <= 0.0 or any(gop <= 0.0 for _gid, gop in groups):
            continue
        # Close scopes that this paint is not inside, then open its new scopes.
        while stack and (len(stack) > len(groups) or stack[-1][0] != groups[len(stack) - 1][0]):
            close_group()
        for gid, gop in groups[len(stack):]:
            stack.append((gid, gop, canvas.copy()))
        spans = _layer_spans(paint.rings, aa, sh, sw)
        if spans is None:
            continue
        _paint_spans(flat, spans, paint.color, paint.opacity, all_grey, sw)
    while stack:
        close_group()

    if all_grey:
        if aa > 1:
            avg = _box_mean(canvas, aa)
        else:
            avg = canvas.astype(np.float64)
        if paper.grain > 0.0:
            yy, xx = np.mgrid[0:height, 0:width]
            h = ((xx * 374761393 + yy * 668265263 + seed * 1442695041) & 0xFFFFFFFF).astype(np.float64)
            noise = (np.sin(h * 0.0001) * 0.5) * (paper.grain * 255.0)
            avg = np.clip(avg + noise, 0.0, 255.0)
        u8 = np.clip(np.floor(avg + 0.5), 0, 255).astype(np.uint8)
        return np.repeat(u8[:, :, None], 3, axis=2)

    if aa > 1:
        avg_rgb = _box_mean(canvas, aa)
    else:
        avg_rgb = canvas.astype(np.float64)
    if paper.grain > 0.0:
        yy, xx = np.mgrid[0:height, 0:width]
        h = ((xx * 374761393 + yy * 668265263 + seed * 1442695041) & 0xFFFFFFFF).astype(np.float64)
        noise = (np.sin(h * 0.0001) * 0.5) * (paper.grain * 255.0)
        avg_rgb = np.clip(avg_rgb + noise[:, :, None], 0.0, 255.0)
    return np.clip(np.floor(avg_rgb + 0.5), 0, 255).astype(np.uint8)


def _rasterize_layers_subpixel(
    width: int,
    height: int,
    paper: PaperSpec,
    layers: list[tuple[str, ColorValue, list[list[tuple[float, float]]]]],
    seed: int,
) -> np.ndarray:
    """Tools-0.4 entry point: opaque (name, colour, rings) layers over a static paper."""
    paints = [_Paint(name, color, rings) for name, color, rings in layers]
    return _rasterize_paint(width, height, paper, resolve_color(paper.color, {}), paints, seed)


def _spec04(doc: DocumentNode) -> bool:
    parts = doc.spec_version.split("-", 1)[0].split(".")
    try:
        return not (parts[0] == "0" and len(parts) > 1 and int(parts[1]) < 4)
    except ValueError:
        return True


def frame_paint_list(doc: DocumentNode, frame_index: int = 0, seed_override: int | None = None):
    """(paper spec, evaluated paper colour, paint list) for one frame. Pure."""
    root = doc.root
    seed = seed_override if seed_override is not None else root.seed
    spec04 = _spec04(doc)

    if isinstance(root, SceneNode):
        env = {"t": 0.0, "f": float(frame_index), "seed": float(seed)}
        paints = _expand_paint(root.items, root.defs, root.precision, env, seed, frame_index, spec04)
        return root.paper, resolve_color(root.paper.color, env), paints

    total_frames = max(1, root.frames)
    t_norm = frame_index / float(max(1, total_frames - 1)) if total_frames > 1 else 0.0
    env = {"t": t_norm, "f": float(frame_index), "seed": float(seed)}

    ov = root.override_for(frame_index)
    if ov is not None:
        merged_defs = {**root.defs, **ov.defs}
        combined_items = list(root.items) + list(ov.items)
        paints = _expand_paint(combined_items, merged_defs, ov.precision, env, seed, frame_index, spec04)
        return ov.paper, resolve_color(ov.paper.color, env), paints

    paints = _expand_paint(root.items, root.defs, root.precision, env, seed, frame_index, spec04)
    return root.paper, resolve_color(root.paper.color, env), paints


def render_document_frame(
    doc: DocumentNode,
    frame_index: int = 0,
    seed_override: int | None = None,
) -> np.ndarray:
    """Renders a single frame `frame_index` from a NorthCel DocumentNode to an (H, W, 3) uint8 RGB array."""
    root = doc.root
    seed = seed_override if seed_override is not None else root.seed
    paper, paper_color, paints = frame_paint_list(doc, frame_index, seed_override)
    return _rasterize_paint(root.width, root.height, paper, paper_color, paints, seed)


def render_film_frames(
    doc: DocumentNode,
    out_dir: str | Path,
    frame_indices: list[int] | None = None,
    mp4_path: str | Path | None = None,
) -> dict[str, Any]:
    """Renders multiple frames of a scene or film to PNGs and optionally muxes an MP4 via ffmpeg."""
    import shutil
    import subprocess

    out_p = Path(out_dir)
    out_p.mkdir(parents=True, exist_ok=True)
    root = doc.root
    n_frames = root.frames if isinstance(root, FilmNode) else 1
    indices = frame_indices if frame_indices is not None else list(range(n_frames))

    written_pngs: list[str] = []
    for idx in indices:
        rgb = render_document_frame(doc, frame_index=idx)
        png_file = out_p / f"f{idx:04d}.png"
        Image.fromarray(rgb, mode="RGB").save(png_file)
        written_pngs.append(str(png_file))

    mp4_written: str | None = None
    if mp4_path is not None:
        ffmpeg_bin = shutil.which("ffmpeg")
        if ffmpeg_bin and len(written_pngs) > 0:
            mp4_out = Path(mp4_path)
            mp4_out.parent.mkdir(parents=True, exist_ok=True)
            cmd = [
                ffmpeg_bin,
                "-y",
                "-framerate",
                str(root.fps),
                "-i",
                str(out_p / "f%04d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                str(mp4_out),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            if proc.returncode == 0 and mp4_out.is_file():
                mp4_written = str(mp4_out)

    return {
        "ok": True,
        "frames_rendered": len(written_pngs),
        "fps": root.fps,
        "width": root.width,
        "height": root.height,
        "frame_paths": written_pngs,
        "mp4_path": mp4_written,
    }
