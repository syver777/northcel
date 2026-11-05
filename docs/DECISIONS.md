# NorthCel (`northcel` / `.ncel`) — Architectural Decision Log

This document records the key architectural, experimental, and naming decisions behind **NorthCel** (`.ncel`), including the evidence and rejected alternatives.

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

- **Context:** NorthCel was previously developed inside another repository as
  `packages/northcel`, `docs/northcel`, `native/ncel` and `packaging/`, with two
  PyPI names (`ncel`, `northcel`), three npm names (one published, one never
  published, one scope that needs an org) and a proprietary licence. Users and
  agents had to learn which of several names to install, and "which package is
  the real one" was impossible to answer.
- **Decision:** NorthCel becomes its own public repository
  (<https://github.com/syver777/northcel>), dual licensed **MIT OR Apache-2.0**, and
  **every install is called `northcel`**: one Python distribution containing the
  reference implementation *and* the launcher (console scripts `northcel` and
  `ncel`), depending on the platform wheel `northcel-native`; one npm package
  `northcel` depending on `northcel-linux-x64`. `ncel` survives only as a short
  command alias. The old `ncel`, `ncel-native` (PyPI) and `@ncel/linux-x64` (npm)
  remain as deprecated alias packages that depend on the real ones. `@ncel/cli`
  was never published and is dropped.
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
