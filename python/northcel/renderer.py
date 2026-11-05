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
    ColorValue,
    DefBlock,
    DocumentNode,
    DropNode,
    FilmNode,
    LayerNode,
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


def _expand_items(
    items: list[SceneItem],
    defs: dict[str, DefBlock],
    precision: str,
    env: dict[str, float],
    seed: int,
    frame_idx: int,
) -> list[tuple[str, ColorValue, list[list[tuple[float, float]]]]]:
    """Expands scene items and `use` blocks into ordered (name, color, rings) layers."""
    layers_out: list[tuple[str, ColorValue, list[list[tuple[float, float]]]]] = []
    named_index: dict[str, int] = {}

    def upsert_layer(name: str, color: ColorValue, rings: list[list[tuple[float, float]]]) -> None:
        if name in named_index:
            layers_out[named_index[name]] = (name, color, rings)
        else:
            named_index[name] = len(layers_out)
            layers_out.append((name, color, rings))

    def process_list(seq: list[SceneItem], local_env: dict[str, float]) -> None:
        for item_idx, item in enumerate(seq):
            if isinstance(item, TransformNode):
                sx, sy = (_eval_num(v, local_env) for v in item.scale)
                ax, ay = (_eval_num(v, local_env) for v in item.anchor)
                dx, dy = (_eval_num(v, local_env) for v in item.translate)
                angle = _eval_num(item.rotate, local_env) * math.pi / 180.0
                c, s = math.cos(angle), math.sin(angle)
                found = item.target_name == "all"
                for li, (nm, col, rings) in enumerate(layers_out):
                    if item.target_name != "all" and nm not in (item.target_name, item.target_name+"__outline"):
                        continue
                    found = True
                    transformed = []
                    for ring in rings:
                        pts = []
                        for x, y in ring:
                            u, v = (x-ax)*sx, (y-ay)*sy
                            pts.append((ax+u*c-v*s+dx, ay+u*s+v*c+dy))
                        transformed.append(pts)
                    layers_out[li] = (nm, col, transformed)
                if not found:
                    raise NorthCelEvaluationError(f"Transform target '{item.target_name}' has not been painted", item.span.line, item.span.column)
                continue
            if isinstance(item, DropNode):
                if item.target_name in named_index:
                    layers_out[named_index[item.target_name]] = (item.target_name, ColorValue.from_tone(0), [])
                out_key = f"{item.target_name}__outline"
                if out_key in named_index:
                    layers_out[named_index[out_key]] = (out_key, ColorValue.from_tone(0), [])
                continue

            if isinstance(item, UseNode):
                d = defs[item.def_name]
                child_env = dict(local_env)
                child_env.update(d.params)
                for k, v in item.args.items():
                    child_env[k] = _eval_num(v, local_env)
                dx = float(child_env.get("dx", 0.0))
                dy = float(child_env.get("dy", 0.0))
                before_len = len(layers_out)
                process_list(list(d.items), child_env)
                if abs(dx) > 1e-9 or abs(dy) > 1e-9:
                    for li in range(before_len, len(layers_out)):
                        nm, col, rlist = layers_out[li]
                        shifted = [[(x + dx, y + dy) for x, y in r] for r in rlist]
                        layers_out[li] = (nm, col, shifted)
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
                upsert_layer(item.name, item.color, final_rings)

                if item.outline_color is not None and item.outline_width > 0.0:
                    stroke_rings: list[list[tuple[float, float]]] = []
                    for r in final_rings:
                        if len(r) >= 3:
                            closed = list(r) + [r[0]]
                            sr = _stroke_to_ring(closed, item.outline_width, item.outline_width)
                            if len(sr) >= 3:
                                stroke_rings.append(sr)
                    if stroke_rings:
                        upsert_layer(f"{item.name}__outline", item.outline_color, stroke_rings)

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
                    layers_out[named_index["tile_wall"]][2].extend(final_rings)
                elif item.name == "beard_and_chest_bristles" and "ink_contours" in named_index:
                    layers_out[named_index["ink_contours"]][2].extend(final_rings)
                else:
                    layers_out.append((item.name, item.color, final_rings))

            elif isinstance(item, StrokeNode):
                pts_eval: list[tuple[float, float]] = []
                for vi, (xe, ye) in enumerate(item.points):
                    x = _eval_num(xe, local_env)
                    y = _eval_num(ye, local_env)
                    bx, by = boil_offset(seed, frame_idx, item_idx + 2000, 0, vi, item.boil)
                    pts_eval.append((x + bx, y + by))
                ring = _stroke_to_ring(pts_eval, item.width_start, item.width_end)
                if len(ring) >= 3:
                    layers_out.append((item.name, item.color, [ring]))

            elif isinstance(item, RibbonNode):
                pts_w: list[tuple[float, float, float]] = []
                for vi, (xe, ye, w) in enumerate(item.points):
                    x = _eval_num(xe, local_env)
                    y = _eval_num(ye, local_env)
                    bx, by = boil_offset(seed, frame_idx, item_idx + 3000, 0, vi, item.boil)
                    pts_w.append((x + bx, y + by, w))
                ring = _ribbon_to_ring(pts_w)
                if len(ring) >= 3:
                    layers_out.append((item.name, item.color, [ring]))

    process_list(items, env)
    return layers_out


def _rasterize_layers_subpixel(
    width: int,
    height: int,
    paper: PaperSpec,
    layers: list[tuple[str, ColorValue, list[list[tuple[float, float]]]]],
    seed: int,
) -> np.ndarray:
    """Rasterizes layers at `N x N` subpixel resolution with exact even-odd winding parity."""
    aa = max(1, int(paper.antialias_grid))
    sh = height * aa
    sw = width * aa

    all_grey = paper.color.is_grey and all(col.is_grey for _, col, _ in layers)
    if all_grey:
        canvas = np.full((sh, sw), paper.color.r, dtype=np.uint8)
    else:
        canvas = np.empty((sh, sw, 3), dtype=np.uint8)
        canvas[:, :, 0] = paper.color.r
        canvas[:, :, 1] = paper.color.g
        canvas[:, :, 2] = paper.color.b

    band_h = 8 * aa
    for _, color, rings in layers:
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
            continue

        y0 = np.asarray(ys0, dtype=np.float64)
        x0 = np.asarray(xs0, dtype=np.float64)
        y1 = np.asarray(ys1, dtype=np.float64)
        x1 = np.asarray(xs1, dtype=np.float64)
        ymin = np.minimum(y0, y1)
        ymax = np.maximum(y0, y1)
        inv_dy = (x1 - x0) / (y1 - y0)

        c_r, c_g, c_b = color.r, color.g, color.b
        for b0 in range(0, sh, band_h):
            b1 = min(sh, b0 + band_h)
            mask = (ymin < b1) & (ymax > b0)
            if not np.any(mask):
                continue
            by0 = y0[mask]
            bx0 = x0[mask]
            by1 = y1[mask]
            binv = inv_dy[mask]
            for sy in range(b0, b1):
                py = sy + 0.5
                active = (by0 > py) != (by1 > py)
                if not np.any(active):
                    continue
                cross = bx0[active] + (py - by0[active]) * binv[active]
                cross.sort()
                ix = np.clip(np.ceil(cross - 0.5).astype(np.int32), 0, sw)
                if all_grey:
                    row = canvas[sy]
                    for k in range(0, len(ix) - 1, 2):
                        if ix[k] < ix[k + 1]:
                            row[ix[k] : ix[k + 1]] = c_r
                else:
                    row = canvas[sy]
                    for k in range(0, len(ix) - 1, 2):
                        if ix[k] < ix[k + 1]:
                            row[ix[k] : ix[k + 1], 0] = c_r
                            row[ix[k] : ix[k + 1], 1] = c_g
                            row[ix[k] : ix[k + 1], 2] = c_b

    if all_grey:
        if aa > 1:
            avg = canvas.reshape(height, aa, width, aa).mean(axis=(1, 3))
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
        avg_rgb = canvas.reshape(height, aa, width, aa, 3).mean(axis=(1, 3))
    else:
        avg_rgb = canvas.astype(np.float64)
    if paper.grain > 0.0:
        yy, xx = np.mgrid[0:height, 0:width]
        h = ((xx * 374761393 + yy * 668265263 + seed * 1442695041) & 0xFFFFFFFF).astype(np.float64)
        noise = (np.sin(h * 0.0001) * 0.5) * (paper.grain * 255.0)
        avg_rgb = np.clip(avg_rgb + noise[:, :, None], 0.0, 255.0)
    return np.clip(np.floor(avg_rgb + 0.5), 0, 255).astype(np.uint8)


def render_document_frame(
    doc: DocumentNode,
    frame_index: int = 0,
    seed_override: int | None = None,
) -> np.ndarray:
    """Renders a single frame `frame_index` from a NorthCel DocumentNode to an (H, W, 3) uint8 RGB array."""
    root = doc.root
    seed = seed_override if seed_override is not None else root.seed

    if isinstance(root, SceneNode):
        env = {"t": 0.0, "f": float(frame_index), "seed": float(seed)}
        layers = _expand_items(root.items, root.defs, root.precision, env, seed, frame_index)
        return _rasterize_layers_subpixel(root.width, root.height, root.paper, layers, seed)

    total_frames = max(1, root.frames)
    t_norm = frame_index / float(max(1, total_frames - 1)) if total_frames > 1 else 0.0
    env = {"t": t_norm, "f": float(frame_index), "seed": float(seed)}

    if frame_index in root.frame_overrides:
        ov = root.frame_overrides[frame_index]
        merged_defs = {**root.defs, **ov.defs}
        combined_items = list(root.items) + list(ov.items)
        layers = _expand_items(combined_items, merged_defs, ov.precision, env, seed, frame_index)
        return _rasterize_layers_subpixel(root.width, root.height, ov.paper, layers, seed)

    layers = _expand_items(root.items, root.defs, root.precision, env, seed, frame_index)
    return _rasterize_layers_subpixel(root.width, root.height, root.paper, layers, seed)


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
