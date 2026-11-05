#!/usr/bin/env python3
"""Generate `python/northcel/data/pins.json` from `native/toolchain.lock`.

One source of truth: the native tree's lock file. Run by `build_python.sh` before
building the wheels, and checked in so a source checkout needs no build.

    python3 packaging/scripts/gen_pins.py

The shower `f0001` oracle hash is not in toolchain.lock (it is a render result).
It is pinned here because it is the value the native phase proved identical to the
Python reference (MAE 0.0, 0 differing pixels) and `northcel verify` re-checks it on
every install.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / "native" / "toolchain.lock"
OUT = ROOT / "python" / "northcel" / "data" / "pins.json"

SHOWER_ORACLE = {
    "sha256": "be0eb036775458d009a2568f5407c973777fe85caa1dac5244f03bb56582d718",
    "width": 1024,
    "height": 1024,
    "source": "python/northcel/examples/shower_f0001.ncel",
    "note": (
        "native render == Python reference render (MAE 0.0, 0 differing pixels)"
    ),
}


def main() -> int:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    tools = {tool["name"]: tool for tool in lock["tools"]}

    moon = tools["moonbit-cli"]
    core = tools["moonbit-core"]
    pins = {
        "schema": "northcel-pins/1",
        "generated_from": "native/toolchain.lock",
        "northcel_version": lock.get("package_version", lock["product_version"]),
        "native_runtime_version": lock["product_version"],
        "spec_version": lock["spec_version"],
        "target": lock["target"],
        "moonbit": {
            "version": moon["version"],
            "archive_url": moon["source"],
            "archive_sha256": moon["archive_sha256"],
            "archive_bytes": moon["archive_bytes"],
            "core_url": core["source"],
            "core_sha256": core["archive_sha256"],
            "core_bytes": core["archive_bytes"],
        },
        "bend": {
            "version": tools["bend-lang"]["version"],
            "sha256": tools["bend-lang"]["binary_sha256"],
            "bytes": tools["bend-lang"]["binary_bytes"],
            "binary": "vendor/linux-x86_64/bin/bend",
        },
        "hvm": {
            "version": tools["hvm"]["version"],
            "sha256": tools["hvm"]["binary_sha256"],
            "bytes": tools["hvm"]["binary_bytes"],
            "binary": "vendor/linux-x86_64/bin/hvm",
        },
        "shaders": {
            "draw430": tools["glsl-shaders"]["sha256"]["draw430"],
            "draw410": tools["glsl-shaders"]["sha256"]["draw410"],
        },
        "gl_runtime": {
            "version": tools["mesa-gl-runtime"]["version"],
            "system_packages": lock["system_packages"],
        },
        "oracle": {"shower_f0001": SHOWER_ORACLE},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(pins, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
