"""Run the bundled native runtime (never replace it, never fall back inside it)."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from . import bundle, platform_info


def available() -> tuple[bool, str | None]:
    """True when the native runtime can actually run here."""
    plat = platform_info.platform_info()
    if not plat.supported:
        return False, " ".join(plat.reasons)
    if bundle.binary() is None:
        return (
            False,
            "the native runtime bundle (`northcel-native` package) is not installed "
            "for this platform; install it with `pip install northcel-native` on Linux "
            "x86_64.",
        )
    return True, None


def run(args: list[str], capture: bool = False) -> subprocess.CompletedProcess:
    exe = bundle.binary()
    if exe is None:  # caller checked availability first
        raise RuntimeError("native runtime bundle missing")
    env = dict(os.environ)
    # Keep the bundle's own bin/ first so `bend` resolves the pinned HVM pair even
    # when another bend/hvm exists on PATH.
    env["PATH"] = str(exe.parent) + os.pathsep + env.get("PATH", "")
    if capture:
        return subprocess.run([str(exe), *args], capture_output=True, text=True, env=env)
    return subprocess.run([str(exe), *args], env=env)


def doctor_json() -> dict | None:
    if bundle.binary() is None:
        return None
    try:
        proc = run(["doctor"], capture=True)
    except Exception:
        return None
    text = (proc.stdout or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def version_line() -> str:
    native = doctor_json()
    if not native:
        return "native runtime: absent"
    return (
        f"native runtime: {native.get('version', '?')} "
        f"(spec {native.get('spec_version', '?')})"
    )


def bundle_path() -> Path | None:
    return bundle.bundle_dir()
