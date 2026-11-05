#!/usr/bin/env bash
# Provision the pinned NorthCel native toolchain into .toolchain/ (user space).
#
# Downloads only what the native stage needs and verifies every sha256.
# Nothing is installed system-wide and no sudo is used.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TC="$ROOT/.toolchain"
DL="$TC/downloads"
mkdir -p "$DL" "$TC/moon" "$TC/bin"

MOON_URL="https://cli.moonbitlang.com/binaries/0.10.19%2Bbee578715/moonbit-linux-x86_64.tar.gz"
CORE_URL="https://cli.moonbitlang.com/cores/core-0.10.19%2Bbee578715.tar.gz"
MOON_SHA="dd1d6d793c9675405ef32b39bce66d40041e2052a9c3f2f403e0a9da98bd94fd"
CORE_SHA="b5b33afc759b8ae332346f357f42235d4c8d54afd91bb891b22ead3d746fa74f"

fetch() {
  local url="$1" sha="$2" out="$3"
  if [[ ! -f "$out" ]]; then
    echo "downloading $(basename "$out")"
    curl -fsSL --retry 3 -o "$out.tmp" "$url"
    mv "$out.tmp" "$out"
  fi
  echo "$sha  $out" | sha256sum -c - >/dev/null
}

echo "== NorthCel native toolchain =="
uname -m | grep -qx 'x86_64' || { echo "error: linux x86_64 only for this artifact"; exit 1; }

if [[ ! -x "$TC/moon/bin/moon" ]]; then
  fetch "$MOON_URL" "$MOON_SHA" "$DL/moonbit-linux-x86_64.tar.gz"
  tar -xzf "$DL/moonbit-linux-x86_64.tar.gz" -C "$TC/moon"
  chmod -R u+rwX "$TC/moon"
  find "$TC/moon/bin" -type f -exec chmod u+x {} +
fi

if [[ ! -d "$TC/moon/lib/core" ]]; then
  fetch "$CORE_URL" "$CORE_SHA" "$DL/core-latest.tar.gz"
  tar -xzf "$DL/core-latest.tar.gz" -C "$TC/moon/lib"
fi

# Bundle the pinned core library for the native target (one-time step).
if [[ ! -f "$TC/moon/lib/core/_build/native/release/bundle/core.core" ]]; then
  echo "bundling MoonBit core"
  ( cd "$TC/moon/lib/core" && MOON_HOME="$TC/moon" "$TC/moon/bin/moon" bundle --warn-list -a --all >/dev/null )
fi

# Bend + HVM2 are pinned prebuilt binaries built from the locked crates.
mkdir -p "$TC/bin"
for tool in bend hvm; do
  if [[ -x "$ROOT/vendor/linux-x86_64/bin/$tool" ]]; then
    cp -f "$ROOT/vendor/linux-x86_64/bin/$tool" "$TC/bin/$tool"
    chmod u+x "$TC/bin/$tool"
  else
    echo "error: vendor/linux-x86_64/bin/$tool missing"; exit 1
  fi
done

if ! command -v "${CC:-cc}" >/dev/null 2>&1; then
  echo "warning: no C compiler on PATH; MoonBit native and the C hosts need one." >&2
  echo "         install build-essential (gcc) or set CC to a working compiler." >&2
fi

echo "moon:  $("$TC/moon/bin/moon" version | head -1)"
echo "bend:  $("$TC/bin/bend" --version)"
echo "hvm:   $("$TC/bin/hvm" --version)"
echo "ok: toolchain in $TC"
