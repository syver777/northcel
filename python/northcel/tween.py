"""Explicit vector correspondence experiment; it cannot judge artistic quality."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .ast_nodes import LayerNode, SceneNode
from .formatter import _fmt_paper
from .parser import parse_ncel
from .renderer import _eval_num
from .rings import decode_rings_payload, encode_ring_b63_q25


def resample(ring, samples=64):
    """Closed polygon, uniform arclength; repeated/zero-length edges are legal."""
    points = np.asarray(ring, dtype=float)
    edges = np.roll(points, -1, axis=0)-points
    lengths = np.linalg.norm(edges, axis=1)
    distance = np.r_[0.0, np.cumsum(lengths)]
    if distance[-1] == 0:
        return np.repeat(points[:1], samples, axis=0)
    at = np.arange(samples)*distance[-1]/samples
    ix = np.minimum(np.searchsorted(distance, at, side="right")-1, len(points)-1)
    u = (at-distance[ix])/np.maximum(lengths[ix], 1e-15)
    return points[ix]+edges[ix]*u[:, None]


def align_ring(left, right, samples=64):
    a, b = resample(left, samples), resample(right, samples)
    # Winding and cyclic start are representation choices, not content choices.
    choices = [(float(np.sum((a-np.roll(c, k, axis=0))**2)), flip, k)
               for flip, c in enumerate((b, b[::-1])) for k in range(samples)]
    _, flip, k = min(choices)
    return a, np.roll(b if flip == 0 else b[::-1], k, axis=0)


def tween_sources(left: str, right: str, steps: int = 4, samples: int = 64,
                  fallback: str = "error") -> tuple[str, dict]:
    if steps < 2 or not 3 <= samples <= 512 or fallback not in ("error", "hold"):
        raise ValueError("steps >=2, samples 3..512, fallback error|hold required")
    a, b = parse_ncel(left).root, parse_ncel(right).root
    if not isinstance(a, SceneNode) or not isinstance(b, SceneNode):
        raise ValueError("Tween inputs must be plain layer/cel scenes, not films")
    if (a.width, a.height) != (b.width, b.height):
        raise ValueError("Tween canvas sizes differ")
    if a.defs or b.defs or any(not isinstance(it, LayerNode) for it in a.items+b.items):
        raise ValueError("Tween inputs must be plain layer/cel scenes without defs")
    try:
        has_motion = any(it.boil or any(_eval_num(v, {}) != 0 for v in it.translate_expr) or it.outline_width for it in a.items+b.items)
    except KeyError:
        has_motion = True
    if has_motion:
        raise ValueError("Bake input outlines/motion before tweening")
    paired = []
    reason = None
    def paper_key(p):
        return p.color.as_rgb_tuple(), p.antialias_grid, p.grain
    if len(a.items) != len(b.items) or paper_key(a.paper) != paper_key(b.paper):
        reason = "layer count or paper differs"
    else:
        for x, y in zip(a.items, b.items):
            ra = decode_rings_payload(x.payload, a.precision)
            rb = decode_rings_payload(y.payload, b.precision)
            if x.name != y.name or x.color.as_rgb_tuple() != y.color.as_rgb_tuple() or len(ra) != len(rb):
                reason = "layer identity, colour or ring topology differs"
                break
            # Rings pair by source order. Authors can reorder them explicitly;
            # nearest-looking contours are NOT evidence of semantic identity.
            paired.append((x, [align_ring(r, s, samples) for r, s in zip(ra, rb)]))
    if reason and fallback == "error":
        raise ValueError("Tween correspondence mismatch: "+reason)
    lines = ['northcel "0.3.0-draft"',
             f'film Tween(width: {a.width}, height: {a.height}, fps: 24, frames: {steps+1}, precision: 0.25px-b63) {{',
             _fmt_paper(a.paper, palette={})]
    for f in range(steps+1):
        lines.append(f"  frame {f} {{")
        if reason or f in (0, steps):
            node = a if f < steps else b
            lines.append(_fmt_paper(node.paper, "    ", palette={}))
            for it in node.items:
                rings = decode_rings_payload(it.payload, node.precision)
                payload = it.payload if node.precision == "0.25px-b63" else "|".join(encode_ring_b63_q25(r) for r in rings)
                lines.append(f'    layer {it.name}(color: {it.color.to_hex()}) {{ "{payload}" }}')
        else:
            for it, rings in paired:
                u = f/steps
                payload = "|".join(encode_ring_b63_q25((p+(q-p)*u).tolist()) for p, q in rings)
                lines.append(f'    layer {it.name}(color: {it.color.to_hex()}) {{ "{payload}" }}')
        lines.append("  }")
    lines.append("}")
    return "\n".join(lines)+"\n", {"tool": "northcel-tween/1", "mode": "hold" if reason else "contour",
                                           "reason": reason, "frames": steps+1, "quality": "unreviewed"}


def main(argv=None):
    p = argparse.ArgumentParser(prog="northcel tween", description=__doc__)
    p.add_argument("left")
    p.add_argument("right")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--steps", type=int, default=4)
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--fallback", choices=("error", "hold"), default="error")
    a = p.parse_args(argv)
    try:
        source, receipt = tween_sources(Path(a.left).read_text(), Path(a.right).read_text(), a.steps, a.samples, a.fallback)
        Path(a.out).write_text(source)
        print(json.dumps(receipt))
        return 0
    except (OSError, ValueError) as exc:
        p.error(str(exc))
