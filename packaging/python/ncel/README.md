# ncel — NorthCel, drawn frame by frame by a native runtime

`ncel` is the one-command NorthCel (`.ncel`) CLI. It runs the **native runtime**:

* **MoonBit** parses the typed scene/film AST, decodes every contour chain, expands
  `def`/`use`, applies frame deltas and the deterministic boil hash;
* **Bend 0.2.38 / HVM 2.0.22** evaluates every `bend_swarm` agent;
* **GLSL 4.30**, compiled by the **Mesa/EGL** driver (llvmpipe, no GPU), rasterises
  the normative `aa×aa` even-odd integration.

The Python reference implementation (`northcel`) ships alongside as the
conformance oracle and as a **clearly labelled** fallback where the native runtime
cannot run. Nothing is ever silently substituted.

## Install

```
pip install ncel            # Linux x86_64
ncel doctor                 # stages, exact versions, platform verdict
ncel verify                 # real renders + determinism, from bundled fixtures
```

Supported today: **Linux x86_64**, glibc >= 2.39, Mesa `libegl1` + `libgl1` +
`mesa-libgallium` (Ubuntu 24.04+, Debian 13, Fedora 40+, RHEL 10).

Not supported yet, and it says so: macOS (Apple's OpenGL caps at 4.1; the 4.30
shader cannot compile — macOS needs Vulkan/MoltenVK or a tested GL 4.1 path),
Windows, and non-x86_64 Linux. On those platforms `pip install ncel` still
installs the CLI, `ncel doctor` prints the exact reason, and `render`/`film`/`check`
use the Python reference renderer, marked `python-reference` — never "native".

`pip install ncel` brings `ncel-native` (the ~3 MB runtime bundle, no download at
first run) and `northcel` (the reference parser/validator/formatter).

## Use

```
ncel render scene.ncel -o frame.png --frame 0 --json
ncel film   film.ncel -o out/ --frames 0..5 --mp4 out.mp4 --json
ncel check  scene.ncel --json
ncel info   scene.ncel --json
ncel fmt    scene.ncel --check
ncel guide                          # offline authoring guide
ncel doctor --json                  # machine-readable stage report
ncel toolchain status|install       # MoonBit compiler, only needed to rebuild
```

`--json` receipts come from the native runtime and include `language`,
`northcel_version`, `spec_version`, size/fps/frames, source bytes, per-frame
`sha256`, stage timings, geometry, swarm counts and `"stage": "MoonBit+Bend+GLSL"`.

## What `doctor` proves

```
ncel 0.2.1  (NorthCel spec 0.2.0-draft)
platform      linux-x86_64 glibc 2.39
supported     yes
native        0.2.0  (bundle checksums 13 verified, stage MoonBit+Bend+GLSL)
  MoonBit       stage present: yes  binary ncel-ast  compiled with MoonBit 0.1.20261102 (ea07287 2026-11-02)
  Bend          bend-lang 0.2.38  …/bin/bend
  HVM2          hvm 2.0.22  …/bin/hvm
  GL runtime    4.5 (Core Profile) Mesa 25.2.8  llvmpipe (LLVM 20.1.2, 256 bits)  GLSL 4.50
  GLSL          draw430 14829a3cbb6c… compiles  draw410 fe4d0c4fe4e0… compiles
  ffmpeg        present (optional, --mp4)
  reference     northcel 0.2.1 — fallback only — non-native reference renderer
```

## What `verify` proves

* a starter scene renders to a 320×180 PNG;
* the shower `f0001` frame reproduces the pinned conformance hash
  (`be0eb036…`), which the Python reference reproduces pixel-for-pixel;
* a 6-frame film renders 6 distinct frames;
* both renders repeat with identical sha256 (determinism).

## Toolchain notes

A runtime needs no downloads: the MoonBit-compiled stage, Bend and HVM2 are inside
`ncel-native`, with every file sha256-pinned in `bundle-manifest.json` and checked
against `native/ncel/toolchain.lock`. The **MoonBit compiler** (101 MB) is only
needed to rebuild the native tree from source — `ncel toolchain install` fetches
and verifies it into `~/.local/share/ncel/toolchain`.

GLSL is not installed; it is compiled by the GL driver. That is why the installer
provisions the **Mesa/EGL runtime** and why `doctor` compiles and links both
shaders as proof.

## Uninstall

```
pip uninstall ncel ncel-native northcel
rm -rf ~/.local/share/ncel        # only if you ran `ncel toolchain install`
```

## Licence

Proprietary — North Noir. See `LICENSE` in the NorthCel distribution.
