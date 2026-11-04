#!/usr/bin/env bash
# Build the npm tarballs: `northcel` (launcher + pre-check) and
# `northcel-linux-x64` (the platform bundle it depends on).
#
#   bash packaging/scripts/build_npm.sh [OUTDIR]
#
# Nothing is published. OUTDIR defaults to dist/npm.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/dist/npm}"

cd "$ROOT"
echo "== generated JS assets (rules.json + compact guide)"
python3 js/northcel/scripts/sync-assets.py

echo "== stage the native bundle for northcel-linux-x64"
python3 packaging/scripts/stage_bundle.py --out js/northcel-linux-x64/bundle

echo "== copy fixtures + pins into the npm package"
bash packaging/scripts/stage_npm_data.sh

chmod +x js/northcel/bin/northcel.js

rm -rf "$OUT"
mkdir -p "$OUT"

echo "== npm pack"
( cd js/northcel-linux-x64 && npm pack --pack-destination "$OUT" >/dev/null )
( cd js/northcel && npm pack --pack-destination "$OUT" >/dev/null )

echo "== tarballs"
( cd "$OUT" && ls -l . && sha256sum ./*.tgz )
