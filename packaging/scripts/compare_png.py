#!/usr/bin/env python3
"""Compare two PNGs frame-for-frame (grey MAE, differing pixels, max channel delta).

Used by the packaging verification to compare an installed render against the
saved Python-reference oracle. Numbers are whole-frame; nothing is cropped,
registered or tuned.

    python3 packaging/scripts/compare_png.py ORACLE.png CANDIDATE.png [--json]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("oracle", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    import numpy as np
    from PIL import Image

    a = np.asarray(Image.open(args.oracle).convert("RGB"), dtype=np.float64)
    b = np.asarray(Image.open(args.candidate).convert("RGB"), dtype=np.float64)
    if a.shape != b.shape:
        raise SystemExit(f"error: shape mismatch {a.shape} vs {b.shape}")

    delta = np.abs(a - b)
    gray_a = a.mean(axis=2)
    gray_b = b.mean(axis=2)
    result = {
        "oracle": str(args.oracle),
        "candidate": str(args.candidate),
        "size": [int(a.shape[1]), int(a.shape[0])],
        "oracle_sha256": sha256(args.oracle),
        "candidate_sha256": sha256(args.candidate),
        "gray_mae": float(np.abs(gray_a - gray_b).mean()),
        "rgb_mae": float(delta.mean()),
        "max_abs": int(delta.max()),
        "diff_pixels": int((delta.max(axis=2) > 0).sum()),
        "total_pixels": int(a.shape[0] * a.shape[1]),
        "bytes_identical": sha256(args.oracle) == sha256(args.candidate),
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            f"{args.candidate} vs {args.oracle}: {result['size'][0]}x{result['size'][1]} "
            f"gray MAE {result['gray_mae']:.6g}, max channel delta {result['max_abs']}, "
            f"differing pixels {result['diff_pixels']}/{result['total_pixels']}, "
            f"bytes identical: {result['bytes_identical']}"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
