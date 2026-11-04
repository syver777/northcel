"""`ncel verify` — prove the installed runtime really renders, from bundled fixtures.

Four checks with the bundled native runtime (never the Python fallback):

1. starter scene renders to a PNG of the expected size;
2. the shower ``f0001`` frame matches the pinned native/conformance hash;
3. a 6-frame film renders every frame;
4. determinism: both renders repeated produce identical bytes.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

from . import EXIT_NO_NATIVE, native, paths
from .doctor import pins


def _fixture(name: str) -> Path:
    """A bundled reference example, also used as the verify fixture."""
    return paths.example(name)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def _run_json(args: list[str]) -> tuple[int, dict | None, str]:
    proc = native.run(args, capture=True)
    text = (proc.stdout or "").strip()
    doc = None
    if text:
        for line in reversed(text.splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    doc = json.loads(line)
                except json.JSONDecodeError:
                    doc = None
                break
    return proc.returncode, doc, (proc.stderr or "").strip()


def run_checks(keep: Path | None = None) -> dict:
    pin = pins()
    oracle = (pin.get("oracle") or {}).get("shower_f0001", {})
    workdir = Path(tempfile.mkdtemp(prefix="ncel-verify-")) if keep is None else keep
    workdir.mkdir(parents=True, exist_ok=True)

    checks: list[dict] = []

    def add(name: str, ok: bool, detail: str, **extra) -> None:
        entry = {"name": name, "ok": bool(ok), "detail": detail}
        entry.update(extra)
        checks.append(entry)

    # 1 — starter scene
    starter = _fixture("starter.ncel")
    out1 = workdir / "starter.png"
    code, receipt, err = _run_json(
        ["render", str(starter), "-o", str(out1), "--frame", "0", "--json"]
    )
    size = (receipt or {}).get("size") or {}
    add(
        "starter-render",
        code == 0 and out1.is_file() and size.get("width") == 320,
        f"exit {code}, {size.get('width')}x{size.get('height')}, {out1.stat().st_size if out1.is_file() else 0} bytes"
        + (f"; stderr: {err}" if code else ""),
        sha256=_sha256(out1) if out1.is_file() else None,
    )

    # 2 — shower f0001 against the pinned oracle hash
    shower = _fixture("shower_f0001.ncel")
    out2 = workdir / "shower_f0001.png"
    code, receipt, err = _run_json(
        ["render", str(shower), "-o", str(out2), "--frame", "0", "--json"]
    )
    got = _sha256(out2) if out2.is_file() else None
    expected = oracle.get("sha256")
    add(
        "shower-f0001-conformance",
        code == 0 and bool(expected) and got == expected,
        f"exit {code}, sha256 {got} vs pinned {expected}"
        + ("" if got == expected else " — a mismatch means the GL driver produced different pixels")
        + (f"; stderr: {err}" if code else ""),
        sha256=got,
        expected=expected,
    )

    # 3 — 6-frame film
    film = _fixture("lantern_film.ncel")
    outdir = workdir / "film"
    code, receipt, err = _run_json(
        ["film", str(film), "-o", str(outdir), "--frames", "0..5", "--json"]
    )
    frames = sorted(outdir.glob("f*.png")) if outdir.is_dir() else []
    add(
        "family-film-6-frames",
        code == 0 and len(frames) == 6,
        f"exit {code}, {len(frames)} frame(s): {', '.join(f.name for f in frames)}"
        + (f"; stderr: {err}" if code else ""),
        hashes={f.name: _sha256(f) for f in frames},
    )

    # 4 — determinism
    repeat2 = workdir / "shower_f0001_repeat.png"
    repeat_dir = workdir / "film_repeat"
    code_a, _, _ = _run_json(
        ["render", str(shower), "-o", str(repeat2), "--frame", "0", "--json"]
    )
    same_still = repeat2.is_file() and got is not None and _sha256(repeat2) == got
    code_b, _, _ = _run_json(
        ["film", str(film), "-o", str(repeat_dir), "--frames", "0..5", "--json"]
    )
    repeat_frames = sorted(repeat_dir.glob("f*.png")) if repeat_dir.is_dir() else []
    same_film = len(repeat_frames) == len(frames) and all(
        _sha256(a) == _sha256(b) for a, b in zip(frames, repeat_frames)
    )
    add(
        "determinism",
        code_a == 0 and code_b == 0 and same_still and same_film,
        f"still identical: {same_still}; 6-frame film identical: {same_film}",
    )

    # 5 — frame uniqueness (a film that renders 6 copies of frame 0 is not a film)
    unique = len({_sha256(f) for f in frames})
    add(
        "film-frames-differ",
        len(frames) == 6 and unique == 6,
        f"{unique}/6 distinct frame hashes",
    )

    return {
        "ok": all(c["ok"] for c in checks),
        "runtime": "native",
        "fixtures": str(_fixture("")),
        "workdir": str(workdir),
        "checks": checks,
    }


def cmd_verify(as_json: bool, keep: str | None) -> int:
    usable, reason = native.available()
    if not usable:
        print(f"northcel: cannot verify the native runtime here — {reason}", file=sys.stderr)
        print(
            "northcel: this release only ships and verifies Linux x86_64; install "
            "`northcel-native` on a supported platform (northcel doctor shows the "
            "details).",
            file=sys.stderr,
        )
        return EXIT_NO_NATIVE

    result = run_checks(Path(keep) if keep else None)
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print("northcel verify — native runtime self-test")
        for check in result["checks"]:
            mark = "PASS" if check["ok"] else "FAIL"
            print(f"  [{mark}] {check['name']}: {check['detail']}")
        print(f"  artifacts: {result['workdir']}")
        print("result: " + ("all checks passed" if result["ok"] else "FAILED"))
    return 0 if result["ok"] else 1
