"""CLI entrypoint for `northcel` and `ncel`: check, fmt, info, render, film, verify."""

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
from .verify import (
    VerificationError,
    contact_report,
    continuity_report,
    diff_report,
    distinct_report,
    onion_report,
)


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
    try:
        _paper, _color, paints = frame_paint_list(doc, args.frame)
    except NorthCelEvaluationError as exc:
        return evaluation_error(path, exc, args.json)
    from .shapes import shape_rows

    rows = shape_rows((p.name, p.color.to_hex(), p.rings) for p in paints)

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


# ------------------------------------------------------------ verification tools
def _load_tool_document(path: Path, command: str, as_json: bool):
    """Load + validate a document for a verification tool, or print located errors."""
    try:
        _src, doc, diags = _load_and_validate(path)
    except (OSError, UnicodeError) as exc:
        tool_error(path, command, f"cannot read document as UTF-8: {exc}", as_json)
        return None
    except (ValueError, ArithmeticError, KeyError) as exc:
        tool_error(path, command, f"cannot parse or validate document; check values and expressions: {exc}", as_json)
        return None
    if doc is None:
        _print_tool_errors(path, command, diags, as_json, located=True)
        return None
    errors = [d.format() for d in diags if d.level == "error"]
    if errors:
        _print_tool_errors(path, command, errors, as_json, located=True)
        return None
    return doc


def _print_tool_errors(path: Path, command: str, errors: list[str], as_json: bool, located: bool) -> None:
    if as_json:
        print(
            json.dumps(
                {
                    "ok": False, "command": command, "file": str(path), "errors": errors,
                    "renderer": "python-reference", "native": False,
                },
                indent=2,
            )
        )
        return
    for error in errors:
        if located:
            print(f"{path}:{error}", file=sys.stderr)
        else:
            print(f"{path}: error: {error}", file=sys.stderr)


def tool_error(path: Path, command: str, message: str, as_json: bool) -> int:
    _print_tool_errors(path, command, [message], as_json, located=False)
    return 1


def _tool_evaluation_error(path: Path, command: str, exc: NorthCelEvaluationError, as_json: bool) -> int:
    message = f"{exc.line}:{exc.column}: error: {exc.message}"
    _print_tool_errors(path, command, [message], as_json, located=True)
    return 1


def _tool_runtime_error(path: Path, command: str, exc: Exception, as_json: bool) -> int:
    return tool_error(
        path, command,
        f"cannot complete {command}: {exc}; check document expressions and file paths",
        as_json,
    )


def _fmt(value: float | None, digits: int = 6) -> str:
    return "inf" if value is None else f"{value:.{digits}f}"


def _bbox_text(bbox) -> str:
    if bbox is None:
        return "-"
    return "[" + ",".join(f"{float(v):g}" for v in bbox) + "]"


def _print_diff(result: dict) -> None:
    overall = result["overall"]
    print(
        f"diff: frame {result['frame']} vs {result['against']} "
        f"({result['width']}x{result['height']})"
    )
    print(
        f"overall: MAE {overall['mae']:.6f}  RMSE {overall['rmse']:.6f}  "
        f"PSNR {_fmt(overall['psnr'], 4)}  max {overall['max_abs']}  "
        f"pixels {overall['pixels']}"
    )
    if overall["identical"]:
        print("the render and the reference are identical")
    if result["groups"]:
        print("groups:")
        print(f"  {'name':<24} {'bbox':<28} {'pixels':>8} {'MAE':>10} {'RMSE':>10} {'PSNR':>10}")
        for row in result["groups"]:
            print(
                f"  {row['name']:<24} {_bbox_text(row['bbox']):<28} {row['pixels']:>8} "
                f"{row['mae']:>10.6f} {row['rmse']:>10.6f} {_fmt(row['psnr'], 4):>10}"
            )
    if result["regions"]:
        print("regions:")
        print(f"  {'name':<24} {'bbox':<28} {'pixels':>8} {'MAE':>10} {'RMSE':>10} {'PSNR':>10}")
        for row in result["regions"]:
            print(
                f"  {row['name']:<24} {_bbox_text(row['bbox']):<28} {row['pixels']:>8} "
                f"{row['mae']:>10.6f} {row['rmse']:>10.6f} {_fmt(row['psnr'], 4):>10}"
            )
    if result["heatmap"]:
        print(f"heatmap: {result['heatmap']}")


def cmd_diff(args: argparse.Namespace) -> int:
    path = Path(args.file)
    doc = _load_tool_document(path, "diff", args.json)
    if doc is None:
        return 1
    try:
        result = diff_report(
            doc,
            args.against,
            frame=args.frame,
            regions=args.region,
            heatmap_path=args.out,
        )
    except NorthCelEvaluationError as exc:
        return _tool_evaluation_error(path, "diff", exc, args.json)
    except VerificationError as exc:
        return tool_error(path, "diff", str(exc), args.json)
    except (OSError, ValueError, ArithmeticError, KeyError) as exc:
        return _tool_runtime_error(path, "diff", exc, args.json)
    result["file"] = str(path)
    result.update(renderer="python-reference", native=False)
    result["against"] = str(Path(args.against))
    if args.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    else:
        _print_diff(result)
    return 0


def _print_onion(result: dict) -> None:
    print(
        f"onion: wrote {result['out']} ({result['width']}x{result['height']}, "
        f"frame {result['frame']}, {result['mode']})"
    )
    for row in result["frames"]:
        tint = f" ({row['tint']})" if row["tint"] else ""
        if row["role"] == "frame":
            print(f"  frame {row['frame']}{tint}")
        elif row["role"] == "render":
            print(f"  render frame {row['frame']}{tint}")
        else:
            print(f"  reference {row['path']}{tint}")


def cmd_onion(args: argparse.Namespace) -> int:
    path = Path(args.file)
    doc = _load_tool_document(path, "onion", args.json)
    if doc is None:
        return 1
    try:
        result = onion_report(doc, args.out, frame=args.frame, against=args.against)
    except NorthCelEvaluationError as exc:
        return _tool_evaluation_error(path, "onion", exc, args.json)
    except VerificationError as exc:
        return tool_error(path, "onion", str(exc), args.json)
    except (OSError, ValueError, ArithmeticError, KeyError) as exc:
        return _tool_runtime_error(path, "onion", exc, args.json)
    result["file"] = str(path)
    result.update(renderer="python-reference", native=False)
    if args.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    else:
        _print_onion(result)
    return 0


def _print_contact(result: dict) -> None:
    count = len(result["sheets"])
    print(f"contact: wrote {count} sheet{'s' if count != 1 else ''}")
    for sheet in result["sheets"]:
        frames = sheet["frames"]
        span = f"{frames[0]}..{frames[-1]}" if len(frames) > 1 else str(frames[0])
        transition = sheet["transition"]
        label = ""
        if transition:
            label = f"  [exact {transition['label']}]" if transition["kind"] == "exact" else "  [range]"
        print(f"  {sheet['path']}  frames {span}{label}")


def cmd_contact(args: argparse.Namespace) -> int:
    path = Path(args.file)
    doc = _load_tool_document(path, "contact", args.json)
    if doc is None:
        return 1
    try:
        result = contact_report(
            doc,
            args.out,
            frames=args.frames,
            every=args.every,
            transitions=args.transitions,
        )
    except NorthCelEvaluationError as exc:
        return _tool_evaluation_error(path, "contact", exc, args.json)
    except VerificationError as exc:
        return tool_error(path, "contact", str(exc), args.json)
    except (OSError, ValueError, ArithmeticError, KeyError) as exc:
        return _tool_runtime_error(path, "contact", exc, args.json)
    result["file"] = str(path)
    result.update(renderer="python-reference", native=False)
    if args.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    else:
        _print_contact(result)
    return 0


def _print_continuity(result: dict) -> None:
    print(
        f"continuity: {result['file']} ({result['frames']} frames at {result['fps']} fps)"
    )
    selection = result["selection"]
    if selection["group"]:
        print(f"group: {selection['group']}")
    if selection["shape"]:
        print(f"shape: {selection['shape']}")
    print(
        f"  {'frame':>5}  {'present':<7} {'bbox':<28} {'width':>8} {'height':>8} "
        f"{'centroid':<18} {'Δw%':>9} {'Δh%':>9} {'Δpos':>9}"
    )
    jumps = {jump["to"]: jump for jump in result["jumps"]}
    for row in result["rows"]:
        jump = jumps.get(row["frame"])
        bbox = _bbox_text(row["bbox"])
        centroid = "-" if row["centroid"] is None else ",".join(f"{v:g}" for v in row["centroid"])
        width_pct = "-" if jump is None or jump["width_change_pct"] is None else f"{jump['width_change_pct']:+.2f}"
        height_pct = "-" if jump is None or jump["height_change_pct"] is None else f"{jump['height_change_pct']:+.2f}"
        position = "-" if jump is None or jump["centroid_distance"] is None else f"{jump['centroid_distance']:.2f}"
        mark = "  <-- >8% height jump" if jump is not None and jump["height_jump"] else ""
        print(
            f"  {row['frame']:>5}  {str(row['present']):<7} {bbox:<28} {row['width']:>8.2f} "
            f"{row['height']:>8.2f} {centroid:<18} {width_pct:>9} {height_pct:>9} "
            f"{position:>9}{mark}"
        )
    print(
        f"height jumps >{result['thresholds']['height_pct']:g}%: "
        f"{len(result['height_jumps'])}; max {result['max_height_jump_pct']:.2f}%"
    )


def cmd_continuity(args: argparse.Namespace) -> int:
    path = Path(args.file)
    doc = _load_tool_document(path, "continuity", args.json)
    if doc is None:
        return 1
    try:
        result = continuity_report(doc, group=args.group, shape=args.shape)
    except NorthCelEvaluationError as exc:
        return _tool_evaluation_error(path, "continuity", exc, args.json)
    except VerificationError as exc:
        return tool_error(path, "continuity", str(exc), args.json)
    except (OSError, ValueError, ArithmeticError, KeyError) as exc:
        return _tool_runtime_error(path, "continuity", exc, args.json)
    result["file"] = str(path)
    result.update(renderer="python-reference", native=False)
    if args.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    else:
        _print_continuity(result)
    return 0


def _print_distinct(result: dict) -> None:
    sampled = ""
    if result["sampled"]:
        sampled = (
            f" (sampled {result['sampled_frames']} of {result['frames']} frames; "
            "use all frames for the film-proof number)"
        )
    print(
        f"distinct: {result['changed_pairs']}/{result['pair_count']} adjacent pairs changed, "
        f"{result['distinct_frames']} distinct frames "
        f"(threshold {result['threshold']:.3f}/255 at {result['width']}x{result['height']}){sampled}"
    )
    print(
        f"measured span: frames {result['first_frame']}..{result['last_frame']} "
        f"at {result['fps']} fps = {result['seconds']:.3f} s"
    )
    print(f"distinct frames/s: {result['distinct_per_second']:.3f}")


def cmd_distinct(args: argparse.Namespace) -> int:
    path = Path(args.file)
    doc = _load_tool_document(path, "distinct", args.json)
    if doc is None:
        return 1
    try:
        result = distinct_report(doc, frames=args.frames, every=args.every)
    except NorthCelEvaluationError as exc:
        return _tool_evaluation_error(path, "distinct", exc, args.json)
    except VerificationError as exc:
        return tool_error(path, "distinct", str(exc), args.json)
    except (OSError, ValueError, ArithmeticError, KeyError) as exc:
        return _tool_runtime_error(path, "distinct", exc, args.json)
    result["file"] = str(path)
    result.update(renderer="python-reference", native=False)
    if args.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    else:
        _print_distinct(result)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=CLI_COMMAND,
        description=f"{LANGUAGE_NAME} ({FILE_EXTENSION}) — AI-drawn video language compiler, formatter, validator, and reference renderer.",
    )
    p.add_argument("--version", action="version", version=f"{CLI_COMMAND} {PACKAGE_VERSION} (spec {SPEC_VERSION})")
    sub = p.add_subparsers(dest="command", required=True)

    from .perceive import register_parser

    register_parser(sub)

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

    p_diff = sub.add_parser(
        "diff",
        help="Render a frame and compare it with a reference image (overall/per-group/per-region error).",
    )
    p_diff.add_argument("file", help="Path to .ncel file")
    p_diff.add_argument("--against", required=True, help="Reference image to compare with")
    p_diff.add_argument("--frame", type=int, default=0, help="Frame index to render (default: 0)")
    p_diff.add_argument(
        "-o",
        "--out",
        help="Optional heatmap PNG of the per-pixel error",
    )
    p_diff.add_argument(
        "--region",
        action="append",
        default=[],
        metavar="NAME:x0,y0,x1,y1",
        help="Manual rectangle to measure; repeatable",
    )
    p_diff.add_argument("--json", action="store_true", help="Output JSON")
    p_diff.set_defaults(func=cmd_diff)

    p_onion = sub.add_parser(
        "onion",
        help="Overlay neighbouring frames (red/blue) or a render against a reference image.",
    )
    p_onion.add_argument("file", help="Path to .ncel file")
    p_onion.add_argument("-o", "--out", required=True, help="Output PNG")
    p_onion.add_argument("--frame", type=int, default=0, help="Frame index (default: 0)")
    p_onion.add_argument("--against", help="Compare a render against this reference image instead")
    p_onion.add_argument("--json", action="store_true", help="Output JSON")
    p_onion.set_defaults(func=cmd_onion)

    p_contact = sub.add_parser(
        "contact",
        help="Write a contact sheet of sampled frames, or one sheet per transition.",
    )
    p_contact.add_argument("file", help="Path to .ncel file")
    p_contact.add_argument(
        "-o",
        "--out",
        required=True,
        help="Sheet PNG, or a directory (writes contact.png inside)",
    )
    p_contact.add_argument("--frames", help="Frame range '0..5' or comma list '0,2,4'")
    p_contact.add_argument(
        "--every",
        type=int,
        default=1,
        help="Sample every Nth frame (default: 1; use it for long films)",
    )
    p_contact.add_argument(
        "--transitions",
        action="store_true",
        help=(
            "Write one sheet per frame override/range declared in the film "
            "(a .png OUT becomes OUT-transitions/)"
        ),
    )
    p_contact.add_argument("--json", action="store_true", help="Output JSON")
    p_contact.set_defaults(func=cmd_contact)

    p_continuity = sub.add_parser(
        "continuity",
        help="Per-frame bbox/width/height/centroid for a group or shape, with adjacent jumps.",
    )
    p_continuity.add_argument("file", help="Path to .ncel file")
    p_continuity.add_argument("--group", required=True, help="Group name (its paint path)")
    p_continuity.add_argument("--shape", help="Optional shape name to restrict the measurement")
    p_continuity.add_argument("--json", action="store_true", help="Output JSON")
    p_continuity.set_defaults(func=cmd_continuity)

    p_distinct = sub.add_parser(
        "distinct",
        help="Measure distinct frames per second with the 320x180 frame-diff film-proof metric.",
    )
    p_distinct.add_argument("file", help="Path to .ncel file")
    p_distinct.add_argument("--frames", help="Frame range '0..5' or comma list '0,2,4'")
    p_distinct.add_argument("--every", type=int, default=1, help="Sample every Nth frame (default: 1)")
    p_distinct.add_argument("--json", action="store_true", help="Output JSON")
    p_distinct.set_defaults(func=cmd_distinct)

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
