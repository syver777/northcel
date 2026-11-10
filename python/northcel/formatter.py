"""Canonical formatter for NorthCel (.ncel) AST documents (spec 0.1 through 0.5)."""

from __future__ import annotations

from typing import Any
from decimal import Decimal

from .ast_nodes import (
    BoilSpec,
    ColorMix,
    ColorValue,
    DefBlock,
    DocumentNode,
    DropNode,
    GroupNode,
    LayerNode,
    MorphNode,
    NudgeNode,
    PaperSpec,
    RibbonNode,
    SceneItem,
    SceneNode,
    StrokeNode,
    SwarmNode,
    TransformNode,
    UseNode,
    WarpNode,
)
from .parser import ExprValue


def _fmt_num(v: float | int) -> str:
    if isinstance(v, int) or float(v).is_integer():
        return str(int(round(float(v))))
    # Shortest round-tripping float, expanded to decimal because the language
    # intentionally has no exponent token. Six-significant-digit formatting
    # silently moved transformed vertices in high-precision edits.
    return format(Decimal(repr(float(v))), "f")


def _fmt_expr(e: Any, parent_precedence: int = 0) -> str:
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
            return f"-{_fmt_expr(e.args[0], 3)}"
        if e.op in ("add", "sub", "mul", "div"):
            sym = {"add": "+", "sub": "-", "mul": "*", "div": "/"}[e.op]
            precedence = 1 if e.op in ("add", "sub") else 2
            text = f"{_fmt_expr(e.args[0], precedence)} {sym} {_fmt_expr(e.args[1], precedence+1)}"
            return f"({text})" if precedence < parent_precedence else text
        args_s = ", ".join(_fmt_expr(a) for a in e.args)
        return f"{e.op}({args_s})"
    return str(e)


def _has_color_ref(c: ColorValue, palette: dict[str, ColorValue] | None) -> bool:
    if isinstance(c, ColorMix):
        return False
    return bool(c.palette_ref and (palette is None or
        (c.palette_ref in palette and palette[c.palette_ref].as_rgb_tuple() == c.as_rgb_tuple())))


def _fmt_mix(c: ColorMix, palette: dict[str, ColorValue] | None = None) -> str:
    return f"mix({_fmt_color_val(c.a, palette)}, {_fmt_color_val(c.b, palette)}, {_fmt_expr(c.u)})"


def _fmt_color_val(c: ColorValue | ColorMix, palette: dict[str, ColorValue] | None = None) -> str:
    if isinstance(c, ColorMix):
        return _fmt_mix(c, palette)
    if _has_color_ref(c, palette):
        return f"${c.palette_ref}"
    return c.to_hex()


def _fmt_color_kv(c: ColorValue | ColorMix, palette: dict[str, ColorValue] | None = None) -> str:
    if isinstance(c, ColorMix):
        return f"color: {_fmt_mix(c, palette)}"
    if _has_color_ref(c, palette):
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


def _fmt_opacity_kv(o: Any) -> str:
    return "" if o is None else f", opacity: {_fmt_expr(o)}"


def _paper_key(p: PaperSpec) -> tuple:
    color = p.color
    key = _fmt_mix(color, None) if isinstance(color, ColorMix) else color.as_rgb_tuple()
    return (key, p.antialias_grid, p.grain)


def _fmt_outline_kv(c: ColorValue | ColorMix | None, w: float, palette: dict[str, ColorValue] | None = None) -> str:
    if c is None or w <= 0.0:
        return ""
    color = _fmt_color_val(c, palette)
    return f", outline: ({color}, {_fmt_num(w)}px)"


def _fmt_palette(pal: dict[str, ColorValue], indent: str = "  ") -> list[str]:
    if not pal:
        return []
    parts = []
    for k, v in pal.items():
        parts.append(f"{k}: {v.to_hex() if not v.is_grey else v.r}")
    return [f"{indent}palette {{ {', '.join(parts)} }}"]


def _fmt_paper(p: PaperSpec, indent: str = "  ", palette: dict[str, ColorValue] | None = None) -> str:
    parts = [_fmt_color_kv(p.color, palette), f"antialias_grid: {p.antialias_grid}"]
    if p.grain > 0:
        parts.append(f"grain: {_fmt_num(p.grain)}")
    return f"{indent}paper {{ {', '.join(parts)} }}"


def _fmt_item(item: SceneItem, indent: str = "  ", palette: dict[str, ColorValue] | None = None) -> list[str]:
    if isinstance(item, TransformNode):
        def pair(v):
            return f"({_fmt_expr(v[0])}, {_fmt_expr(v[1])})"
        anchor = f", anchor: {pair(item.anchor)}" if item.anchor_explicit else ""
        return [f"{indent}transform {item.target_name}(scale: {pair(item.scale)}, rotate: {_fmt_expr(item.rotate)}{anchor}, translate: {pair(item.translate)})"]
    if isinstance(item, LayerNode):
        rings_part = f", rings: {item.rings_count}" if item.rings_count is not None else ""
        extra = (
            _fmt_outline_kv(item.outline_color, item.outline_width, palette)
            + _fmt_boil_kv(item.boil)
            + _fmt_translate_kv(item.translate_expr)
            + _fmt_opacity_kv(item.opacity)
        )
        kw = "cel" if (item.outline_color is not None and item.outline_width > 0) else "layer"
        return [
            f'{indent}{kw} {item.name}({_fmt_color_kv(item.color, palette)}{rings_part}{extra}) {{ "{item.payload}" }}'
        ]
    if isinstance(item, SwarmNode):
        extra = _fmt_boil_kv(item.boil) + _fmt_translate_kv(item.translate_expr) + _fmt_opacity_kv(item.opacity)
        return [
            f'{indent}bend_swarm {item.name}(agents: {item.agents}, {_fmt_color_kv(item.color, palette)}{extra}) {{ "{item.payload}" }}'
        ]
    if isinstance(item, StrokeNode):
        if abs(item.width_start - item.width_end) < 1e-6:
            w_kv = f"width: {_fmt_num(item.width_start)}"
        else:
            w_kv = f"taper: ({_fmt_num(item.width_start)}, {_fmt_num(item.width_end)})"
        extra = _fmt_boil_kv(item.boil) + _fmt_opacity_kv(item.opacity)
        pts_s = ", ".join(f"({_fmt_expr(x)}, {_fmt_expr(y)})" for x, y in item.points)
        return [f"{indent}stroke {item.name}({_fmt_color_kv(item.color, palette)}, {w_kv}{extra}) {{ {pts_s} }}"]
    if isinstance(item, RibbonNode):
        extra = _fmt_boil_kv(item.boil) + _fmt_opacity_kv(item.opacity)
        pts_s = ", ".join(f"({_fmt_expr(x)}, {_fmt_expr(y)}, {_fmt_num(w)})" for x, y, w in item.points)
        return [f"{indent}ribbon {item.name}({_fmt_color_kv(item.color, palette)}{extra}) {{ {pts_s} }}"]
    if isinstance(item, MorphNode):
        samples = f", samples: {item.samples}" if item.samples is not None else ""
        extra = _fmt_outline_kv(item.outline_color, item.outline_width, palette) + _fmt_opacity_kv(item.opacity)
        return [
            f'{indent}morph {item.name}({_fmt_color_kv(item.color, palette)}, u: {_fmt_expr(item.u)}{samples}{extra}) '
            f'{{ "{item.payload_a}" => "{item.payload_b}" }}'
        ]
    if isinstance(item, GroupNode):
        attrs = []
        if tuple(item.pivot) != (0.0, 0.0):
            attrs.append(f"pivot: ({_fmt_expr(item.pivot[0])}, {_fmt_expr(item.pivot[1])})")
        if item.clip:
            attrs.append(f"clip: {item.clip}")
        if item.parent:
            attrs.append(f"parent: {item.parent}")
        if item.opacity is not None:
            attrs.append(f"opacity: {_fmt_expr(item.opacity)}")
        head = f"{indent}group {item.name}" + (f"({', '.join(attrs)})" if attrs else "") + " {"
        lines = [head]
        for child in item.items:
            lines.extend(_fmt_item(child, indent + "  ", palette))
        lines.append(f"{indent}}}")
        return lines
    if isinstance(item, WarpNode):
        handles = ", ".join(
            f"({_fmt_expr(x)}, {_fmt_expr(y)}, {_fmt_expr(dx)}, {_fmt_expr(dy)})"
            for x, y, dx, dy in item.handles)
        if len(item.handles) == 1:
            handles += ","  # Preserve a tuple of one handle, not a parenthesised value.
        mode = getattr(item, "mode", "smooth")
        extra = ", mode: arap" if mode == "arap" else ""
        return [f"{indent}warp {item.target_name}(handles: ({handles}), radius: {_fmt_expr(item.radius)}{extra})"]
    if isinstance(item, NudgeNode):
        return [f"{indent}nudge {item.target_name}(vertex: {item.vertex}, ring: {item.ring}, "
                f"dx: {_fmt_expr(item.dx)}, dy: {_fmt_expr(item.dy)})"]
    if isinstance(item, UseNode):
        args_s = ", ".join(f"{k}: {_fmt_expr(v)}" for k, v in item.args.items())
        return [f"{indent}use {item.def_name}({args_s})"]
    if isinstance(item, DropNode):
        return [f"{indent}drop {item.target_name}"]
    return []


def _fmt_def(d: DefBlock, indent: str = "  ", palette: dict[str, ColorValue] | None = None) -> list[str]:
    params_s = ", ".join(f"{k}: {_fmt_num(v)}" for k, v in d.params.items())
    head = f"{indent}def {d.name}({params_s}) {{" if params_s else f"{indent}def {d.name} {{"
    lines = [head]
    for it in d.items:
        lines.extend(_fmt_item(it, indent + "  ", palette))
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
        lines.append(_fmt_paper(root.paper, "  ", root.palette))
        for d in root.defs.values():
            lines.extend(_fmt_def(d, "  ", root.palette))
        for item in root.items:
            lines.extend(_fmt_item(item, "  ", root.palette))
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
        lines.append(_fmt_paper(root.paper, "  ", root.palette))
        for d in root.defs.values():
            lines.extend(_fmt_def(d, "  ", root.palette))
        for item in root.items:
            lines.extend(_fmt_item(item, "  ", root.palette))
        blocks = [(f"{f_idx}", root.frame_overrides[f_idx]) for f_idx in sorted(root.frame_overrides)]
        # Ranges keep source order: among overlapping ranges the later one wins.
        blocks += [(f"{lo}..{hi}", f_scene) for lo, hi, f_scene in root.frame_ranges]
        for label, f_scene in blocks:
            lines.append(f"  frame {label} {{")
            local = {k: v for k, v in f_scene.palette.items()
                     if k not in root.palette or v.as_rgb_tuple() != root.palette[k].as_rgb_tuple()}
            scope = {**root.palette, **local}
            lines.extend(_fmt_palette(local, "    "))
            if _paper_key(f_scene.paper) != _paper_key(root.paper):
                lines.append(_fmt_paper(f_scene.paper, "    ", scope))
            for d in f_scene.defs.values():
                lines.extend(_fmt_def(d, "    ", scope))
            for item in f_scene.items:
                lines.extend(_fmt_item(item, "    ", scope))
            lines.append("  }")
        lines.append("}")

    return "\n".join(lines) + "\n"
