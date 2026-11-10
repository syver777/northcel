"""Typed AST nodes for NorthCel (.ncel) up to spec 0.4."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    line: int
    column: int


@dataclass(frozen=True)
class ColorValue:
    """Represents either a greyscale tone (0..255), an RGB color (r, g, b), or a palette reference."""

    r: int
    g: int
    b: int
    is_grey: bool = True
    palette_ref: str | None = None

    @classmethod
    def from_tone(cls, tone: int) -> "ColorValue":
        v = int(tone)
        return cls(r=v, g=v, b=v, is_grey=True, palette_ref=None)

    @classmethod
    def from_rgb(cls, r: int, g: int, b: int) -> "ColorValue":
        return cls(r=int(r), g=int(g), b=int(b), is_grey=(r == g == b), palette_ref=None)

    @classmethod
    def from_hex(cls, hex_str: str) -> "ColorValue":
        h = hex_str.lstrip("#")
        if len(h) not in (3, 6):
            raise ValueError("hex colours must have 3 or 6 digits")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return cls(r=r, g=g, b=b, is_grey=(r == g == b), palette_ref=None)

    @classmethod
    def from_palette_ref(cls, name: str, resolved: "ColorValue") -> "ColorValue":
        return cls(r=resolved.r, g=resolved.g, b=resolved.b, is_grey=resolved.is_grey, palette_ref=name)

    def to_hex(self) -> str:
        return f"#{self.r:02X}{self.g:02X}{self.b:02X}"

    def as_rgb_tuple(self) -> tuple[int, int, int]:
        return (self.r, self.g, self.b)


@dataclass(frozen=True)
class ColorMix:
    """Spec 0.4 colour expression `mix(a, b, u)`: evaluated per frame, sRGB, u clamped to 0..1.

    `a` and `b` are colours (`ColorValue`) or nested mixes. Each channel is
    `floor(a + (b - a) * u + 0.5)`, so the evaluated colour is an 8-bit RGB value.
    """

    a: "ColorValue | ColorMix"
    b: "ColorValue | ColorMix"
    u: Any

    def describe(self) -> str:
        def side(c: "ColorValue | ColorMix") -> str:
            if isinstance(c, ColorMix):
                return c.describe()
            return f"${c.palette_ref}" if c.palette_ref else c.to_hex()
        return f"mix({side(self.a)}, {side(self.b)}, …)"


#: A colour attribute value: a static colour or a per-frame colour expression.
ColorSpec = ColorValue | ColorMix


@dataclass(frozen=True)
class BoilSpec:
    amplitude_px: float = 0.0
    frequency: float = 1.0
    seed_offset: int = 0


@dataclass(frozen=True)
class PaperSpec:
    color: ColorSpec = field(default_factory=lambda: ColorValue.from_tone(239))
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
    outline_color: ColorSpec | None = None
    outline_width: float = 0.0
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))
    opacity: Any = None  # spec 0.4: None means opaque (attribute absent)


@dataclass(frozen=True)
class SwarmNode:
    name: str
    agents: int
    color: ColorSpec
    payload: str
    boil: BoilSpec | None = None
    translate_expr: tuple[Any, Any] = (0.0, 0.0)
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))
    opacity: Any = None


@dataclass(frozen=True)
class StrokeNode:
    name: str
    color: ColorSpec
    width_start: float
    width_end: float
    points: list[tuple[Any, Any]]
    boil: BoilSpec | None = None
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))
    opacity: Any = None


@dataclass(frozen=True)
class RibbonNode:
    name: str
    color: ColorSpec
    points: list[tuple[Any, Any, float]]
    boil: BoilSpec | None = None
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))
    opacity: Any = None


@dataclass(frozen=True)
class MorphNode:
    """Spec 0.4 `morph name(color: ..., u: expr[, samples: N, outline: ..., opacity: ...]) { "A" => "B" }`.

    Ring i of payload A is paired with ring i of payload B. Each pair is resampled
    by arclength to `samples` points (default: the larger vertex count, at least 8),
    winding-normalised, start-aligned by the cyclic shift with least squared
    distance about the centroids, then linearly interpolated at u (clamped 0..1).
    u <= 0 paints A's decoded rings exactly; u >= 1 paints B's exactly.
    """

    name: str
    color: ColorSpec
    u: Any
    payload_a: str
    payload_b: str
    samples: int | None = None
    outline_color: ColorSpec | None = None
    outline_width: float = 0.0
    opacity: Any = None
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class GroupNode:
    """Spec 0.5 named group: a paint unit with a pivot, optional clip/parent and opacity.

    Groups may contain primitives, `use`, transforms, warps, nudges and nested
    groups. The group name addresses all its paints for transforms/warps and for
    clipping. `clip` names another entry (or group) whose coverage limits this
    group. `parent` is an optional rigging link: the child group joins the
    parent's transform path.
    """

    name: str
    items: list["SceneItem"]
    pivot: tuple[Any, Any] = (0.0, 0.0)
    clip: str | None = None
    parent: str | None = None
    opacity: Any = None
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class WarpNode:
    """Spec 0.5 handle-based free-form deformation.

    `handles` is a tuple of (x, y, dx, dy). Each point inside `radius` of a
    handle receives the weighted average of the handle offsets, with a smooth
    falloff `(1 - (d/r)^2)^2`. Handles may be expressions, so an AI can animate
    a petal, cloth or squash with a few numbers.
    """

    target_name: str
    handles: tuple[tuple[Any, Any, Any, Any], ...]
    radius: Any = 120.0
    #: "smooth" (spec 0.5 weighted falloff) or "arap" (spec 0.6 rigid energy).
    mode: str = "smooth"
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class NudgeNode:
    """Spec 0.5 per-vertex offset on a named shape (ring/vertex indices)."""

    target_name: str
    vertex: int
    dx: Any
    dy: Any
    ring: int = 0
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class DropNode:
    """v0.2 Frame Delta primitive: removes a named layer/item inherited from the base film."""

    target_name: str
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class TransformNode:
    target_name: str
    scale: tuple[Any, Any] = (1.0, 1.0)
    rotate: Any = 0.0
    anchor: tuple[Any, Any] = (0.0, 0.0)
    translate: tuple[Any, Any] = (0.0, 0.0)
    anchor_explicit: bool = False
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class DefBlock:
    name: str
    params: dict[str, float]
    items: list["SceneItem"]
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))


@dataclass(frozen=True)
class UseNode:
    def_name: str
    args: dict[str, Any]
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))
    # Spec 0.4: `opacity` in a use's arguments is group opacity (see renderer).
    # It is also kept in `args`, so a def may still read it as a parameter.


SceneItem = (LayerNode | SwarmNode | StrokeNode | RibbonNode | MorphNode | UseNode | DropNode
             | TransformNode | GroupNode | WarpNode | NudgeNode)


@dataclass(frozen=True)
class SceneNode:
    name: str
    width: int = 1024
    height: int = 1024
    fps: int = 6
    precision: str = "0.25px"
    seed: int = 42
    palette: dict[str, ColorValue] = field(default_factory=dict)
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
    palette: dict[str, ColorValue] = field(default_factory=dict)
    paper: PaperSpec = field(default_factory=PaperSpec)
    defs: dict[str, DefBlock] = field(default_factory=dict)
    items: list[SceneItem] = field(default_factory=list)
    frame_overrides: dict[int, SceneNode] = field(default_factory=dict)
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))
    #: Spec 0.4 `frame A..B { ... }` blocks, inclusive, in source order.
    #: An exact `frame N` wins over every range; among ranges the last one wins.
    frame_ranges: list[tuple[int, int, SceneNode]] = field(default_factory=list)

    def override_for(self, frame_index: int) -> SceneNode | None:
        """The single override block that applies to `frame_index`, or None."""
        if frame_index in self.frame_overrides:
            return self.frame_overrides[frame_index]
        for lo, hi, scene in reversed(self.frame_ranges):
            if lo <= frame_index <= hi:
                return scene
        return None


@dataclass(frozen=True)
class DocumentNode:
    spec_version: str
    root: SceneNode | FilmNode
    span: SourceSpan = field(default_factory=lambda: SourceSpan(1, 1))
