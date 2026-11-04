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
