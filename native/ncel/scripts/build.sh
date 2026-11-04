#!/usr/bin/env bash
# Build the NorthCel native runtime without requiring GNU make.
# Same outputs as the Makefile: build/bin/{ncel-native,ncel-ast,ncel-gl} and
# build/share/ncel/{draw430,draw410}.glsl.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD="${BUILD:-$ROOT/build}"
MOON_HOME="${MOON_HOME:-$ROOT/.toolchain/moon}"
MOON="${MOON:-$MOON_HOME/bin/moon}"
CC="${CC:-$(command -v cc || command -v gcc || true)}"
CFLAGS="${CFLAGS:--O2 -std=c11 -Wall -Wextra}"

[[ -x "$MOON" ]] || { echo "error: $MOON not found; run scripts/provision-toolchain.sh"; exit 1; }
[[ -n "$CC" ]] || { echo "error: no C compiler (set CC)"; exit 1; }

mkdir -p "$BUILD/bin" "$BUILD/share/ncel"

t0=$(date +%s)
echo "== MoonBit AST stage =="
(cd "$ROOT/moonbit" && MOON_HOME="$MOON_HOME" "$MOON" build --target native --release cmd/ncel_ast)
cp "$ROOT/moonbit/_build/native/release/build/cmd/ncel_ast/ncel_ast.exe" "$BUILD/bin/ncel-ast"
chmod +x "$BUILD/bin/ncel-ast"

echo "== C GLSL host =="
"$CC" $CFLAGS -o "$BUILD/bin/ncel-gl" \
  "$ROOT/src/gl/ncel_gl.c" "$ROOT/src/gl/ncel_ir.c" -ldl -lm

echo "== C CLI =="
"$CC" $CFLAGS -I "$ROOT/src/cli" -o "$BUILD/bin/ncel-native" \
  "$ROOT/src/cli/ncel_native.c" "$ROOT/src/cli/sha256.c"

cp "$ROOT/shaders/draw430.glsl" "$ROOT/shaders/draw410.glsl" "$BUILD/share/ncel/"
t1=$(date +%s)
echo "ok: built in $((t1 - t0))s -> $BUILD"
"$BUILD/bin/ncel-native" --version
