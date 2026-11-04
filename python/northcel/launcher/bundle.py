"""Locate and verify the bundled native runtime (`northcel-native` wheel)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def bundle_dir() -> Path | None:
    """Directory of the installed native bundle, or None when it is not installed."""
    module = None
    for name in ("northcel_native_bundle", "ncel_native_bundle"):
        # `ncel_native_bundle` is the 0.2.1 predecessor's module name; still honoured
        # so an environment that upgraded the launcher keeps its installed bundle.
        try:
            module = __import__(name, fromlist=["__file__"])  # noqa: PLC0415
            break
        except Exception:
            continue
    if module is None:
        return None
    path = Path(module.__file__).resolve().parent
    return path if (path / "bundle-manifest.json").is_file() else path


def manifest_path() -> Path | None:
    root = bundle_dir()
    if not root:
        return None
    manifest = root / "bundle-manifest.json"
    return manifest if manifest.is_file() else None


def load_manifest() -> dict | None:
    path = manifest_path()
    if not path:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def binary() -> Path | None:
    root = bundle_dir()
    if not root:
        return None
    exe = root / "bin" / "ncel-native"
    return exe if exe.is_file() else None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksums(manifest: dict | None = None) -> dict:
    """Hash every file named in the bundle manifest.

    Returns {"checked": n, "failed": [{"path", "expected", "actual"}], "missing": [...]}.
    """
    root = bundle_dir()
    manifest = manifest if manifest is not None else load_manifest()
    if not root or not manifest:
        return {"checked": 0, "failed": [], "missing": [], "available": False}

    checked = 0
    failed: list[dict] = []
    missing: list[str] = []
    for entry in manifest.get("files", []):
        rel = entry.get("path", "")
        target = root / rel
        if not target.is_file():
            missing.append(rel)
            continue
        actual = sha256_file(target)
        checked += 1
        if actual != entry.get("sha256"):
            failed.append(
                {"path": rel, "expected": entry.get("sha256"), "actual": actual}
            )
    return {
        "checked": checked,
        "failed": failed,
        "missing": missing,
        "available": True,
    }
