"""The labelled, non-native path: the Python reference implementation.

This module is used ONLY when the native stages cannot run on this platform
(macOS, Windows, non-x86_64 Linux, no EGL, or an explicit `--no-native`). Every
entry point prints one clear line to stderr and marks its receipt with
``"renderer": "python-reference"``. Nothing here is called "native".
"""

from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

NOTICE = (
    "northcel: native runtime unavailable — {reason}\n"
    "northcel: using the non-native Python reference renderer (northcel {version}). "
    "Results are the reference implementation, not the MoonBit+Bend+GLSL runtime."
)


def _northcel_version() -> str:
    from ..config import PACKAGE_VERSION

    return PACKAGE_VERSION


def notify(reason: str | None) -> None:
    print(
        NOTICE.format(reason=(reason or "not available").rstrip("."), version=_northcel_version()),
        file=sys.stderr,
        flush=True,
    )


def require() -> bool:
    try:
        from .. import cli  # noqa: F401
    except Exception:
        print(
            "northcel: the Python reference renderer is not importable from this "
            "installation. Reinstall with `pip install northcel`.",
            file=sys.stderr,
        )
        return False
    return True


def delegate(argv: list[str]) -> int:
    """Run a northcel CLI command verbatim (check/info/fmt/guide)."""
    if not require():
        return 1
    from ..cli import main as northcel_main

    return int(northcel_main(argv))


def _load(path: Path):
    from ..cli import _load_and_validate

    return _load_and_validate(path)


def render(file: str, out: str | None, frame: int, seed: int | None, as_json: bool) -> int:
    from ..renderer import NorthCelEvaluationError, render_document_frame
    from ..cli import evaluation_error

    path = Path(file)
    _, doc, diags = _load(path)
    if doc is None:
        for err in diags:
            print(f"{path}:{err}", file=sys.stderr)
        return 1
    errors = [d for d in diags if d.level == "error"]
    if errors:
        for err in errors:
            print(f"{path}:{err.format()}", file=sys.stderr)
        return 1

    import numpy as np
    from PIL import Image

    started = time.monotonic()
    try:
        rgb = render_document_frame(doc, frame_index=frame, seed_override=seed)
    except NorthCelEvaluationError as exc:
        return evaluation_error(path, exc, as_json)
    out_path = Path(out) if out else path.with_suffix(".png")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(np.asarray(rgb), mode="RGB").save(out_path)
    elapsed = time.monotonic() - started

    if as_json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "renderer": "python-reference",
                    "language": "NorthCel",
                    "northcel_version": _northcel_version(),
                    "spec_version": doc.spec_version,
                    "input": str(path),
                    "output": str(out_path),
                    "frame": {"index": frame, "count": 1},
                    "size": {"width": int(rgb.shape[1]), "height": int(rgb.shape[0])},
                    "seconds": round(elapsed, 4),
                    "native": False,
                },
                indent=2,
            )
        )
    else:
        print(
            f"Rendered {out_path} ({rgb.shape[1]}x{rgb.shape[0]}, frame {frame}) "
            f"in {elapsed:.3f}s [python-reference]"
        )
    return 0


def film(
    file: str,
    out_dir: str,
    frames: str | None,
    mp4: str | None,
    as_json: bool,
) -> int:
    from ..renderer import NorthCelEvaluationError, render_film_frames
    from ..cli import evaluation_error

    path = Path(file)
    _, doc, diags = _load(path)
    if doc is None:
        for err in diags:
            print(f"{path}:{err}", file=sys.stderr)
        return 1
    errors = [d for d in diags if d.level == "error"]
    if errors:
        for err in errors:
            print(f"{path}:{err.format()}", file=sys.stderr)
        return 1

    indices: list[int] | None = None
    if frames:
        if ".." in frames:
            lo, hi = frames.split("..", 1)
            indices = list(range(int(lo), int(hi) + 1))
        else:
            indices = [int(x) for x in frames.split(",") if x.strip()]

    started = time.monotonic()
    try:
        result = render_film_frames(
            doc, out_dir=out_dir, frame_indices=indices, mp4_path=mp4
        )
    except NorthCelEvaluationError as exc:
        return evaluation_error(path, exc, as_json)
    result["seconds"] = round(time.monotonic() - started, 4)
    if as_json:
        result.update({"renderer": "python-reference", "native": False})
        print(json.dumps(result, indent=2))
    else:
        count = result.get("frames_rendered") or len(
            result.get("frame_paths") or result.get("frames") or result.get("outputs") or []
        )
        print(f"Rendered {count} frame(s) into {out_dir} [python-reference]")
    return 0


def fmt_requires_reference() -> int:
    print(
        "northcel: `fmt` is provided by the Python reference implementation that "
        "ships in this same package — run `python -m northcel fmt FILE`.",
        file=sys.stderr,
    )
    return 1


def ffmpeg_present() -> bool:
    return shutil.which("ffmpeg") is not None
