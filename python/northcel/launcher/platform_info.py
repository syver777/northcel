"""Platform facts for the native runtime, and the honest support verdict.

The native runtime is Linux x86_64 only. It needs glibc >= 2.39 (the pinned Bend
and HVM binaries import GLIBC_2.39 symbols) and a Mesa/EGL GL runtime. Anything
else is reported as unsupported; nothing here pretends otherwise.
"""

from __future__ import annotations

import glob
import os
import platform as _platform
import shutil
import sys
from dataclasses import dataclass, field

MIN_GLIBC = (2, 39)

SUPPORTED_OS = "linux"
SUPPORTED_ARCHES = ("x86_64", "amd64")

# Well-known Homebrew prefixes to look for an EGL runtime in. Homebrew on Linux is
# `/home/linuxbrew/.linuxbrew`; `/usr/local` is the default on macOS and is where a
# root install of anything unbundled lands. `$HOMEBREW_PREFIX` and `~/.linuxbrew` are
# added on top of these at call time. Kept as a module constant so tests can isolate.
HOMEBREW_PREFIXES = ("/home/linuxbrew/.linuxbrew", "/usr/local")

# The distribution paths the probe historically checked, in its original order.
DISTRO_LIB_DIRS = (
    "/usr/lib/x86_64-linux-gnu",
    "/usr/lib64",
    "/usr/lib",
    "/lib/x86_64-linux-gnu",
    "/lib64",
    "/lib",
)


def glibc_version() -> str | None:
    """Return the running glibc version as 'major.minor', or None."""
    try:
        raw = os.confstr("CS_GNU_LIBC_VERSION")  # e.g. "glibc 2.39"
    except (AttributeError, ValueError, OSError):
        raw = None
    if not raw:
        try:  # fall back to the dynamic loader's own answer
            import ctypes

            libc = ctypes.CDLL("libc.so.6")
            libc.gnu_get_libc_version.restype = ctypes.c_char_p
            raw = libc.gnu_get_libc_version().decode("utf-8", "replace")
            return ".".join(raw.split(".")[:2])
        except Exception:
            return None
    parts = raw.strip().split()
    if not parts:
        return None
    ver = parts[-1]
    return ".".join(ver.split(".")[:2])


def _version_tuple(text: str | None) -> tuple[int, ...]:
    if not text:
        return ()
    out = []
    for piece in text.split("."):
        try:
            out.append(int(piece))
        except ValueError:
            break
    return tuple(out)


def _egl_search_dirs() -> list[tuple[str, str]]:
    """Directories to search for libEGL.so.1, in the order that matters.

    The launcher used to look only at distribution paths and `ldconfig -p`, which made
    a perfectly usable Mesa invisible whenever it lived somewhere else: Homebrew
    installs Mesa **keg-only** under `$(brew --prefix)`, and anything on
    `LD_LIBRARY_PATH` is exactly what `dlopen("libEGL.so.1")` in the native host will
    use. The gate has to see what the loader sees, or it refuses to render a machine
    that can render.

    Order (first hit wins, matching dynamic-loader precedence as closely as a
    filesystem probe can):
      1. `LD_LIBRARY_PATH` entries, left to right (the loader's own order)
      2. Homebrew prefixes: `$HOMEBREW_PREFIX`, /home/linuxbrew/.linuxbrew,
         ~/.linuxbrew, /usr/local — both `lib/` and keg-only `opt/*/lib`
      3. the interpreter's own prefixes (venv / pyenv / conda `lib`, `lib64`)
      4. the distribution paths, then `ldconfig -p`
    Returns `(label, directory)` pairs; the label is only used for diagnostics.
    """
    dirs: list[tuple[str, str]] = []

    for entry in os.environ.get("LD_LIBRARY_PATH", "").split(os.pathsep):
        if entry:
            dirs.append(("LD_LIBRARY_PATH", entry))

    prefixes: list[str] = []
    env_prefix = os.environ.get("HOMEBREW_PREFIX")
    if env_prefix:
        prefixes.append(env_prefix)
    home = os.environ.get("HOME")
    prefixes += list(HOMEBREW_PREFIXES)
    if home:
        prefixes.append(os.path.join(home, ".linuxbrew"))
    for prefix in prefixes:
        dirs.append(("Homebrew prefix", os.path.join(prefix, "lib")))
        dirs.append(("Homebrew prefix", os.path.join(prefix, "lib64")))
        # Keg-only formulae (mesa among them) are linked at `opt/<name>/lib` only.
        for pattern in ("opt/*/lib", "opt/*/lib64"):
            for match in sorted(glob.glob(os.path.join(prefix, pattern))):
                dirs.append(("Homebrew keg", match))

    for prefix in sorted({sys.prefix, sys.base_prefix}):
        dirs.append(("Python prefix", os.path.join(prefix, "lib")))
        dirs.append(("Python prefix", os.path.join(prefix, "lib64")))

    dirs += [("distribution", directory) for directory in DISTRO_LIB_DIRS]
    return dirs


def find_egl_runtime() -> str | None:
    """Locate libEGL.so.1 the same way the native host dlopen()s it."""
    seen: set[str] = set()
    for _label, directory in _egl_search_dirs():
        if directory in seen:
            continue
        seen.add(directory)
        candidate = os.path.join(directory, "libEGL.so.1")
        if os.path.exists(candidate):
            return candidate
    found = shutil.which("ldconfig")
    if found:
        try:
            import subprocess

            out = subprocess.run(
                [found, "-p"], capture_output=True, text=True, timeout=10
            ).stdout
            for line in out.splitlines():
                if "libEGL.so.1" in line and "=>" in line:
                    return line.split("=>", 1)[1].strip()
        except Exception:
            pass
    return None


@dataclass
class PlatformInfo:
    os: str
    arch: str
    glibc: str | None
    supported: bool
    reasons: list[str] = field(default_factory=list)
    egl: str | None = None

    def as_dict(self) -> dict:
        return {
            "os": self.os,
            "arch": self.arch,
            "glibc": self.glibc,
            "egl_runtime": self.egl,
            "supported": self.supported,
            "reasons": list(self.reasons),
        }


def machine() -> str:
    return (_platform.machine() or "").lower()


def platform_info() -> PlatformInfo:
    sys_os = "linux" if sys.platform.startswith("linux") else sys.platform
    arch = machine()
    glibc = glibc_version() if sys_os == "linux" else None
    reasons: list[str] = []

    if sys_os != SUPPORTED_OS:
        reasons.append(
            "the native runtime is built and conformance-verified on Linux x86_64 "
            f"only; this is {sys_os}/{arch}. macOS needs Vulkan/MoltenVK or a tested "
            "GL 4.1 path (see native/BUILD.md section 7) and Windows is untouched."
        )
    else:
        if arch not in SUPPORTED_ARCHES:
            reasons.append(
                f"the native runtime is x86_64 only; this machine is {arch} "
                "(linux-aarch64 is not built)."
            )
        if not glibc:
            reasons.append("could not determine the glibc version.")
        elif _version_tuple(glibc) < MIN_GLIBC:
            reasons.append(
                f"glibc {glibc} is older than the required 2.39 (the pinned Bend/HVM "
                "binaries need GLIBC_2.39). Ubuntu 24.04+, Debian 13, Fedora 40+ and "
                "RHEL 10 satisfy it."
            )

    egl = find_egl_runtime() if sys_os == "linux" else None
    if sys_os == "linux" and arch in SUPPORTED_ARCHES and not egl:
        reasons.append(
            "no libEGL.so.1 found in LD_LIBRARY_PATH, the Homebrew prefix, the Python "
            "prefix or the distribution library paths: GLSL is compiled by the GL "
            "driver, so the Mesa/EGL runtime is required (apt install libegl1 libgl1 "
            "mesa-libgallium | dnf install mesa-libEGL mesa-dri-drivers). Run `ncel "
            "doctor` after installing it."
        )

    return PlatformInfo(
        os=sys_os,
        arch=arch,
        glibc=glibc,
        supported=not reasons,
        reasons=reasons,
        egl=egl,
    )
