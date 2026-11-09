"""Contour in-betweens; they cannot judge artistic quality.

Default mode: explicit correspondence. Both drawings must have the same layers
and ring topology; ring i pairs with ring i, and a mismatch is an error unless
`--fallback hold` is given.

`--match` mode: shape correspondence across topology mismatch (for example two
independently generated drawings fitted with `northcel fit`). Both drawings are
stacked into painter's-order shapes, matched colour-aware (Hungarian on
centroid/area), and written as one spec 0.4 film using `morph`, `mix`, `opacity`
and `frame A..B`. When the match is below the thresholds the transition becomes
an explicit cut or dissolve, and the receipt says so. See `northcel.correspond`.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from .ast_nodes import ColorMix, LayerNode, SceneNode
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
    if any(isinstance(it.color, ColorMix) or isinstance(it.outline_color, ColorMix) or it.opacity is not None
           for it in a.items+b.items) or isinstance(a.paper.color, ColorMix) or isinstance(b.paper.color, ColorMix):
        raise ValueError("Explicit tween inputs must use static colours and no opacity; try --match")
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


def _hex_rgb(text: str) -> tuple[int, int, int]:
    h = text.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        raise ValueError(f"expected a #RRGGBB colour, got {text!r}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def load_colour_changes(path: str) -> list[tuple[tuple[int, int, int], tuple[int, int, int]]]:
    """JSON list of [colourA, colourB] pairs, each "#RRGGBB" or [r, g, b]; order does not matter."""
    data = json.loads(Path(path).read_text())
    if not isinstance(data, list) or any(not isinstance(p, list) or len(p) != 2 for p in data):
        raise ValueError("--colour-changes must be a JSON list of [colourA, colourB] pairs")
    out = []
    for pair in data:
        out.append(tuple(_hex_rgb(c) if isinstance(c, str) else tuple(int(v) for v in c) for c in pair))
    return out


def match_tween(left: str, right: str, steps: int = 4, *, fps: int = 24, mode: str = "auto",
                fallback: str = "cut", min_match: float = 0.5, max_displacement: float = 32.0,
                match_cost: float = 2.0, colour_changes=(), image_a=None, image_b=None,
                gap_fraction: float = 0.5, underpaint_min_area: float = 300.0,
                antialias_grid: int = 4, easing: str = "smooth") -> tuple[str, dict]:
    """Two drawings -> a spec 0.4 film: A at frame 0, B at frame `steps`, in-betweens between."""
    from .correspond import FilmOptions, Key, MatchOptions, Transition, film_from_keys
    from .shapes import drawing_from_source

    if steps < 1:
        raise ValueError("--steps must be >= 1")
    a = drawing_from_source(left, image_a, gap_fraction=gap_fraction, underpaint_min_area=underpaint_min_area)
    b = drawing_from_source(right, image_b, gap_fraction=gap_fraction, underpaint_min_area=underpaint_min_area)
    if (a.width, a.height) != (b.width, b.height):
        raise ValueError("Tween canvas sizes differ")
    options = FilmOptions(fps=fps, frames=steps + 1, antialias_grid=antialias_grid,
                          transition_seconds=steps / fps, easing=easing, min_match=min_match,
                          max_displacement=max_displacement, fallback=fallback, name="Tween",
                          match=MatchOptions(colour_changes=colour_changes, match_cost=match_cost))
    keys = [Key(a, 0.0, "left"), Key(b, steps / fps, "right")]
    return film_from_keys(keys, [Transition(mode)], options)


def main(argv=None):
    p = argparse.ArgumentParser(prog="northcel tween", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("left")
    p.add_argument("right")
    p.add_argument("-o", "--out", required=True)
    p.add_argument("--steps", type=int, default=4)
    p.add_argument("--samples", type=int, default=64)
    p.add_argument("--fallback", choices=("error", "hold", "cut", "dissolve"), default=None,
                   help="explicit mode: error|hold (default error); --match: cut|dissolve (default cut)")
    p.add_argument("--receipt", help="write the JSON receipt here too")
    m = p.add_argument_group("--match (shape correspondence across topology mismatch, spec 0.4 output)")
    m.add_argument("--match", action="store_true", help="match stacked shapes instead of pairing rings by order")
    m.add_argument("--mode", choices=("auto", "morph", "cut", "dissolve", "hold"), default="auto",
                   help="auto morphs only when the match passes --min-match and --max-displacement")
    m.add_argument("--fps", type=int, default=24)
    m.add_argument("--min-match", type=float, default=0.5, help="minimum matched area fraction for auto morph")
    m.add_argument("--max-displacement", type=float, default=32.0, help="maximum weighted displacement (px) for auto morph")
    m.add_argument("--match-cost", type=float, default=2.0, help="pairs costing this or more stay unmatched")
    m.add_argument("--colour-changes", help='JSON [["#FEFEFE", "#EE2C2C"], ...]: colour changes a shape may make')
    m.add_argument("--image-a", help="source image of LEFT, for the see-through gap test when stacking a planar fit")
    m.add_argument("--image-b", help="source image of RIGHT")
    m.add_argument("--gap-fraction", type=float, default=0.5)
    m.add_argument("--underpaint-min-area", type=float, default=300.0)
    m.add_argument("--easing", choices=("smooth", "linear", "ease"), default="smooth")
    m.add_argument("--antialias-grid", type=int, choices=(1, 2, 4, 8), default=4)
    a = p.parse_args(argv)
    try:
        if a.match:
            fallback = a.fallback or "cut"
            if fallback not in ("cut", "dissolve"):
                raise ValueError("--match --fallback must be cut or dissolve")
            changes = load_colour_changes(a.colour_changes) if a.colour_changes else []
            source, receipt = match_tween(
                Path(a.left).read_text(), Path(a.right).read_text(), a.steps, fps=a.fps, mode=a.mode,
                fallback=fallback, min_match=a.min_match, max_displacement=a.max_displacement,
                match_cost=a.match_cost, colour_changes=changes, image_a=a.image_a, image_b=a.image_b,
                gap_fraction=a.gap_fraction, underpaint_min_area=a.underpaint_min_area,
                antialias_grid=a.antialias_grid, easing=a.easing)
        else:
            fallback = a.fallback or "error"
            if fallback not in ("error", "hold"):
                raise ValueError("--fallback cut|dissolve requires --match")
            source, receipt = tween_sources(Path(a.left).read_text(), Path(a.right).read_text(), a.steps, a.samples, fallback)
        if a.receipt:
            Path(a.receipt).write_text(json.dumps(receipt, indent=2) + "\n")
        Path(a.out).write_text(source)
        print(json.dumps(receipt))
        return 0
    except (OSError, ValueError, SyntaxError) as exc:
        p.error(str(exc))
