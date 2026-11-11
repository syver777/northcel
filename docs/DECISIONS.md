# NorthCel (`northcel` / `.ncel`) — Architectural Decision Log

This document records the key architectural, experimental, and naming decisions behind **NorthCel** (`.ncel`), including the evidence and rejected alternatives.

## Decision 10 · 2026-11-09: Spec 0.5 addressable edits land in the reference first

- **Decision:** Add named groups with pivots, clipping, opacity and optional
  parent transform paths; deterministic handle-based warp; integer-indexed nudge;
  and reuse keys with `use` plus frame deltas. These are general constructs, not
  subject-specific recipes, rigs or presets. Stable fit ids and evaluated shape
  queries make geometry addressable without inferring semantic parts.
- **Compatibility:** Explicit older headers retain their rules. Headerless
  documents mean the current spec. Both launchers route the interpreted newer
  spec and detected 0.4/0.5 constructs to the labelled Python reference; the
  native runtime stays at spec 0.3. JS checks remain explicitly partial.
- **Distribution:** the PyPI, Homebrew and installer paths ship the same tools;
  the native runtime remains spec 0.3 and is never handed a newer document.
- **Rejected:** declaration-order-dependent parent pivots, truncating fractional
  indices, and passing headerless newer documents to the older native runtime.

---

## Decision 9 · 2026-11-09: Spec 0.4 (mix, morph, frame ranges, opacity) lands in the reference first; native routes away

- **Context:** A 15-second film whose 90 frames were separate AI-drawn images
  (6 fps, traced with `fit`) is polished to 20 fps by contour correspondence
  outside NorthCel. The authoring model needs to cover independently drawn keys:
  ordered-ring `tween` requires identical topology; a planar fit leaks paper once
  it moves; static colour bakes `rgb()` literals into every in-between; without an
  interpolation primitive the film becomes hundreds of baked scenes; `frame N` is
  exact-frame only; and cuts are the only fallback. The reference renderer also
  needs to stay responsive at 1080p.
- **Decision:** Spec 0.4.0-draft adds `mix(a, b, u)` colours (sRGB,
  `floor(a + (b−a)u + 0.5)`, u clamped), `morph name(u: …) { "A" => "B" }`
  (ring i ↔ ring i; winding normalised, arclength resampled, start aligned by the
  least-squares cyclic shift; exact endpoints), inclusive `frame A..B` blocks (an
  exact `frame N` wins, then the last range in source order; one block per frame,
  never merged) and `opacity` on primitives and on `use` (group opacity),
  composited per 8-bit subpixel as `floor(c + (s−c)α + 0.5)`. The same tools add
  `fit --stacked`, `tween --match` and the `northcel.correspond` API, with its
  thresholds as documented defaults.
- **Why the reference first, against "two implementations, one truth":** the
  MoonBit/Bend/GLSL runtime cannot be built or verified on the machine where this
  was done, and shipping an unverified native change would break the rule worse
  than a documented gap. Instead the gap is explicit: the native runtime keeps
  implementing spec 0.3; both launchers detect spec 0.4 documents and use the
  labelled Python reference (npm without Python exits 3); the conformance case is
  `reference_only` and reports SKIP, not PASS, against native. A native release
  that implements spec 0.4 must pass case `05` forward and reverse before the
  routing is removed.
- **Why `frame A..B` and not `frames A..B`:** `frames` is the film header
  attribute, and `film X { frames: 2 }` is the documented common mistake with its
  own diagnostic (Decision 6). Extending `frame` keeps one keyword per concept.
- **Why last-range-wins instead of merging:** one block per frame keeps an
  override readable on its own and makes the paint list of a frame a function of
  one block, as for `frame N`. Overlaps are legal (and warned about) so that a
  short insert can sit inside a long hold.
- **Why opacity per subpixel on 8 bits:** it keeps the canvas `uint8` (no 4×
  memory at 1080p×16 subpixels), keeps fully opaque documents byte-identical,
  and gives a formula a GL host can reproduce on RGBA32F. Group opacity blends a
  saved canvas, so a dissolve needs no alpha channel.
- **Why old headers ignore `opacity`:** applying it to a document that declares
  0.3 would change its pixels. It is applied for 0.4 and newer headers and
  headerless documents; older headers get a warning. `mix`, `morph` and ranges
  are validation errors in an old-header document, naming the header to use.
- **Matching is evidence, not judgement:** `tween --match` reports the matched
  area fraction and sqrt-area-weighted displacement and falls back to an explicit
  cut or dissolve below thresholds (0.5 and 32 px by default). Colour changes are
  allowed only along author-listed pairs. The receipt is `quality: "unreviewed"`.
  Big pose changes (crouch, spin, landing) need a drawn key.
- **Renderer speed without semantic change:** the fill was vectorised (all
  crossings of a layer at once, per-row pairing, span painting) and the box filter
  sums rows in `uint16`; the formulas are unchanged and 153 frames from 57
  documents (repository corpus plus fitted 1080p frames) hash identically before
  and after. 1080p fitted frames: 0.75–1.93 s → 0.21–0.52 s on an Apple M1. No
  macOS GPU runtime was attempted.
- **Rejected:** a native port without a machine to verify it; silently letting
  `ncel-native` reject (or partly understand) 0.4 files; optical flow or image
  blending for dissolves (pixels stay vector-derived); a `frames` statement;
  merging overlapping ranges; float canvases for opacity; Hungarian matching via
  SciPy (a 60-line deterministic NumPy implementation avoids a new dependency).

---

## Decision 8 · 2026-11-04: The documentation is part of the product, and CI renders it

- **Context:** The language shipped with a 66-line tutorial, a 35-line reference
  and a 38-line examples page, which cannot teach a language however good the
  renderer is; and a docs page that drifts from the parser is worse than a thin
  one.
- **Decision:** The docs are a numbered writing guide (14 pages) with, on every
  construct page, the syntax, a complete `.ncel`, a rendered image of that file, a
  deliberate mistake with the **real** diagnostic and the exact command; a
  patterns cookbook of ten complete animations with contact sheets and sizes; a
  gallery; an error page generated from the source; and a truthful architecture
  page. `docs/scripts/check_docs.py` extracts and renders every snippet, renders
  every pattern and contact sheet, reproduces every diagnostic, and checks every
  relative link. CI runs it.
- **Why the reference renderer for the committed hashes:** the native GLSL pixels
  depend on the host Mesa version. The reference is the normative oracle and is
  pure NumPy, so its pixels are reproducible on any runner. The committed images
  are therefore reference renders, labelled as such; native agreement is measured
  separately (52 differing pixels over 296 frames) and disclosed on the
  architecture page rather than claimed away.
- **Why the error page is generated:** the only way to keep "every diagnostic"
  true is to run the parser and embed what it printed. A hand-written error list
  is a promise to drift.
- **Rejected:** mocked screenshots or hand-drawn "output" (the docs would become
  marketing); native hashes in CI (a Mesa upgrade would fail unrelated builds);
  rendering every snippet on every page load (the website is separate, and the
  repo should stay light); keeping `tutorial.md` and `reference.md` as parallel
  sources (two copies drift — the tutorial is now a redirect and the reference
  keeps only the CLI/contract).

---

## Decision 7 · 2026-11-04: One install name (`northcel`), its own repository, dual licence

- **Context:** NorthCel is an independent drawing language with one install path.
  A single public repository keeps the package, docs, native tree and packaging
  together; users and agents need one name to install and one answer to "which
  package is the real one".
- **Decision:** NorthCel becomes its own public repository
  (<https://github.com/syver777/northcel>), dual licensed **MIT OR Apache-2.0**, and
  **every install is called `northcel`**: one Python distribution containing the
  reference implementation *and* the launcher (console scripts `northcel` and
  `ncel`), depending on the platform wheel `northcel-native`; one npm package
  `northcel` depending on `northcel-linux-x64`. `ncel` is a short command alias.
  On PyPI, `ncel` is a deprecated alias package that installs `northcel`; npm
  keeps the `northcel` launcher only.
- **Why `ncel` is not a package name:** npm rejected the bare name as too similar
  to existing packages, and a scoped `@ncel/...` or a `...-cli` suffix would make
  users learn a second name for no benefit.
- **Why one distribution:** two distributions that both install an `ncel` script
  fight over it (pip install order decides which one wins, and an upgrade of the
  other silently changes behaviour). One distribution owns both entry points and
  imports the reference in-package.
- **Licence:** MIT OR Apache-2.0 is the conventional choice for a language (Rust,
  Swift): permissive for tooling adoption, patent-granting for implementers.
- **Rejected:** keeping a second canonical copy in another repository (two copies
  drift), publishing a `ncel` npm alias (name rejected), and a `-cli` suffix.

---

## Decision 6 · 2026-11-04: Honest partial JS checks; full means Python

- **Evidence:** On macOS, npm 0.2.0 without Python called `film B { frames: 2 }`
  `OK` (exit 0). The full parser correctly rejected unknown film statement `frames`.
- **Decision:** Keep a small zero-dependency structural pre-check, never label it
  full validation or bare OK. All JS results have `partial: true`, `validator: "js"`,
  `reason` and `next`. A clean pre-check retains exit 0 for incremental editing;
  actual detected errors exit 1. `--require-full` turns clean partial into exit 2.
  `ok` describes that validator's checks only, not whether full validation ran.
- **Full path:** Probe Python and delegate, preserving output/exit status. Never
  fall back after a Python diagnostic, error or signal. Python 0.2.1 JSON marks
  `partial: false`; bridge strips `--require-full` for old Python compatibility.
  Full parse/semantic success still requires real renders/visual inspection.
- **Scope:** Generate allowed statements/version/alphabet from reference sources;
  generate the packaged guide from canonical agent-guide text and test freshness.
  Duplicate names warn because replacing cels/layers is already legal. No grammar
  tightening, normative spec edit or rendering change in tools release 0.2.1.
- **Rejected:** Treating partial success as OK, failing every Node-only check by
  default (unhelpful for editing), or claiming a rushed JS port is fully conformant.

---

## Decision 1 · 2026-11-03: Replace Scanline Strips & Thick Capsules with Connected Subpixel Iso-Contours

- **Context:** In the initial 5-variant *Man in the Shower* experiment (`f0001` & `f0002`), all five variants scored `0.800–0.827` SSIM (below the `0.911` `v7` JS+SVG baseline) because the primitive extractor used horizontal scanline spans (`body_spans`, `hair_cap_spans`), painted the hair dome at tone `33` instead of the measured `48`, and turned skeletonized ink pixels into thick capsules with artificial tangent bow/overshoot.
- **Decision:** Extract closed connected fractional iso-contours at the five measured tonal transitions (`239` paper/water, `189` tile, `132` skin, `48` hair wash, `14` deepest ink) with even-odd winding parity (`fill-rule="evenodd"`), and remove artificial pen overshoot/bow.
- **Alternatives Rejected:**
  - *Keeping scanline intervals with denser vertical spacing:* still fractured diagonal contours and overwrote ear/forehead anatomy.
  - *Integer pixel-center contour tracing (`cv2.findContours` on binary masks):* lost half a pixel at every boundary and plateaued at `0.9013 / 0.9127` SSIM.
- **Evidence:** Switching to fractional iso-contours raised all 5 native Linux variants to **`0.9619–0.9623` SSIM on `f0001`** and **`0.9720–0.9725` SSIM on `f0002`** (and vs. lossless Chromium `v7` `0.9113 / 0.9123`).

---

## Decision 2 · 2026-11-03: Combine MoonBit + Bend + GLSL Strengths into One Language

- **Context:** Benchmarking 5 language combinations (`GLSL`, `GLSL+Forth`, `GLSL+Bend`, `GLSL+Mojo`, `MoonBit+Mojo`) proved that different languages are execution paradigms, not sources of extra visual information — yet each paradigm excels at one distinct layer of AI-drawn animation.
- **Decision:** Design NorthCel around the triad:
  1. **MoonBit-style typed declarative scene AST** (`scene`/`film`, `paper`, `def`/`use`, `layer`, `stroke`, `ribbon`, `bend_swarm`) + compact relative contour decoding + `line:column` diagnostics.
  2. **Bend-style stateless parallel agent swarms** (`bend_swarm` & stateless vertex `boil`) where every droplet, bristle, or frame is a pure function of `(seed, frame_index, agent_id)`.
  3. **GLSL-style `N×N` subpixel winding/SDF rasterization** (`antialias_grid: 4`, 8-row spatial edge binning, box integration).
  4. **Pure-Python + NumPy Reference Implementation:** Make the user-installable package (`pip install northcel`) a zero-compiler pure-Python + NumPy renderer that matches the GLSL backend within `0.0115` MAE (`0.999992+` SSIM), while keeping MoonBit/Bend/GLSL as optional native backends.
- **Alternatives Rejected:**
  - *Requiring users to install MoonBit, Rust/Bend, and EGL/OpenGL toolchains just to run `pip install northcel`:* too heavy and brittle for general CLI/agent users.
  - *Forth stack-machine syntax for AI authoring:* RPN stack manipulation is error-prone for LLMs when editing complex scenes.

---

## Decision 3 · 2026-11-03: Two Explicit Precision Tiers (`1px` Base-63 vs. `0.25px` Quarter-Pixel)

- **Context:** When we compressed traced contours to `1px` Base-63 (`v0`), source size dropped to `29,560 bytes / 19,123 tokens` (**20.4% smaller** than `v7` JS+SVG's `37,120 bytes / 23,617 tokens`) with `0.9366 / 0.9463` SSIM, but lost subpixel diagonal sharpness compared to full `0.25px` GLSL (`0.9619 / 0.9720` SSIM).
- **Decision:** Support **both** `precision: 0.25px` (default quarter-pixel relative deltas, hitting `0.9617 / 0.9718` SSIM at `131,240 bytes` — 32% smaller than raw uncompressed tables, `3.5×` `v7` bytes) and `precision: 1px` (Base-63 compact mode, `29,560 bytes`), while adding native AI-authored primitives (`def`/`use`, `film`, `stroke`, `ribbon`, `boil`, `color`) that take only `~1 KB` (`458 tokens`) for a 6-frame animated shot (`lantern_film.ncel`).
- **Evidence:** Documented in `docs/examples.md` with exact byte and `cl100k` token counts.

---

## Decision 4 · 2026-11-03: Retire "Noir"/`.noir` Name Due to Aztec Noir Collision; Adopt `NorthCel` (`.ncel`)

- **Context:** The initial prototype used the working name `NoirLang` and extension `.noir`. However, `.noir` collides directly with Aztec's zero-knowledge proof language **Noir** (`noir-lang.org`, `.nr`/`.noir`), creating ecosystem, syntax-highlighting, and search confusion.
- **Decision:** Rename the language to **NorthCel**, file extension **`.ncel`**, CLI commands **`northcel`** and **`ncel`**, PyPI package **`northcel`**, npm package **`northcel`**, and public docs URL **`https://northnoir.com/northcel`**. Keep all naming constants in a single module (`python/northcel/config.py`).
- **Evidence:** Both `northcel` on PyPI and `northcel` on npm were verified unoccupied (`HTTP 404`) prior to release.

---

## Decision 5 · 2026-11-03: Add `precision: 0.25px-b63`, `palette`, `cel`/`outline`, and Frame `drop` Deltas in v0.2.0

- **Context:** NorthCel `0.1.0` was tested on a complete 15-second, 90-drawing (`1536×864`) AI-drawn film (monochrome opening → jump → blue sky & clouds → colour arrival → cloud landing → grass landing → sitting with walking duck), both via automated contour fitting (all 90 frames) and hand-written AI authoring (8 representative frames across 3 self-review rounds).
- **Measured Weaknesses of `0.1.0` Exposed by the 90-Frame Video:**
  1. **Source size explosion on 90 subpixel frames:** Space-separated `0.25px` text coordinates plus uncleaned antialias boundary halos took `6,704,285 bytes` (`74.5 KB/frame`, `4.25M tokens`) for the 90 frames.
  2. **Duplicate fill + stroke coordinates in AI-authored cels:** In `0.1.0`, every hand-authored cloud, shirt, trouser leg, shoe, and duck body required a `layer` block for the fill and a second `stroke` block repeating the exact same coordinates for the black ink outline (`8,830 bytes/frame` in Round 3).
  3. **Per-frame color drift & antialias fringe misclassification:** Fitting colors per frame without a shared `palette` and without excluding the 3px greyscale antialias halo around black ink caused dark olive pants to be misclassified as brown hair in early v0.2 tests (`f0066..f0083`) and caused subtle frame-to-frame hue drift.
  4. **Inability to patch/drop inherited layers in `film`:** `frame k` overrides in `0.1.0` only appended layers on top of base layers instead of replacing or dropping named layers in place.
- **Decision (Implemented in `0.2.0`):**
  1. Add `precision: 0.25px-b63` (Quarter-Pixel Base-63 relative encoding with collinear step subdivision) + 3px ink-halo exclusion and chromaticity gating (`chroma > 28`, R-G hair separation).
  2. Add `palette { name: #RRGGBB, ... }` and `$name` references.
  3. Add `cel` / `outline: ($ink, Wpx)` coupled fill + boundary ink stroke primitive.
  4. Add in-place named layer replacement and `drop <layer_name>` inside `film` `frame k` blocks.
- **Measured Before vs. After Evidence:**
  - **90-Frame Fitted Film:** Source size dropped from **`6,704,285 B` (`4,249,852 tok`) to `914,478 B` (`684,528 tok` — `-86.4%` bytes / `7.33×` smaller)**, Global Windowed SSIM improved from **`0.9719` to `0.9756`** (Block SSIM `0.9728`), Exact Canny Edge IoU improved from **`0.4412` to `0.4959`**, and render speed improved from `1.037s/frame` to **`0.957s/frame`**.
  - **8 AI-Authored Frames:** Mean source size dropped from **`8,830 B` (`5,052 tok`) to `4,718 B` (`3,303 tok` — `-46.6%` bytes)** while improving Block SSIM (`0.7852 -> 0.7869`) and Edge IoU (`0.0303 -> 0.0317`).
# 0.4.0 / spec 0.3 — evidence-driven intact drawing edits (2026-11-05)

- A 90-drawing film showed scale/position discontinuities that translation alone
  could not express without requantising all contours. Add immediate named/all
  transforms (anchor, scale/reflection, clockwise rotation, translation) plus pure
  bounded cubic/quintic easing. Preserve old `use(scale: ...)` parameter semantics.
- Keep MoonBit (typed AST/IR/geometry), Bend/HVM2 (independent agents) and GLSL
  (subpixel integration). No new native stage replaces any of them. The Python
  oracle implements the same operations. NCIR v1 is unchanged.
- Integrate Phase B's demonstrated contour-fitting approach as a real optional
  `fit` authoring tool. OpenCV/scikit-image are justified **offline numerical
  tracing dependencies only**, not artistic judges, runtime image inputs, optical
  flow, or semantic character/limb segmentation. Author-provided intact-cel mattes
  are allowed. Count every contour byte; paper texture can cost megabytes/frame.
- Marching squares cuts cell corners and blurs pencil texture. `--cell-edges`
  restores colour-region cell-boundary geometry; it trades compactness for
  fidelity without a per-pixel lookup table or embedded raster.
- `tween` bakes arclength-resampled contour interpolation to normal language
  geometry. Pair rings explicitly by order, align winding/start, never silently
  guess semantic identity. Topology mismatch errors unless the author requests
  a documented hold. A legal tween can still look wrong; keep visual review.
- A measured textured-frame render took 69–85s with all edges in each 8-row band.
  Add exact 32px cell partitioning with right-edge parity seeds. GLSL still owns
  the same crossing/integration formula; golden/oracle comparisons gate release.
- Fix toolchain reproducibility without redistributing the compiler: immutable
  official URLs use **moonc** `0.10.19+bee578715`, not **moon** `0.1.20261102`.
  Their checksums match the archives pinned in `native/toolchain.lock`.
- In the local film study, the author selected intact-cel mattes and existing
  empty texture patches, then used deterministic Poisson boundary blending to
  restore only occluded stage underpaint. This is numerical **offline authoring**,
  not a learned image generator, semantic/quality judge or a fourth native stage.
  The repaired plate is traced into fully counted vector contours before native
  rendering. Hidden limbs are never reconstructed: occlusions use explicit holds
  of neighbouring whole existing drawings. Contour-tween trials are accepted only
  when they do not fold black torso/limb regions; otherwise use a hold.

## 10. NCIR v2 and the Vello tolerance tier (tools 0.7.0)

NCIR v2 is a binary, per-frame paint list emitted by the Python evaluator after
every transform, group, clip, warp and morph has been resolved. It carries ring
topology, group scopes with opacity, resolved clip rings, per-paint opacity,
paper and grain. Accelerated renderers consume it; they never parse `.ncel` or
re-implement evaluation.

The Vello/wgpu renderer (`northcel render|film --renderer vello`) is shipped as
the optional, per-platform `northcel-vello` wheel set (`northcel[vello]`). It is
a **tolerance tier**: Vello's analytic area antialiasing cannot reproduce the
reference's `aa x aa` subpixel box integration byte-for-byte. The Python
reference stays the exact, normative tier; conformance compares the Vello tier
with a mean-absolute-error limit and never claims byte equality. A missing
module is an install error, not a silent fallback to another renderer.

Rationale: the film workflow needs both exact review renders and a fast preview
tier for iteration. Keeping the exact tier as the oracle preserves every
existing pixel guarantee, while the optional wheel keeps heavy GPU dependencies
out of the core install. The native MoonBit/Bend/GLSL runtime is unchanged and
remains Linux x86_64 spec 0.3; spec 0.4+ documents keep routing to the labelled
reference.

`warp(mode: arap)` is the same kind of decision: a deterministic rigid-energy
solve in the reference, not a new primitive. It operates on the paint's ring
graph (the fill follows its rings), with fixed iteration counts and no random
state.
