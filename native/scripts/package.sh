#!/usr/bin/env bash
# Package the Linux x86_64 native runtime artifact + checksum.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${BUILD:-$ROOT/build}"
VER="$(sed -n 's/^version = "\(.*\)"/\1/p' "$ROOT/moonbit/moon.mod" | head -1)"
VER="${VER:-0.2.0}"
NAME="ncel-native-$VER-linux-x86_64"
STAGE="$ROOT/artifacts/$NAME"
TAR="$ROOT/artifacts/$NAME.tar.gz"

[[ -x "$BUILD/bin/ncel-native" ]] || { echo "error: run scripts/build.sh first"; exit 1; }
rm -rf "$STAGE" "$TAR" "$TAR.sha256"
mkdir -p "$STAGE/bin" "$STAGE/share/ncel" "$STAGE/tests/fixtures" "$STAGE/licenses"

cp "$BUILD/bin/ncel-native" "$BUILD/bin/ncel-ast" "$BUILD/bin/ncel-gl" "$STAGE/bin/"
cp "$ROOT/vendor/linux-x86_64/bin/bend" "$ROOT/vendor/linux-x86_64/bin/hvm" "$STAGE/bin/"
cp "$BUILD/share/ncel/draw430.glsl" "$BUILD/share/ncel/draw410.glsl" "$STAGE/share/ncel/"
cp "$ROOT/toolchain.lock" "$ROOT/BUILD.md" "$ROOT/README.md" "$ROOT/LICENSE-NOTES.md" "$STAGE/"
cp -r "$ROOT/tests/fixtures/"* "$STAGE/tests/fixtures/"
cp "$ROOT/tests/probe_check.py" "$ROOT/tests/compare_oracle.py" "$ROOT/tests/render_reference.py" "$ROOT/tests/run-tests.sh" "$STAGE/tests/"

# Licences of vendored components.
cp "$ROOT/moonbit/../.toolchain/moon/lib/core/LICENSE" "$STAGE/licenses/moonbit-core-LICENSE" 2>/dev/null || true
cat > "$STAGE/licenses/README.txt" <<'EOF'
ncel-native bundles or links:
  MoonBit CLI + core (Apache-2.0)            https://www.moonbitlang.com
  bend-lang 0.2.38 (Apache-2.0)              https://github.com/bendlang/bend
  hvm 2.0.22 (Apache-2.0)                    https://github.com/higherorderco/hvm
  stb_image_write 1.16 (public domain / MIT) https://github.com/nothings/stb
  Mesa llvmpipe EGL runtime (MIT, system)    https://mesa3d.org
NorthCel native runtime, MoonBit sources and GLSL shaders: Proprietary, North Noir.
EOF

( cd "$ROOT/artifacts" && tar --sort=name --mtime='2026-11-04 00:00:00Z' \
    --owner=0 --group=0 --numeric-owner -czf "$NAME.tar.gz" "$NAME" )
sha256sum "$TAR" > "$TAR.sha256"

# Source artifact for other platforms / rebuilds (not a macOS claim).
SRCNAME="ncel-native-$VER-source"
SRCSTAGE="$ROOT/artifacts/$SRCNAME"
SRCTAR="$ROOT/artifacts/$SRCNAME.tar.gz"
rm -rf "$SRCSTAGE" "$SRCTAR" "$SRCTAR.sha256"
mkdir -p "$SRCSTAGE"
for item in moonbit src shaders tests scripts vendor Makefile toolchain.lock BUILD.md README.md LICENSE-NOTES.md; do
  cp -r "$ROOT/$item" "$SRCSTAGE/"
done
# Source only: drop MoonBit build outputs.
rm -rf "$SRCSTAGE/moonbit/_build"
( cd "$ROOT/artifacts" && tar --sort=name --mtime='2026-11-04 00:00:00Z' \
    --owner=0 --group=0 --numeric-owner -czf "$SRCNAME.tar.gz" "$SRCNAME" )
sha256sum "$SRCTAR" > "$SRCTAR.sha256"

BYTES=$(stat -c%s "$TAR")
SBYTES=$(stat -c%s "$SRCTAR")
echo "artifact: $TAR"
echo "bytes:    $BYTES"
echo "sha256:   $(cut -d' ' -f1 "$TAR.sha256")"
echo "source:   $SRCTAR"
echo "bytes:    $SBYTES"
echo "sha256:   $(cut -d' ' -f1 "$SRCTAR.sha256")"
