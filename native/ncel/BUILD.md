# Building the NorthCel native runtime (Linux x86_64)

This tree builds a real native renderer: **MoonBit** parses the typed scene/film
AST and decodes contour chains, **Bend/HVM2** evaluates stateless agent swarms,
and **GLSL** (compiled by a headless Mesa/EGL runtime) rasterises every pixel.

Nothing here is Python. The Python reference renderer in `packages/northcel/` is
used only by the conformance tests as an oracle.

## 1. Prerequisites (Ubuntu 24.04 / Debian, x86_64)

System packages (no sudo is needed on the North Noir VM because they are already
present; on a fresh machine install them normally):

```
libegl1 libgl1 mesa-libgallium build-essential
# optional, only for `film --mp4`
ffmpeg
```

* `libEGL.so.1` + Mesa llvmpipe is the **GL runtime**. GLSL is not a package you
  install: it is compiled by the GL driver. This host uses the Mesa surfaceless
  EGL platform (`EGL_PLATFORM_SURFACELESS_MESA`) and an OpenGL 4.5 core context
  backed by `llvmpipe` (CPU). No GPU is required.
* A C compiler (`cc`/`gcc`) is needed to build the MoonBit native binary and the
  two C hosts. It is not needed at render time.

## 2. Provision the pinned toolchain (user space)

```
cd native/ncel
bash scripts/provision-toolchain.sh
```

That downloads and sha256-verifies:

| tool | version | size |
| --- | --- | --- |
| MoonBit CLI | `0.1.20261102 (ea07287 2026-11-02)` | 101.0 MB |
| MoonBit core | `core-latest` (2026-11-04 pin) | 2.8 MB |
| Bend | `bend-lang 0.2.38` (vendored binary) | 3.6 MB |
| HVM2 | `hvm 2.0.22` (vendored binary) | 2.9 MB |

Total download ≈ **104 MB**; the packed artifact is ≈ 8 MB because Bend/HVM are
shipped as binaries. Exact URLs, sha256 and licences are in `toolchain.lock`.

## 3. Build

```
cd native/ncel
make -j4
```

Outputs:

```
build/bin/ncel-native     orchestration CLI
build/bin/ncel-ast        MoonBit typed AST / contour / frame stage
build/bin/ncel-gl         EGL + GLSL rasteriser
build/share/ncel/draw430.glsl
build/share/ncel/draw410.glsl
```

Measured on the North Noir VM (8 vCPU, shared): **≈ 12 s** for a clean build
(MoonBit stage ≈ 9 s, C hosts ≈ 2 s). Rebuilds are incremental.

## 4. Verify

```
build/bin/ncel-native doctor          # exact versions + GL backend + shader hashes
make test                             # conformance + examples + determinism
```

`doctor` must report `"ok": true`, `gl_renderer` containing `llvmpipe`, and both
shaders compiling.

## 5. Use

```
build/bin/ncel-native check  scene.ncel
build/bin/ncel-native render scene.ncel -o frame.png --frame 0 --json
build/bin/ncel-native film   film.ncel -o out/ --frames 0..5 --mp4 out.mp4 --json
```

Frame PNGs are written one per frame (`fNNNN.png`); MP4 muxing is delegated to
system `ffmpeg` and is optional. `--json` receipts carry `language`,
`northcel_version`, spec version, size/fps/frames, source bytes, per-frame
sha256, timings, geometry and the swarm-stage counts.

## 6. Determinism

* Every frame is a pure function of `(document, frame_index, seed)`.
* The rasteriser reads no clock, texture, image or random source. The shader's
  sample grid is fixed at `aa × aa` (default 4×4 = 0.25 px).
* Bend agents are independent terms; HVM2 evaluation order does not affect the
  normal form. Agent results are validated (ring and vertex counts) before use.
* Paper grain is applied in C with the reference formula and `sin()` from libm,
  so 8-bit rounding matches the Python oracle.
* `tests/run-tests.sh determinism` renders frames forward and shuffled and
  compares sha256 sums.

## 7. Known failures / limits

* **macOS:** OpenGL is capped at 4.1, so `draw430.glsl` (GLSL 4.30) will not
  compile. `draw410.glsl` is the 4.10-compatible variant; it compiles and links
  here under Mesa 4.50, but it has **not** been executed on macOS. A verified
  macOS build needs Vulkan/MoltenVK (or a tested GL 4.1 driver) and is out of
  scope for this Linux-first phase. Do not claim macOS support.
* **HVM U24 numbers:** Bend numbers are 24-bit. The swarm stage therefore carries
  coordinates in fixed-point (1/1024 px, or 1/256 px above 2048 px canvas), and
  the normative 32-bit line-boil hash is evaluated in MoonBit (exact, matching
  the Python oracle). Bend remains the evaluator for every `bend_swarm` agent.
* **HVM definition size:** a single Bend definition is limited to 4095 nodes; the
  generator emits one dispatch function with inline agent bodies (the shape the
  shower experiment proved). Very large single frames still work; if a future
  frame exceeds the limit the generator must chunk the dispatch tree.
* **Colour profile:** the FBO is `RGBA32F`; the host applies the reference
  `floor(v + 0.5)` rounding, so no 8-bit GL conversion tie-breaking is involved.
* **GLSL float precision:** edges are uploaded as float32 (from the f64 IR).
  Rasterisation matches the Python float64 oracle exactly on the tested frames;
  differences are possible only for a subpixel centre within ~1e-3 px of an edge.
* **No Python fallback:** `ncel-native` never invokes the Python renderer. The
  pip/npm/brew wrappers decide fallback policy; this binary reports a hard error.

## 8. Layout

```
moonbit/            MoonBit module (typed AST, lexer/parser, ring decoders,
                    frame expansion, NCIR writer, Bend program generator)
src/gl/             NCIR reader, EGL/GLSL host, vendored stb_image_write
src/cli/            ncel-native CLI + SHA-256
shaders/            draw430.glsl (Linux) / draw410.glsl (4.1-portable)
vendor/linux-x86_64 pinned Bend + HVM2 binaries
tests/              conformance, examples, determinism, oracle comparisons
scripts/            provision-toolchain.sh, package.sh
toolchain.lock      machine-readable pins for the packaging worker
```
