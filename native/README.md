# NorthCel native runtime

A genuinely native renderer for NorthCel (`.ncel`) 0.2:

* **MoonBit** — lexer, recursive-descent parser, typed scene/film AST, palette
  and `$ref` resolution, `def`/`use` expansion, `cel` outlines, `drop`, frame
  overrides, all three contour encodings, expression evaluation, and the
  deterministic 32-bit line-boil hash. Emits a compact binary IR (`NCIR v1`).
* **Bend / HVM2** — evaluates every `bend_swarm` agent (one agent per ring) in a
  parallel binary-fork tree. Results are validated before use.
* **GLSL** — the fragment shader performs the normative `N×N` subpixel
  even-odd winding integration with 8-row band acceleration; the host provides a
  headless Mesa/EGL (`llvmpipe`) OpenGL core context and applies the reference
  paper grain and 8-bit rounding.

The native CLI never falls back to the Python reference renderer.

## Grammar → stage map

| NorthCel construct | Handled by |
| --- | --- |
| `scene` / `film`, attributes, `frame k { }` deltas | MoonBit parser + expansion |
| `paper` (`color`, `antialias_grid`, `grain`) | MoonBit IR; grain in the C host with the reference formula; grid in GLSL |
| `palette { }` + `$name` refs | MoonBit (resolved at parse time, matching the reference) |
| `def` / `use` (params, `dx`/`dy`, nested, in-place replacement) | MoonBit expansion |
| `layer` / `wash` / `cel` + `outline: ($ink, Wpx)` | MoonBit ring decode + stroke expansion; fill/outline rasterised by GLSL |
| `stroke` with `taper` | MoonBit polyline → closed ribbon polygon |
| `ribbon` (per-vertex widths) | MoonBit polyline → closed ribbon polygon |
| `bend_swarm` / `swarm` | MoonBit decodes agents → **Bend/HVM2** evaluates rings (fixed-point translation) → MoonBit applies boil + shower merge rules |
| `boil` | MoonBit exact stateless 32-bit hash (see BUILD.md §7 for why not Bend) |
| `drop` and in-place layer replacement | MoonBit expansion |
| `0.25px`, `1px`, `0.25px-b63` ring chains | MoonBit decoders |
| Even-odd fill, `aa×aa` subpixel coverage, 8-row bands | GLSL shader |
| PNG output / MP4 muxing | C host (`stb_image_write`) / system `ffmpeg` |

## Build and run

See `BUILD.md`. Quick start:

```
bash scripts/provision-toolchain.sh
make -j4
build/bin/ncel-native doctor
build/bin/ncel-native render packages/northcel/northcel/examples/shower_f0001.ncel -o f1.png --json
```

## CLI

```
ncel-native doctor [--json]
ncel-native check  FILE [--json]
ncel-native info   FILE [--json]
ncel-native render FILE [-o OUT.png] [--frame N] [--seed N] [--json]
ncel-native film   FILE -o OUTDIR [--frames 0..5|0,2,4] [--mp4 OUT] [--json]
```

`render`/`film --json` receipts include `language`, `northcel_version`,
`spec_version`, size/fps/frames, source bytes, per-frame `sha256`, stage timings,
geometry counts, swarm counts and `"stage": "MoonBit+Bend+GLSL"`.

## Determinism

Every frame is a pure function of `(document, frame_index, seed)`. There is no
clock, RNG state, texture read, image input or wall-clock dependence. The shader
uses a fixed subpixel grid; Bend agents are pure independent terms. Frame bytes
are identical whether rendered alone, forward or in shuffled order, and the same
PINNED toolchain reproduces the same hashes on the same platform.

## Status

Linux x86_64 is the verified reference platform (Mesa llvmpipe + EGL, GLSL 4.30,
software rasterisation). macOS is **not** claimed: Apple's OpenGL caps at 4.1 and
`draw410.glsl` has only been compiled/linked, not executed, on that platform.

Conformance against the Python reference renderer is measured by
`tests/run-tests.sh`; see the phase report for numbers.
