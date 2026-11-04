#!/usr/bin/env python3
"""Stage the native runtime bundle for packaging (wheel + npm platform package).

Source of truth: `native/ncel/artifacts/ncel-native-<ver>-linux-x86_64/`, then
`native/ncel/toolchain.lock` for every pin. If the artifact directory is missing,
the artifact tarball is extracted; if that is missing too, the native tree is built
(`scripts/provision-toolchain.sh` + `make`) — that is the only slow path.

    python3 packaging/scripts/stage_bundle.py --out packaging/python/ncel-native/ncel_native_bundle

Writes `<out>/bundle-manifest.json` with the sha256 of every bundled file and fails
loudly if a bundled Bend/HVM/shader hash disagrees with `toolchain.lock`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "native" / "ncel"
LOCK = NATIVE / "toolchain.lock"
ARTIFACTS = NATIVE / "artifacts"

PACKAGE_VERSION = "0.2.1"

BINARIES = ("ncel-native", "ncel-ast", "ncel-gl", "bend", "hvm")
SHADERS = ("draw430.glsl", "draw410.glsl")
EXTRA_FILES = ("README.md", "BUILD.md", "LICENSE-NOTES.md", "toolchain.lock")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def lock_data() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def artifact_dir(version: str) -> Path:
    name = f"ncel-native-{version}-linux-x86_64"
    stage = ARTIFACTS / name
    if (stage / "bin" / "ncel-native").is_file():
        return stage
    tarball = ARTIFACTS / f"{name}.tar.gz"
    if tarball.is_file():
        with tarfile.open(tarball, "r:gz") as tar:
            tar.extractall(ARTIFACTS)
        return stage
    print(f"staging: building the native tree (no artifact at {stage})", file=sys.stderr)
    subprocess.run(["bash", "scripts/provision-toolchain.sh"], cwd=NATIVE, check=True)
    subprocess.run(["bash", "scripts/build.sh"], cwd=NATIVE, check=True)
    subprocess.run(["bash", "scripts/package.sh"], cwd=NATIVE, check=True)
    if not (stage / "bin" / "ncel-native").is_file():
        raise SystemExit(f"error: still no artifact at {stage}")
    return stage


def clean(out: Path) -> None:
    for rel in ("bin", "share", "licenses"):
        shutil.rmtree(out / rel, ignore_errors=True)
    for name in (*EXTRA_FILES, "bundle-manifest.json"):
        (out / name).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="destination bundle directory")
    args = parser.parse_args()

    lock = lock_data()
    version = lock["product_version"]
    source = artifact_dir(version)
    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    clean(out)

    for rel in ("bin", "share/ncel", "licenses"):
        (out / rel).mkdir(parents=True, exist_ok=True)

    executables = []
    for name in BINARIES:
        src = source / "bin" / name
        if not src.is_file():
            raise SystemExit(f"error: missing {src}")
        dst = out / "bin" / name
        shutil.copy2(src, dst)
        dst.chmod(dst.stat().st_mode | 0o755)
        executables.append(str(dst.relative_to(out)))

    for name in SHADERS:
        src = source / "share" / "ncel" / name
        if not src.is_file():
            raise SystemExit(f"error: missing {src}")
        shutil.copy2(src, out / "share" / "ncel" / name)

    for name in EXTRA_FILES:
        src = source / name
        if src.is_file():
            shutil.copy2(src, out / name)

    licences = source / "licenses"
    if licences.is_dir():
        for item in licences.iterdir():
            if item.is_file():
                shutil.copy2(item, out / "licenses" / item.name)

    tools = {tool["name"]: tool for tool in lock["tools"]}

    # Pins vs. bytes: a bundle may never drift from the lock file it claims.
    checks = {
        "bin/bend": tools["bend-lang"]["binary_sha256"],
        "bin/hvm": tools["hvm"]["binary_sha256"],
        "share/ncel/draw430.glsl": tools["glsl-shaders"]["sha256"]["draw430"],
        "share/ncel/draw410.glsl": tools["glsl-shaders"]["sha256"]["draw410"],
    }
    for rel, expected in checks.items():
        actual = sha256(out / rel)
        if actual != expected:
            raise SystemExit(
                f"error: {rel} sha256 {actual} does not match toolchain.lock {expected}"
            )

    files = []
    for path in sorted(p for p in out.rglob("*") if p.is_file()):
        rel = path.relative_to(out).as_posix()
        if rel.endswith("__init__.py") or rel.startswith("__pycache__"):
            continue  # Python carrier only, not part of the native bundle
        files.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
                "executable": path.name in BINARIES,
            }
        )

    manifest = {
        "schema": "ncel-bundle-manifest/1",
        "product": "ncel-native",
        "package_version": PACKAGE_VERSION,
        "runtime_version": version,
        "spec_version": lock["spec_version"],
        "target": lock["target"],
        "min_glibc": "2.39",
        "verified_on": lock["verified_on"],
        "toolchain": {
            "moonbit": {
                "version": tools["moonbit-cli"]["version"],
                "core": tools["moonbit-core"]["version"],
                "compiled_stage": "bin/ncel-ast",
            },
            "bend": {
                "version": tools["bend-lang"]["version"],
                "sha256": tools["bend-lang"]["binary_sha256"],
            },
            "hvm": {
                "version": tools["hvm"]["version"],
                "sha256": tools["hvm"]["binary_sha256"],
            },
            "gl_runtime": {
                "version": tools["mesa-gl-runtime"]["version"],
                "system_packages": lock["system_packages"],
            },
            "glsl_shaders": tools["glsl-shaders"]["sha256"],
        },
        "total_bytes": sum(entry["bytes"] for entry in files),
        "files": files,
    }
    (out / "bundle-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    total = manifest["total_bytes"]
    print(f"staged {len(files)} files, {total} bytes ({total / 1e6:.2f} MB) -> {out}")
    print(f"       executables: {', '.join(executables)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
