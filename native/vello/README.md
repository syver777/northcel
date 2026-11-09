# NorthCel Vello prototype — Phase 4

**Experimental, standalone, fixture-based renderer.** This is real Vello 0.11.0
on wgpu 30.0.1, not a reference-renderer wrapper, image replay, or shipped CLI
backend. Rust reads evaluated polygons/colours from JSON, builds a Vello scene,
dispatches compute work, reads RGBA8 pixels back, and writes a 1920×1080 PNG.
Python is used only to export the fixture and produce an independent oracle.

## Build and run

Requirements: a recent Rust/Cargo (tested with 1.99.1), a C linker, and a wgpu
compute-capable adapter. Linux Vulkan can use hardware or Mesa lavapipe; an EGL
library alone is not sufficient. Oracle/evidence scripts need Python 3, NumPy,
and Pillow. The pinned versions are in `Cargo.lock` (always use `--locked`).

From the repository root:

```sh
export PATH="$HOME/.cargo/bin:$PATH"
cd native/vello
cargo build --release --locked
cargo test --release --locked
cargo fmt --check
cargo clippy --release --locked --all-targets -- -D warnings
python3 -m unittest discover -s scripts -p 'test_*.py' -v

target/release/ncel-vello --fixture fixtures/skyline_1080.paintlist.json \
  --out out/frame.png --repeat 2 --json
python3 scripts/verify.py --out out/linux
```

`--repeat N` compares **every raw RGBA buffer**, not just hashes. By default it
also writes `.pass1`, `.pass2`, … PNGs; `--no-pass-files` saves only pass 0 while
still comparing all buffers. `--cpu` selects Vello CPU **coarse stages**, not a
fully CPU renderer: fine rasterisation still uses wgpu. `WGPU_BACKEND=vulkan`
is honoured through wgpu's environment overrides. No adapter is a hard error.
There is no silent Python fallback and no CLI routing change.

### This VPS: userspace software Vulkan

The host had `libvulkan.so.1` but no ICD or `/dev/dri`. Instead of changing
system packages, verification downloaded and extracted Ubuntu's matching Mesa
package into temporary storage:

```sh
mkdir -p /tmp/opencode/phase4-vulkan
cd /tmp/opencode/phase4-vulkan
apt-get download mesa-vulkan-drivers=25.2.8-0ubuntu0.24.04.2
dpkg-deb -x mesa-vulkan-drivers_25.2.8-0ubuntu0.24.04.2_amd64.deb root
export LD_LIBRARY_PATH=/tmp/opencode/phase4-vulkan/root/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}
export VK_ICD_FILENAMES=/tmp/opencode/phase4-vulkan/root/usr/share/vulkan/icd.d/lvp_icd.json
export WGPU_BACKEND=vulkan
export XDG_RUNTIME_DIR=/tmp/opencode/phase4-xdg
mkdir -p "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
cd /home/dev/northcel-vello/native/vello
python3 scripts/verify.py --out out/linux
```

Package SHA-256:
`b3be471db0ec27eb28c1ea75a4d2e6bb3207c5904bdc3823dbba9ce530026939`.
Its existing system LLVM/libdrm dependencies were available. The package and
its binaries are **not vendored**. Other systems should install their own
Vulkan driver or adapt these temporary paths; availability of this Ubuntu
package version is not a portable prerequisite.

## Fixture contract, not full NCIR

The existing NCIR v1 writer (`../moonbit/cmd/ncel_ast/ir.mbt`, `write_ir`) emits
band-repeated, non-horizontal edges and RGB. It does not preserve ring topology,
layer opacity, group-opacity scopes, or resolved clipping, and the current
native pipeline does not implement this fixture's complete spec-0.5 feature
set. Extending those existing files is outside this prototype's scope. Thus the
permitted documented-fixture route is used, **not binary NCIR ingestion**.

`scripts/make_fixture.py` deterministically writes a `.ncel` source and its
`northcel-paintlist-v1` JSON snapshot using the reference's `frame_paint_list`.
The runtime never reads the source PNG or embeds raster data. The JSON carries:

- `format`, `source`, `frame_index`, `width`, `height`, `seed`;
- `paper`: RGB bytes, grain amplitude, reference antialias grid;
- `layers` in back-to-front paint order: name, RGB bytes, opacity, ordered
  `(group_id, opacity)` ancestors, polygon rings, and resolved clip shapes.

Each layer's rings form an even-odd fill; point coordinates are evaluated f64
pixel coordinates. Strokes, ribbons, swarms, transforms, pivot rotation, warp,
and nudge are **already expanded by Python**, not implemented by Rust. The
fixture has 26 paints, 40 rings, 2,427 fill vertices, and 102 clip vertices.
The grain-0 and grain-0.008 variants have identical geometry and paint colours.

```sh
python3 scripts/make_fixture.py --check
python3 scripts/make_fixture.py --name skyline_1080_flat --grain 0 --check
# Omit --check to regenerate these fixtures.
python3 scripts/compare.py --vello out/linux/vello_skyline_1080_flat.png \
  --reference out/linux/reference_skyline_1080_flat.png \
  --heatmap out/linux/diff_manual.png --json-out out/linux/compare_manual.json
```

The verification runner checks regeneration, renders the Python oracle twice,
runs Vello eight times in one process plus twice in a fresh process, compares
raw buffers and PNG bytes, tests `--cpu` on the flat fixture, and exercises a
32×32 group-overlap / same-winding clip-hole regression. Source and output
SHA-256s, exact commands, adapter details, and unrounded timing arrays are in
`out/linux/verification.json`. Copied Mac evidence remains locally in `out/`
but is ignored by Git and is **not** used as Linux evidence.

## Timing definitions

- `init`: adapter, device, and Vello renderer initialisation.
- `scene_build`: conversion of evaluated fixture geometry into a Vello scene.
- `render_passes`: **CPU encoding/submission**, not completed GPU-only timing.
- `readback_passes`: copy, wait for submitted rendering, map, and unpack rows.
- `render_including_readback_passes`: sum of the previous two; a completed
  render+readback wall-time measure. Warm median excludes pass 0; not GPU
  timestamp-query timing.
- `grain_passes`, `png_passes`: separate CPU postprocess and file encoding.
- `total`: render function wall time, including init, texture allocation, buffer
  comparisons, FNV hashing, and PNG I/O; excludes input JSON loading and process
  startup. The runner also reports process wall time.

Python `render_ms` includes frame expansion and rasterisation, but excludes
source parsing and PNG encoding. This small, software-only scene is not a
general performance benchmark; first-pass shader/cache costs are not hidden.

## Verified Linux results (2026-11-09)

Ubuntu 24.04.4 x86_64, 8-vCPU AMD EPYC VPS. Adapter:
`llvmpipe (LLVM 20.1.2, 256 bits)`, Vulkan, `device_type: Cpu`, driver
`Mesa 25.2.8-0ubuntu0.24.04.2 (LLVM 20.1.2)`. This is Vello's compute renderer
on **software Vulkan**, not a hardware-GPU speed measurement.

Build: initial dependency/release build **112.63 s**; final source rebuild
**4.76 s**. Rust tests **9 passed** (2.41 s command wall); Python tests
**3 passed** (0.26 s command wall). Formatting and strict Clippy passed
(Clippy 0.69 s). Six CLI smoke checks passed, including an explicit no-driver
hard failure. Full evidence regeneration took **38.07 s**.

Every full-size comparison below is against a newly generated Python reference
with the same geometry and colours, over **2,073,600 pixels**. MAE is per RGB
channel in 0–255 units; timing is completed render+readback, **excluding grain,
PNG, init and scene build**. Warm medians use passes 1–7 of the first process.

| Fixture / Vello mode | First render+readback (ms) | Warm median (ms) | RGB MAE | Max channel delta | Differing pixels |
| --- | ---: | ---: | ---: | ---: | ---: |
| grain 0.008 / default | 9278.521188 | 67.047407 | 0.02553851594650206 | 21 | 35,277 (1.701244212962963%) |
| grain 0 / default | 560.730021 | 96.641029 | 0.025290477109053498 | 21 | 34,668 (1.671875%) |
| grain 0 / `--cpu` coarse stages | 401.443840 | 206.766808 | 0.025290477109053498 | 21 | 34,668 (1.671875%) |

Warm render+readback ranges were 52.804880–264.782347 ms (grain),
41.531705–266.607607 ms (flat), and 173.039016–349.309948 ms (`--cpu`). The
first-ever render includes expensive shader/driver work; later processes
benefit from caching. Fresh-process second-pass times were 385.799789,
155.556440, and 211.785278 ms respectively, demonstrating substantial VPS
scheduling/cache variability. No fixed throughput or general speedup is claimed.

Python render times (ms, two independent calls): grain
`[4269.125038990751, 2719.1302578430623]`; flat
`[2592.306112870574, 2186.7085420526564]`. Grain adds a separate warm median
60.215243 ms of CPU work; the median of paired completed render+readback+grain
times was 169.100212 ms. PNG encoding is separately recorded.

Flat-reference uniform 3×3 interiors cover 1,992,103 pixels: MAE
**0.0023250136497292894**, maximum delta **1**. Only **19** full-frame pixels
have delta >16. Grain prevents any 3×3 neighbourhood from being exactly
uniform, so the grain variant's zero-size interior statistic is **not evidence
of exact interiors**. Full-frame PSNR is 57.46997321807041 dB (grain) and
57.49294422936403 dB (flat).

**Determinism:** all 8 passes in the first process and both passes in the
second process matched exactly for each of the three cases: **0 differing
RGBA bytes/pixels**, maximum delta **0**. Independent-process PNG bytes also
matched. Default and `--cpu` flat outputs are byte-identical to each other,
but **not** to Python. Python's two raw outputs also matched. This demonstrates
repeatability on this adapter/driver only, not across GPUs or driver versions.

The 32×32 semantic regression matched Python exactly: **0 differing RGB bytes,
max delta 0**; group-overlap RGB `[128, 128, 255]`, clip-hole RGB
`[255, 255, 255]`, and clipped fill RGB `[0, 255, 0]`. All preview and semantic
gates passed. Render and heatmap were also inspected visually; the heatmap is
16× amplified, not an unscaled error image.

## Conformance recommendation

Use Vello as a **tolerance-based preview/fast tier**, subject to future real-GPU
benchmarks. Keep the reference / existing GLSL path as the byte-exact tier for
their implemented and verified feature subsets; route unsupported features to
the labelled reference. Do not use Vello hashes for verification receipts.

The local regression gate is RGB MAE ≤ 0.25 (0–255 units), maximum channel delta
≤ 32, and at most 0.1% of pixels with any channel delta > 16. These are
**fixture-specific candidate bounds**, not an adopted cross-platform standard.
The 32×32 semantics check separately requires maximum delta ≤ 1. A policy needs
a much broader multi-adapter/feature corpus and per-region/edge-aware checks.
The runner records determinism independently: tolerance conformance does not
imply byte determinism. No `DECISIONS.md` or CLI policy was changed.

## Limitations

- Vello analytic area AA differs from the reference's fixed 4×4 sample grid.
- Vello composites in floating point and quantises to RGBA8; the reference
  rounds to bytes after each subpixel paint and group composite. Even interior
  pixels can differ. The group-scope off-by-one in the copied WIP is fixed and
  tested; exact compositing equivalence is not claimed.
- Single clip shapes use even-odd filling, including same-winding holes.
  Multiple clip shapes are only approximated by a combined NonZero path;
  overlaps with opposite winding and holes are not a general union. This is
  explicitly reported; arbitrary clipping conformance is not claimed.
- Grain is applied to an already quantised Vello RGBA8 image; the reference
  adds grain before final quantisation. The lattice/sine formula is shared,
  but its rounding order and cross-platform libm output need not match.
- Canvas dimensions are limited to 8,192 each; no animation loop, text, images,
  gradients, binary NCIR reader, or end-to-end native parser is implemented.
- This work does not establish real-GPU throughput, Windows/DX12 support,
  Linux hardware Vulkan support, or macOS/Metal conformance. Old Mac output is
  not verification of the final Rust changes.
- `--cpu` is not a CPU-exactness solution: AA/compositing remain Vello's, with
  fine rasterisation on the selected wgpu adapter (software Vulkan here).

## Licences

This prototype's Cargo manifest declares `MIT OR Apache-2.0`, matching Vello's
permissive dual licence. Vello 0.11.0, wgpu 30.0.1, pollster 1.0.1, serde, and
serde_json are MIT/Apache-2.0; png 0.18.1 is also MIT/Apache-2.0. Exact transitive
package versions/checksums are pinned in `Cargo.lock`; licence expressions are
recorded in `THIRD-PARTY.md`. Dependencies come from crates.io, not copied
source. No GPL renderer, font, image asset, or model was added. Mesa/LLVM are
external system/runtime components, not redistributed by this commit. Anyone
shipping a binary must retain applicable upstream copyright/licence notices,
including the existing repository's licence; this is not a legal audit.
