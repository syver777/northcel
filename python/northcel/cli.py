"""CLI entrypoint for `northcel` and `ncel`: check, fmt, info, render, film."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time
from typing import Sequence

from PIL import Image

from .ast_nodes import FilmNode, LayerNode, RibbonNode, SceneNode, StrokeNode, SwarmNode
from .config import CLI_COMMAND, FILE_EXTENSION, LANGUAGE_NAME, PACKAGE_VERSION, SPEC_VERSION
from .formatter import format_document
from .parser import NorthCelSyntaxError, parse_ncel
from .renderer import render_document_frame, render_film_frames
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
                        "color": it.color.to_hex(),
                        "rings": len(rings),
                        "vertices": v_cnt,
                    }
                )
            elif isinstance(it, StrokeNode):
                total_rings += 1
                total_vertices += len(it.points) * 2
                layers_summary.append(
                    {
                        "kind": "stroke",
                        "name": it.name,
                        "color": it.color.to_hex(),
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
                        "color": it.color.to_hex(),
                        "points": len(it.points),
                    }
                )

    inspect_items(root.items, root.precision)
    if isinstance(root, FilmNode):
        for f_scene in root.frame_overrides.values():
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
    rgb = render_document_frame(doc, frame_index=args.frame, seed_override=args.seed)
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
    res = render_film_frames(doc, out_dir=args.out_dir, frame_indices=indices, mp4_path=args.mp4)
    res["seconds"] = round(time.monotonic() - t0, 4)
    print(json.dumps(res, indent=2))
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
    p_info.set_defaults(func=cmd_info)

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
