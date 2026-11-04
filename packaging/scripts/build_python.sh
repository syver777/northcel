#!/usr/bin/env bash
# Build the PyPI artifacts: ncel-native (platform wheel) and ncel (launcher).
#
#   bash packaging/scripts/build_python.sh [OUTDIR]
#
# OUTDIR defaults to work/checks/ncel-packaging/wheels.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/work/checks/ncel-packaging/wheels}"
PLATFORM_TAG="manylinux_2_39_x86_64"

# Reproducible wheel/sdist timestamps (setuptools + wheel honour this).
export SOURCE_DATE_EPOCH="${SOURCE_DATE_EPOCH:-1793750400}" # 2026-11-04T00:00:00Z

cd "$ROOT"
echo "== pins from native/ncel/toolchain.lock"
python3 packaging/scripts/gen_pins.py

echo "== fixtures (single source: packages/northcel/northcel)"
cp packages/northcel/northcel/examples/shower_f0001.ncel \
   packages/northcel/northcel/examples/lantern_film.ncel \
   packaging/python/ncel/ncel/data/
cp packages/northcel/northcel/AGENT-GUIDE.md packaging/python/ncel/ncel/data/

echo "== stage the native bundle"
python3 packaging/scripts/stage_bundle.py --out packaging/python/ncel-native/ncel_native_bundle

rm -rf "$OUT"
mkdir -p "$OUT"

echo "== build ncel-native (platform wheel)"
( cd packaging/python/ncel-native && python3 -m build --wheel --outdir "$OUT" >/dev/null )
python3 packaging/scripts/fix_wheel_tag.py "$OUT"/ncel_native-*-py3-none-any.whl --platform "$PLATFORM_TAG"

echo "== build ncel (launcher wheel + sdist)"
( cd packaging/python/ncel && python3 -m build --outdir "$OUT" >/dev/null )

echo "== twine check"
python3 -m twine check "$OUT"/* 2>&1 | tail -5

echo "== artifacts"
( cd "$OUT" && ls -l . && sha256sum ./* )
