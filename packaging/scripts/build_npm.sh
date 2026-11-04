#!/usr/bin/env bash
# Build the npm tarballs (main `ncel` + platform `@ncel/linux-x64`).
#
#   bash packaging/scripts/build_npm.sh [OUTDIR]
#
# Nothing is published. OUTDIR defaults to work/checks/ncel-packaging/npm.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/work/checks/ncel-packaging/npm}"

cd "$ROOT"
echo "== stage the native bundle for @ncel/linux-x64"
python3 packaging/scripts/stage_bundle.py --out packaging/npm/ncel-linux-x64/bundle

echo "== copy fixtures + guide into the launcher package"
mkdir -p packaging/npm/ncel/data
cp packaging/python/ncel/ncel/data/AGENT-GUIDE.md \
   packaging/python/ncel/ncel/data/pins.json \
   packaging/python/ncel/ncel/data/starter.ncel \
   packaging/python/ncel/ncel/data/lantern_film.ncel \
   packaging/python/ncel/ncel/data/shower_f0001.ncel \
   packaging/npm/ncel/data/
cp packages/northcel/LICENSE packaging/npm/ncel/LICENSE
chmod +x packaging/npm/ncel/bin/ncel.js

rm -rf "$OUT"
mkdir -p "$OUT"

echo "== npm pack"
( cd packaging/npm/ncel-linux-x64 && npm pack --pack-destination "$OUT" >/dev/null )
( cd packaging/npm/ncel && npm pack --pack-destination "$OUT" >/dev/null )

echo "== tarballs"
( cd "$OUT" && ls -l . && sha256sum ./*.tgz )
