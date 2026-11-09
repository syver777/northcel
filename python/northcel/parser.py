"""Lexer and recursive-descent parser for NorthCel (.ncel) up to spec 0.4 with line:column diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any

from .ast_nodes import (
    BoilSpec,
    ColorMix,
    ColorValue,
    DefBlock,
    DocumentNode,
    DropNode,
    FilmNode,
    GroupNode,
    LayerNode,
    MorphNode,
    NudgeNode,
    PaperSpec,
    RibbonNode,
    SceneItem,
    SceneNode,
    SourceSpan,
    StrokeNode,
    SwarmNode,
    TransformNode,
    UseNode,
    WarpNode,
)
from .config import SPEC_VERSION


class NorthCelSyntaxError(SyntaxError):
    """Structured syntax error with 1-based line and column."""

    def __init__(self, message: str, line: int, column: int) -> None:
        super().__init__(f"{line}:{column}: {message}")
        self.message = message
        self.line = line
        self.column = column


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int


@dataclass(frozen=True)
class ExprValue:
    """Represents a constant or pure time-dependent expression (`lerp`, `sin`, `cos`, `step`, param ref)."""

    op: str
    args: tuple[Any, ...]

    def eval(self, env: dict[str, float]) -> float:
        if self.op == "const":
            return float(self.args[0])
        if self.op == "var":
            name = str(self.args[0])
            if name not in env:
                raise KeyError(f"Undefined parameter or variable '{name}'")
            return float(env[name])
        if self.op == "neg":
            return -self.args[0].eval(env)
        if self.op == "add":
            return self.args[0].eval(env) + self.args[1].eval(env)
        if self.op == "sub":
            return self.args[0].eval(env) - self.args[1].eval(env)
        if self.op == "mul":
            return self.args[0].eval(env) * self.args[1].eval(env)
        if self.op == "div":
            denom = self.args[1].eval(env)
            return self.args[0].eval(env) / (denom if abs(denom) > 1e-12 else 1.0)
        if self.op == "lerp":
            a = self.args[0].eval(env)
            b = self.args[1].eval(env)
            u = max(0.0, min(1.0, self.args[2].eval(env)))
            return a + (b - a) * u
        if self.op == "sin":
            return math.sin(self.args[0].eval(env))
        if self.op == "cos":
            return math.cos(self.args[0].eval(env))
        if self.op == "step":
            edge = self.args[0].eval(env)
            x = self.args[1].eval(env)
            return 0.0 if x < edge else 1.0
        if self.op == "ease":
            u = max(0.0, min(1.0, self.args[0].eval(env)))
            return u*u*u*(u*(u*6.0 - 15.0) + 10.0)
        if self.op == "smoothstep":
            a, b, x = (v.eval(env) for v in self.args)
            if a == b:
                return 0.0 if x < a else 1.0
            u = max(0.0, min(1.0, (x-a)/(b-a)))
            return u*u*(3.0-2.0*u)
        raise ValueError(f"Unknown expression op '{self.op}'")


_TOKEN_SPEC = re.compile(
    r"""
    (?P<WS>[ \t\r]+)|
    (?P<NL>\n)|
    (?P<COMMENT>//[^\n]*)|
    (?P<STRING>"(?:\\.|[^"\\])*")|
    (?P<HEX>\#[0-9A-Fa-f]{3,6}\b)|
    (?P<UNIT_NUM>-?(?:\d+\.\d+|\d+)(?:px-b63|px|deg)\b)|
    (?P<NUMBER>-?(?:\d+\.\d+|\d+))|
    (?P<IDENT>[A-Za-z_][A-Za-z0-9_]*)|
    (?P<RANGE>\.\.)|
    (?P<ARROW>=>)|
    (?P<PUNCT>[{}()\[\]:,;+\-*/=$])
    """,
    re.VERBOSE,
)


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    line = 1
    line_start = 0
    pos = 0
    n = len(source)
    while pos < n:
        m = _TOKEN_SPEC.match(source, pos)
        if not m:
            col = pos - line_start + 1
            ch = source[pos]
            raise NorthCelSyntaxError(f"Unexpected character {ch!r}", line, col)
        kind = m.lastgroup or "UNKNOWN"
        text = m.group()
        col = pos - line_start + 1
        pos = m.end()
        if kind == "NL":
            line += 1
            line_start = pos
            continue
        if kind in ("WS", "COMMENT"):
            continue
        tokens.append(Token(kind=kind, value=text, line=line, column=col))
    tokens.append(Token(kind="EOF", value="", line=line, column=pos - line_start + 1))
    return tokens


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.idx = 0
        self.active_palette: dict[str, ColorValue] = {}

    def cur(self) -> Token:
        return self.tokens[self.idx]

    def peek(self, offset: int = 1) -> Token:
        i = min(len(self.tokens) - 1, self.idx + offset)
        return self.tokens[i]

    def advance(self) -> Token:
        tok = self.tokens[self.idx]
        if self.idx < len(self.tokens) - 1:
            self.idx += 1
        return tok

    def expect(self, kind: str, value: str | None = None) -> Token:
        tok = self.cur()
        if tok.kind != kind or (value is not None and tok.value != value):
            expected = f"'{value}'" if value is not None else kind
            got = f"'{tok.value}'" if tok.value else tok.kind
            raise NorthCelSyntaxError(f"Expected {expected}, got {got}", tok.line, tok.column)
        return self.advance()

    def match(self, kind: str, value: str | None = None) -> Token | None:
        tok = self.cur()
        if tok.kind == kind and (value is None or tok.value == value):
            return self.advance()
        return None

    def parse_document(self) -> DocumentNode:
        first = self.cur()
        span = SourceSpan(first.line, first.column)
        spec_ver = SPEC_VERSION
        if self.cur().kind == "IDENT" and self.cur().value == "northcel":
            self.advance()
            ver_tok = self.cur()
            if ver_tok.kind == "STRING":
                spec_ver = self.advance().value[1:-1]
            elif ver_tok.kind == "NUMBER":
                spec_ver = self.advance().value
            else:
                raise NorthCelSyntaxError(
                    "Expected version string or number after 'northcel'", ver_tok.line, ver_tok.column
                )
            self.match("PUNCT", ";")

        root_tok = self.cur()
        if root_tok.kind == "IDENT" and root_tok.value == "scene":
            root: SceneNode | FilmNode = self.parse_scene()
        elif root_tok.kind == "IDENT" and root_tok.value == "film":
            root = self.parse_film()
        else:
            raise NorthCelSyntaxError(
                f"Expected 'scene' or 'film' declaration, got '{root_tok.value or root_tok.kind}'",
                root_tok.line,
                root_tok.column,
            )

        if self.cur().kind != "EOF":
            extra = self.cur()
            raise NorthCelSyntaxError(
                f"Unexpected trailing token '{extra.value}'", extra.line, extra.column
            )
        return DocumentNode(spec_version=spec_ver, root=root, span=span)

    def parse_scene(self) -> SceneNode:
        kw = self.expect("IDENT", "scene")
        name_tok = self.expect("IDENT")
        attrs = self.parse_attr_list() if self.cur().value == "(" else {}
        self.expect("PUNCT", "{")

        width = int(self._eval_const(attrs.get("width", 1024)))
        height = int(self._eval_const(attrs.get("height", 1024)))
        fps = int(self._eval_const(attrs.get("fps", 6)))
        seed = int(self._eval_const(attrs.get("seed", 42)))
        precision = str(attrs.get("precision", "0.25px"))

        palette: dict[str, ColorValue] = {}
        self.active_palette = palette
        paper = PaperSpec()
        defs: dict[str, DefBlock] = {}
        items: list[SceneItem] = []

        while not (self.cur().kind == "PUNCT" and self.cur().value == "}"):
            if self.cur().kind == "EOF":
                raise NorthCelSyntaxError("Unclosed 'scene' block", kw.line, kw.column)
            tok = self.cur()
            if tok.kind == "IDENT" and tok.value == "palette":
                palette.update(self.parse_palette())
            elif tok.kind == "IDENT" and tok.value == "paper":
                paper = self.parse_paper()
            elif tok.kind == "IDENT" and tok.value == "def":
                d = self.parse_def()
                defs[d.name] = d
            elif tok.kind == "IDENT" and tok.value == "use":
                items.append(self.parse_use())
            elif tok.kind == "IDENT" and tok.value == "drop":
                items.append(self.parse_drop())
            elif tok.kind == "IDENT" and tok.value == "transform":
                items.append(self.parse_transform())
            elif tok.kind == "IDENT" and tok.value in ("layer", "wash", "cel"):
                items.append(self.parse_layer(is_cel=(tok.value == "cel")))
            elif tok.kind == "IDENT" and tok.value in ("bend_swarm", "swarm"):
                items.append(self.parse_swarm())
            elif tok.kind == "IDENT" and tok.value == "stroke":
                items.append(self.parse_stroke())
            elif tok.kind == "IDENT" and tok.value == "ribbon":
                items.append(self.parse_ribbon())
            elif tok.kind == "IDENT" and tok.value == "morph":
                items.append(self.parse_morph())
            elif tok.kind == "IDENT" and tok.value == "group":
                items.append(self.parse_group())
            elif tok.kind == "IDENT" and tok.value == "warp":
                items.append(self.parse_warp())
            elif tok.kind == "IDENT" and tok.value == "nudge":
                items.append(self.parse_nudge())
            else:
                raise NorthCelSyntaxError(
                    f"Unknown scene statement '{tok.value}'", tok.line, tok.column
                )

        self.expect("PUNCT", "}")
        return SceneNode(
            name=name_tok.value,
            width=width,
            height=height,
            fps=fps,
            precision=precision,
            seed=seed,
            palette=palette,
            paper=paper,
            defs=defs,
            items=items,
            span=SourceSpan(kw.line, kw.column),
        )

    def parse_film(self) -> FilmNode:
        kw = self.expect("IDENT", "film")
        name_tok = self.expect("IDENT")
        attrs = self.parse_attr_list() if self.cur().value == "(" else {}
        self.expect("PUNCT", "{")

        width = int(self._eval_const(attrs.get("width", 1024)))
        height = int(self._eval_const(attrs.get("height", 1024)))
        fps = int(self._eval_const(attrs.get("fps", 6)))
        frames = int(self._eval_const(attrs.get("frames", 2)))
        seed = int(self._eval_const(attrs.get("seed", 42)))
        precision = str(attrs.get("precision", "0.25px"))

        palette: dict[str, ColorValue] = {}
        self.active_palette = palette
        paper = PaperSpec()
        defs: dict[str, DefBlock] = {}
        items: list[SceneItem] = []
        frame_overrides: dict[int, SceneNode] = {}
        frame_ranges: list[tuple[int, int, SceneNode]] = []

        while not (self.cur().kind == "PUNCT" and self.cur().value == "}"):
            if self.cur().kind == "EOF":
                raise NorthCelSyntaxError("Unclosed 'film' block", kw.line, kw.column)
            tok = self.cur()
            if tok.kind == "IDENT" and tok.value == "palette":
                palette.update(self.parse_palette())
            elif tok.kind == "IDENT" and tok.value == "paper":
                paper = self.parse_paper()
            elif tok.kind == "IDENT" and tok.value == "def":
                d = self.parse_def()
                defs[d.name] = d
            elif tok.kind == "IDENT" and tok.value == "use":
                items.append(self.parse_use())
            elif tok.kind == "IDENT" and tok.value == "drop":
                items.append(self.parse_drop())
            elif tok.kind == "IDENT" and tok.value == "transform":
                items.append(self.parse_transform())
            elif tok.kind == "IDENT" and tok.value in ("layer", "wash", "cel"):
                items.append(self.parse_layer(is_cel=(tok.value == "cel")))
            elif tok.kind == "IDENT" and tok.value in ("bend_swarm", "swarm"):
                items.append(self.parse_swarm())
            elif tok.kind == "IDENT" and tok.value == "stroke":
                items.append(self.parse_stroke())
            elif tok.kind == "IDENT" and tok.value == "ribbon":
                items.append(self.parse_ribbon())
            elif tok.kind == "IDENT" and tok.value == "morph":
                items.append(self.parse_morph())
            elif tok.kind == "IDENT" and tok.value == "group":
                items.append(self.parse_group())
            elif tok.kind == "IDENT" and tok.value == "warp":
                items.append(self.parse_warp())
            elif tok.kind == "IDENT" and tok.value == "nudge":
                items.append(self.parse_nudge())
            elif tok.kind == "IDENT" and tok.value == "frame":
                f_lo, f_hi, f_scene = self.parse_frame_override(width, height, fps, precision, seed, paper, palette)
                if f_hi is None:
                    frame_overrides[f_lo] = f_scene
                else:
                    frame_ranges.append((f_lo, f_hi, f_scene))
            else:
                raise NorthCelSyntaxError(
                    f"Unknown film statement '{tok.value}'", tok.line, tok.column
                )

        self.expect("PUNCT", "}")
        return FilmNode(
            name=name_tok.value,
            width=width,
            height=height,
            fps=fps,
            frames=frames,
            precision=precision,
            seed=seed,
            palette=palette,
            paper=paper,
            defs=defs,
            items=items,
            frame_overrides=frame_overrides,
            span=SourceSpan(kw.line, kw.column),
            frame_ranges=frame_ranges,
        )

    def parse_frame_override(
        self,
        width: int,
        height: int,
        fps: int,
        precision: str,
        seed: int,
        default_paper: PaperSpec,
        parent_palette: dict[str, ColorValue],
    ) -> tuple[int, int | None, SceneNode]:
        kw = self.expect("IDENT", "frame")
        idx_tok = self.expect("NUMBER")
        if "." in idx_tok.value:
            raise NorthCelSyntaxError("Frame index must be an integer", idx_tok.line, idx_tok.column)
        f_idx = int(idx_tok.value)
        f_hi: int | None = None
        if self.match("RANGE"):
            # Spec 0.4: `frame A..B { ... }` applies to every frame A..B inclusive.
            hi_tok = self.expect("NUMBER")
            if "." in idx_tok.value or "." in hi_tok.value:
                raise NorthCelSyntaxError("Frame range bounds must be integers", idx_tok.line, idx_tok.column)
            f_hi = int(hi_tok.value)
            if f_hi < f_idx:
                raise NorthCelSyntaxError(
                    f"Frame range {f_idx}..{f_hi} is reversed; write {f_hi}..{f_idx}", idx_tok.line, idx_tok.column
                )
        self.expect("PUNCT", "{")
        paper = default_paper
        local_palette = dict(parent_palette)
        prev_palette = self.active_palette
        self.active_palette = local_palette
        defs: dict[str, DefBlock] = {}
        items: list[SceneItem] = []
        while not (self.cur().kind == "PUNCT" and self.cur().value == "}"):
            if self.cur().kind == "EOF":
                raise NorthCelSyntaxError("Unclosed 'frame' block", kw.line, kw.column)
            tok = self.cur()
            if tok.kind == "IDENT" and tok.value == "palette":
                local_palette.update(self.parse_palette())
            elif tok.kind == "IDENT" and tok.value == "paper":
                paper = self.parse_paper()
            elif tok.kind == "IDENT" and tok.value == "def":
                d = self.parse_def()
                defs[d.name] = d
            elif tok.kind == "IDENT" and tok.value == "use":
                items.append(self.parse_use())
            elif tok.kind == "IDENT" and tok.value == "drop":
                items.append(self.parse_drop())
            elif tok.kind == "IDENT" and tok.value == "transform":
                items.append(self.parse_transform())
            elif tok.kind == "IDENT" and tok.value in ("layer", "wash", "cel"):
                items.append(self.parse_layer(is_cel=(tok.value == "cel")))
            elif tok.kind == "IDENT" and tok.value in ("bend_swarm", "swarm"):
                items.append(self.parse_swarm())
            elif tok.kind == "IDENT" and tok.value == "stroke":
                items.append(self.parse_stroke())
            elif tok.kind == "IDENT" and tok.value == "ribbon":
                items.append(self.parse_ribbon())
            elif tok.kind == "IDENT" and tok.value == "morph":
                items.append(self.parse_morph())
            elif tok.kind == "IDENT" and tok.value == "group":
                items.append(self.parse_group())
            elif tok.kind == "IDENT" and tok.value == "warp":
                items.append(self.parse_warp())
            elif tok.kind == "IDENT" and tok.value == "nudge":
                items.append(self.parse_nudge())
            else:
                raise NorthCelSyntaxError(f"Unknown frame statement '{tok.value}'", tok.line, tok.column)
        self.expect("PUNCT", "}")
        self.active_palette = prev_palette
        return (
            f_idx,
            f_hi,
            SceneNode(
                name=f"frame_{f_idx}" if f_hi is None else f"frames_{f_idx}_{f_hi}",
                width=width,
                height=height,
                fps=fps,
                precision=precision,
                seed=seed,
                palette=local_palette,
                paper=paper,
                defs=defs,
                items=items,
                span=SourceSpan(kw.line, kw.column),
            ),
        )

    def parse_palette(self) -> dict[str, ColorValue]:
        kw = self.expect("IDENT", "palette")
        raw = self.parse_kv_brace_or_paren()
        out: dict[str, ColorValue] = {}
        for k, v in raw.items():
            if isinstance(v, ColorMix):
                raise NorthCelSyntaxError(
                    f"Palette entry '{k}' cannot be a mix(); palette colours are static", kw.line, kw.column
                )
            if isinstance(v, ColorValue):
                out[k] = v
            elif isinstance(v, (int, float, ExprValue)):
                out[k] = ColorValue.from_tone(int(round(self._eval_const(v))))
            elif isinstance(v, str) and v.startswith("#"):
                out[k] = ColorValue.from_hex(v)
        return out

    def parse_paper(self) -> PaperSpec:
        kw = self.expect("IDENT", "paper")
        attrs = self.parse_kv_brace_or_paren()
        color = self._extract_color(attrs, default_tone=239, span=SourceSpan(kw.line, kw.column))
        aa = int(self._eval_const(attrs.get("antialias_grid", 4)))
        grain = float(self._eval_const(attrs.get("grain", 0.0)))
        return PaperSpec(color=color, antialias_grid=aa, grain=grain, span=SourceSpan(kw.line, kw.column))

    def parse_def(self) -> DefBlock:
        kw = self.expect("IDENT", "def")
        name_tok = self.expect("IDENT")
        params: dict[str, float] = {}
        if self.cur().value == "(":
            raw_attrs = self.parse_attr_list()
            for k, v in raw_attrs.items():
                params[k] = float(self._eval_const(v))
        self.expect("PUNCT", "{")
        items: list[LayerNode | SwarmNode | StrokeNode | RibbonNode | MorphNode | TransformNode] = []
        while not (self.cur().kind == "PUNCT" and self.cur().value == "}"):
            if self.cur().kind == "EOF":
                raise NorthCelSyntaxError(f"Unclosed 'def {name_tok.value}' block", kw.line, kw.column)
            tok = self.cur()
            if tok.kind == "IDENT" and tok.value in ("layer", "wash", "cel"):
                items.append(self.parse_layer(is_cel=(tok.value == "cel")))
            elif tok.kind == "IDENT" and tok.value in ("bend_swarm", "swarm"):
                items.append(self.parse_swarm())
            elif tok.kind == "IDENT" and tok.value == "stroke":
                items.append(self.parse_stroke())
            elif tok.kind == "IDENT" and tok.value == "ribbon":
                items.append(self.parse_ribbon())
            elif tok.kind == "IDENT" and tok.value == "transform":
                items.append(self.parse_transform())
            elif tok.kind == "IDENT" and tok.value == "morph":
                items.append(self.parse_morph())
            elif tok.kind == "IDENT" and tok.value == "group":
                items.append(self.parse_group())
            elif tok.kind == "IDENT" and tok.value == "warp":
                items.append(self.parse_warp())
            elif tok.kind == "IDENT" and tok.value == "nudge":
                items.append(self.parse_nudge())
            else:
                raise NorthCelSyntaxError(
                    f"Unsupported statement '{tok.value}' inside def block", tok.line, tok.column
                )
        self.expect("PUNCT", "}")
        return DefBlock(name=name_tok.value, params=params, items=items, span=SourceSpan(kw.line, kw.column))

    def parse_use(self) -> UseNode:
        kw = self.expect("IDENT", "use")
        name_tok = self.expect("IDENT")
        args = self.parse_attr_list() if self.cur().value == "(" else {}
        self.match("PUNCT", ";")
        return UseNode(def_name=name_tok.value, args=args, span=SourceSpan(kw.line, kw.column))

    def parse_transform(self) -> TransformNode:
        kw = self.expect("IDENT", "transform")
        target = self.expect("IDENT").value
        attrs = self.parse_attr_list()
        for key in attrs:
            if key not in ("scale", "rotate", "anchor", "translate"):
                raise NorthCelSyntaxError(f"Unknown transform attribute '{key}'", kw.line, kw.column)
        def number(value):
            if isinstance(value, str):
                return ExprValue("const", (self._eval_const(value),))
            if not isinstance(value, (int, float, ExprValue)):
                raise NorthCelSyntaxError("Expected a numeric transform component", kw.line, kw.column)
            return value
        def pair(key, default, scalar=False):
            value = attrs.get(key, default)
            if not isinstance(value, tuple):
                if scalar:
                    return (number(value), number(value))
                raise NorthCelSyntaxError(f"transform.{key} requires 2 components", kw.line, kw.column)
            if len(value) != 2:
                raise NorthCelSyntaxError(f"transform.{key} requires 2 components", kw.line, kw.column)
            return (number(value[0]), number(value[1]))
        self.match("PUNCT", ";")
        return TransformNode(target, pair("scale", (1.0, 1.0), True), number(attrs.get("rotate", 0.0)),
                             pair("anchor", (0.0, 0.0)), pair("translate", (0.0, 0.0)),
                             "anchor" in attrs, SourceSpan(kw.line, kw.column))

    def _attr_pair(self, attrs: dict[str, Any], key: str, default: tuple[Any, Any],
                   line: int, column: int) -> tuple[Any, Any]:
        value = attrs.get(key, default)
        if not isinstance(value, tuple) or len(value) != 2:
            raise NorthCelSyntaxError(f"{key} requires 2 components", line, column)
        return value

    def _attr_name(self, attrs: dict[str, Any], key: str, line: int, column: int) -> str | None:
        value = attrs.get(key)
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, ExprValue) and value.op == "var":
            return str(value.args[0])
        raise NorthCelSyntaxError(f"{key} must name an entry", line, column)

    def parse_group_item(self) -> SceneItem:
        tok = self.cur()
        if tok.kind == "IDENT" and tok.value in ("layer", "wash", "cel"):
            return self.parse_layer(is_cel=(tok.value == "cel"))
        if tok.kind == "IDENT" and tok.value in ("bend_swarm", "swarm"):
            return self.parse_swarm()
        if tok.kind == "IDENT" and tok.value == "stroke":
            return self.parse_stroke()
        if tok.kind == "IDENT" and tok.value == "ribbon":
            return self.parse_ribbon()
        if tok.kind == "IDENT" and tok.value == "morph":
            return self.parse_morph()
        if tok.kind == "IDENT" and tok.value == "use":
            return self.parse_use()
        if tok.kind == "IDENT" and tok.value == "transform":
            return self.parse_transform()
        if tok.kind == "IDENT" and tok.value == "group":
            return self.parse_group()
        if tok.kind == "IDENT" and tok.value == "warp":
            return self.parse_warp()
        if tok.kind == "IDENT" and tok.value == "nudge":
            return self.parse_nudge()
        raise NorthCelSyntaxError(f"Unsupported group statement '{tok.value}'", tok.line, tok.column)

    def parse_group(self) -> GroupNode:
        kw = self.expect("IDENT", "group")
        name_tok = self.expect("IDENT")
        attrs = self.parse_attr_list() if self.cur().value == "(" else {}
        for key in attrs:
            if key not in ("pivot", "clip", "parent", "opacity"):
                raise NorthCelSyntaxError(f"Unknown group attribute '{key}'", kw.line, kw.column)
        pivot = self._attr_pair(attrs, "pivot", (0.0, 0.0), kw.line, kw.column)
        clip = self._attr_name(attrs, "clip", kw.line, kw.column)
        parent = self._attr_name(attrs, "parent", kw.line, kw.column)
        self.expect("PUNCT", "{")
        items: list[SceneItem] = []
        while not (self.cur().kind == "PUNCT" and self.cur().value == "}"):
            if self.cur().kind == "EOF":
                raise NorthCelSyntaxError(f"Unclosed 'group {name_tok.value}' block", kw.line, kw.column)
            items.append(self.parse_group_item())
        self.expect("PUNCT", "}")
        return GroupNode(name_tok.value, items, pivot, clip, parent,
                         attrs.get("opacity"), SourceSpan(kw.line, kw.column))

    def parse_warp(self) -> WarpNode:
        kw = self.expect("IDENT", "warp")
        target = self.expect("IDENT").value
        attrs = self.parse_attr_list()
        for key in attrs:
            if key not in ("handles", "radius"):
                raise NorthCelSyntaxError(f"Unknown warp attribute '{key}'", kw.line, kw.column)
        handles = attrs.get("handles")
        if not isinstance(handles, tuple) or not handles:
            raise NorthCelSyntaxError("warp needs handles: ((x, y, dx, dy), ...)", kw.line, kw.column)
        for h in handles:
            if not isinstance(h, tuple) or len(h) != 4:
                raise NorthCelSyntaxError("each warp handle needs 4 components (x, y, dx, dy)",
                                          kw.line, kw.column)
        self.match("PUNCT", ";")
        return WarpNode(target, handles, attrs.get("radius", 120.0), SourceSpan(kw.line, kw.column))

    def parse_nudge(self) -> NudgeNode:
        kw = self.expect("IDENT", "nudge")
        target = self.expect("IDENT").value
        attrs = self.parse_attr_list()
        for key in attrs:
            if key not in ("vertex", "ring", "dx", "dy"):
                raise NorthCelSyntaxError(f"Unknown nudge attribute '{key}'", kw.line, kw.column)
        if "vertex" not in attrs:
            raise NorthCelSyntaxError("nudge needs vertex:", kw.line, kw.column)
        self.match("PUNCT", ";")
        return NudgeNode(target, int(self._eval_const(attrs["vertex"])),
                         attrs.get("dx", 0.0), attrs.get("dy", 0.0),
                         int(self._eval_const(attrs.get("ring", 0))),
                         SourceSpan(kw.line, kw.column))

    def parse_drop(self) -> DropNode:
        kw = self.expect("IDENT", "drop")
        name_tok = self.expect("IDENT")
        self.match("PUNCT", ";")
        return DropNode(target_name=name_tok.value, span=SourceSpan(kw.line, kw.column))

    def parse_layer(self, is_cel: bool = False) -> LayerNode:
        kw = self.advance()  # layer, wash, or cel
        name_tok = self.expect("IDENT")
        attrs = self.parse_attr_list()
        self.expect("PUNCT", "{")
        payload_tok = self.expect("STRING")
        self.expect("PUNCT", "}")
        color = self._extract_color(attrs, default_tone=14, span=SourceSpan(kw.line, kw.column))
        rings_cnt = int(self._eval_const(attrs["rings"])) if "rings" in attrs else None
        boil = self._extract_boil(attrs)
        tx = self._extract_translate(attrs)
        outline_col, outline_w = self._extract_outline(attrs, is_cel, SourceSpan(kw.line, kw.column))
        return LayerNode(
            name=name_tok.value,
            color=color,
            rings_count=rings_cnt,
            payload=payload_tok.value[1:-1],
            boil=boil,
            translate_expr=tx,
            outline_color=outline_col,
            outline_width=outline_w,
            span=SourceSpan(kw.line, kw.column),
            opacity=self._extract_opacity(attrs, SourceSpan(kw.line, kw.column)),
        )

    def parse_swarm(self) -> SwarmNode:
        kw = self.advance()  # bend_swarm or swarm
        name_tok = self.expect("IDENT")
        attrs = self.parse_attr_list()
        self.expect("PUNCT", "{")
        payload_tok = self.expect("STRING")
        self.expect("PUNCT", "}")
        color = self._extract_color(attrs, default_tone=14, span=SourceSpan(kw.line, kw.column))
        agents = int(self._eval_const(attrs.get("agents", 1)))
        boil = self._extract_boil(attrs)
        tx = self._extract_translate(attrs)
        return SwarmNode(
            name=name_tok.value,
            agents=agents,
            color=color,
            payload=payload_tok.value[1:-1],
            boil=boil,
            translate_expr=tx,
            span=SourceSpan(kw.line, kw.column),
            opacity=self._extract_opacity(attrs, SourceSpan(kw.line, kw.column)),
        )

    def parse_stroke(self) -> StrokeNode:
        kw = self.expect("IDENT", "stroke")
        name_tok = self.expect("IDENT")
        attrs = self.parse_attr_list()
        self.expect("PUNCT", "{")
        points: list[tuple[Any, Any]] = []
        while not (self.cur().kind == "PUNCT" and self.cur().value == "}"):
            self.expect("PUNCT", "(")
            x_expr = self.parse_expr()
            self.expect("PUNCT", ",")
            y_expr = self.parse_expr()
            self.expect("PUNCT", ")")
            self.match("PUNCT", ",")
            points.append((x_expr, y_expr))
        self.expect("PUNCT", "}")
        color = self._extract_color(attrs, default_tone=14, span=SourceSpan(kw.line, kw.column))
        if "taper" in attrs and isinstance(attrs["taper"], tuple) and len(attrs["taper"]) == 2:
            w0 = float(self._eval_const(attrs["taper"][0]))
            w1 = float(self._eval_const(attrs["taper"][1]))
        else:
            w = float(self._eval_const(attrs.get("width", 2.5)))
            w0, w1 = w, w
        boil = self._extract_boil(attrs)
        return StrokeNode(
            name=name_tok.value,
            color=color,
            width_start=w0,
            width_end=w1,
            points=points,
            boil=boil,
            span=SourceSpan(kw.line, kw.column),
            opacity=self._extract_opacity(attrs, SourceSpan(kw.line, kw.column)),
        )

    def parse_ribbon(self) -> RibbonNode:
        kw = self.expect("IDENT", "ribbon")
        name_tok = self.expect("IDENT")
        attrs = self.parse_attr_list() if self.cur().value == "(" else {}
        self.expect("PUNCT", "{")
        points: list[tuple[Any, Any, float]] = []
        while not (self.cur().kind == "PUNCT" and self.cur().value == "}"):
            self.expect("PUNCT", "(")
            x_expr = self.parse_expr()
            self.expect("PUNCT", ",")
            y_expr = self.parse_expr()
            self.expect("PUNCT", ",")
            w_val = float(self._eval_const(self.parse_expr()))
            self.expect("PUNCT", ")")
            self.match("PUNCT", ",")
            points.append((x_expr, y_expr, w_val))
        self.expect("PUNCT", "}")
        color = self._extract_color(attrs, default_tone=14, span=SourceSpan(kw.line, kw.column))
        boil = self._extract_boil(attrs)
        return RibbonNode(
            name=name_tok.value,
            color=color,
            points=points,
            boil=boil,
            span=SourceSpan(kw.line, kw.column),
            opacity=self._extract_opacity(attrs, SourceSpan(kw.line, kw.column)),
        )

    def parse_morph(self) -> MorphNode:
        kw = self.expect("IDENT", "morph")
        name_tok = self.expect("IDENT")
        span = SourceSpan(kw.line, kw.column)
        attrs = self.parse_attr_list()
        self.expect("PUNCT", "{")
        a_tok = self.expect("STRING")
        self.expect("ARROW")
        b_tok = self.expect("STRING")
        self.expect("PUNCT", "}")
        for key in attrs:
            if key not in _MORPH_ATTRS:
                raise NorthCelSyntaxError(f"Unknown morph attribute '{key}'", kw.line, kw.column)
        if "u" not in attrs:
            raise NorthCelSyntaxError(f"morph '{name_tok.value}' requires a u: expression", kw.line, kw.column)
        u = attrs["u"]
        if isinstance(u, str):
            u = ExprValue("const", (self._eval_const(u),))
        if not isinstance(u, ExprValue):
            raise NorthCelSyntaxError("morph u must be a number or expression", kw.line, kw.column)
        samples = None
        if "samples" in attrs:
            raw = attrs["samples"]
            if not isinstance(raw, (int, float, ExprValue)):
                raise NorthCelSyntaxError("morph samples must be an integer", kw.line, kw.column)
            value = self._eval_const(raw)
            if value != int(value):
                raise NorthCelSyntaxError("morph samples must be an integer", kw.line, kw.column)
            samples = int(value)
        outline_col, outline_w = self._extract_outline(attrs, False, span)
        return MorphNode(
            name=name_tok.value,
            color=self._extract_color(attrs, default_tone=14, span=span),
            u=u,
            payload_a=a_tok.value[1:-1],
            payload_b=b_tok.value[1:-1],
            samples=samples,
            outline_color=outline_col,
            outline_width=outline_w,
            opacity=self._extract_opacity(attrs, span),
            span=span,
        )

    def parse_kv_brace_or_paren(self) -> dict[str, Any]:
        if self.cur().value == "(":
            return self.parse_attr_list()
        self.expect("PUNCT", "{")
        attrs: dict[str, Any] = {}
        while not (self.cur().kind == "PUNCT" and self.cur().value == "}"):
            key = self.expect("IDENT").value
            self.expect("PUNCT", ":")
            attrs[key] = self.parse_attr_value()
            self.match("PUNCT", ",")
        self.expect("PUNCT", "}")
        return attrs

    def parse_attr_list(self) -> dict[str, Any]:
        self.expect("PUNCT", "(")
        attrs: dict[str, Any] = {}
        while not (self.cur().kind == "PUNCT" and self.cur().value == ")"):
            key = self.expect("IDENT").value
            if self.cur().value in (":", "="):
                self.advance()
            else:
                tok = self.cur()
                raise NorthCelSyntaxError(f"Expected ':' after attribute '{key}'", tok.line, tok.column)
            attrs[key] = self.parse_attr_value()
            self.match("PUNCT", ",")
        self.expect("PUNCT", ")")
        return attrs

    def parse_attr_value(self) -> Any:
        tok = self.cur()
        if tok.kind == "HEX":
            hex_tok = self.advance()
            if len(hex_tok.value) - 1 not in (3, 6):
                raise NorthCelSyntaxError("Hex colours must have 3 or 6 digits", hex_tok.line, hex_tok.column)
            return ColorValue.from_hex(hex_tok.value)
        if tok.kind == "PUNCT" and tok.value == "$":
            self.advance()
            ref_tok = self.expect("IDENT")
            if ref_tok.value not in self.active_palette:
                raise NorthCelSyntaxError(
                    f"Undefined palette color '${ref_tok.value}'", ref_tok.line, ref_tok.column
                )
            return ColorValue.from_palette_ref(ref_tok.value, self.active_palette[ref_tok.value])
        if tok.kind == "STRING":
            return self.advance().value[1:-1]
        if tok.kind == "UNIT_NUM":
            return self.advance().value
        if tok.kind == "IDENT" and tok.value == "mix" and self.peek().value == "(":
            return self.parse_mix()
        if tok.kind == "IDENT" and tok.value == "rgb" and self.peek().value == "(":
            self.advance()
            self.expect("PUNCT", "(")
            r = int(self._eval_const(self.parse_expr()))
            self.expect("PUNCT", ",")
            g = int(self._eval_const(self.parse_expr()))
            self.expect("PUNCT", ",")
            b = int(self._eval_const(self.parse_expr()))
            self.expect("PUNCT", ")")
            return ColorValue.from_rgb(r, g, b)
        if tok.kind == "PUNCT" and tok.value == "(" and self._tuple_ahead():
            self.advance()
            items = [self.parse_attr_value()]
            while self.match("PUNCT", ","):
                if self.cur().value == ")":
                    break
                items.append(self.parse_attr_value())
            self.expect("PUNCT", ")")
            return tuple(items)
        return self.parse_expr()

    def parse_mix(self) -> ColorMix:
        """`mix(colourA, colourB, u)`; colours may be literals, $refs or nested mixes."""
        kw = self.expect("IDENT", "mix")
        self.expect("PUNCT", "(")
        sides = []
        for _ in range(2):
            at = self.cur()
            value = self.parse_attr_value()
            if isinstance(value, str) and value.startswith("#"):
                value = ColorValue.from_hex(value)
            elif isinstance(value, ExprValue) and value.op == "var" and str(value.args[0]) in self.active_palette:
                name = str(value.args[0])
                value = ColorValue.from_palette_ref(name, self.active_palette[name])
            if not isinstance(value, (ColorValue, ColorMix)):
                raise NorthCelSyntaxError("mix() expects two colours and a number: mix(#RRGGBB, $name, u)",
                                          at.line, at.column)
            sides.append(value)
            self.expect("PUNCT", ",")
        u = self.parse_expr()
        if not (self.cur().kind == "PUNCT" and self.cur().value == ")"):
            raise NorthCelSyntaxError("mix() takes exactly 3 arguments", kw.line, kw.column)
        self.expect("PUNCT", ")")
        return ColorMix(sides[0], sides[1], u)

    def _tuple_ahead(self) -> bool:
        depth = 0
        for token in self.tokens[self.idx:]:
            if token.value == "(":
                depth += 1
            elif token.value == ")":
                depth -= 1
                if depth == 0:
                    return False
            elif token.value == "," and depth == 1:
                return True
        return False

    def parse_expr(self) -> ExprValue:
        node = self.parse_term()
        while self.cur().kind == "PUNCT" and self.cur().value in ("+", "-"):
            op = self.advance().value
            right = self.parse_term()
            node = ExprValue("add" if op == "+" else "sub", (node, right))
        return node

    def parse_term(self) -> ExprValue:
        node = self.parse_factor()
        while self.cur().kind == "PUNCT" and self.cur().value in ("*", "/"):
            op = self.advance().value
            right = self.parse_factor()
            node = ExprValue("mul" if op == "*" else "div", (node, right))
        return node

    def parse_factor(self) -> ExprValue:
        tok = self.cur()
        if tok.kind == "PUNCT" and tok.value == "-":
            self.advance()
            return ExprValue("neg", (self.parse_factor(),))
        if tok.kind == "NUMBER":
            self.advance()
            return ExprValue("const", (float(tok.value),))
        if tok.kind == "UNIT_NUM":
            self.advance()
            raw = re.sub(r"(px-b63|px|deg)$", "", tok.value)
            return ExprValue("const", (float(raw),))
        if tok.kind == "IDENT":
            ident = self.advance().value
            if self.cur().kind == "PUNCT" and self.cur().value == "(":
                self.advance()
                args = []
                if not (self.cur().kind == "PUNCT" and self.cur().value == ")"):
                    args.append(self.parse_expr())
                    while self.match("PUNCT", ","):
                        args.append(self.parse_expr())
                self.expect("PUNCT", ")")
                if ident not in ("lerp", "sin", "cos", "step", "ease", "smoothstep"):
                    raise NorthCelSyntaxError(f"Unknown function '{ident}'", tok.line, tok.column)
                arity = {"ease": 1, "smoothstep": 3}.get(ident)
                if arity is not None and len(args) != arity:
                    raise NorthCelSyntaxError(f"{ident} expects {arity} arguments", tok.line, tok.column)
                return ExprValue(ident, tuple(args))
            return ExprValue("var", (ident,))
        if tok.kind == "PUNCT" and tok.value == "(":
            self.advance()
            inner = self.parse_expr()
            self.expect("PUNCT", ")")
            return inner
        raise NorthCelSyntaxError(f"Expected expression, got '{tok.value or tok.kind}'", tok.line, tok.column)

    def _eval_const(self, val: Any) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            raw = re.sub(r"(px-b63|px|deg)$", "", val.strip())
            return float(raw)
        if isinstance(val, ExprValue):
            return val.eval({"t": 0.0, "f": 0.0, "seed": 42.0})
        raise ValueError(f"Cannot evaluate constant from {val!r}")

    def _resolve_color_val(self, c: Any, span: SourceSpan) -> ColorValue | ColorMix:
        if isinstance(c, (ColorValue, ColorMix)):
            return c
        if isinstance(c, str) and c.startswith("#"):
            return ColorValue.from_hex(c)
        if isinstance(c, ExprValue) and c.op == "var" and str(c.args[0]) in self.active_palette:
            nm = str(c.args[0])
            return ColorValue.from_palette_ref(nm, self.active_palette[nm])
        raise NorthCelSyntaxError("Invalid color attribute value", span.line, span.column)

    def _extract_color(self, attrs: dict[str, Any], default_tone: int, span: SourceSpan) -> ColorValue | ColorMix:
        for key in ("color", "fill"):
            if key in attrs:
                return self._resolve_color_val(attrs[key], span)
        if "tone" in attrs:
            t = int(round(self._eval_const(attrs["tone"])))
            return ColorValue.from_tone(t)
        return ColorValue.from_tone(default_tone)

    def _extract_outline(
        self, attrs: dict[str, Any], is_cel: bool, span: SourceSpan
    ) -> tuple[ColorValue | None, float]:
        if "outline" not in attrs and "ink_width" not in attrs and not is_cel:
            return (None, 0.0)
        default_col = self.active_palette.get("ink", ColorValue.from_hex("#0D0D0D"))
        if "outline" in attrs:
            ov = attrs["outline"]
            if isinstance(ov, tuple) and len(ov) == 2:
                col = self._resolve_color_val(ov[0], span)
                w = float(self._eval_const(ov[1]))
                return (col, w)
            w = float(self._eval_const(ov))
            return (default_col, w)
        if "ink_width" in attrs:
            w = float(self._eval_const(attrs["ink_width"]))
            col = self._resolve_color_val(attrs["ink"], span) if "ink" in attrs else default_col
            return (col, w)
        return (None, 0.0)

    def _extract_opacity(self, attrs: dict[str, Any], span: SourceSpan) -> ExprValue | None:
        """Spec 0.4 `opacity: expr`, clamped to 0..1 at render time. Absent means opaque."""
        if "opacity" not in attrs:
            return None
        value = attrs["opacity"]
        if isinstance(value, (int, float)):
            return ExprValue("const", (float(value),))
        if isinstance(value, ExprValue):
            return value
        raise NorthCelSyntaxError("opacity must be a number or expression in 0..1", span.line, span.column)

    def _extract_boil(self, attrs: dict[str, Any]) -> BoilSpec | None:
        if "boil" not in attrs:
            return None
        b = attrs["boil"]
        if isinstance(b, tuple) and len(b) >= 2:
            amp = float(self._eval_const(b[0]))
            freq = float(self._eval_const(b[1]))
            return BoilSpec(amplitude_px=amp, frequency=freq)
        amp = float(self._eval_const(b))
        return BoilSpec(amplitude_px=amp, frequency=1.0)

    def _extract_translate(self, attrs: dict[str, Any]) -> tuple[Any, Any]:
        if "translate" in attrs and isinstance(attrs["translate"], tuple) and len(attrs["translate"]) == 2:
            return (attrs["translate"][0], attrs["translate"][1])
        dx = attrs.get("dx", ExprValue("const", (0.0,)))
        dy = attrs.get("dy", ExprValue("const", (0.0,)))
        return (dx, dy)


_MORPH_ATTRS = ("color", "fill", "tone", "u", "samples", "outline", "ink", "ink_width", "opacity")


def parse_ncel(source: str) -> DocumentNode:
    """Parses a NorthCel (.ncel) source string into a DocumentNode."""
    tokens = tokenize(source)
    parser = _Parser(tokens)
    return parser.parse_document()
