"""Typed AST nodes for NorthCel (.ncel) v0.1."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    line: int
    column: int


@dataclass(frozen=True)
class ColorValue:
    """Represents either a greyscale tone (0..255) or an RGB color (r, g, b)."""

    r: int
    g: int
    b: int
    is_grey: bool = True

    @classmethod
    def from_tone(cls, tone: int) -> "ColorValue":
        v = int(tone)
        return cls(r=v, g=v, b=v, is_grey=True)

    @classmethod
    def from_rgb(cls, r: int, g: int, b: int) -> "ColorValue":
        return cls(r=int(r), g=int(g), b=int(b), is_grey=(r == g == b))

    @classmethod
    def from_hex(cls, hex_str: str) -> "ColorValue":
        h = hex_str.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return cls(r=r, g=g, b=b, is_grey=(r == g == b))

    def to_hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def as_rgb_tuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)


@dataclass(frozen=True)
class BoilSpec:
    amplitude_px: float = 0.0
    frequency: float = 1.0
    seed_offset: int = 0


@dataclass(frozen=True)
class PaperSpec:
    color: ColorValue = field(default_factory=lambda: ColorValue.from_tone(239))
    antialias_grid: int = 4
    grain: float = 0.0
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class LayerNode:
    name: str
    color: ColorValue
    rings_count: int | None
    payload: str
    boil: BoilSpec | None = None
    translate_expr: tuple[Any, Any] = (0.0, 0.0)
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class SwarmNode:
    name: str
    agents: int
    color: ColorValue
    payload: str
    boil: BoilSpec | None = None
    translate_expr: tuple[Any, Any] = (0.0, 0.0)
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class StrokeNode:
    name: str
    color: ColorValue
    width_start: float
    width_end: float
    points: list[tuple[Any, Any]]
    boil: BoilSpec | None = None
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class RibbonNode:
    name: str
    color: ColorValue
    points: list[tuple[Any, Any, float]]
    boil: BoilSpec | None = None
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class DefBlock:
    name: str
    params: dict[str, float]
    items: list[LayerNode | SwarmNode | StrokeNode | RibbonNode]
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class UseNode:
    def_name: str
    args: dict[str, Any]
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


SceneItem = LayerNode | SwarmNode | StrokeNode | RibbonNode | UseNode


@dataclass(frozen=True)
class SceneNode:
    name: str
    width: int = 1024
    height: int = 1024
    fps: int = 6
    precision: str = "0.25px"
    seed: int = 42
    paper: PaperSpec = field(default_factory=PaperSpec)
    defs: dict[str, DefBlock] = field(default_factory=dict)
    items: list[SceneItem] = field(default_factory=list)
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class FilmNode:
    name: str
    width: int = 1024
    height: int = 1024
    fps: int = 6
    frames: int = 2
    precision: str = "0.25px"
    seed: int = 42
    paper: PaperSpec = field(default_factory=PaperSpec)
    defs: dict[str, DefBlock] = field(default_factory=dict)
    items: list[SceneItem] = field(default_factory=list)
    frame_overrides: dict[int, SceneNode] = field(default_factory=dict)
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class DocumentNode:
    spec_version: str
    root: SceneNode | FilmNode
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))
