"""Filesystem layout of the installed package.

Everything the launcher needs to read ships *inside* the single `northcel`
distribution: the reference examples, the guide, and the generated toolchain
pins. Only the native binaries live in the separate `northcel-native` wheel.
"""

from __future__ import annotations

from pathlib import Path

#: Directory of the import package (`.../site-packages/northcel`).
PKG_DIR = Path(__file__).resolve().parent.parent

#: Reference `.ncel` examples — also the fixtures `verify` renders.
EXAMPLES = PKG_DIR / "examples"

#: Generated data (toolchain pins).
DATA = PKG_DIR / "data"

#: The offline authoring guide shown by `northcel guide`.
GUIDE = PKG_DIR / "AGENT-GUIDE.md"

#: The conformance suite (`check`/render probes).
CONFORMANCE = PKG_DIR / "conformance"


def example(name: str) -> Path:
    """Path to a bundled example, e.g. ``example("shower_f0001.ncel")``."""
    return EXAMPLES / name


def pins_path() -> Path:
    return DATA / "pins.json"
