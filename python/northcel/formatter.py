"""Canonical formatter for NorthCel (.ncel) v0.2 AST documents."""

from __future__ import annotations

from typing import Any

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
    UseNode,
)
from .parser import ExprValue


def _fmt_num(v: float | int) -> str:
    if isinstance(v, int) or float(v).is_integer():
        return str(int(round(float(v))))
    return f"{float(v):g}"


def _fmt_expr(e: Any) -> str:
    if isinstance(e, (int, float)):
        return _fmt_num(e)
    if isinstance(e, str):
        return e
    if isinstance(e, ExprValue):
        if e.op == "const":
            return _fmt_num(e.args[0])
        if e.op == "var":
            return str(e.args[0])
        if e.op == "neg":
            return f"-{_fmt_expr(e.args[0])}"
        if e.op in ("add", "sub", "mul", "div"):
            sym = {"add": "+", "sub": "-", "mul": "*", "div": "/"}[e.op]
            return f"{_fmt_expr(e.args[0])} {sym} {_fmt_expr(e.args[1])}"
        args_s = ", ".join(_fmt_expr(a) for a in e.args)
        return f"{e.op}({args_s})"
    return str(e)


def _fmt_color_val(c: ColorValue) -> str:
    if c.palette_ref:
        return f"${c.palette_ref}"
    if c.is_grey:
        return str(c.r)
    return c.to_hex()


def _fmt_color_kv(c: ColorValue) -> str:
    if c.palette_ref:
        return f"color: ${c.palette_ref}"
    if c.is_grey:
        return f"tone: {c.r}"
    return f"color: {c.to_hex()}"


def _fmt_boil_kv(b: BoilSpec | None) -> str:
    if b is None or b.amplitude_px <= 0.0:
        return ""
    if abs(b.frequency - 1.0) < 1e-6:
        return f", boil: {_fmt_num(b.amplitude_px)}px"
    return f", boil: ({_fmt_num(b.amplitude_px)}, {_fmt_num(b.frequency)})"


def _fmt_translate_kv(tx: tuple[Any, Any]) -> str:
    s0, s1 = _fmt_expr(tx[0]), _fmt_expr(tx[1])
    if s0 == "0" and s1 == "0":
        return ""
    return f", translate: ({s0}, {s1})"


def _fmt_outline_kv(c: ColorValue | None, w: float) -> str:
    if c is None or w <= 0.0:
        return ""
    return f", outline: ({_fmt_color_val(c)}, {_fmt_num(w)}px)"


def _fmt_palette(pal: dict[str, ColorValue], indent: str = "  ") -> list[str]:
    if not pal:
        return []
    parts = []
    for k, v in pal.items():
        parts.append(f"{k}: {v.to_hex() if not v.is_grey else v.r}")
    return [f"{indent}palette {{ {', '.join(parts)} }}"]


def _fmt_paper(p: PaperSpec, indent: str = "  ") -> str:
    parts = [_fmt_color_kv(p.color), f"antialias_grid: {p.antialias_grid}"]
    if p.grain > 0:
        parts.append(f"grain: {_fmt_num(p.grain)}")
    return f"{indent}paper {{ {', '.join(parts)} }}"


def _fmt_item(item: SceneItem, indent: str = "  ") -> list[str]:
    if isinstance(item, LayerNode):
        rings_part = f", rings: {item.rings_count}" if item.rings_count is not None else ""
        extra = (
            _fmt_outline_kv(item.outline_color, item.outline_width)
            + _fmt_boil_kv(item.boil)
            + _fmt_translate_kv(item.translate_expr)
        )
        kw = "cel" if (item.outline_color is not None and item.outline_width > 0) else "layer"
        return [
            f'{indent}{kw} {item.name}({_fmt_color_kv(item.color)}{rings_part}{extra}) {{ "{item.payload}" }}'
        ]
    if isinstance(item, SwarmNode):
        extra = _fmt_boil_kv(item.boil) + _fmt_translate_kv(item.translate_expr)
        return [
            f'{indent}bend_swarm {item.name}(agents: {item.agents}, {_fmt_color_kv(item.color)}{extra}) {{ "{item.payload}" }}'
        ]
    if isinstance(item, StrokeNode):
        if abs(item.width_start - item.width_end) < 1e-6:
            w_kv = f"width: {_fmt_num(item.width_start)}"
        else:
            w_kv = f"taper: ({_fmt_num(item.width_start)}, {_fmt_num(item.width_end)})"
        extra = _fmt_boil_kv(item.boil)
        pts_s = ", ".join(f"({_fmt_expr(x)}, {_fmt_expr(y)})" for x, y in item.points)
        return [f"{indent}stroke {item.name}({_fmt_color_kv(item.color)}, {w_kv}{extra}) {{ {pts_s} }}"]
    if isinstance(item, RibbonNode):
        extra = _fmt_boil_kv(item.boil)
        pts_s = ", ".join(f"({_fmt_expr(x)}, {_fmt_expr(y)}, {_fmt_num(w)})" for x, y, w in item.points)
        return [f"{indent}ribbon {item.name}({_fmt_color_kv(item.color)}{extra}) {{ {pts_s} }}"]
    if isinstance(item, UseNode):
        args_s = ", ".join(f"{k}: {_fmt_expr(v)}" for k, v in item.args.items())
        return [f"{indent}use {item.def_name}({args_s})"]
    if isinstance(item, DropNode):
        return [f"{indent}drop {item.target_name}"]
    return []


def _fmt_def(d: DefBlock, indent: str = "  ") -> list[str]:
    params_s = ", ".join(f"{k}: {_fmt_num(v)}" for k, v in d.params.items())
    head = f"{indent}def {d.name}({params_s}) {{" if params_s else f"{indent}def {d.name} {{"
    lines = [head]
    for it in d.items:
        lines.extend(_fmt_item(it, indent + "  "))
    lines.append(f"{indent}}}")
    return lines


def format_document(doc: DocumentNode, include_version_header: bool = True) -> str:
    """Formats a DocumentNode into canonical .ncel source text."""
    lines: list[str] = []
    if include_version_header:
        lines.append(f'northcel "{doc.spec_version}"')
        lines.append("")

    root = doc.root
    if isinstance(root, SceneNode):
        attrs = [
            f"width: {root.width}",
            f"height: {root.height}",
            f"fps: {root.fps}",
            f"precision: {root.precision}",
        ]
        if root.seed != 42:
            attrs.append(f"seed: {root.seed}")
        lines.append(f"scene {root.name}({', '.join(attrs)}) {{")
        lines.extend(_fmt_palette(root.palette, "  "))
        lines.append(_fmt_paper(root.paper, "  "))
        for d in root.defs.values():
            lines.extend(_fmt_def(d, "  "))
        for item in root.items:
            lines.extend(_fmt_item(item, "  "))
        lines.append("}")
    else:
        attrs = [
            f"width: {root.width}",
            f"height: {root.height}",
            f"fps: {root.fps}",
            f"frames: {root.frames}",
            f"precision: {root.precision}",
            f"seed: {root.seed}",
        ]
        lines.append(f"film {root.name}({', '.join(attrs)}) {{")
        lines.extend(_fmt_palette(root.palette, "  "))
        lines.append(_fmt_paper(root.paper, "  "))
        for d in root.defs.values():
            lines.extend(_fmt_def(d, "  "))
        for item in root.items:
            lines.extend(_fmt_item(item, "  "))
        for f_idx in sorted(root.frame_overrides):
            f_scene = root.frame_overrides[f_idx]
            lines.append(f"  frame {f_idx} {{")
            for d in f_scene.defs.values():
                lines.extend(_fmt_def(d, "    "))
            for item in f_scene.items:
                lines.extend(_fmt_item(item, "    "))
            lines.append("  }")
        lines.append("}")

    return "\n".join(lines) + "\n"
