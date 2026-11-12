"""`northcel doctor` — exact stage availability and versions, and the honest verdict."""

from __future__ import annotations

import json

from . import EXIT_NO_NATIVE, NATIVE_RUNTIME_VERSION, SPEC_VERSION, __version__, bundle, native, paths
from . import platform_info as plat_mod


def pins() -> dict:
    path = paths.pins_path()
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def reference_version() -> str:
    """Version of the Python reference bundled with this launcher.

    The launcher and the reference ship in the same distribution, so prefer the
    package config over stale installed metadata (for example when running from
    a source checkout through ``PYTHONPATH``).
    """
    return __version__


def collect() -> dict:
    plat = plat_mod.platform_info()
    pin = pins()
    manifest = bundle.load_manifest()
    checks = bundle.verify_checksums(manifest)
    native_doc = native.doctor_json() if bundle.binary() else None

    errors: list[str] = []
    if not plat.supported:
        errors.extend(plat.reasons)
    if bundle.binary() is None:
        errors.append(
            "native runtime bundle not installed (pip install northcel-native on Linux x86_64)"
        )
    if checks.get("failed"):
        errors.append(
            "native bundle checksum mismatch: "
            + ", ".join(item["path"] for item in checks["failed"])
        )
    if checks.get("missing"):
        errors.append("native bundle is missing files: " + ", ".join(checks["missing"]))
    if bundle.binary() and not native_doc:
        errors.append("`ncel-native doctor` did not return a usable report")

    moonbit_pin = pin.get("moonbit", {}).get("version")
    stages = {
        "moonbit": {
            "present": bool(native_doc and native_doc.get("moonbit_stage")),
            "binary": "ncel-ast",
            "compiled_with": moonbit_pin,
            "compiler_installed": _moonbit_compiler_installed(),
        },
        "bend": {
            "present": bool(native_doc and native_doc.get("bend_path")),
            "version": (native_doc or {}).get("bend_version", "").strip() or None,
            "path": (native_doc or {}).get("bend_path") or None,
        },
        "hvm": {
            "present": bool(native_doc and native_doc.get("hvm_path")),
            "version": (native_doc or {}).get("hvm_version", "").strip() or None,
            "path": (native_doc or {}).get("hvm_path") or None,
        },
        "gl": {
            "present": bool(native_doc and (native_doc.get("gl") or {}).get("ok")),
            "version": (native_doc or {}).get("gl", {}).get("gl_version"),
            "renderer": (native_doc or {}).get("gl", {}).get("gl_renderer"),
            "glsl": (native_doc or {}).get("gl", {}).get("glsl_version"),
            "egl_runtime": plat.egl,
        },
        "glsl_shaders": {
            name: {
                "sha256": data.get("sha256"),
                "compiles": bool((data.get("compile") or {}).get("ok")),
                "path": data.get("path"),
            }
            for name, data in ((native_doc or {}).get("shaders") or {}).items()
        },
        "ffmpeg": {
            "present": bool((native_doc or {}).get("ffmpeg")),
            "optional": True,
        },
    }

    native_ok = (
        plat.supported
        and bundle.binary() is not None
        and not checks.get("failed")
        and not checks.get("missing")
        and bool(native_doc)
        and bool((native_doc or {}).get("ok"))
    )

    return {
        "ok": native_ok,
        "ncel_version": __version__,
        "platform": plat.as_dict(),
        "native": {
            "available": native_ok,
            "runtime_version": (native_doc or {}).get("version") or NATIVE_RUNTIME_VERSION,
            "expected_runtime_version": NATIVE_RUNTIME_VERSION,
            "spec_version": (native_doc or {}).get("spec_version") or SPEC_VERSION,
            "bundle": str(bundle.bundle_dir()) if bundle.bundle_dir() else None,
            "manifest": bool(manifest),
            "checksums": {
                "verified": checks.get("checked", 0),
                "failed": checks.get("failed", []),
                "missing": checks.get("missing", []),
            },
            "stage": _stage_label(native_doc),
            "python_fallback_in_binary": bool((native_doc or {}).get("python_fallback")),
        },
        "stages": stages,
        "reference": {
            "package": "northcel",
            "version": reference_version(),
            "role": "fallback only — non-native reference renderer",
        },
        "errors": errors,
    }


def _stage_label(native_doc: dict | None) -> str | None:
    """`ncel-native doctor` reports stage booleans, not a label; receipts say this."""
    if not native_doc:
        return None
    stages = (
        native_doc.get("moonbit_stage"),
        native_doc.get("gl_stage"),
        bool(native_doc.get("bend_path")),
        bool(native_doc.get("hvm_path")),
    )
    return "MoonBit+Bend+GLSL" if all(stages) else None


def _moonbit_compiler_installed() -> bool:
    from . import toolchain

    return toolchain.moonbit_compiler() is not None


def _yes(flag: bool) -> str:
    return "yes" if flag else "NO"


def print_human(doc: dict) -> None:
    plat = doc["platform"]
    native_info = doc["native"]
    stages = doc["stages"]

    print(f"northcel {doc['ncel_version']}  (NorthCel spec {native_info['spec_version']})")
    glibc = f" glibc {plat['glibc']}" if plat.get("glibc") else ""
    print(f"platform      {plat['os']}-{plat['arch']}{glibc}")
    print(f"supported     {_yes(plat['supported'])}")
    for reason in plat.get("reasons", []):
        print(f"              - {reason}")

    if native_info["available"]:
        print(
            f"native        {native_info['runtime_version']}  "
            f"(bundle checksums {native_info['checksums']['verified']} verified, "
            f"stage {native_info['stage']})"
        )
    else:
        print(
            "native        NOT AVAILABLE"
            + (f" (bundle {native_info['bundle']})" if native_info.get("bundle") else "")
        )

    def line(label: str, value: str) -> None:
        print(f"  {label:<12}  {value}")

    moon = stages["moonbit"]
    line(
        "MoonBit",
        f"stage present: {_yes(moon['present'])}  binary {moon['binary']}  "
        f"compiled with MoonBit {moon['compiled_with'] or '?'}  "
        f"compiler installed: {_yes(moon['compiler_installed'])}",
    )
    bend = stages["bend"]
    line("Bend", f"{(bend['version'] or 'missing').strip()}  {bend['path'] or ''}".rstrip())
    hvm = stages["hvm"]
    line("HVM2", f"{(hvm['version'] or 'missing').strip()}  {hvm['path'] or ''}".rstrip())
    gl = stages["gl"]
    line(
        "GL runtime",
        f"{(gl['version'] or 'missing')}  {gl['renderer'] or ''}  GLSL {gl['glsl'] or '?'}".rstrip(),
    )
    shaders = stages["glsl_shaders"]
    if shaders:
        parts = [
            f"{name} {data['sha256'][:12]}… {'compiles' if data['compiles'] else 'FAILED'}"
            for name, data in shaders.items()
        ]
        line("GLSL", "  ".join(parts))
    line("ffmpeg", "present (optional, --mp4)" if stages["ffmpeg"]["present"] else "absent (optional)")
    line(
        "reference",
        f"northcel {doc['reference']['version']} — {doc['reference']['role']}",
    )
    if doc["errors"]:
        print("errors:")
        for err in doc["errors"]:
            print(f"  - {err}")


def cmd_doctor(as_json: bool) -> int:
    doc = collect()
    if as_json:
        print(json.dumps(doc, indent=2))
    else:
        print_human(doc)
    return 0 if doc["ok"] else EXIT_NO_NATIVE
