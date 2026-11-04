#!/usr/bin/env bash
# Publish (or dry-run) NorthCel 0.3.1 — PREPARED, NOT RUN.
#
#   bash packaging/scripts/publish_0_3_1.sh --dry-run     # print what would happen
#   bash packaging/scripts/publish_0_3_1.sh               # actually publish
#
# Read packaging/RELEASE.md first. Two things must be true before the real run:
#
#   1. `northcel-native`/`northcel` are *new* on PyPI and free, and
#   2. nobody else has published npm `northcel@0.3.1` / `northcel-linux-x64@0.3.1`.
#
# Credentials are read from the environment (never from this file, never echoed):
#
#   PyPI   TWINE_USERNAME=__token__  TWINE_PASSWORD=<token>      (or ~/.pypirc)
#   npm    NPM_TOKEN=<token>, or `npm login` beforehand
#
# Publish order matters: a platform artifact must exist before the main package
# whose dependency points at it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION="0.3.1"
DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

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

step "build every artifact for $VERSION"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] bash packaging/scripts/build_python.sh dist/python"
  echo "  [dry-run] bash packaging/scripts/build_npm.sh    dist/npm"
else
  bash packaging/scripts/build_python.sh dist/python
  bash packaging/scripts/build_npm.sh dist/npm
fi

step "prove the artifacts before publishing anything"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] bash packaging/scripts/verify.sh"
else
  bash packaging/scripts/verify.sh
fi

step "build the deprecated aliases (published last)"
for pkg in pypi-ncel pypi-ncel-native; do
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "  [dry-run] python3 -m build --outdir dist/deprecated packaging/deprecated/$pkg"
  else
    python3 -m build --outdir dist/deprecated "packaging/deprecated/$pkg" >/dev/null
  fi
done

step "PyPI: northcel-native (platform wheel) first"
do_it python3 -m twine upload --non-interactive \
  "dist/python/northcel_native-${VERSION}-py3-none-manylinux_2_39_x86_64.whl"

step "PyPI: northcel (wheel + sdist)"
do_it python3 -m twine upload --non-interactive \
  "dist/python/northcel-${VERSION}-py3-none-any.whl" "dist/python/northcel-${VERSION}.tar.gz"

step "npm: northcel-linux-x64 first, then northcel"
do_it npm publish "dist/npm/northcel-linux-x64-${VERSION}.tgz" --access public
do_it npm publish "dist/npm/northcel-${VERSION}.tgz" --access public

step "PyPI: deprecated aliases, then mark them deprecated"
do_it python3 -m twine upload --non-interactive dist/deprecated/*
echo "  note: PyPI has no per-release deprecation flag; the alias descriptions and"
echo "        READMEs say DEPRECATED, and 0.3.1 is the last version they carry."

step "npm: deprecated alias + deprecation notice"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] npm publish packaging/deprecated/npm-ncel-linux-x64 --access public"
  echo "  [dry-run] npm deprecate @ncel/linux-x64@${VERSION} \"NorthCel is one package now: npm install -g northcel\""
else
  ( cd packaging/deprecated/npm-ncel-linux-x64 && npm publish --access public )
  npm deprecate "@ncel/linux-x64@${VERSION}" \
    "NorthCel is one package now: npm install -g northcel"
fi

step "verify the published source installs"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "  [dry-run] pip install --index-url https://pypi.org/simple northcel==${VERSION}"
  echo "  [dry-run] npm install -g northcel@${VERSION}"
else
  python3 -m venv /tmp/northcel-published
  /tmp/northcel-published/bin/pip install --index-url https://pypi.org/simple "northcel==${VERSION}"
  /tmp/northcel-published/bin/northcel doctor
  /tmp/northcel-published/bin/northcel verify
  npm install -g "northcel@${VERSION}"
  northcel doctor
fi

step "tag the release"
do_it git tag -a "v${VERSION}" -m "NorthCel ${VERSION}" 
do_it git push origin "v${VERSION}"
