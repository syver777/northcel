#!/usr/bin/env bash
# Build the optional Vello renderer wheel(s) for the host platform.
#
#   bash packaging/scripts/build_vello.sh [OUTDIR]
#
# OUTDIR defaults to dist/vello. Requires Rust (cargo) and maturin; the CI
# workflow `.github/workflows/vello.yml` builds every supported platform.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/dist/vello}"
PY="${PYTHON:-python3}"

"$PY" -m pip install --quiet --upgrade maturin
mkdir -p "$OUT"
cd "$ROOT/native/vello-python"
PYO3_PYTHON="$("$PY" -c 'import sys; print(sys.executable)')" \
  "$PY" -m maturin build --release --locked -o "$OUT"
ls -l "$OUT"
