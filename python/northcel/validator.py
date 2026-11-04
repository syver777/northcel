"""Semantic validator for NorthCel (.ncel) AST documents."""

from __future__ import annotations

from dataclasses import dataclass

from .ast_nodes import (
    ColorValue,
    DefBlock,
    DocumentNode,
    FilmNode,
    LayerNode,
    RibbonNode,
    SceneItem,
    StrokeNode,
    SwarmNode,
    UseNode,
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


def _check_color(c: ColorValue, line: int, col: int, out: list[ValidationDiagnostic]) -> None:
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

    return out
