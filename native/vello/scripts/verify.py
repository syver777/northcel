#!/usr/bin/env python3
"""Regenerate Linux evidence; never reuses the copied Mac output files.

Run from native/vello after cargo build --release --locked:
    python3 scripts/verify.py --out out/linux
Requires numpy/Pillow and a wgpu compute-capable adapter (including lavapipe).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import statistics
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import PIL
from PIL import Image

from compare import compare_images
from make_fixture import FIX, REPO, build_scene, parse_ncel, to_json
from northcel.renderer import render_document_frame

ROOT = Path(__file__).resolve().parents[1]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n")


def image_hashes(path: Path) -> dict:
    with Image.open(path) as image:
        rgba = image.convert("RGBA").tobytes()
    return {"png_sha256": sha(path.read_bytes()), "rgba_sha256": sha(rgba)}


def reference(source: str, output: Path) -> tuple[dict, np.ndarray]:
    t = time.perf_counter()
    doc = parse_ncel(source)
    parse_ms = (time.perf_counter() - t) * 1000
    times, arrays = [], []
    for _ in range(2):
        t = time.perf_counter()
        arrays.append(render_document_frame(doc, 0))
        times.append((time.perf_counter() - t) * 1000)
    t = time.perf_counter()
    Image.fromarray(arrays[0]).save(output)
    png_ms = (time.perf_counter() - t) * 1000
    return {
        "parse_ms": parse_ms,
        "render_ms": times,
        "png_ms": png_ms,
        "raw_rgb_identical": bool(np.array_equal(*arrays)),
        "raw_rgb_sha256": [sha(a.tobytes()) for a in arrays],
        **image_hashes(output),
    }, arrays[0]


def run_vello(binary: Path, fixture: Path, output: Path, repeat: int, cpu: bool) -> dict:
    command = [str(binary), "--fixture", str(fixture), "--out", str(output),
               "--repeat", str(repeat), "--no-pass-files", "--json"]
    if cpu:
        command.append("--cpu")
    t = time.perf_counter()
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=True)
    wall_ms = (time.perf_counter() - t) * 1000
    receipt = json.loads(result.stdout)
    receipt["command"] = shlex.join(command)
    receipt["process_wall_ms"] = wall_ms
    receipt["stderr"] = result.stderr
    receipt.update(image_hashes(output))
    completed = receipt["timing_ms"]["render_including_readback_passes"]
    receipt["completed_render_readback_ms_median_excluding_first"] = statistics.median(completed[1:])
    write_json(output.with_suffix(".json"), receipt)
    print(f"{output.stem}: completed render+readback median {receipt['completed_render_readback_ms_median_excluding_first']:.6f} ms; "
          f"in-process identical: {receipt['deterministic_in_process']}", flush=True)
    return receipt


def cross_process(a: Path, b: Path) -> dict:
    with Image.open(a) as im:
        first = np.array(im.convert("RGBA"), dtype=np.int16)
    with Image.open(b) as im:
        second = np.array(im.convert("RGBA"), dtype=np.int16)
    delta = np.abs(first - second)
    return {
        "differing_rgba_bytes": int(np.count_nonzero(delta)),
        "differing_pixels": int(np.any(delta != 0, axis=2).sum()),
        "max_channel_delta": int(delta.max()),
        "png_bytes_identical": a.read_bytes() == b.read_bytes(),
        "raw_rgba_identical": bool(np.array_equal(first, second)),
        "hashes": [image_hashes(a), image_hashes(b)],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("out/linux"))
    ap.add_argument("--binary", type=Path, default=Path("target/release/ncel-vello"))
    args = ap.parse_args()
    os.chdir(ROOT)
    output = args.out
    output.mkdir(parents=True, exist_ok=True)
    binary = args.binary.resolve()
    evidence = {
        "status": "fixture-based prototype, not NCIR or CLI integration",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "python": sys.version,
        "numpy": np.__version__,
        "pillow": PIL.__version__,
        "environment": {k: os.environ.get(k) for k in (
            "VK_ICD_FILENAMES", "VK_DRIVER_FILES", "LD_LIBRARY_PATH", "WGPU_BACKEND", "XDG_RUNTIME_DIR")},
        "binary_sha256": sha(binary.read_bytes()),
        "source_sha256": {},
        "reference_source_sha256": {},
        "preview_fixture_gate": {"rgb_mae_lte": 0.25, "max_channel_delta_lte": 32,
                                 "pixels_delta_gt_16_pct_lte": 0.1},
        "cases": {},
    }
    files = [ROOT / "Cargo.toml", ROOT / "Cargo.lock", *sorted((ROOT / "src").glob("*.rs")),
             *sorted((ROOT / "scripts").glob("*.py")), *sorted(FIX.glob("*"))]
    for path in files:
        evidence["source_sha256"][str(path.relative_to(ROOT))] = sha(path.read_bytes())
    for path in sorted((REPO / "python/northcel").glob("*.py")):
        evidence["reference_source_sha256"][str(path.relative_to(REPO))] = sha(path.read_bytes())

    all_passed = True
    for stem, grain in (("skyline_1080", 0.008), ("skyline_1080_flat", 0)):
        source_path = FIX / f"{stem}.ncel"
        fixture_path = FIX / f"{stem}.paintlist.json"
        source = source_path.read_text()
        assert source == build_scene(grain), f"source does not reproduce: {source_path}"
        assert json.loads(fixture_path.read_text()) == to_json(parse_ncel(source), 0, source_path.name)
        ref_path = output / f"reference_{stem}.png"
        ref_receipt, _ = reference(source, ref_path)
        write_json(output / f"reference_{stem}.json", ref_receipt)
        for cpu in ([False, True] if grain == 0 else [False]):
            name = stem + ("_cpu" if cpu else "")
            first = output / f"vello_{name}.png"
            second = output / f"vello_{name}_process_b.png"
            runs = [run_vello(binary, fixture_path, first, 8, cpu),
                    run_vello(binary, fixture_path, second, 2, cpu)]
            cross = cross_process(first, second)
            comparison = compare_images(str(first), str(ref_path), str(output / f"diff_{name}.png"))
            write_json(output / f"compare_{name}.json", comparison)
            hist = comparison["max_channel_histogram"]
            gt16_pct = 100 * sum(hist[k] for k in ("17-64", "65-128", "129-255")) / comparison["pixels"]
            gate = (comparison["full_frame"]["mae"] <= 0.25
                    and comparison["full_frame"]["max_channel_delta"] <= 32 and gt16_pct <= 0.1)
            all_passed &= gate and ref_receipt["raw_rgb_identical"]
            evidence["cases"][name] = {
                "fixture_reproduced_from_source": True,
                "reference": ref_receipt,
                "runs": runs,
                "cross_process_determinism": cross,
                "comparison": comparison,
                "pixels_delta_gt_16_pct": gt16_pct,
                "preview_fixture_gate_passed": gate,
            }
            print(f"{name}: MAE {comparison['full_frame']['mae']}, "
                  f"max {comparison['full_frame']['max_channel_delta']}, "
                  f"different pixels {comparison['differing_pixels_any_channel']}; "
                  f"cross-process identical: {cross['raw_rgba_identical']}", flush=True)

    # Integer-aligned geometry isolates group compositing and even-odd clipping
    # from analytic-AA edge differences. The second group paint must stay inside
    # the same offscreen layer; the clip hole deliberately has the SAME winding.
    # Use the existing q25 encoder rather than depending on hand-written payloads.
    from make_fixture import payload, rect
    semantic_source = ('northcel "0.5.0-draft"\n'
        'scene Semantics(width: 32, height: 32, fps: 1, precision: 0.25px, seed: 1) {\n'
        ' paper { color: #FFFFFF, antialias_grid: 4, grain: 0 }\n'
        ' group overlap(opacity: 0.5) {\n'
        f'  layer red(color: #FF0000) {{ "{payload(rect(2, 2, 14, 14))}" }}\n'
        f'  layer blue(color: #0000FF) {{ "{payload(rect(8, 2, 20, 14))}" }}\n'
        ' }\n'
        f' layer mask(color: #000000, opacity: 0) {{ "{payload(rect(2, 18, 20, 30), rect(6, 22, 12, 26))}" }}\n'
        ' group clipped(clip: mask) {\n'
        f'  layer green(color: #00FF00) {{ "{payload(rect(0, 16, 24, 32))}" }}\n'
        ' }\n}\n')
    semantic_fixture = output / "semantics.paintlist.json"
    write_json(semantic_fixture, to_json(parse_ncel(semantic_source), 0, "semantics.ncel"))
    (output / "semantics.ncel").write_text(semantic_source)
    ref_receipt, ref = reference(semantic_source, output / "reference_semantics.png")
    run = run_vello(binary, semantic_fixture, output / "vello_semantics.png", 2, False)
    with Image.open(output / "vello_semantics.png") as image:
        actual = np.array(image.convert("RGB"), dtype=np.int16)
    delta = np.abs(actual - ref.astype(np.int16))
    semantic_passed = int(delta.max()) <= 1
    evidence["semantic_regression"] = {
        "max_channel_delta": int(delta.max()), "differing_bytes": int(np.count_nonzero(delta)),
        "reference": ref_receipt, "run": run, "passed_with_delta_lte_1": semantic_passed,
        "overlap_rgb": actual[8, 10].tolist(), "clip_hole_rgb": actual[24, 8].tolist(),
        "clipped_fill_rgb": actual[20, 4].tolist(),
    }
    all_passed &= semantic_passed
    evidence["all_preview_and_semantic_gates_passed"] = bool(all_passed)
    write_json(output / "verification.json", evidence)
    print(f"verification written to {output / 'verification.json'}; gates passed: {all_passed}")
    # Exact determinism is measured, not made a prerequisite for the preview tier.
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
