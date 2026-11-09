#!/usr/bin/env python3
"""Build the Phase 4 Vello fixture from a real NorthCel scene.

Writes a source/paint-list pair under ``native/vello/fixtures/``:

* ``skyline_1080.ncel`` -- a 1920x1080 NorthCel 0.5 scene that exercises the
  features the Vello prototype needs: even-odd holes, per-layer opacity,
  group opacity, clipping, a pivot transform, warp, nudge, strokes, a ribbon
  and a swarm.
* ``skyline_1080.paintlist.json`` -- the flattened paint list for frame 0,
  exported from the Python reference renderer's own ``frame_paint_list``.
* ``skyline_1080_flat.*`` -- the same scene with paper grain 0, used to
  separate rasteriser differences from grain-rounding noise.

  This is the closest existing representation to what the MoonBit stage
  flattens before rasterisation; it is NOT NCIR (see native/vello/README.md).

The script is deterministic. Run from anywhere:

    python3 native/vello/scripts/make_fixture.py
    python3 native/vello/scripts/make_fixture.py --name skyline_1080_flat --grain 0
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "python"))

from northcel.parser import parse_ncel  # noqa: E402
from northcel.renderer import frame_paint_list  # noqa: E402
from northcel.rings import encode_ring_q25  # noqa: E402

WID, HEI = 1920, 1080
FIX = Path(__file__).resolve().parents[1] / "fixtures"


def ring(pts):
    return encode_ring_q25(pts)


def payload(*rings):
    return "|".join(ring(r) for r in rings)


def circle(cx, cy, rx, ry=None, n=160, phase=0.0):
    ry = rx if ry is None else ry
    return [
        (cx + rx * math.cos(phase + 2 * math.pi * i / n),
         cy + ry * math.sin(phase + 2 * math.pi * i / n))
        for i in range(n)
    ]


def blob(cx, cy, rx, ry, lobes=9, amp=0.10, n=360, phase=0.0):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        r = 1.0 + amp * math.sin(lobes * t + phase) + 0.45 * amp * math.sin(2 * lobes * t + 0.7)
        pts.append((cx + rx * r * math.cos(t), cy + ry * r * math.sin(t)))
    return pts


def hills(top, amp, freq, phase, bottom=HEI + 80, step=16):
    pts = []
    x = -80
    while x <= WID + 80:
        y = top + amp * math.sin(x / freq + phase) + 0.35 * amp * math.sin(x / (freq * 0.31) + 1.7)
        pts.append((x, y))
        x += step
    pts.append((WID + 80, bottom))
    pts.append((-80, bottom))
    return pts


def rect(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def arch(cx, y0, half_w, top_r, y1):
    """A round-topped window outline (flat sides, semicircular top)."""
    pts = [(cx - half_w, y1), (cx - half_w, y0), ]
    for i in range(1, 48):
        a = math.pi - math.pi * i / 48.0
        pts.append((cx + top_r * math.cos(a), y0 - top_r * math.sin(a)))
    pts.append((cx + half_w, y0))
    pts.append((cx + half_w, y1))
    return pts


def build_scene(grain: float) -> str:
    cloud_a = blob(520, 220, 250, 92, lobes=8, amp=0.13, phase=0.4)
    cloud_b = blob(1390, 150, 205, 72, lobes=7, amp=0.16, phase=1.9)
    sun = circle(1585, 255, 104, n=192)
    sun_halo = circle(1585, 255, 132, n=192)
    hills_far = hills(610, 58, 260, 0.5)
    hills_near = hills(728, 42, 185, 2.1)
    ground = hills(884, 16, 130, 0.9)

    body = rect(520, 560, 880, 806)
    roof = [(478, 578), (700, 428), (922, 578)]
    chimney = rect(806, 452, 856, 548)
    door = rect(596, 682, 684, 806)
    win_mask = arch(780, 646, 46, 46, 736)
    win_frame_outer = arch(780, 644, 50, 50, 738)
    win_frame_inner = arch(780, 650, 42, 42, 730)

    trunk = [(1162, 610), (1212, 606), (1222, 884), (1174, 884)]
    canopy = blob(1196, 516, 224, 176, lobes=11, amp=0.12, phase=0.2)
    gap_a = circle(1138, 474, 22, n=48)
    gap_b = circle(1246, 548, 17, n=40)
    gap_c = circle(1178, 592, 13, n=36)

    fence = []
    for i in range(7):
        x = 1408 + i * 54
        top = 792 - 22 * math.sin(i * 1.3)
        fence.append(rect(x, top, x + 26, 884))

    birds = []
    for i, (bx, by) in enumerate(((360, 330), (402, 306), (446, 336), (900, 300), (948, 276))):
        s = 15 + 3 * (i % 2)
        birds.append([(bx - s, by), (bx, by - 9), (bx + s, by), (bx, by - 4)])

    parts = []
    parts.append('northcel "0.5.0-draft"')
    parts.append("")
    parts.append(f'scene SkylineVello(width: {WID}, height: {HEI}, fps: 12, precision: 0.25px, seed: 20261009) {{')
    parts.append(f"  paper {{ color: #BFD8E8, antialias_grid: 4, grain: {grain:g} }}")
    parts.append("")

    # Back to front. Each layer is a single even-odd path over all of its rings.
    parts.append(f'  layer sky_haze(color: #AECFE4, opacity: 0.35) {{ "{payload(hills(1010, 20, 340, 1.2))}" }}')
    parts.append(f'  layer sun_halo(color: #F6D98A, opacity: 0.35) {{ "{payload(sun_halo)}" }}')
    parts.append(f'  layer sun(color: #F2C14E) {{ "{payload(sun)}" }}')
    parts.append(f'  layer cloud_a(color: #F8F4EC) {{ "{payload(cloud_a)}" }}')
    parts.append(f'  layer cloud_b(color: #F1EDE4) {{ "{payload(cloud_b)}" }}')
    parts.append(f'  layer hills_far(color: #7FA37A) {{ "{payload(hills_far)}" }}')
    parts.append(f'  layer hills_near(color: #567B52) {{ "{payload(hills_near)}" }}')
    parts.append(f'  layer ground(color: #4F6F49) {{ "{payload(ground)}" }}')
    parts.append('  stroke horizon_ink(color: #3A4A5A, taper: (5, 3)) { (40, 702), (1880, 700) }')
    parts.append("")
    parts.append("  group house(pivot: (700, 806), opacity: 0.96) {")
    parts.append(f'    layer chimney(color: #8A5A4A) {{ "{payload(chimney)}" }}')
    parts.append(f'    layer house_body(color: #C9805A) {{ "{payload(body)}" }}')
    parts.append(f'    layer roof(color: #6B3F35) {{ "{payload(roof)}" }}')
    parts.append(f'    layer door(color: #4A2E28) {{ "{payload(door)}" }}')
    parts.append(f'    layer window_mask(color: #000000, opacity: 0) {{ "{payload(win_mask)}" }}')
    parts.append("    group glow(pivot: (780, 690), clip: window_mask, opacity: 0.62) {")
    parts.append(f'      layer window_light(color: #FFE2A0) {{ "{payload(win_mask)}" }}')
    parts.append(f'      layer window_band(color: #FFB347, opacity: 0.7) {{ "{payload(rect(736, 700, 824, 716))}" }}')
    parts.append("    }")
    parts.append(f'    layer window_frame(color: #4A2E28) {{ "{payload(win_frame_outer, win_frame_inner)}" }}')
    parts.append("  }")
    parts.append("")
    parts.append(f'  layer tree_trunk(color: #5A3B2B) {{ "{payload(trunk)}" }}')
    parts.append(f'  layer tree_canopy(color: #3F6B3F) {{ "{payload(canopy, gap_a, gap_b, gap_c)}" }}')
    parts.append(f'  layer fence(color: #9A7B55) {{ "{payload(*fence)}" }}')
    parts.append(f'  bend_swarm birds(agents: 5, color: #3A4A5A) {{ "{payload(*birds)}" }}')
    parts.append("")
    parts.append('  stroke roofline_ink(color: #2E231F, width: 4px) { (478, 578), (700, 428), (922, 578) }')
    parts.append('  stroke trunk_ink(color: #2E231F, width: 3px) { (1166, 884), (1186, 620) }')
    parts.append('  ribbon path(color: #D9C9A3) { (120, 1010, 18), (520, 970, 10), (980, 1020, 16), (1500, 980, 9), (1840, 1030, 14) }')
    parts.append("")
    parts.append("  group vane(pivot: (700, 428), opacity: 0.9) {")
    parts.append(f'    layer vane_post(color: #2E231F) {{ "{payload(rect(696, 372, 704, 430))}" }}')
    parts.append(f'    layer vane_arrow(color: #2E231F) {{ "{payload([(646, 384), (700, 366), (754, 384), (700, 376)])}" }}')
    parts.append("  }")
    parts.append("  transform vane(rotate: 12deg)")
    parts.append("  warp cloud_b(handles: ((1390, 150, 26, -14), (1250, 190, -10, 8)), radius: 260)")
    parts.append("  nudge cloud_a(vertex: 0, dx: 6px, dy: -3px)")
    parts.append("}")
    return "\n".join(parts) + "\n"


def to_json(doc, frame_index: int, source_name: str) -> dict:
    paper, paper_color, paints = frame_paint_list(doc, frame_index)
    layers = []
    for p in paints:
        layers.append(
            {
                "name": p.name,
                "color": list(p.color.as_rgb_tuple()),
                "opacity": float(p.opacity),
                "group_opacity": [[int(gid), float(op)] for gid, op in p.groups],
                "rings": [[[float(x), float(y)] for x, y in r] for r in p.rings],
                "clip_shapes": (
                    [
                        [[[float(x), float(y)] for x, y in r] for r in shape]
                        for shape in p.clip_shapes
                    ]
                    if p.clip_shapes
                    else []
                ),
            }
        )
    root = doc.root
    return {
        "format": "northcel-paintlist-v1",
        "source": source_name,
        "frame_index": frame_index,
        "width": int(root.width),
        "height": int(root.height),
        "seed": int(root.seed),
        "paper": {
            "rgb": list(paper_color.as_rgb_tuple()),
            "grain": float(paper.grain),
            "antialias_grid": int(paper.antialias_grid),
        },
        "paint_order": "back_to_front",
        "layers": layers,
        "notes": [
            "Flattened paint list exported from python/northcel/renderer.py frame_paint_list().",
            "Rings are already resolved (boil, transform, warp, nudge, stroke and ribbon expansion applied).",
            "clip_shapes contains the resolved rings of every clip target; the reference treats their spans as a union.",
            "This is not NCIR: NCIR v1 stores band-partitioned edges and does not carry ring topology, opacity, group scopes or clips.",
        ],
    }


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="skyline_1080", help="fixture stem (default skyline_1080)")
    ap.add_argument("--check", action="store_true", help="verify existing files without rewriting")
    ap.add_argument(
        "--grain",
        type=float,
        default=0.008,
        help="paper grain for the generated scene (default 0.008; 0 makes a flat variant)",
    )
    args = ap.parse_args()

    FIX.mkdir(parents=True, exist_ok=True)
    source = build_scene(args.grain)
    ncel_path = FIX / f"{args.name}.ncel"
    json_path = FIX / f"{args.name}.paintlist.json"
    doc = parse_ncel(source)
    data = to_json(doc, 0, ncel_path.name)
    json_text = json.dumps(data, separators=(",", ":")) + "\n"
    if args.check:
        if ncel_path.read_text(encoding="utf-8") != source:
            raise SystemExit(f"source does not reproduce: {ncel_path}")
        if json_path.read_text(encoding="utf-8") != json_text:
            raise SystemExit(f"paint list does not reproduce: {json_path}")
    else:
        ncel_path.write_text(source, encoding="utf-8")
        json_path.write_text(json_text, encoding="utf-8")
    nrings = sum(len(l["rings"]) for l in data["layers"])
    nverts = sum(len(r) for l in data["layers"] for r in l["rings"])
    print(
        f"{'verified' if args.check else 'wrote'} {ncel_path} ({len(source)} bytes) and "
        f"{json_path}: "
        f"{len(data['layers'])} layers, {nrings} rings, {nverts} vertices, "
        f"{data['width']}x{data['height']}, grain {data['paper']['grain']:g}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
