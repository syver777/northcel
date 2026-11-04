"""Carrier for the native NorthCel runtime bundle.

This package contains no Python logic: it ships `bin/`, `share/ncel/` and
`bundle-manifest.json`. The `ncel` launcher locates it with `bundle_dir()` and
executes `bin/ncel-native` directly.
"""

from __future__ import annotations

from pathlib import Path

__version__ = "0.2.1"


def bundle_dir() -> Path:
    return Path(__file__).resolve().parent
