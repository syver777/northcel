#!/usr/bin/env python3
"""Cross-implementation conformance runner.

    python3 tests/conformance.py [--native] [--json] [--keep DIR]

Three things are checked, and each one is only checked if it can actually be
checked on this machine:

1. **Reference probes** — the Python reference renders every case in
   `python/northcel/conformance/conformance_manifest.json` and every `(x, y)`
   probe matches its expected RGB within `tolerance_mae`.
2. **Determinism** — a film rendered frame-by-frame in forward order and in
   reverse order produces byte-identical frames.
3. **Native agreement** (`--native`, Linux x86_64 with the bundle installed) — the
   native runtime renders the same cases and agrees with the reference pixel by
   pixel within the same tolerance. The PNG *bytes* are allowed to differ (different
   encoders); the pixels are not.

Exit code 0 means every check that ran passed. A check that could not run is
reported as SKIP, never as a pass.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "python" / "northcel" / "conformance" / "conformance_manifest.json"

#: Human progress goes to stderr when --json is asked for, so stdout stays parseable.
QUIET = False


def say(message: str = "") -> None:
    print(message, file=sys.stderr if QUIET else sys.stdout, flush=True)


def _import_reference():
    pkg = ROOT / "python"
    if str(pkg) not in sys.path:
        sys.path.insert(0, str(pkg))
    from northcel.parser import parse_ncel, NorthCelSyntaxError  # noqa: PLC0415
    from northcel.validator import validate_document  # noqa: PLC0415
    from northcel.renderer import render_document_frame, render_film_frames  # noqa: PLC0415

    return {
        "parse": parse_ncel,
        "syntax_error": NorthCelSyntaxError,
        "validate": validate_document,
        "render": render_document_frame,
        "film": render_film_frames,
    }


def _load(name: str, ref) -> object:
    src = (MANIFEST.parent / name).read_text(encoding="utf-8")
    doc = ref["parse"](src)
    errors = [d for d in ref["validate"](doc) if d.level == "error"]
    if errors:
        raise SystemExit(f"{name}: reference validation failed: {[e.format() for e in errors]}")
    return doc


def _probe_deltas(image, probes) -> list[tuple[int, str]]:
    """Max per-channel delta for every probe, with a readable line for failures."""
    out = []
    for probe in probes:
        x, y = int(probe["x"]), int(probe["y"])
        want = tuple(int(c) for c in probe["rgb"])
        got = tuple(int(c) for c in image[y, x][:3])
        delta = max(abs(a - b) for a, b in zip(want, got))
        out.append((delta, f"({x},{y}) want {want} got {got} maxΔ {delta} {probe.get('note', '')}"))
    return out


def check_reference(manifest: dict, ref, results: dict) -> None:
    tolerance = float(manifest.get("tolerance_mae", 1.0))
    cases = []
    for case in manifest["cases"]:
        doc = _load(case["file"], ref)
        ok = True
        notes = []
        if "probes" in case:
            image = ref["render"](doc, frame_index=0)
            for delta, text in _probe_deltas(image, case["probes"]):
                ok = ok and delta <= tolerance
                notes.append(f"maxΔ {delta} vs tolerance {tolerance}: {text}")
        else:
            for frame, probes in case["probes_by_frame"].items():
                image = ref["render"](doc, frame_index=int(frame))
                for delta, text in _probe_deltas(image, probes):
                    ok = ok and delta <= tolerance
                    notes.append(f"frame {frame}: maxΔ {delta}: {text}")
        cases.append({"case": case["name"], "ok": ok, "notes": notes})
        say(f"  [{'PASS' if ok else 'FAIL'}] reference probes: {case['name']}")
        for note in notes if not ok else []:
            say(f"         {note}")
    results["reference_probes"] = {"ok": all(c["ok"] for c in cases), "cases": cases}


def check_determinism(manifest: dict, ref, results: dict) -> None:
    film_case = next((c for c in manifest["cases"] if "probes_by_frame" in c), None)
    if film_case is None:
        results["determinism"] = {"ok": None, "detail": "no film case in the manifest"}
        return
    doc = _load(film_case["file"], ref)
    frames = sorted(int(f) for f in film_case["probes_by_frame"])
    forward = [bytes(ref["render"](doc, frame_index=f)) for f in frames]
    reverse = {
        f: bytes(ref["render"](doc, frame_index=f)) for f in reversed(frames)
    }
    same = all(forward[i] == reverse[f] for i, f in enumerate(frames))
    say(f"  [{'PASS' if same else 'FAIL'}] determinism: {film_case['name']} frames {frames}")
    results["determinism"] = {"ok": same, "case": film_case["name"], "frames": frames}


def _native_binary() -> Path | None:
    explicit = os.environ.get("NCEL_NATIVE_BIN")
    if explicit:
        path = Path(explicit)
        return path if path.is_file() else None
    try:
        from northcel.launcher import bundle  # noqa: PLC0415
    except Exception:
        return None
    return bundle.binary()


def check_native(manifest: dict, ref, results: dict, workdir: Path) -> None:
    binary = _native_binary()
    if binary is None:
        say("  [SKIP] native agreement: no native bundle on this machine")
        results["native_agreement"] = {
            "ok": None,
            "detail": "no native bundle installed; run `northcel doctor` on Linux x86_64",
        }
        return

    import numpy as np  # noqa: PLC0415
    from PIL import Image  # noqa: PLC0415

    tolerance = float(manifest.get("tolerance_mae", 1.0))
    cases = []
    for case in manifest["cases"]:
        if case.get("reference_only"):
            # Not a pass: the native runtime does not implement this spec version.
            say(f"  [SKIP] native agreement: {case['name']} ({case.get('reference_only_reason', 'reference only')})")
            continue
        source = MANIFEST.parent / case["file"]
        frames = sorted(int(f) for f in case.get("probes_by_frame", {"0": []}))
        doc = _load(case["file"], ref)
        hashes = {}
        for frame in frames + list(reversed(frames)):
            out = workdir / f"native_{case['name']}_{frame}.png"
            proc = subprocess.run(
                [str(binary), "render", str(source), "-o", str(out), "--frame", str(frame), "--json"],
                capture_output=True, text=True,
            )
            if proc.returncode != 0 or not out.is_file():
                cases.append({"case": case["name"], "frame": frame, "ok": False, "detail": (proc.stderr or "").strip()[:200]})
                say(f"  [FAIL] native render: {case['name']} frame {frame}, exit {proc.returncode}: {(proc.stderr or '').strip()[:200]}")
                continue
            native_img = np.asarray(Image.open(out).convert("RGB"), dtype=np.int16)
            ref_img = np.asarray(ref["render"](doc, frame_index=frame), dtype=np.int16)
            mae = float(np.abs(native_img - ref_img).mean())
            same = frame not in hashes or hashes[frame] == out.read_bytes()
            hashes[frame] = out.read_bytes()
            limit = float(case.get("tolerance_mae", tolerance))
            ok = mae <= limit and same
            cases.append({"case": case["name"], "frame": frame, "ok": ok, "mae": round(mae, 6), "deterministic": same})
            say(f"  [{'PASS' if ok else 'FAIL'}] native agreement: {case['name']} frame {frame} MAE {mae:.6f}; deterministic={same}")
    results["native_agreement"] = {"ok": all(c["ok"] for c in cases), "binary": str(binary), "cases": cases}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--native", action="store_true", help="also compare against the native runtime")
    parser.add_argument("--json", action="store_true", help="print a JSON report")
    parser.add_argument("--keep", help="keep artifacts in this directory")
    args = parser.parse_args()
    global QUIET
    QUIET = args.json

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    workdir = Path(args.keep) if args.keep else Path(tempfile.mkdtemp(prefix="northcel-conformance-"))
    workdir.mkdir(parents=True, exist_ok=True)

    ref = _import_reference()
    say(f"NorthCel conformance — {len(manifest['cases'])} case(s), spec {manifest['spec_version']}")
    results: dict = {"spec_version": manifest["spec_version"], "workdir": str(workdir)}
    check_reference(manifest, ref, results)
    check_determinism(manifest, ref, results)
    if args.native:
        check_native(manifest, ref, results, workdir)

    checked = [v for k, v in results.items() if isinstance(v, dict) and v.get("ok") is not None]
    failed = [k for k, v in results.items() if isinstance(v, dict) and v.get("ok") is False]
    results["ok"] = not failed
    results["failed"] = failed

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        say(f"checked {len(checked)} group(s); failed: {', '.join(failed) if failed else 'none'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
