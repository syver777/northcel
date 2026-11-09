"""CLI entrypoint for `northcel` and `ncel`: check, fmt, info, render, film."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Sequence

from PIL import Image

from .ast_nodes import ColorMix, FilmNode, LayerNode, MorphNode, RibbonNode, StrokeNode, SwarmNode
from .config import CLI_COMMAND, FILE_EXTENSION, LANGUAGE_NAME, PACKAGE_VERSION, SPEC_VERSION
from .formatter import format_document
from .parser import NorthCelSyntaxError, parse_ncel
from .renderer import NorthCelEvaluationError, frame_paint_list, render_document_frame, render_film_frames
from .rings import decode_rings_payload
from .validator import validate_document


def _load_and_validate(path: Path):
    if not path.is_file():
        return None, None, [f"1:1: error: File not found: {path}"]
    src = path.read_text(encoding="utf-8")
    try:
        doc = parse_ncel(src)
    except NorthCelSyntaxError as exc:
        return src, None, [f"{exc.line}:{exc.column}: error: {exc.message}"]
    diags = validate_document(doc)
    return src, doc, diags


def cmd_check(args: argparse.Namespace) -> int:
    path = Path(args.file)
    _, doc, diags = _load_and_validate(path)
    if doc is None:
        errors = diags
        warnings = []
    else:
        errors = [d.format() for d in diags if d.level == "error"]
        warnings = [d.format() for d in diags if d.level == "warning"]

    ok = len(errors) == 0
    if args.json:
        print(
            json.dumps(
                {
                    "ok": ok,
                    "partial": False,
                    "validator": "python",
                    "file": str(path),
                    "spec_version": doc.spec_version if doc else None,
                    "errors": errors,
                    "warnings": warnings,
                },
                indent=2,
            )
        )
    else:
        for w in warnings:
            print(f"{path}:{w}", file=sys.stderr)
        for e in errors:
            print(f"{path}:{e}", file=sys.stderr)
        if ok:
            print(f"{path}: OK ({LANGUAGE_NAME} {doc.spec_version if doc else SPEC_VERSION})")
    return 0 if ok else 1


def cmd_guide(args: argparse.Namespace) -> int:
    sys.stdout.write(Path(__file__).with_name("AGENT-GUIDE.md").read_text(encoding="utf-8"))
    return 0


def cmd_fmt(args: argparse.Namespace) -> int:
    path = Path(args.file)
    src, doc, diags = _load_and_validate(path)
    if doc is None:
        for e in diags:
            print(f"{path}:{e}", file=sys.stderr)
        return 1
    errors = [d for d in diags if d.level == "error"]
    if errors:
        for e in errors:
            print(f"{path}:{e.format()}", file=sys.stderr)
        return 1

    formatted = format_document(doc, include_version_header=True)
    if args.check:
        if src != formatted:
            print(f"{path}: needs formatting", file=sys.stderr)
            return 1
        print(f"{path}: formatted")
        return 0
    if args.write:
        path.write_text(formatted, encoding="utf-8")
        print(f"{path}: formatted in-place")
        return 0
    sys.stdout.write(formatted)
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    path = Path(args.file)
    src, doc, diags = _load_and_validate(path)
    if doc is None:
        for e in diags:
            print(f"{path}:{e}", file=sys.stderr)
        return 1
    root = doc.root
    total_rings = 0
    total_vertices = 0
    layers_summary = []

    def inspect_items(items, precision: str):
        nonlocal total_rings, total_vertices
        for it in items:
            if isinstance(it, (LayerNode, SwarmNode)):
                rings = decode_rings_payload(it.payload, precision=precision)
                v_cnt = sum(len(r) for r in rings)
                total_rings += len(rings)
                total_vertices += v_cnt
                layers_summary.append(
                    {
                        "kind": "layer" if isinstance(it, LayerNode) else "bend_swarm",
                        "name": it.name,
                        "color": _color_text(it.color),
                        "rings": len(rings),
                        "vertices": v_cnt,
                    }
                )
            elif isinstance(it, MorphNode):
                rings_a = decode_rings_payload(it.payload_a, precision=precision)
                rings_b = decode_rings_payload(it.payload_b, precision=precision)
                total_rings += len(rings_a)
                total_vertices += sum(len(r) for r in rings_a) + sum(len(r) for r in rings_b)
                layers_summary.append(
                    {
                        "kind": "morph",
                        "name": it.name,
                        "color": _color_text(it.color),
                        "rings": len(rings_a),
                        "vertices": [sum(len(r) for r in rings_a), sum(len(r) for r in rings_b)],
                    }
                )
            elif isinstance(it, StrokeNode):
                total_rings += 1
                total_vertices += len(it.points) * 2
                layers_summary.append(
                    {
                        "kind": "stroke",
                        "name": it.name,
                        "color": _color_text(it.color),
                        "points": len(it.points),
                    }
                )
            elif isinstance(it, RibbonNode):
                total_rings += 1
                total_vertices += len(it.points) * 2
                layers_summary.append(
                    {
                        "kind": "ribbon",
                        "name": it.name,
                        "color": _color_text(it.color),
                        "points": len(it.points),
                    }
                )

    inspect_items(root.items, root.precision)
    if isinstance(root, FilmNode):
        for f_scene in root.frame_overrides.values():
            inspect_items(f_scene.items, f_scene.precision)
        for _lo, _hi, f_scene in root.frame_ranges:
            inspect_items(f_scene.items, f_scene.precision)

    info = {
        "file": str(path),
        "bytes": len(src.encode("utf-8")) if src else 0,
        "spec_version": doc.spec_version,
        "kind": "film" if isinstance(root, FilmNode) else "scene",
        "name": root.name,
        "width": root.width,
        "height": root.height,
        "fps": root.fps,
        "frames": root.frames if isinstance(root, FilmNode) else 1,
        "precision": root.precision,
        "seed": root.seed,
        "defs": list(root.defs.keys()),
        "total_rings": total_rings,
        "total_vertices": total_vertices,
        "layers": layers_summary,
    }
    print(json.dumps(info, indent=2))
    return 0


def _color_text(c) -> str:
    return c.describe() if isinstance(c, ColorMix) else c.to_hex()


def cmd_render(args: argparse.Namespace) -> int:
    path = Path(args.file)
    _, doc, diags = _load_and_validate(path)
    if doc is None:
        for e in diags:
            print(f"{path}:{e}", file=sys.stderr)
        return 1
    errors = [d for d in diags if d.level == "error"]
    if errors:
        for e in errors:
            print(f"{path}:{e.format()}", file=sys.stderr)
        return 1

    t0 = time.monotonic()
    try:
        rgb = render_document_frame(doc, frame_index=args.frame, seed_override=args.seed)
    except NorthCelEvaluationError as exc:
        return evaluation_error(path, exc, args.json)
    out_p = Path(args.out) if args.out else path.with_suffix(".png")
    out_p.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(rgb, mode="RGB").save(out_p)
    elapsed = time.monotonic() - t0
    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "input": str(path),
                    "output": str(out_p),
                    "frame": args.frame,
                    "width": int(rgb.shape[1]),
                    "height": int(rgb.shape[0]),
                    "seconds": round(elapsed, 4),
                },
                indent=2,
            )
        )
    else:
        print(f"Rendered {out_p} ({rgb.shape[1]}x{rgb.shape[0]}, frame {args.frame}) in {elapsed:.3f}s")
    return 0


def cmd_film(args: argparse.Namespace) -> int:
    path = Path(args.file)
    _, doc, diags = _load_and_validate(path)
    if doc is None:
        for e in diags:
            print(f"{path}:{e}", file=sys.stderr)
        return 1
    errors = [d for d in diags if d.level == "error"]
    if errors:
        for e in errors:
            print(f"{path}:{e.format()}", file=sys.stderr)
        return 1

    indices: list[int] | None = None
    if args.frames:
        if ".." in args.frames:
            a_s, b_s = args.frames.split("..", 1)
            indices = list(range(int(a_s), int(b_s) + 1))
        else:
            indices = [int(x.strip()) for x in args.frames.split(",") if x.strip()]

    t0 = time.monotonic()
    try:
        res = render_film_frames(doc, out_dir=args.out_dir, frame_indices=indices, mp4_path=args.mp4)
    except NorthCelEvaluationError as exc:
        return evaluation_error(path, exc, False)
    res["seconds"] = round(time.monotonic() - t0, 4)
    print(json.dumps(res, indent=2))
    return 0


def evaluation_error(path: Path, exc: NorthCelEvaluationError, as_json: bool) -> int:
    message = f"{exc.line}:{exc.column}: error: {exc.message}"
    if as_json:
        print(json.dumps({"ok": False, "renderer": "python-reference", "native": False, "errors": [message]}))
    else:
        print(f"{path}:{message}", file=sys.stderr)
    return 1


def _parse_csv_floats(text: str, n: int, name: str) -> list[float]:
    parts = [p.strip() for p in text.split(",")]
    if len(parts) != n:
        raise ValueError(f"{name} needs {n} comma-separated numbers")
    return [float(p) for p in parts]


def cmd_shapes(args: argparse.Namespace) -> int:
    """List/query evaluated shapes of one frame with stable names and geometry."""
    path = Path(args.file)
    _, doc, diags = _load_and_validate(path)
    if doc is None:
        for e in diags:
            print(f"{path}:{e}", file=sys.stderr)
        return 1
    errors = [d for d in diags if d.level == "error"]
    if errors:
        for e in errors:
            print(f"{path}:{e.format()}", file=sys.stderr)
        return 1
    _paper, _color, paints = frame_paint_list(doc, args.frame)
    rows = []
    for paint in paints:
        pts = [p for ring in paint.rings for p in ring]
        if not pts:
            continue
        lo = [min(p[0] for p in pts), min(p[1] for p in pts)]
        hi = [max(p[0] for p in pts), max(p[1] for p in pts)]
        area = sum(abs(0.5 * sum(r[i][0] * r[(i+1) % len(r)][1] - r[(i+1) % len(r)][0] * r[i][1]
                                 for i in range(len(r)))) for r in paint.rings if len(r) >= 3)
        cx = (lo[0] + hi[0]) / 2
        cy = (lo[1] + hi[1]) / 2
        rows.append({"id": paint.name, "color": paint.color.to_hex(),
                     "area": round(area, 2), "bbox": [round(lo[0], 2), round(lo[1], 2),
                                                      round(hi[0], 2), round(hi[1], 2)],
                     "centroid": [round(cx, 2), round(cy, 2)]})
    # Parent by bbox containment; children and neighbours from the full list.
    for rec in rows:
        cx, cy = rec["centroid"]
        parent, best = None, None
        for other in rows:
            if other is rec or other["area"] <= rec["area"]:
                continue
            x0, y0, x1, y1 = other["bbox"]
            if x0 <= cx <= x1 and y0 <= cy <= y1 and (best is None or other["area"] < best):
                parent, best = other["id"], other["area"]
        rec["parent"] = parent
    for rec in rows:
        rec["children"] = [o["id"] for o in rows if o.get("parent") == rec["id"]]
        cx, cy = rec["centroid"]
        near = sorted(((abs(o["centroid"][0]-cx)+abs(o["centroid"][1]-cy), o["id"])
                       for o in rows if o["id"] != rec["id"]))[:3]
        rec["neighbours"] = [n for _d, n in near]

    selected = rows
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",") if x.strip()}
        selected = [r for r in selected if r["id"] in wanted]
    if args.color:
        col = args.color.upper()
        if not col.startswith("#"):
            col = "#" + col
        selected = [r for r in selected if r["color"].upper() == col]
    if args.area_min is not None:
        selected = [r for r in selected if r["area"] >= args.area_min]
    if args.area_max is not None:
        selected = [r for r in selected if r["area"] <= args.area_max]
    if args.bbox:
        x0, y0, x1, y1 = _parse_csv_floats(args.bbox, 4, "--bbox")
        selected = [r for r in selected
                    if not (r["bbox"][2] < x0 or r["bbox"][0] > x1 or r["bbox"][3] < y0 or r["bbox"][1] > y1)]
    if args.centroid:
        cx, cy, rad = _parse_csv_floats(args.centroid, 3, "--centroid")
        selected = [r for r in selected
                    if (r["centroid"][0]-cx) ** 2 + (r["centroid"][1]-cy) ** 2 <= rad * rad]
    if args.parent:
        selected = [r for r in selected if r.get("parent") == args.parent]
    if args.mask:
        mask = Image.open(args.mask).convert("L")
        mw, mh = mask.size
        selected = [r for r in selected
                    if 0 <= int(r["centroid"][0]) < mw and 0 <= int(r["centroid"][1]) < mh
                    and mask.getpixel((int(r["centroid"][0]), int(r["centroid"][1]))) > 127]
    print(json.dumps({"file": str(path), "frame": args.frame, "count": len(selected),
                      "shapes": selected}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=CLI_COMMAND,
        description=f"{LANGUAGE_NAME} ({FILE_EXTENSION}) — AI-drawn video language compiler, formatter, validator, and reference renderer.",
    )
    p.add_argument("--version", action="version", version=f"{CLI_COMMAND} {PACKAGE_VERSION} (spec {SPEC_VERSION})")
    sub = p.add_subparsers(dest="command", required=True)

    p_check = sub.add_parser("check", help="Parse and validate a .ncel file with line:column diagnostics.")
    p_check.add_argument("file", help="Path to .ncel file")
    p_check.add_argument("--json", action="store_true", help="Output structured JSON diagnostics")
    p_check.add_argument("--require-full", action="store_true", help="Require full validation (always performed by this Python CLI)")
    p_check.set_defaults(func=cmd_check)

    p_guide = sub.add_parser("guide", help="Print the compact authoring and verification guide.")
    p_guide.set_defaults(func=cmd_guide)

    p_fmt = sub.add_parser("fmt", help="Format a .ncel file into canonical form.")
    p_fmt.add_argument("file", help="Path to .ncel file")
    p_fmt.add_argument("-w", "--write", action="store_true", help="Write formatted output in-place")
    p_fmt.add_argument("--check", action="store_true", help="Exit non-zero if file is not canonically formatted")
    p_fmt.set_defaults(func=cmd_fmt)

    p_info = sub.add_parser("info", help="Inspect scene/film metadata, layers, rings, and vertex counts.")
    p_info.add_argument("file", help="Path to .ncel file")
    # `info` only ever speaks JSON, so `--json` is accepted and ignored — but it must be
    # accepted: the launcher and the native runtime both document `info FILE [--json]`
    # (see launcher/cli.py USAGE and native/README.md), and a script written against
    # one implementation has to keep working against the other.
    p_info.add_argument("--json", action="store_true", help="Output JSON (always on; accepted for CLI parity)")
    p_info.set_defaults(func=cmd_info)

    p_shapes = sub.add_parser("shapes", help="List or query evaluated shapes by id, colour, area, location, or parent.")
    p_shapes.add_argument("file", help="Path to .ncel file")
    p_shapes.add_argument("--frame", type=int, default=0, help="Frame index (default: 0)")
    p_shapes.add_argument("--ids", help="Comma list of shape ids")
    p_shapes.add_argument("--color", help="Exact #RRGGBB colour")
    p_shapes.add_argument("--area-min", type=float)
    p_shapes.add_argument("--area-max", type=float)
    p_shapes.add_argument("--bbox", help="x0,y0,x1,y1 intersection")
    p_shapes.add_argument("--centroid", help="x,y,radius")
    p_shapes.add_argument("--parent", help="Parent shape id")
    p_shapes.add_argument("--mask", help="Only shapes whose centroid lies in this image mask")
    p_shapes.add_argument("--json", action="store_true", help="Output JSON (always on)")
    p_shapes.set_defaults(func=cmd_shapes)

    p_render = sub.add_parser("render", help="Render a single frame of a .ncel scene or film to PNG.")
    p_render.add_argument("file", help="Path to .ncel file")
    p_render.add_argument("-o", "--out", help="Output PNG path (default: <file>.png)")
    p_render.add_argument("-f", "--frame", type=int, default=0, help="Frame index to render (default: 0)")
    p_render.add_argument("--seed", type=int, default=None, help="Optional seed override")
    p_render.add_argument("--json", action="store_true", help="Output JSON summary")
    p_render.set_defaults(func=cmd_render)

    p_film = sub.add_parser("film", help="Render a sequence of frames from a .ncel film to PNGs and optional MP4.")
    p_film.add_argument("file", help="Path to .ncel file")
    p_film.add_argument("-o", "--out-dir", required=True, help="Directory for rendered f0000.png frames")
    p_film.add_argument("--frames", help="Optional frame range '0..5' or comma list '0,1,2'")
    p_film.add_argument("--mp4", help="Optional output MP4 file path (muxed with ffmpeg if available)")
    p_film.set_defaults(func=cmd_film)

    return p


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
