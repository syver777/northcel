#!/usr/bin/env bash
# Copy the fixtures and pins the npm package ships into js/northcel/data/.
#
# There is exactly one copy of each fixture in the repository (python/northcel);
# this script stages them for packing and is what CI uses before `npm pack`.
#
#   bash packaging/scripts/stage_npm_data.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

mkdir -p js/northcel/data
cp python/northcel/data/pins.json \
   python/northcel/examples/starter.ncel \
   python/northcel/examples/lantern_film.ncel \
   python/northcel/examples/shower_f0001.ncel \
   js/northcel/data/
ls -l js/northcel/data
