#!/usr/bin/env bash
# Re-run the packaging verification on this machine (Linux x86_64 for the native
# runtime; the Python reference works anywhere).
#
#   bash packaging/scripts/verify.sh [--skip-npm] [--skip-pip] [--dir DIR]
#
# Each path gets a fresh directory and its own install; nothing is installed
# system-wide, and the results are printed as PASS/FAIL lines.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WORK="${NCEL_VERIFY_DIR:-/tmp/northcel-verify-run}"
SKIP_NPM=0
SKIP_PIP=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-npm) SKIP_NPM=1 ;;
    --skip-pip) SKIP_PIP=1 ;;
    --dir) shift; WORK="${1:?--dir needs a value}" ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done

PASS=0
FAIL=0
check() { # check NAME COMMAND...
  local name="$1"; shift
  if "$@" >/dev/null 2>&1; then
    printf '  [PASS] %s\n' "$name"; PASS=$((PASS + 1))
  else
    printf '  [FAIL] %s\n' "$name"; FAIL=$((FAIL + 1))
  fi
}

new_venv() { # new_venv DIR
  if python3 -m venv "$1" >/dev/null 2>&1; then return 0; fi
  virtualenv -q -p python3 "$1"
}

rm -rf "$WORK"
mkdir -p "$WORK"
echo "NorthCel packaging verification in $WORK"

if [ "$SKIP_PIP" -eq 0 ]; then
  echo "== pip: built wheels"
  new_venv "$WORK/pip"
  # --find-links serves the just-built northcel + northcel-native; numpy and Pillow
  # still come from the index (they are dependencies, not artifacts of this repo).
  check "pip install built wheels" "$WORK/pip/bin/pip" install -q \
        --find-links "$ROOT/dist/python" northcel
  check "northcel doctor" "$WORK/pip/bin/northcel" doctor
  check "northcel verify" "$WORK/pip/bin/northcel" verify
  check "ncel alias works" "$WORK/pip/bin/ncel" doctor
  "$WORK/pip/bin/northcel" render "$ROOT/python/northcel/examples/shower_f0001.ncel" \
      -o "$WORK/pip/shower.png" --json >/dev/null
  check "shower hash pinned" bash -c \
    "test \"\$(sha256sum '$WORK/pip/shower.png' | cut -d' ' -f1)\" = be0eb036775458d009a2568f5407c973777fe85caa1dac5244f03bb56582d718"
fi

if [ "$SKIP_NPM" -eq 0 ] && compgen -G "$ROOT/dist/npm/northcel-*.tgz" >/dev/null; then
  echo "== npm: prepared tarballs"
  mkdir -p "$WORK/npm"
  ( cd "$WORK/npm" && npm init -y >/dev/null 2>&1 )
  check "npm install tarballs" bash -c \
    "cd '$WORK/npm' && npm install --no-audit --no-fund \
      '$ROOT'/dist/npm/northcel-linux-x64-*.tgz \
      '$ROOT'/dist/npm/northcel-*.tgz"
  check "npx northcel doctor" "$WORK/npm/node_modules/.bin/northcel" doctor
  check "npx northcel verify" "$WORK/npm/node_modules/.bin/northcel" verify
  check "npx ncel alias" "$WORK/npm/node_modules/.bin/ncel" doctor
fi

echo "== curl installer: dry run"
check "install.sh --dry-run" env HOME="$WORK/home" bash "$ROOT/packaging/install.sh" --dry-run

echo
echo "passed $PASS, failed $FAIL"
[ "$FAIL" -eq 0 ]
