"""Semantic validator for NorthCel (.ncel) AST documents."""

from __future__ import annotations

from dataclasses import dataclass

from .ast_nodes import (
    ColorMix,
    ColorValue,
    DefBlock,
    DocumentNode,
    FilmNode,
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
    UseNode,
    WarpNode,
)
from .config import SUPPORTED_SPEC_VERSIONS
from .rings import RingEncodingError, decode_rings_payload


@dataclass(frozen=True)
class ValidationDiagnostic:
    level: str  # "error" or "warning"
    message: str
    line: int
    column: int

    def format(self) -> str:
        return f"{self.line}:{self.column}: {self.level}: {self.message}"


def _check_color(c: ColorValue | ColorMix | None, line: int, col: int, out: list[ValidationDiagnostic]) -> None:
    if c is None:
        return
    if isinstance(c, ColorMix):
        _check_color(c.a, line, col, out)
        _check_color(c.b, line, col, out)
        return
    for ch_name, val in (("r", c.r), ("g", c.g), ("b", c.b)):
        if not (0 <= val <= 255):
            out.append(
                ValidationDiagnostic(
                    "error", f"Color channel {ch_name}={val} out of range [0..255]", line, col
                )
            )


def _validate_items(
    items: list[SceneItem],
    defs: dict[str, DefBlock],
    precision: str,
    out: list[ValidationDiagnostic],
) -> None:
    for item in items:
        if isinstance(item, LayerNode):
            _check_color(item.color, item.span.line, item.span.column, out)
            try:
                rings = decode_rings_payload(item.payload, precision=precision)
                if item.rings_count is not None and item.rings_count != len(rings):
                    out.append(
                        ValidationDiagnostic(
                            "warning",
                            f"Layer '{item.name}' declares rings: {item.rings_count}, but payload contains {len(rings)} rings",
                            item.span.line,
                            item.span.column,
                        )
                    )
            except RingEncodingError as exc:
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Layer '{item.name}' has invalid ring payload: {exc}",
                        item.span.line,
                        item.span.column,
                    )
                )
        elif isinstance(item, SwarmNode):
            _check_color(item.color, item.span.line, item.span.column, out)
            if item.agents <= 0:
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Swarm '{item.name}' must have agents >= 1 (got {item.agents})",
                        item.span.line,
                        item.span.column,
                    )
                )
            try:
                rings = decode_rings_payload(item.payload, precision=precision)
                if len(rings) == 0:
                    out.append(
                        ValidationDiagnostic(
                            "error",
                            f"Swarm '{item.name}' payload decoded to 0 rings",
                            item.span.line,
                            item.span.column,
                        )
                    )
            except RingEncodingError as exc:
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Swarm '{item.name}' has invalid ring payload: {exc}",
                        item.span.line,
                        item.span.column,
                    )
                )
        elif isinstance(item, StrokeNode):
            _check_color(item.color, item.span.line, item.span.column, out)
            if len(item.points) < 2:
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Stroke '{item.name}' requires at least 2 control points",
                        item.span.line,
                        item.span.column,
                    )
                )
            if item.width_start <= 0 or item.width_end <= 0:
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Stroke '{item.name}' widths must be > 0",
                        item.span.line,
                        item.span.column,
                    )
                )
        elif isinstance(item, RibbonNode):
            _check_color(item.color, item.span.line, item.span.column, out)
            if len(item.points) < 2:
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Ribbon '{item.name}' requires at least 2 (x, y, width) points",
                        item.span.line,
                        item.span.column,
                    )
                )
        elif isinstance(item, MorphNode):
            _check_color(item.color, item.span.line, item.span.column, out)
            _check_color(item.outline_color, item.span.line, item.span.column, out)
            try:
                rings_a = decode_rings_payload(item.payload_a, precision=precision)
                rings_b = decode_rings_payload(item.payload_b, precision=precision)
            except RingEncodingError as exc:
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Morph '{item.name}' has invalid ring payload: {exc}",
                        item.span.line,
                        item.span.column,
                    )
                )
            else:
                if not rings_a or len(rings_a) != len(rings_b):
                    out.append(
                        ValidationDiagnostic(
                            "error",
                            f"Morph '{item.name}' pairs ring i with ring i, but its sides have {len(rings_a)} and {len(rings_b)} rings",
                            item.span.line,
                            item.span.column,
                        )
                    )
            if item.samples is not None and not (MORPH_MIN_SAMPLES <= item.samples <= MORPH_MAX_SAMPLES):
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Morph '{item.name}' samples must be {MORPH_MIN_SAMPLES}..{MORPH_MAX_SAMPLES} (got {item.samples})",
                        item.span.line,
                        item.span.column,
                    )
                )
        elif isinstance(item, GroupNode):
            _validate_items(item.items, defs, precision, out)
            for name in (item.clip, item.parent):
                if name is not None and not any(ch.isalnum() or ch == "_" for ch in name):
                    out.append(ValidationDiagnostic(
                        "error", f"Group '{item.name}' target '{name}' must be a name",
                        item.span.line, item.span.column))
        elif isinstance(item, WarpNode):
            if not item.handles:
                out.append(ValidationDiagnostic(
                    "error", f"Warp '{item.target_name}' needs at least one handle",
                    item.span.line, item.span.column))
            for h in item.handles:
                if len(h) != 4:
                    out.append(ValidationDiagnostic(
                        "error", f"Warp '{item.target_name}' handles need (x, y, dx, dy)",
                        item.span.line, item.span.column))
        elif isinstance(item, NudgeNode):
            if item.ring < 0 or item.vertex < 0:
                out.append(ValidationDiagnostic(
                    "error", f"Nudge '{item.target_name}' ring/vertex must be >= 0",
                    item.span.line, item.span.column))
        elif isinstance(item, UseNode):
            if item.def_name not in defs:
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Use of undefined def block '{item.def_name}'",
                        item.span.line,
                        item.span.column,
                    )
                )


MORPH_MIN_SAMPLES = 3
MORPH_MAX_SAMPLES = 1024


def spec_minor(version: str) -> int:
    """`"0.4.0-draft"` -> 4. Unknown shapes count as the current draft."""
    parts = version.split("-", 1)[0].split(".")
    try:
        return int(parts[1]) if parts[0] == "0" and len(parts) > 1 else 99
    except ValueError:
        return 99


def _is_mix(c: object) -> bool:
    return isinstance(c, ColorMix)


def spec04_features(doc: DocumentNode) -> list[tuple[str, int, int]]:
    """Every use of a spec 0.4 construct as (feature, line, column).

    Features: `mix`, `morph`, `frame-range`, `opacity`. The launcher uses this to
    route such documents to the Python reference, because the native runtime
    (spec 0.3) does not implement them.
    """
    found: list[tuple[str, int, int]] = []

    def paper(p: PaperSpec) -> None:
        if _is_mix(p.color):
            found.append(("mix", p.span.line, p.span.column))

    def items(seq) -> None:
        for it in seq:
            line, col = it.span.line, it.span.column
            if isinstance(it, MorphNode):
                found.append(("morph", line, col))
            if _is_mix(getattr(it, "color", None)) or _is_mix(getattr(it, "outline_color", None)):
                found.append(("mix", line, col))
            if getattr(it, "opacity", None) is not None:
                found.append(("opacity", line, col))
            if isinstance(it, UseNode) and "opacity" in it.args:
                found.append(("opacity", line, col))
            if isinstance(it, GroupNode):
                items(it.items)

    def scene(node) -> None:
        paper(node.paper)
        for d in node.defs.values():
            items(d.items)
        items(node.items)

    root = doc.root
    scene(root)
    if isinstance(root, FilmNode):
        for f_scene in root.frame_overrides.values():
            scene(f_scene)
        for _lo, _hi, f_scene in root.frame_ranges:
            found.append(("frame-range", f_scene.span.line, f_scene.span.column))
            scene(f_scene)
    return found


def spec05_features(doc: DocumentNode) -> list[tuple[str, int, int]]:
    """Every use of a spec 0.5 construct as (feature, line, column)."""
    found: list[tuple[str, int, int]] = []

    def items(seq) -> None:
        for it in seq:
            if isinstance(it, GroupNode):
                found.append(("group", it.span.line, it.span.column))
                items(it.items)
            elif isinstance(it, WarpNode):
                found.append(("warp", it.span.line, it.span.column))
            elif isinstance(it, NudgeNode):
                found.append(("nudge", it.span.line, it.span.column))

    def scene(node) -> None:
        for d in node.defs.values():
            items(d.items)
        items(node.items)

    root = doc.root
    scene(root)
    if isinstance(root, FilmNode):
        for f_scene in root.frame_overrides.values():
            scene(f_scene)
        for _lo, _hi, f_scene in root.frame_ranges:
            scene(f_scene)
    return found


def _check_spec05(doc: DocumentNode, out: list[ValidationDiagnostic]) -> None:
    if spec_minor(doc.spec_version) >= 5:
        return
    seen: set[tuple[str, int, int]] = set()
    for feature, line, col in spec05_features(doc):
        if (feature, line, col) in seen:
            continue
        seen.add((feature, line, col))
        out.append(ValidationDiagnostic(
            "error",
            f"{feature} requires northcel \"0.5.0-draft\" (this document declares '{doc.spec_version}')",
            line, col))


def _check_spec04(doc: DocumentNode, out: list[ValidationDiagnostic]) -> None:
    if spec_minor(doc.spec_version) >= 4:
        return
    seen: set[tuple[str, int, int]] = set()
    for feature, line, col in spec04_features(doc):
        if (feature, line, col) in seen:
            continue
        seen.add((feature, line, col))
        if feature == "opacity":
            out.append(
                ValidationDiagnostic(
                    "warning",
                    f"opacity is a spec 0.4 attribute and is ignored in a '{doc.spec_version}' document; "
                    f"declare northcel \"0.4.0-draft\" to use it",
                    line,
                    col,
                )
            )
        else:
            out.append(
                ValidationDiagnostic(
                    "error",
                    f"{feature} requires northcel \"0.4.0-draft\" (this document declares '{doc.spec_version}')",
                    line,
                    col,
                )
            )


def validate_document(doc: DocumentNode) -> list[ValidationDiagnostic]:
    """Returns a list of errors and warnings for a parsed DocumentNode."""
    out: list[ValidationDiagnostic] = []
    if doc.spec_version not in SUPPORTED_SPEC_VERSIONS:
        out.append(
            ValidationDiagnostic(
                "error",
                f"Unsupported NorthCel version '{doc.spec_version}'. Supported: {SUPPORTED_SPEC_VERSIONS}",
                doc.span.line,
                doc.span.column,
            )
        )

    root = doc.root
    if root.width <= 0 or root.height <= 0 or root.width > 8192 or root.height > 8192:
        out.append(
            ValidationDiagnostic(
                "error",
                f"Canvas dimensions {root.width}x{root.height} out of valid range [1..8192]",
                root.span.line,
                root.span.column,
            )
        )
    if root.fps <= 0 or root.fps > 240:
        out.append(
            ValidationDiagnostic(
                "error",
                f"FPS {root.fps} out of valid range [1..240]",
                root.span.line,
                root.span.column,
            )
        )
    if root.precision not in ("0.25px", "0.25px-b63", "1px"):
        out.append(
            ValidationDiagnostic(
                "error",
                f"Unsupported precision '{root.precision}' (expected '0.25px', '0.25px-b63', or '1px')",
                root.span.line,
                root.span.column,
            )
        )
    _check_color(root.paper.color, root.paper.span.line, root.paper.span.column, out)
    if doc.spec_version in SUPPORTED_SPEC_VERSIONS:
        _check_spec04(doc, out)
    _check_spec05(doc, out)
    if root.paper.antialias_grid not in (1, 2, 4, 8):
        out.append(
            ValidationDiagnostic(
                "error",
                f"paper.antialias_grid must be 1, 2, 4, or 8 (got {root.paper.antialias_grid})",
                root.paper.span.line,
                root.paper.span.column,
            )
        )

    for d in root.defs.values():
        _validate_items(list(d.items), root.defs, root.precision, out)

    _validate_items(root.items, root.defs, root.precision, out)

    if isinstance(root, FilmNode):
        if root.frames <= 0:
            out.append(
                ValidationDiagnostic(
                    "error",
                    f"Film frames count must be >= 1 (got {root.frames})",
                    root.span.line,
                    root.span.column,
                )
            )
        for f_idx, f_scene in root.frame_overrides.items():
            if not (0 <= f_idx < root.frames):
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Frame override index {f_idx} out of range [0..{root.frames - 1}]",
                        f_scene.span.line,
                        f_scene.span.column,
                    )
                )
            merged_defs = {**root.defs, **f_scene.defs}
            _validate_items(f_scene.items, merged_defs, root.precision, out)
            for d in f_scene.defs.values():
                _validate_items(list(d.items), merged_defs, root.precision, out)
        previous: list[tuple[int, int, SceneNode]] = []
        for lo, hi, f_scene in root.frame_ranges:
            if not (0 <= lo <= hi < root.frames):
                out.append(
                    ValidationDiagnostic(
                        "error",
                        f"Frame range {lo}..{hi} out of range [0..{root.frames - 1}]",
                        f_scene.span.line,
                        f_scene.span.column,
                    )
                )
            for plo, phi, p_scene in previous:
                if lo <= phi and plo <= hi:
                    out.append(
                        ValidationDiagnostic(
                            "warning",
                            f"Frame range {lo}..{hi} overlaps {plo}..{phi} (line {p_scene.span.line}); "
                            f"the later block wins for frames {max(lo, plo)}..{min(hi, phi)}",
                            f_scene.span.line,
                            f_scene.span.column,
                        )
                    )
            previous.append((lo, hi, f_scene))
            merged_defs = {**root.defs, **f_scene.defs}
            _validate_items(f_scene.items, merged_defs, root.precision, out)
            for d in f_scene.defs.values():
                _validate_items(list(d.items), merged_defs, root.precision, out)

    return out
