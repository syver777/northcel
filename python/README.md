# `northcel` — the reference implementation and the one-command CLI

This directory is one Python distribution: the **normative reference implementation**
(parser, semantic validator, formatter, CPU renderer) *and* the **launcher** that
runs the native runtime whenever the platform supports it.

**This distribution is tools 0.7.1 / spec 0.6.0-draft.** `pip install northcel`
installs the same tools from PyPI; Homebrew and install.sh pin them too. The npm
package is a launcher with a structural pre-check, not a renderer.

```
pip install northcel        # installs this package + the northcel-native bundle
northcel doctor             # stages, exact versions, platform verdict
northcel verify             # real renders + determinism, from bundled fixtures
ncel doctor                 # short alias, same program
```

## Two implementations, one command

**Tools 0.7.1, spec 0.6.0-draft:** addressable `group` blocks with pivots,
opacity, clipping and parenting; group-wide `transform`; handle-based `warp`
(including `warp(mode: arap)`) and per-vertex `nudge`; `use` plus delta frames;
`mix` colour expressions, `morph`, `frame A..B` ranges and `opacity`;
`fit --stacked` with stable ids and `shapes` queries, `fit --figure`, and
`tween --match` (Python API: `northcel.correspond`). Newer-spec documents render
with the labelled Python reference; the bundled native runtime 0.4.0 implements
spec 0.3. See the
[polishing pattern](https://github.com/syver777/northcel/blob/main/docs/patterns/12-polishing-ai-frames.md)
and the
[editable-drawing guide](https://github.com/syver777/northcel/blob/main/docs/guide/17-editable-drawings.md).

```
pip install 'northcel[fit]'
northcel fit drawing.png -o drawing.ncel --colors 128 --cell-edges --tolerance 0.05 --min-area 0
northcel tween pose_a.ncel pose_b.ncel -o trial.ncel --fallback hold
```

These are offline numerical authoring tools, not image models. They emit ordinary
vector source with no embedded raster. High-fidelity pencil texture can cost
megabytes per drawing; receipts count all geometry. A legal tween can still fold
or double lines: inspect every inserted drawing and keep a hold when it looks bad.

`northcel` dispatches, in this order:

1. **Native runtime** — MoonBit parses the typed scene/film AST, decodes every
   contour chain, expands `def`/`use`, applies frame deltas and the deterministic
   boil hash; **Bend 0.2.38 / HVM 2.0.22** evaluates every `bend_swarm` agent;
   **GLSL 4.30**, compiled by the **Mesa/EGL** driver (llvmpipe, no GPU),
   rasterises the normative `aa×aa` even-odd integration.
2. **Python reference** — this package's own renderer, used only where the native
    stages cannot run or the document needs a newer spec (including headerless
    documents, spec 0.5 in this checkout). It prints a notice to stderr and labels the result
   `python-reference`. Nothing is ever silently substituted.
3. **`check` only:** the zero-dependency JS pre-check in the npm package, clearly
   labelled `PARTIAL`. It never reports a document as valid.

## Install and use

```
pip install northcel
northcel render scene.ncel -o frame.png --frame 0 --json
northcel film   film.ncel -o out/ --frames 0..5 --mp4 out.mp4 --json
northcel check  scene.ncel --json
northcel info   scene.ncel --json
northcel fmt    scene.ncel --check
northcel guide                      # offline authoring guide
northcel doctor --json              # machine-readable stage report
northcel toolchain status|install   # MoonBit compiler, only needed to rebuild
```

`--json` receipts from the native runtime include `language`, `northcel_version`,
`spec_version`, size/fps/frames, source bytes, per-frame `sha256`, stage timings,
geometry, swarm counts and `"stage": "MoonBit+Bend+GLSL"`.

## Platforms

Supported natively today: **Linux x86_64**, glibc ≥ 2.39, Mesa `libegl1` +
`libgl1` + `mesa-libgallium` (Ubuntu 24.04+, Debian 13, Fedora 40+, RHEL 10).

Everything else installs and is honest: macOS (Apple's OpenGL caps at 4.1; the
4.30 shader cannot compile there — macOS needs Vulkan/MoltenVK or a tested GL 4.1
path), Windows and non-x86_64 Linux get `northcel doctor` exit 3 with the exact
reason, and `render`/`film`/`check` run the Python reference, marked
`python-reference` — never "native".

## What `doctor` prints

```
northcel 0.7.1  (native runtime 0.4.0, spec 0.3.0-draft, native)
platform      linux-x86_64 glibc 2.39
supported     yes
native        0.4.0  (bundle checksums verified, stage MoonBit+Bend+GLSL)
  MoonBit       stage present: yes  binary ncel-ast  compiled with MoonBit 0.1.20261102 (ea07287 2026-11-02)
  Bend          bend-lang 0.2.38  …/bin/bend
  HVM2          hvm 2.0.22  …/bin/hvm
  GL runtime    4.5 (Core Profile) Mesa 25.2.8  llvmpipe (LLVM 20.1.2, 256 bits)  GLSL 4.50
  GLSL          draw430 791c9dc80b4b… compiles  draw410 5367bf91b40c… compiles
  ffmpeg        present (optional, --mp4)
```

## What `verify` proves

- a starter scene renders to a 320×180 PNG;
- the shower `f0001` frame reproduces the pinned conformance hash (`be0eb036…`),
  which the Python reference reproduces pixel-for-pixel;
- a 6-frame film renders 6 distinct frames;
- both renders repeat with identical sha256 (determinism).

## Toolchain notes

A runtime needs no downloads: the MoonBit-compiled stage, Bend and HVM2 ship inside
`northcel-native`, with every file sha256-pinned in `bundle-manifest.json` and
checked against `native/toolchain.lock`. The **MoonBit compiler** (101 MB) is only
needed to rebuild the native tree — `northcel toolchain install` fetches and
verifies it into `~/.local/share/ncel/toolchain` (the directory name is historical).

GLSL is not installed; it is compiled by the GL driver. That is why the installer
provisions the **Mesa/EGL runtime**, and why `doctor` compiles and links both
shaders as proof.

## Python API

```python
from northcel import parse_ncel, validate_document, format_document
from northcel.renderer import render_document_frame, render_film_frames

doc = parse_ncel(open("scene.ncel").read())
print([d.format() for d in validate_document(doc) if d.level == "error"])
rgb = render_document_frame(doc, frame_index=0)      # numpy uint8 (H, W, 3)
```

## Uninstall

```
pip uninstall northcel northcel-native
rm -rf ~/.local/share/ncel        # only if you ran `northcel toolchain install`
```

## Licence

Dual licensed under MIT OR Apache-2.0 — see `LICENSE-MIT` and `LICENSE-APACHE` in
the repository root.
