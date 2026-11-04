"""Pinned-toolchain provisioning (explicit, sha256-verified, user space only).

A *runtime* needs no downloads: the MoonBit-compiled stage, Bend and HVM2 all ship
inside the `ncel-native` bundle. This module exists for the other case — rebuilding
the native tree from source — and for reporting exactly what is installed.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path

from . import bundle


def home() -> Path:
    base = os.environ.get("NCEL_HOME")
    if base:
        return Path(base).expanduser()
    xdg = os.environ.get("XDG_DATA_HOME")
    root = Path(xdg).expanduser() if xdg else Path.home() / ".local" / "share"
    return root / "ncel"


def toolchain_dir() -> Path:
    return home() / "toolchain"


def moonbit_compiler() -> Path | None:
    for cand in (toolchain_dir() / "moon" / "bin" / "moon", home() / "moon" / "bin" / "moon"):
        if cand.is_file() and os.access(cand, os.X_OK):
            return cand
    return None


def _moonbit_info() -> dict:
    path = Path(__file__).with_name("data") / "pins.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("moonbit", {})
    except Exception:
        return {}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _download(url: str, dest: Path, sha256: str, dry_run: bool) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and _sha256(dest) == sha256:
        print(f"  cached  {dest.name}")
        return
    print(f"  fetch   {url}")
    if dry_run:
        return
    tmp = dest.with_suffix(dest.suffix + ".part")
    # curl gives resumable downloads; urllib is the fallback.
    if shutil.which("curl"):
        subprocess.run(
            ["curl", "-fL", "--retry", "3", "-C", "-", "-o", str(tmp), url], check=True
        )
    else:
        with urllib.request.urlopen(url, timeout=120) as response, tmp.open("wb") as handle:
            shutil.copyfileobj(response, handle)
    actual = _sha256(tmp)
    if actual != sha256:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"sha256 mismatch for {url}: {actual} != {sha256}")
    tmp.replace(dest)
    print(f"  verify  {dest.name} sha256 ok")


def status() -> dict:
    info = _moonbit_info()
    compiler = moonbit_compiler()
    manifest = bundle.load_manifest() or {}
    return {
        "home": str(home()),
        "toolchain_dir": str(toolchain_dir()),
        "moonbit": {
            "pinned_version": info.get("version"),
            "compiler": str(compiler) if compiler else None,
            "compiler_installed": compiler is not None,
            "core_present": (toolchain_dir() / "moon" / "lib" / "core").is_dir(),
        },
        "bend": manifest.get("toolchain", {}).get("bend"),
        "hvm": manifest.get("toolchain", {}).get("hvm"),
        "note": (
            "the runtime needs no download: the MoonBit-compiled stage, Bend and HVM2 "
            "are bundled in ncel-native. This directory is only used to rebuild from source."
        ),
    }


def install_moonbit(dry_run: bool = False) -> int:
    info = _moonbit_info()
    url = info.get("archive_url")
    sha = info.get("archive_sha256")
    core_url = info.get("core_url")
    core_sha = info.get("core_sha256")
    if not (url and sha and core_url and core_sha):
        print("ncel: pins.json is missing the MoonBit toolchain pins", file=sys.stderr)
        return 1

    target = toolchain_dir() / "moon"
    downloads = toolchain_dir() / "downloads"
    print(f"ncel toolchain: MoonBit {info.get('version')} -> {target}")
    if dry_run:
        print("  (dry run: nothing will be downloaded or written)")

    if not (target / "bin" / "moon").is_file() or not dry_run:
        archive = downloads / "moonbit-linux-x86_64.tar.gz"
        _download(url, archive, sha, dry_run)
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)
            with tarfile.open(archive, "r:gz") as tar:
                tar.extractall(target)
            for exe in (target / "bin").glob("*"):
                exe.chmod(exe.stat().st_mode | 0o111)
        core_archive = downloads / "core-latest.tar.gz"
        _download(core_url, core_archive, core_sha, dry_run)
        if not dry_run:
            (target / "lib").mkdir(parents=True, exist_ok=True)
            with tarfile.open(core_archive, "r:gz") as tar:
                tar.extractall(target / "lib")
            env = dict(os.environ, MOON_HOME=str(target))
            bundle_core = target / "lib" / "core"
            if bundle_core.is_dir():
                subprocess.run(
                    [str(target / "bin" / "moon"), "bundle", "--warn-list", "-a", "--all"],
                    cwd=bundle_core,
                    env=env,
                    check=False,
                )

    # Bend/HVM2 source-build copies come from the same pinned bundle.
    bindir = toolchain_dir() / "bin"
    root = bundle.bundle_dir()
    if not dry_run and root:
        bindir.mkdir(parents=True, exist_ok=True)
        for tool in ("bend", "hvm"):
            src = root / "bin" / tool
            if src.is_file():
                dest = bindir / tool
                shutil.copy2(src, dest)
                dest.chmod(dest.stat().st_mode | 0o111)

    if dry_run:
        print("  would verify: moon version, bend --version, hvm --version")
        return 0

    compiler = moonbit_compiler()
    print(f"  moon: {_capture([str(compiler), 'version']) if compiler else 'MISSING'}")
    print(f"  bend: {_capture([str(bindir / 'bend'), '--version'])}")
    print(f"  hvm:  {_capture([str(bindir / 'hvm'), '--version'])}")
    return 0 if compiler else 1


def _capture(argv: list[str]) -> str:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        return (proc.stdout or proc.stderr or "").strip().splitlines()[0]
    except Exception as exc:  # pragma: no cover - diagnostics only
        return f"error: {exc}"


def cmd_toolchain(action: str, as_json: bool, dry_run: bool) -> int:
    if action == "status":
        info = status()
        if as_json:
            print(json.dumps(info, indent=2))
        else:
            moon = info["moonbit"]
            print(f"ncel toolchain home: {info['toolchain_dir']}")
            print(
                f"  MoonBit compiler: {'installed at ' + moon['compiler'] if moon['compiler_installed'] else 'not installed (not needed to run)'}"
                f"  pin {moon['pinned_version']}"
            )
            print(f"  Bend (bundled):   {(info['bend'] or {}).get('version')}  sha256 {(info['bend'] or {}).get('sha256', '')[:12]}…")
            print(f"  HVM2 (bundled):   {(info['hvm'] or {}).get('version')}  sha256 {(info['hvm'] or {}).get('sha256', '')[:12]}…")
            print(f"  note: {info['note']}")
        return 0
    if action == "install":
        return install_moonbit(dry_run=dry_run)
    print("usage: ncel toolchain <status|install> [--json] [--dry-run]", file=sys.stderr)
    return 2
