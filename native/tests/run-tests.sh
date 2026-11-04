#!/usr/bin/env bash
# NorthCel native runtime test suite.
#
#   tests/run-tests.sh [all|conformance|examples|determinism|oracle|perf]
#
# Uses the built artifacts in build/ (run `make` first). The Python reference
# renderer is used ONLY as a test oracle; the native CLI never calls it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$ROOT/../.." && pwd)"
BIN="$ROOT/build/bin"
CLI="$BIN/ncel-native"
OUT="${NCEL_TEST_OUT:-$ROOT/test-out}"
MODE="${1:-all}"

export PATH="$ROOT/.toolchain/bin:$ROOT/vendor/linux-x86_64/bin:$PATH"
export NCEL_AST="$BIN/ncel-ast"
export NCEL_GL="$BIN/ncel-gl"
export NCEL_SHADER="$ROOT/build/share/ncel/draw430.glsl"
export NCEL_BEND="$ROOT/vendor/linux-x86_64/bin/bend"

mkdir -p "$OUT"

fail() { echo "FAIL: $*" >&2; exit 1; }

require_build() {
  [[ -x "$CLI" ]] || fail "build/bin/ncel-native missing; run make"
  [[ -x "$BIN/ncel-ast" ]] || fail "build/bin/ncel-ast missing; run make"
  [[ -x "$BIN/ncel-gl" ]] || fail "build/bin/ncel-gl missing; run make"
}

doctor() {
  require_build
  echo "== doctor =="
  "$CLI" doctor | tee "$OUT/doctor.json"
  python3 - "$OUT/doctor.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["ok"], "doctor not ok"
assert d["gl"]["ok"], "GL probe failed"
assert "llvmpipe" in d["gl"]["gl_renderer"], d["gl"]
for k in ("draw430", "draw410"):
    assert d["shaders"][k]["compile"]["ok"], d["shaders"][k]
print("doctor: ok", d["gl"]["gl_renderer"], d["bend_version"].strip(), d["hvm_version"].strip())
PY
}

conformance() {
  require_build
  echo "== conformance suite =="
  local dir="$OUT/conformance"
  rm -rf "$dir"; mkdir -p "$dir"
  for f in "$ROOT"/tests/fixtures/conformance/*.ncel; do
    base="$(basename "$f" .ncel)"
    "$CLI" check "$f" >/dev/null
    case "$base" in
      03_film_def_use_boil)
        for fr in 0 1 2; do
          "$CLI" render "$f" --frame "$fr" -o "$dir/${base}_f$(printf '%04d' "$fr").png" --json >/dev/null
        done ;;
      *)
        "$CLI" render "$f" --frame 0 -o "$dir/${base}_f0000.png" --json >/dev/null ;;
    esac
  done
  python3 "$ROOT/tests/probe_check.py" "$ROOT/tests/fixtures/conformance/conformance_manifest.json" "$dir" | tee "$OUT/conformance.log"
}

examples() {
  require_build
  local ex="$REPO/python/northcel/examples"
  [[ -d "$ex" ]] || { echo "examples dir not found, skipping"; return 0; }
  echo "== examples =="
  local dir="$OUT/examples"; rm -rf "$dir"; mkdir -p "$dir"
  for f in "$ex"/*.ncel; do
    base="$(basename "$f" .ncel)"
    echo "-- $base"
    "$CLI" check "$f"
    "$CLI" film "$f" -o "$dir/$base" --frames 0 --json >"$dir/$base.json"
    python3 -c "import json,sys;d=json.load(open(sys.argv[1]));assert d['frames_rendered']==1" "$dir/$base.json"
  done
  echo "examples: all rendered"
}

determinism() {
  require_build
  echo "== determinism (forward vs shuffled) =="
  local film="$REPO/python/northcel/examples/lantern_film.ncel"
  local dir="$OUT/determinism"; rm -rf "$dir"; mkdir -p "$dir/a" "$dir/b"
  "$CLI" film "$film" -o "$dir/a" --frames 0..5 --json >"$dir/a.json"
  # Shuffled order, one frame per invocation.
  for fr in 5 2 0 4 1 3; do
    "$CLI" render "$film" --frame "$fr" -o "$dir/b/f$(printf '%04d' "$fr").png" --json >/dev/null
  done
  python3 - "$dir" <<'PY'
import hashlib, json, sys, pathlib
d = pathlib.Path(sys.argv[1])
def hashes(p):
    out = {}
    for f in sorted(p.glob("*.png")):
        out[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    return out
a, b = hashes(d / "a"), hashes(d / "b")
assert a == b, (a, b)
print("determinism: identical hashes for", len(a), "frames")
PY
  # Shower (Bend stage) rendered twice must also match byte for byte.
  local sh="$REPO/python/northcel/examples/shower_f0001.ncel"
  "$CLI" render "$sh" -o "$dir/sh-1.png" --json >"$dir/sh-1.json"
  "$CLI" render "$sh" -o "$dir/sh-2.png" --json >"$dir/sh-2.json"
  cmp "$dir/sh-1.png" "$dir/sh-2.png" || fail "shower frame not deterministic"
  echo "determinism: shower Bend+GLSL bytes identical"
}

oracle() {
  require_build
  local py="$REPO/python"
  [[ -d "$py/northcel" ]] || { echo "python reference not found, skipping"; return 0; }
  echo "== oracle: Python reference comparison =="
  local dir="$OUT/oracle"; rm -rf "$dir"; mkdir -p "$dir/native" "$dir/reference"
  for f in shower_f0001 shower_f0002 shower_f0001_compact; do
    src="$REPO/python/northcel/examples/$f.ncel"
    "$CLI" render "$src" -o "$dir/native/$f.png" --json >"$dir/$f.json"
    python3 "$ROOT/tests/render_reference.py" "$py" "$src" "$dir/reference/$f.png" 0
  done
  for f in 0001 0030 0043 0055 0067 0076 0085 0015 0028 0037 0062 0090; do
    src="$REPO/work/checks/northcel-b/fitted_v02/ncel/f$f.ncel"
    [[ -f "$src" ]] || continue
    "$CLI" render "$src" -o "$dir/native/tv7_f$f.png" --json >"$dir/tv7_f$f.json"
    python3 "$ROOT/tests/render_reference.py" "$py" "$src" "$dir/reference/tv7_f$f.png" 0
  done
  python3 "$ROOT/tests/compare_oracle.py" --native "$dir/native" --reference "$dir/reference" \
    --out "$dir/metrics.json" --teacher "$REPO/work/checks/northcel-b/teacher/frames" | tee "$dir/metrics.txt"
}

grammar() {
  require_build
  echo "== full 0.2 grammar fixture =="
  local src="$ROOT/tests/fixtures/grammar/grammar_all.ncel"
  local dir="$OUT/grammar"; rm -rf "$dir"; mkdir -p "$dir/native" "$dir/reference"
  for fr in 0 1 2; do
    "$CLI" render "$src" --frame "$fr" -o "$dir/native/f$(printf '%04d' "$fr").png" --json >/dev/null
  done
  local py="$REPO/python"
  if [[ -d "$py/northcel" ]]; then
    for fr in 0 1 2; do
      python3 "$ROOT/tests/render_reference.py" "$py" "$src" "$dir/reference/f$(printf '%04d' "$fr").png" "$fr"
    done
    python3 "$ROOT/tests/compare_oracle.py" --native "$dir/native" --reference "$dir/reference" --out "$dir/metrics.json" | tee "$dir/metrics.txt"
    python3 - "$dir/metrics.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
for r in d["frames"]:
    assert r["gray_mae"] <= 0.0115, r
print("grammar: within spec tolerance on", len(d["frames"]), "frames")
PY
  else
    echo "grammar: rendered 3 frames (python oracle unavailable)"
  fi
}

perf() {
  require_build
  echo "== performance (native vs Python reference) =="
  local py="$REPO/python"
  local src="$REPO/python/northcel/examples/shower_f0001.ncel"
  local tv="$REPO/work/checks/northcel-b/fitted_v02/ncel/f0076.ncel"
  for target in "$src" "$tv"; do
    [[ -f "$target" ]] || continue
    echo "-- $(basename "$target")"
    /usr/bin/time -f "native wall=%e s peak_rss=%M KB" "$CLI" render "$target" -o "$OUT/perf-$(basename "$target").png" --json >/dev/null
    if [[ -d "$py/northcel" ]]; then
      /usr/bin/time -f "python wall=%e s peak_rss=%M KB" python3 "$ROOT/tests/render_reference.py" "$py" "$target" "$OUT/perf-ref.png" 0 >/dev/null
    fi
  done
}

case "$MODE" in
  all) doctor; conformance; examples; grammar; determinism; oracle ;;
  conformance) conformance ;;
  examples) examples ;;
  determinism) determinism ;;
  oracle) oracle ;;
  grammar) grammar ;;
  perf) perf ;;
  doctor) doctor ;;
  *) fail "unknown mode $MODE" ;;
esac
echo "== $MODE: PASS =="
