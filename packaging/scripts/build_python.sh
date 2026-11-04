#!/usr/bin/env bash
# Build the PyPI artifacts: `northcel-native` (platform wheel) and `northcel`
# (reference + launcher wheel and sdist).
#
#   bash packaging/scripts/build_python.sh [OUTDIR]
#
# OUTDIR defaults to dist/python.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/dist/python}"
PLATFORM_TAG="manylinux_2_39_x86_64"

# Reproducible wheel/sdist timestamps (setuptools + wheel honour this).
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1793750400}" # 2026-11-04T00:00:00Z

cd "$ROOT"
echo "== pins from native/toolchain.lock"
python3 packaging/scripts/gen_pins.py

echo "== stage the native bundle"
python3 packaging/scripts/stage_bundle.py --out python/northcel-native/northcel_native_bundle

rm -rf "$OUT"
mkdir -p "$OUT"

echo "== build northcel-native (platform wheel)"
( cd python/northcel-native && python3 -m build --wheel --outdir "$OUT" >/dev/null )
python3 packaging/scripts/fix_wheel_tag.py "$OUT"/northcel_native-*-py3-none-any.whl --platform "$PLATFORM_TAG"

echo "== build northcel (reference + launcher, wheel + sdist)"
( cd python && python3 -m build --outdir "$OUT" >/dev/null )

echo "== twine check"
python3 -m twine check "$OUT"/* 2>&1 | tail -5

echo "== artifacts"
( cd "$OUT" && ls -l . && sha256sum ./* )
