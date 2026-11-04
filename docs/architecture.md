# Architecture: grammar → swarms → pixels

NorthCel has two implementations of one language. The **native runtime** is the
product on Linux x86_64; the **Python reference** is the normative oracle and the
labelled fallback everywhere else. This page describes the native pipeline and
where the reference sits.

## The three stages

```text
.ncel source
   │
   ├─ 1. MoonBit  (ncel-ast)      lex, parse, typed AST, palette, def/use,
   │                               frame deltas, ring decode, cel outlines,
   │                               expression evaluation, boil hash
   │                              → NCIR v1 (binary) + a Bend program
   │
   ├─ 2. Bend / HVM2 (bend, hvm)  evaluate every bend_swarm agent
   │                              (one agent per ring) in a binary-fork tree
   │                              → agent rings, validated by the host
   │
   └─ 3. GLSL        (ncel-gl)    headless Mesa/EGL OpenGL 4.5 context,
                                  fragment shader does N×N subpixel even-odd
                                  integration with 8-row bands
                                 → RGBA32F framebuffer; host adds paper grain
                                   and 8-bit rounding → PNG / frames → ffmpeg
```

The native CLI never calls Python and never falls back silently. If a stage is
missing it exits with a hard error; deciding to use the reference is the
launcher's job, and the launcher labels the result.

## What each stage owns

| Stage | Owns | Does not own |
| --- | --- | --- |
| **MoonBit** | grammar, typed AST, `palette`/`$ref`, `def`/`use` expansion, `drop` and in-place replacement, frame deltas, all three ring decoders, `cel` outline expansion, stroke/ribbon → closed polygon, expression evaluation, the 32-bit boil hash, NCIR emission, Bend codegen | rasterisation, pixel values |
| **Bend / HVM2** | evaluating each `bend_swarm` agent as an independent term, in parallel, order-independently | parsing, colours, paint order, transforms after the stage |
| **GLSL** | even-odd winding at `N×N` subpixel centres, coverage, 8-row band acceleration, the framebuffer | grammar, geometry expansion, paper grain, file I/O |
| **C host** | EGL/GL context, shader compile/link, FBO readback, paper grain, 8-bit rounding, PNG (`stb_image_write`), MP4 (`ffmpeg`) | drawing semantics |

A few consequences worth knowing:

- **Boil is MoonBit, not Bend.** HVM2 numbers are U24; the normative boil hash is
  a 32-bit multiply/xor chain that cannot be represented there. Bend remains the
  evaluator for every swarm agent; the boil stays exact so boil-using scenes
  match the reference.
- **Bend carries agent vertices at quarter-pixel precision**, and the host
  applies transforms after the stage. This keeps fractional `translate` exact.
  The host validates every agent/ring/vertex count before drawing.
- **The framebuffer is `RGBA32F`**, so the 8-bit tie-breaking is done once, in the
  host, with the reference formula. A driver cannot round differently per tile.

## Render pipeline order (normative)

1. Parse the document and resolve the root (`scene` or `film`), its header,
   palette and declarations.
2. Expand `def`/`use` (parameters, `dx`/`dy`, in-place replacement), then apply
   the frame's `drop` list and overrides.
3. Decode every ring payload with the document's precision.
4. Build closed polygons for strokes and ribbons, and expand `cel` outlines.
5. Evaluate expressions with `f`, `t` and `seed`.
6. Evaluate swarm agents (Bend/HVM2), validate counts, merge the results into the
   paint list.
7. Apply boil per vertex (stateless hash of seed, frame, item, ring, vertex).
8. Rasterise in paint order: paper, then each layer, at `aa×aa` subpixel
   resolution, even-odd parity.
9. Add paper grain, round to 8-bit RGB, write the PNG (and mux frames for MP4).

Steps 1–7 are deterministic pure functions of the document, frame index and seed.
Step 8 is deterministic for a fixed subpixel grid. Step 9 is deterministic.

## Determinism guarantees

Every frame is a pure function of `(document, frame_index, seed)`. There is no
clock, RNG state, texture, image input or cross-frame state.

Measured in the native report:

| Check | Result |
| --- | --- |
| Same shower frame twice | identical SHA-256 |
| Six-frame lantern film, forward vs shuffled frame order | identical SHA-256 for all frames |
| Mesa `LP_NUM_THREADS=1/2/4/8` | one unique SHA-256 |
| Native vs Python over 296 frames / ~388 M pixels | **52 differing pixels**, worst grey MAE 2.06e-4, worst block SSIM 0.99999931 |

The 52 pixels come from float32 edge upload in GLSL versus float64 crossings in
NumPy. That is the honest meaning of "the two implementations agree": not
byte-identical on every frame, but two orders of magnitude inside the spec's
`0.0115` tolerance. The docs check uses the reference renderer for its committed
hashes so the values do not depend on the host's Mesa version.

## Where the Python reference fits

The reference (`pip install northcel`, `python/northcel/`) is:

- the **normative oracle** for the language and the rasterisation rules;
- the **fallback renderer** on platforms without a native bundle, always labelled
  `"renderer": "python-reference"` — never called native;
- the **conformance source** (`tests/conformance.py`, the shower probes and the
  fitted-film comparison);
- the **checker/formatter** used by the `fmt` command and by the docs check.

The native runtime matches the reference on the 10 conformance probes, is
pixel-identical on the shower frames, and differs by a handful of edge pixels on
the fitted Test Video 7 tiers. Both implementations are in this repository; a
change to rendering semantics must land in both and be measured.

## Platform matrix

| Platform | Native build | Native render | Status |
| --- | :---: | :---: | --- |
| Linux x86_64, glibc ≥ 2.39, Mesa/EGL + llvmpipe | yes | yes | **verified** |
| Linux x86_64 with a GPU GL driver | not tested | not tested | likely works, unclaimed |
| Linux x86_64, older glibc | no | no | the pinned Bend/HVM need `GLIBC_2.39` |
| Linux aarch64 | no | no | reference renderer only |
| macOS | no | no | Apple GL 4.1; needs Vulkan/MoltenVK or a tested GL 4.1 path |
| Windows | no | no | reference renderer only |

The native bundle ships inside the package (≈2.8 MB compressed): the
MoonBit-compiled stage, pinned `bend` + `hvm` binaries, the shaders, and
`bundle-manifest.json` with a checksum for every file. Nothing is downloaded at
first run. The MoonBit compiler is optional and only needed to rebuild the tree.

The `draw410.glsl` shader is the 4.1-compatible variant. It compiles, links and
produces byte-identical output under Mesa 4.50 here, but it has **not** been run
on macOS. That is why macOS is unsupported rather than "probably fine".

## Verify this yourself

Every claim above is reproducible on Linux x86_64 with a Mesa/EGL runtime. These are
the commands with the output from one machine (0.3.1 installed by the release
one-liner, Mesa 25.2.8 llvmpipe, no GPU). `…` marks a trimmed path.

```console
$ northcel doctor
northcel 0.3.1  (NorthCel spec 0.2.0-draft)
platform      linux-x86_64 glibc 2.39
supported     yes
native        0.2.0  (bundle checksums 13 verified, stage MoonBit+Bend+GLSL)
  MoonBit       stage present: yes  binary ncel-ast  compiled with MoonBit 0.1.20261102 (ea07287 2026-11-02)  compiler installed: NO
  Bend          bend-lang 0.2.38  …/northcel_native_bundle/bin/bend
  HVM2          hvm 2.0.22  …/northcel_native_bundle/bin/hvm
  GL runtime    4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2  llvmpipe (LLVM 20.1.2, 256 bits)  GLSL 4.50
  GLSL          draw430 14829a3cbb6c… compiles  draw410 fe4d0c4fe4e0… compiles
  ffmpeg        present (optional, --mp4)
  reference     northcel 0.3.1 — fallback only — non-native reference renderer
```

`northcel doctor --json` carries the same facts as fields:
`stages.moonbit.compiled_with`, `stages.bend.version`, `stages.hvm.version`,
`stages.gl.version` / `.renderer` / `.glsl`, and the sha256 of each shader under
`stages.glsl_shaders`.

Presence is not use. The stages are proved to run by tracing the process tree and by
removing each one:

```console
$ ncel verify
  [PASS] starter-render / shower-f0001-conformance / family-film-6-frames /
         determinism / film-frames-differ      → result: all checks passed

$ strace -f -e trace=execve ncel render examples/patterns/09-crowd-swarm.ncel \
      -o /tmp/swarm.png --frame 1 --json 2>&1 | grep -o 'bin/[a-z-]*' | sort -u
bin/bend
bin/hvm
bin/ncel-ast
bin/ncel-gl
bin/ncel-native
```

A `bend_swarm` document reports what Bend actually evaluated:

```console
$ ncel render examples/patterns/09-crowd-swarm.ncel -o /tmp/swarm.png --frame 1 --json
{"ok":true,…,"geometry":{"layers":4,"rings":38,"vertices":260},
 "swarm":{"tasks":2,"agents":36,"points":252,"stage":"Bend/HVM2"},
 "stage":"MoonBit+Bend+GLSL",
 "timings":{"bend_s":0.0881,"ir_s":0.0046,"gl_s":0.3559,"total_s":0.4486},…}
```

The document declares two swarms of 18 agents, so 36 agents / 36 swarm rings + 2
background rings = 38 rings; a zero agent count would mean the stage was skipped.
`ncel film` on the same file renders six distinct frames and reports the same
`"stage"`, but a **film** receipt lists per-frame SHA-256 values and does not repeat
the swarm block — use `render` (one frame) when you want the agent counts.

The bundle is byte-identical to the tree it was built from, so "MoonBit" and
"`draw430.glsl`" are not labels:

```console
$ sha256sum …/northcel_native_bundle/bin/ncel-ast \
            native/artifacts/ncel-native-0.2.0-linux-x86_64/bin/ncel-ast
f6dc365ea7edf6ef2d17807ae8aea6a4502e0c272e5900ddda6d2f34f4f40614  (both)
$ sha256sum …/northcel_native_bundle/share/ncel/draw430.glsl \
            …/share/ncel/draw410.glsl native/shaders/draw430.glsl native/shaders/draw410.glsl
14829a3cbb6cd868b876ed6afd3567338073c1c64fc0e98e13a7221511ec5b41  (draw430, both)
fe4d0c4fe4e07d05a77ff6a5a5bb0eb5889587aa6f5be841da1acbe6a039ad45  (draw410, both)
```

`ncel-ast` is an ELF executable whose symbol table is MoonBit's
(`moonbitlang/core/builtin`, `__moonbit_internal_argv`, …) and which mentions no
Python module at all; the Python parser is not inside it. Two negative controls on a
copy of the bundle — rename `bin/bend`, then rename `main` in `draw430.glsl` — fail
the render with `ncel-native: missing stage ( bend)` and `ncel-gl: program link
failed: error: fragment shader lacks 'main'`. A stage that could be skipped would not
produce those errors.

**What a receipt does and does not name.** The labelled fallback prints
`"renderer": "python-reference", "native": false`. A native `render`/`film` receipt
carries no `renderer` key; it identifies itself by `"stage": "MoonBit+Bend+GLSL"`
(and, on a single frame, `"swarm": {…, "stage": "Bend/HVM2"}`). `ncel verify --json`
reports `"runtime": "native"`. So: absence of `python-reference` means the native
path ran, and the `stage` field is the explicit marker. On the swarm frame above the
native and reference renders differ in **0 pixels**.

## Why these three stages

The design came from measuring five stacks on the *Man in the Shower*
reconstruction and the 90-frame *Test Video 7* film. The finding was that a
language is an execution paradigm, not extra visual information:

- a typed declarative scene layer makes a compact, surgically editable document
  and gives exact `line:column` diagnostics;
- an independent-agent evaluator fits repetitive organic detail (rain, grass,
  bristles) and is order-independent by construction;
- a subpixel coverage rasteriser gives crisp antialiased contours and even-odd
  apertures without per-shape special cases.

The full decision record, with the rejected alternatives and measured numbers, is
in [DECISIONS.md](DECISIONS.md). The normative grammar is
[SPEC-0.2.0-draft](spec/SPEC-0.2.0-draft.md).

## The docs check

`docs/scripts/check_docs.py` is part of the architecture in a small way: it is the
reason the documentation can be trusted. It extracts every `.ncel` fence from the
guide, runs `check` and renders it with the reference, compares pixels against
`docs/scripts/expected.json`, renders every `examples/patterns/*.ncel` and its
contact sheet, reproduces every diagnostic in [errors.md](errors.md), and verifies
every relative link and image path. CI runs it on every push. A docs change that
does not render cannot merge.
