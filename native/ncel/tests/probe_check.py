#!/usr/bin/env python3
"""Conformance probe checker for the NorthCel native runtime.

Renders are compared with the normative probe colours in the conformance
manifest, using the manifest's tolerance (default MAE 1.0).
"""
import json
import sys

import numpy as np
from PIL import Image


def check(manifest_path, render_dir):
    man = json.load(open(manifest_path))
    tol = float(man.get("tolerance_mae", 1.0))
    failures = []
    for case in man["cases"]:
        name = case["name"]
        if "probes" in case:
            groups = {0: case["probes"]}
        else:
            groups = {int(k): v for k, v in case["probes_by_frame"].items()}
        for frame, probes in groups.items():
            png = f"{render_dir}/{name}_f{frame:04d}.png"
            img = np.asarray(Image.open(png).convert("RGB")).astype(int)
            for p in probes:
                x, y = int(p["x"]), int(p["y"])
                want = np.asarray(p["rgb"], dtype=int)
                got = img[y, x]
                diff = float(np.abs(got - want).mean())
                if diff > tol:
                    failures.append(
                        f"{name} frame {frame} ({x},{y}): got {got.tolist()} want {want.tolist()} MAE {diff}"
                    )
                else:
                    print(f"ok {name} f{frame} ({x},{y}) = {got.tolist()}")
    if failures:
        for f in failures:
            print("FAIL", f)
        return 1
    total = 0
    for case in man["cases"]:
        if "probes" in case:
            total += len(case["probes"])
        else:
            total += sum(len(v) for v in case["probes_by_frame"].values())
    print(f"conformance probes: {total} ok")
    return 0


if __name__ == "__main__":
    sys.exit(check(sys.argv[1], sys.argv[2]))
