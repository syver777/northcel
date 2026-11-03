# NorthCel (`northcel` / `.ncel`) — Architectural Decision Log

This document records the key architectural, experimental, and naming decisions behind **NorthCel** (`.ncel`), including the evidence and rejected alternatives.

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
- **Evidence:** Documented in `docs/northcel/examples.md` with exact byte and `cl100k` token counts.

---

## Decision 4 · 2026-11-03: Retire "Noir"/`.noir` Name Due to Aztec Noir Collision; Adopt `NorthCel` (`.ncel`)

- **Context:** The initial prototype used the working name `NoirLang` and extension `.noir`. However, `.noir` collides directly with Aztec's zero-knowledge proof language **Noir** (`noir-lang.org`, `.nr`/`.noir`), creating ecosystem, syntax-highlighting, and search confusion.
- **Decision:** Rename the language to **NorthCel**, file extension **`.ncel`**, CLI commands **`northcel`** and **`ncel`**, PyPI package **`northcel`**, npm package **`northcel`**, and public docs URL **`https://northnoir.com/northcel`**. Keep all naming constants in a single module (`packages/northcel/northcel/config.py`).
- **Evidence:** Both `northcel` on PyPI and `northcel` on npm were verified unoccupied (`HTTP 404`) prior to release.
