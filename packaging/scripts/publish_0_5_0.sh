#!/usr/bin/env bash
# Publish (or dry-run) NorthCel 0.5.0 — tools only. PREPARED, NOT RUN by itself.
#
#   bash packaging/scripts/publish_0_5_0.sh --dry-run
#   bash packaging/scripts/publish_0_5_0.sh
#
# 0.5.0 moves only the tools. `northcel-native` and `northcel-linux-x64` stay at
# 0.4.0 and must already exist on the registries. Never republish them.
#
# Credentials are read from the environment (never from this file, never echoed):
#   PyPI  TWINE_USERNAME=__token__ TWINE_PASSWORD=<token>  (or ~/.pypirc)
#   npm   NPM_TOKEN=<token>, or `npm login` beforehand
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="0.5.0"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

if [ -z "${TWINE_PASSWORD:-}" ] && [ -n "${NORTH_NOIR_PYPI_API:-}" ]; then
  TWINE_USERNAME="__token__"
  TWINE_PASSWORD="$NORTH_NOIR_PYPI_API"
  export TWINE_USERNAME TWINE_PASSWORD
fi

cd "$ROOT"
if [ "$DRY_RUN" -eq 0 ] && [ -n "$(git status --porcelain)" ]; then
  echo "refusing to publish from a dirty tree" >&2
  exit 1
fi

step() { printf '\n== %s\n' "$*"; }
do_it() {
  if [ "$DRY_RUN" -eq 1 ]; then
    printf '  [dry-run] %s\n' "$*"
  else
    printf '  $ %s\n' "$*"
    "$@"
  fi
}

step "verify the 0.4.0 native artifacts already exist"
if [ "$DRY_RUN" -eq 0 ]; then
  python3 - <<'PY'
import json, urllib.request
pypi = json.load(urllib.request.urlopen("https://pypi.org/pypi/northcel-native/json", timeout=30))
assert "0.4.0" in pypi["releases"], "northcel-native 0.4.0 is missing on PyPI"
npm = json.load(urllib.request.urlopen("https://registry.npmjs.org/northcel-linux-x64/latest", timeout=30))
assert npm["version"] == "0.4.0", f"northcel-linux-x64 is {npm['version']}, expected 0.4.0"
print("native artifacts 0.4.0 verified")
PY
fi

step "build the tools-only artifacts for $VERSION"
rm -rf "dist/python-$VERSION" "dist/npm-$VERSION" "dist/deprecated-$VERSION"
mkdir -p "dist/python-$VERSION" "dist/npm-$VERSION" "dist/deprecated-$VERSION"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] (cd python && python3 -m build --outdir ../dist/python-$VERSION)"
  echo "  [dry-run] (cd js/northcel && npm pack --pack-destination ../../dist/npm-$VERSION)"
  echo "  [dry-run] python3 -m build --outdir dist/deprecated-$VERSION packaging/deprecated/pypi-ncel"
else
  ( cd python && python3 -m build --outdir "../dist/python-$VERSION" >/dev/null )
  ( cd js/northcel && npm pack --pack-destination "../../dist/npm-$VERSION" >/dev/null )
  python3 -m build --outdir "dist/deprecated-$VERSION" packaging/deprecated/pypi-ncel >/dev/null
fi

step "twine check"
do_it python3 -m twine check dist/python-$VERSION/* dist/deprecated-$VERSION/*

step "prove the wheel in a fresh venv before publishing"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] python3 -m venv /tmp/northcel-$VERSION && pip install wheel"
  echo "  [dry-run] northcel check/film examples/patterns/12-polishing-ai-frames.ncel"
else
  rm -rf "/tmp/northcel-$VERSION"
  python3 -m venv "/tmp/northcel-$VERSION"
  "/tmp/northcel-$VERSION/bin/pip" install -q --no-cache-dir \
    "dist/python-$VERSION/northcel-$VERSION-py3-none-any.whl"
  "/tmp/northcel-$VERSION/bin/northcel" --version
  "/tmp/northcel-$VERSION/bin/northcel" check examples/patterns/12-polishing-ai-frames.ncel --json \
    >/tmp/northcel-$VERSION-check.json
  "/tmp/northcel-$VERSION/bin/northcel" film examples/patterns/12-polishing-ai-frames.ncel \
    -o "/tmp/northcel-$VERSION-frames" --frames 0..6 --json \
    >/tmp/northcel-$VERSION-film.json
  python3 - <<'PY'
import json
check = json.load(open('/tmp/northcel-0.5.0-check.json'))
film = json.load(open('/tmp/northcel-0.5.0-film.json'))
assert check['ok'] and film['ok'] and film['frames_rendered'] == 7, (check, film)
print('fresh-venv check/film ok')
PY
fi

step "PyPI: northcel wheel + sdist (native 0.4.0 already published)"
do_it python3 -m twine upload --non-interactive \
  "dist/python-$VERSION/northcel-$VERSION-py3-none-any.whl" "dist/python-$VERSION/northcel-$VERSION.tar.gz"

step "npm: the launcher only (northcel-linux-x64 stays 0.4.0)"
do_it npm publish "dist/npm-$VERSION/northcel-$VERSION.tgz" --access public

step "PyPI: deprecated ncel alias (depends on northcel==$VERSION)"
do_it python3 -m twine upload --non-interactive "dist/deprecated-$VERSION"/*

step "tag the release"
do_it git tag -a "v$VERSION" -m "NorthCel $VERSION"
do_it git push origin "v$VERSION"
