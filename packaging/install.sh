#!/usr/bin/env bash
# northcel one-line installer for Linux x86_64.
#
# Public one-liner:
#
#   curl -fsSL https://raw.githubusercontent.com/syver777/northcel/main/packaging/install.sh | bash
#
# From a checkout:   bash packaging/install.sh
#
# Installs the `northcel` CLI (short alias `ncel`) with the native NorthCel runtime
# (MoonBit + Bend/HVM2 + GLSL via Mesa/EGL) into user space, verifies every bundled
# checksum, and proves the installation with real renders. No root unless you ask
# for Mesa to be installed.
#
#   --dry-run        print every action, change nothing
#   --uninstall      remove what this installer created
#   --no-verify      skip the render/conformance self-test
#   --with-moonbit   also provision the pinned MoonBit compiler (101 MB, source builds only)
#   --install-mesa   allow the one privileged step: install Mesa/EGL with sudo
#   --version X.Y.Z  install a specific northcel version (default 0.3.1)
#   --prefix DIR     install root (default $HOME/.local/share/ncel)
#   --bin-dir DIR    where the `northcel` symlink goes (default $HOME/.local/bin)
#   -h, --help       this text
#
# Linux x86_64 only, glibc >= 2.39, Mesa EGL/llvmpipe. macOS and Windows are not
# supported in this release and this script says so instead of pretending.
set -euo pipefail

NCEL_VERSION="0.3.1"
NCEL_HOME="${NCEL_HOME:-$HOME/.local/share/ncel}"
BIN_DIR="${NCEL_BIN_DIR:-$HOME/.local/bin}"
INDEX_URL="${NCEL_INDEX_URL:-https://pypi.org/simple}"
DRY_RUN=0
UNINSTALL=0
NO_VERIFY=0
WITH_MOONBIT=0
INSTALL_MESA=0

say() { printf '%s\n' "$*"; }
warn() { printf 'northcel: %s\n' "$*" >&2; }
die() { printf 'northcel: %s\n' "$1" >&2; exit "${2:-1}"; }
run() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  [dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

usage() {
  cat <<'EOF'
northcel installer for Linux x86_64 — installs the `northcel` CLI (alias `ncel`)
and the native NorthCel runtime (MoonBit + Bend/HVM2 + GLSL via Mesa/EGL) into
user space.

  --dry-run        print every action, change nothing
  --uninstall      remove what this installer created
  --no-verify      skip the render/conformance self-test
  --with-moonbit   also provision the pinned MoonBit compiler (101 MB, source builds only)
  --install-mesa   allow the one privileged step: install Mesa/EGL with sudo
  --version X.Y.Z  install a specific northcel version (default 0.3.1)
  --prefix DIR     install root (default $HOME/.local/share/ncel)
  --bin-dir DIR    where the `northcel` symlink goes (default $HOME/.local/bin)
  -h, --help       this text
EOF
}

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --no-verify) NO_VERIFY=1 ;;
    --with-moonbit) WITH_MOONBIT=1 ;;
    --install-mesa) INSTALL_MESA=1 ;;
    --version) shift; NCEL_VERSION="${1:?--version needs a value}" ;;
    --version=*) NCEL_VERSION="${1#--version=}" ;;
    --prefix) shift; NCEL_HOME="${1:?--prefix needs a value}" ;;
    --prefix=*) NCEL_HOME="${1#--prefix=}" ;;
    --bin-dir) shift; BIN_DIR="${1:?--bin-dir needs a value}" ;;
    --bin-dir=*) BIN_DIR="${1#--bin-dir=}" ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown option '$1' (try --help)" 2 ;;
  esac
  shift
done

VENV="$NCEL_HOME/venv"
MARKER="$NCEL_HOME/.northcel-install"

# ---------------------------------------------------------------- platform gate

detect_platform() {
  OS="$(uname -s)"
  ARCH="$(uname -m)"
  if [ "$OS" != "Linux" ]; then
    die "the native runtime is built and conformance-verified on Linux x86_64 only,
northcel: this is $OS/$ARCH. macOS needs Vulkan/MoltenVK or a tested GL 4.1 path and
northcel: Windows is untouched (see native/BUILD.md section 7). Nothing was changed.
northcel: For a labelled non-native renderer use: pip install northcel" 3
  fi
  case "$ARCH" in
    x86_64|amd64) ;;
    *) die "the native runtime is x86_64 only; this machine is $ARCH (nothing was changed)." 3 ;;
  esac
  GLIBC="$(getconf GNU_LIBC_VERSION 2>/dev/null | awk '{print $2}' || true)"
  if [ -z "$GLIBC" ]; then
    GLIBC="$(ldd --version 2>/dev/null | head -1 | awk '{print $NF}' || true)"
  fi
  if [ -n "$GLIBC" ]; then
    GLIBC_MAJOR="${GLIBC%%.*}"
    GLIBC_REST="${GLIBC#*.}"
    GLIBC_MINOR="${GLIBC_REST%%.*}"
    if [ "${GLIBC_MAJOR:-0}" -lt 2 ] || { [ "${GLIBC_MAJOR:-0}" -eq 2 ] && [ "${GLIBC_MINOR:-0}" -lt 39 ]; }; then
      die "glibc $GLIBC is older than the required 2.39 (the pinned Bend/HVM binaries
northcel: need GLIBC_2.39). Ubuntu 24.04+, Debian 13, Fedora 40+ and RHEL 10 satisfy it.
northcel: Nothing was changed." 3
    fi
  fi
  say "platform: linux-$ARCH, glibc ${GLIBC:-unknown}"
}

have_egl() {
  for candidate in /usr/lib/x86_64-linux-gnu/libEGL.so.1 /usr/lib64/libEGL.so.1 \
                   /usr/lib/libEGL.so.1 /lib/x86_64-linux-gnu/libEGL.so.1; do
    [ -e "$candidate" ] && return 0
  done
  if command -v ldconfig >/dev/null 2>&1; then
    ldconfig -p 2>/dev/null | grep -q 'libEGL\.so\.1' && return 0
  fi
  return 1
}

mesa_hint() {
  if command -v apt-get >/dev/null 2>&1; then
    warn "  sudo apt-get install -y libegl1 libgl1 mesa-libgallium"
  elif command -v dnf >/dev/null 2>&1; then
    warn "  sudo dnf install -y mesa-libEGL mesa-dri-drivers mesa-libGL"
  elif command -v zypper >/dev/null 2>&1; then
    warn "  sudo zypper install -y libEGL1 Mesa-libgallium"
  elif command -v pacman >/dev/null 2>&1; then
    warn "  sudo pacman -S --needed mesa"
  else
    warn "  install the Mesa EGL runtime (libEGL.so.1) with your package manager"
  fi
}

install_mesa() {
  if command -v apt-get >/dev/null 2>&1; then
    run sudo apt-get update -qq
    run sudo apt-get install -y libegl1 libgl1 mesa-libgallium
  elif command -v dnf >/dev/null 2>&1; then
    run sudo dnf install -y mesa-libEGL mesa-dri-drivers mesa-libGL
  elif command -v zypper >/dev/null 2>&1; then
    run sudo zypper install -y libEGL1 Mesa-libgallium
  elif command -v pacman >/dev/null 2>&1; then
    run sudo pacman -S --needed --noconfirm mesa
  else
    die "no supported package manager found; install the Mesa EGL runtime manually" 3
  fi
}

ensure_gl_runtime() {
  if have_egl; then
    say "GL runtime: libEGL.so.1 present"
    return 0
  fi
  warn "no libEGL.so.1 found — GLSL is compiled by the GL driver, so the Mesa/EGL"
  warn "runtime is required. Install it with:"
  mesa_hint
  if [ "$INSTALL_MESA" -eq 1 ]; then
    say "installing Mesa (the only privileged step) ..."
    install_mesa
    have_egl || die "Mesa installation did not provide libEGL.so.1" 3
    say "GL runtime: installed"
  else
    die "re-run with --install-mesa to let this script install it, or install it yourself" 3
  fi
}

# ------------------------------------------------------------------- uninstall

do_uninstall() {
  say "northcel uninstall"
  for link in northcel ncel; do
    if [ -L "$BIN_DIR/$link" ]; then
      target="$(readlink -f "$BIN_DIR/$link" 2>/dev/null || true)"
      case "$target" in
        "$NCEL_HOME"/*) run rm -f "$BIN_DIR/$link"; say "  removed symlink $BIN_DIR/$link" ;;
        *) warn "leaving $BIN_DIR/$link alone (it does not point into $NCEL_HOME)" ;;
      esac
    fi
  done
  # `.ncel-install` is the marker written by the 0.2.1 installer; keep removing it.
  if [ -f "$MARKER" ] || [ -f "$NCEL_HOME/.ncel-install" ]; then
    run rm -rf "$NCEL_HOME"
    say "  removed $NCEL_HOME"
  elif [ -d "$NCEL_HOME" ]; then
    warn "$NCEL_HOME was not created by this installer; leaving it in place"
  else
    say "  nothing to remove"
  fi
  say "done."
}

# --------------------------------------------------------------------- install

find_python() {
  for candidate in python3 python3.12 python3.11; do
    if command -v "$candidate" >/dev/null 2>&1; then
      version="$("$candidate" -c 'import sys;print("%d.%d"%sys.version_info[:2])' 2>/dev/null || echo 0.0)"
      major="${version%%.*}"
      minor="${version#*.}"
      if [ "${major:-0}" -ge 3 ] && [ "${minor:-0}" -ge 10 ]; then
        printf '%s' "$candidate"
        return 0
      fi
    fi
  done
  return 1
}

make_venv() {
  # python3 -m venv needs python3-venv on Debian/Ubuntu; virtualenv is the fallback.
  if run "$PYTHON" -m venv "$VENV" >/dev/null 2>&1; then
    return 0
  fi
  if command -v virtualenv >/dev/null 2>&1; then
    warn "python3 -m venv unavailable; using virtualenv"
    run virtualenv -q -p "$PYTHON" "$VENV"
    return 0
  fi
  die "cannot create a virtual environment. Install python3-venv
northcel:   sudo apt-get install -y python3-venv      # Debian/Ubuntu
northcel:   sudo dnf install -y python3-virtualenv    # Fedora
northcel: or: pip install --user virtualenv" 4
}

verify_bundle() {
  "$VENV/bin/python" - <<'PY'
import json, sys
from pathlib import Path
try:
    import northcel_native_bundle as ncel_native_bundle
except Exception:
    print("no native bundle installed for this platform")
    sys.exit(0)
root = Path(ncel_native_bundle.__file__).parent
manifest = json.loads((root / "bundle-manifest.json").read_text())
import hashlib
bad, missing = [], []
for entry in manifest["files"]:
    path = root / entry["path"]
    if not path.is_file():
        missing.append(entry["path"])
        continue
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != entry["sha256"]:
        bad.append(entry["path"])
print(f"bundle: {len(manifest['files'])} files, {manifest['total_bytes']} bytes, "
      f"runtime {manifest['runtime_version']}, spec {manifest['spec_version']}")
if missing or bad:
    print("CHECKSUM FAILURE:", missing, bad)
    sys.exit(1)
print("bundle: every sha256 matches")
PY
}

do_install() {
  say "northcel installer — version $NCEL_VERSION"
  detect_platform
  ensure_gl_runtime

  PYTHON="$(find_python)" || die "python3 >= 3.10 is required and was not found" 4
  say "python: $("$PYTHON" -c 'import sys;print(sys.version.split()[0])') ($PYTHON)"
  say "install root: $NCEL_HOME"

  if [ "$DRY_RUN" -eq 1 ]; then
    say "  [dry-run] create venv at $VENV"
    say "  [dry-run] pip install --only-binary=:all: --no-cache-dir --index-url $INDEX_URL northcel==$NCEL_VERSION"
    say "  [dry-run] verify bundled sha256 manifest"
    say "  [dry-run] link $BIN_DIR/northcel -> $VENV/bin/northcel (and ncel)"
    [ "$NO_VERIFY" -eq 0 ] && say "  [dry-run] northcel verify (real renders + determinism)"
    [ "$WITH_MOONBIT" -eq 1 ] && say "  [dry-run] northcel toolchain install --moonbit (101 MB)"
    say "dry run complete; nothing was changed."
    return 0
  fi

  run mkdir -p "$NCEL_HOME" "$BIN_DIR"
  if [ ! -x "$VENV/bin/python" ]; then
    say "creating virtual environment ..."
    make_venv
  else
    say "virtual environment: reusing $VENV"
  fi

  say "installing northcel==$NCEL_VERSION from $INDEX_URL ..."
  run "$VENV/bin/python" -m pip install --quiet --upgrade pip >/dev/null 2>&1 || true
  run "$VENV/bin/python" -m pip install --quiet --no-cache-dir --only-binary=:all: \
      --index-url "$INDEX_URL" "northcel==$NCEL_VERSION"

  say "verifying installed bundle ..."
  run verify_bundle

  printf '%s\n' "installed_by=northcel-install.sh" "version=$NCEL_VERSION" "at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$MARKER"
  run ln -sfn "$VENV/bin/northcel" "$BIN_DIR/northcel"
  run ln -sfn "$VENV/bin/northcel" "$BIN_DIR/ncel"
  say "linked: $BIN_DIR/northcel -> $VENV/bin/northcel (alias: $BIN_DIR/ncel)"

  if [ "$WITH_MOONBIT" -eq 1 ]; then
    say "provisioning the pinned MoonBit compiler (source builds only) ..."
    run "$VENV/bin/northcel" toolchain install
  fi

  say ""
  run "$VENV/bin/northcel" doctor || true

  if [ "$NO_VERIFY" -eq 0 ]; then
    say ""
    say "running the conformance self-test (real renders, determinism) ..."
    if ! run "$VENV/bin/northcel" verify; then
      die "the installed runtime failed its self-test; run '$VENV/bin/northcel doctor --json'" 5
    fi
  fi

  say ""
  say "northcel is installed."
  case ":$PATH:" in
    *":$BIN_DIR:"*) say "run: northcel doctor" ;;
    *) say "add $BIN_DIR to PATH, then run: northcel doctor"
       say "  export PATH=\"$BIN_DIR:\$PATH\"" ;;
  esac
  say "uninstall: $0 --uninstall   (or re-run this script with --uninstall)"
}

if [ "$UNINSTALL" -eq 1 ]; then
  do_uninstall
else
  do_install
fi
