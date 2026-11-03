"""NorthCel (.ncel) — the AI-drawn video programming language."""

from .config import (
    CLI_COMMAND,
    CLI_SHORT_ALIAS,
    DOCS_URL,
    FILE_EXTENSION,
    LANGUAGE_NAME,
    NPM_PACKAGE,
    PACKAGE_VERSION,
    PYPI_PACKAGE,
    SPEC_VERSION,
)
from .ast_nodes import (
    BoilSpec,
    ColorValue,
    DefBlock,
    DocumentNode,
    FilmNode,
    LayerNode,
    PaperSpec,
    RibbonNode,
    SceneNode,
    StrokeNode,
    SwarmNode,
    UseNode,
)
from .parser import NorthCelSyntaxError, parse_ncel
from .validator import ValidationDiagnostic, validate_document
from .formatter import format_document
from .rings import (
    decode_ring_b63_1px,
    decode_ring_q25,
    decode_rings_payload,
    encode_ring_b63_1px,
    encode_ring_q25,
    encode_rings_payload,
)
from .renderer import render_document_frame, render_film_frames

__version__ = PACKAGE_VERSION

__all__ = [
    "LANGUAGE_NAME",
    "FILE_EXTENSION",
    "CLI_COMMAND",
    "CLI_SHORT_ALIAS",
    "PYPI_PACKAGE",
    "NPM_PACKAGE",
    "PACKAGE_VERSION",
    "SPEC_VERSION",
    "DOCS_URL",
    "__version__",
    "BoilSpec",
    "ColorValue",
    "DefBlock",
    "DocumentNode",
    "FilmNode",
    "LayerNode",
    "PaperSpec",
    "RibbonNode",
    "SceneNode",
    "StrokeNode",
    "SwarmNode",
    "UseNode",
    "NorthCelSyntaxError",
    "parse_ncel",
    "ValidationDiagnostic",
    "validate_document",
    "format_document",
    "decode_ring_b63_1px",
    "decode_ring_q25",
    "decode_rings_payload",
    "encode_ring_b63_1px",
    "encode_ring_q25",
    "encode_rings_payload",
    "render_document_frame",
    "render_film_frames",
]
