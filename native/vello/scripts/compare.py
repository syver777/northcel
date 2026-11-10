#!/usr/bin/env python3
"""Pixel comparison for the Phase 4 Vello prototype.

Usage:
    python3 native/vello/scripts/compare.py \
        --vello native/vello/out/vello_1080_f0000.png \
        --reference native/vello/out/reference_1080_f0000.png \
        [--heatmap native/vello/out/diff_1080.png] [--json-out native/vello/out/compare.json]

Reports full-frame RGB MAE, maximum channel delta, differing-pixel counts and
the same numbers restricted to flat reference interior (3x3 uniform neighbourhood),
which separates colour correctness from anti-aliasing differences at edges.
"""
from __future__ import annotations

import argparse
import json
import time

import numpy as np
from PIL import Image


def load_rgb(path: str) -> np.ndarray:
    return np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)


def uniform_mask(reference: np.ndarray, radius: int = 1) -> np.ndarray:
    """True where every pixel in a (2r+1)^2 window has the same RGB as the centre."""
    h, w, _ = reference.shape
    mask = np.ones((h, w), dtype=bool)
    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            if dx == 0 and dy == 0:
                continue
            y0, y1 = max(0, -dy), min(h, h - dy)
            x0, x1 = max(0, -dx), min(w, w - dx)
            dst = (slice(y0, y1), slice(x0, x1))
            src = (slice(y0 + dy, y1 + dy), slice(x0 + dx, x1 + dx))
            equal = np.all(reference[dst] == reference[src], axis=2)
            mask[dst] &= equal
    # Pixels whose window would fall outside the image cannot be certified.
    if radius:
        mask[:radius, :] = False
        mask[-radius:, :] = False
        mask[:, :radius] = False
        mask[:, -radius:] = False
    return mask


def stats(diff: np.ndarray, mask: np.ndarray | None = None) -> dict:
    if mask is not None:
        d = diff[mask]
    else:
        d = diff.reshape(-1, 3)
    if d.size == 0:
        return {
            "pixels": 0,
            "mae": 0.0,
            "max_channel_delta": 0,
            "mean_max_channel_delta": 0.0,
        }
    return {
        "pixels": int(d.shape[0]),
        "mae": float(np.abs(d).mean()),
        "max_channel_delta": int(np.abs(d).max()),
        "mean_max_channel_delta": float(np.abs(d).max(axis=1).mean()),
    }


def compare_images(vello_path: str, reference_path: str, heatmap: str | None = None) -> dict:
    t0 = time.perf_counter()
    vello = load_rgb(vello_path)
    reference = load_rgb(reference_path)
    if vello.shape != reference.shape:
        raise ValueError(f"size mismatch: vello {vello.shape} vs reference {reference.shape}")

    diff = vello - reference
    absdiff = np.abs(diff)
    max_delta = absdiff.max(axis=2)
    full = stats(diff)
    flat = stats(diff, uniform_mask(reference, radius=1))

    total = reference.shape[0] * reference.shape[1]
    nonzero = int((max_delta > 0).sum())
    buckets = {
        "0": int((max_delta == 0).sum()),
        "1": int((max_delta == 1).sum()),
        "2-4": int(((max_delta >= 2) & (max_delta <= 4)).sum()),
        "5-16": int(((max_delta >= 5) & (max_delta <= 16)).sum()),
        "17-64": int(((max_delta >= 17) & (max_delta <= 64)).sum()),
        "65-128": int(((max_delta >= 65) & (max_delta <= 128)).sum()),
        "129-255": int((max_delta >= 129).sum()),
    }
    mse = float((diff.astype(np.float64) ** 2).mean())
    psnr = float("inf") if mse == 0.0 else float(10.0 * np.log10((255.0**2) / mse))

    report = {
        "vello": vello_path,
        "reference": reference_path,
        "width": int(reference.shape[1]),
        "height": int(reference.shape[0]),
        "pixels": total,
        "full_frame": full,
        "flat_interior_3x3": flat,
        "differing_pixels_any_channel": nonzero,
        "differing_pixels_pct": 100.0 * nonzero / total,
        "exact_pixels": buckets["0"],
        "exact_pixels_pct": 100.0 * buckets["0"] / total,
        "max_channel_histogram": buckets,
        "psnr_db": psnr,
        "compare_wall_ms": 0.0,
    }

    if heatmap:
        gain = 16
        heat = np.clip(max_delta.astype(np.float64) * gain, 0, 255).astype(np.uint8)
        Image.fromarray(heat).save(heatmap)
        report["heatmap"] = heatmap

    report["compare_wall_ms"] = (time.perf_counter() - t0) * 1000.0
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vello", required=True)
    ap.add_argument("--reference", required=True)
    ap.add_argument("--heatmap", default=None)
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()
    report = compare_images(args.vello, args.reference, args.heatmap)
    text = json.dumps(report, indent=2)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
