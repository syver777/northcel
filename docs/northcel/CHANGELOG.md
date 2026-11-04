# Changelog — NorthCel (`northcel` / `.ncel`)

All notable changes to the **NorthCel** language specification, reference implementation, CLI, and editor tooling are documented in this file.

---

## [0.2.1] — Tools only; specification remains `0.2.0-draft` (2026-11-04)

### Fixed
- Owner-reported macOS defect: npm 0.2.0 without Python printed `OK` and exited 0
  for `film B { frames: 2 }`, although the Python parser rejects it. JS output
  now always says **PARTIAL** and JSON marks `partial: true`, `validator: "js"`,
  `reason` and `next`. Exit 0 means no pre-check errors, not full validity.
- Token-based structural pre-check catches unknown statements, malformed headers,
  unbalanced delimiters/quotes, multiline ring errors and unknown palette references.
  Duplicate names warn (replacement remains legal); no language semantics changed.
- A Python subprocess that fails to launch or is terminated can no longer be
  converted into exit 0. Python diagnostics and normal exit codes pass through.
- Detect pipx-style Python CLI entrypoints on PATH as well as importable modules;
  skip npm's own aliases to avoid recursive delegation.

### Added
- `check --require-full`: clean JS-only checks exit 2; detected errors exit 1;
  successful full Python checks exit 0. Python 0.2.1 accepts the flag and marks
  JSON `partial: false, validator: "python"`. Older Python CLI remains supported.
- Offline `npx northcel guide` (also Python `northcel guide`), generated from the
  compact section of the canonical agent guide. Generated JS rule metadata shares
  version, statement sets and ring alphabet with the reference implementation.
- Node regression/delegation tests, every repository `.ncel` example plus broken
  variants, guide sync and full-parser snippet tests. Documented coverage/limits
  and real Node-only authoring trial; npm tarball prepared for owner publication.
- The Node-only trial found an old README/tutorial `def`/`use` example applying
  `dx`/`dy` twice. Corrected authoring snippets without changing historical
  fixtures or reference rendering semantics.

---

## [0.2.0] — Specification `0.2.0-draft` (2026-11-03)

### Added (Evidence-Driven from the 90-Frame *Test Video 7* Ruvil 7.3 Benchmark)
- **Quarter-Pixel Base-63 Ring-Chain Encoding (`precision: 0.25px-b63`):**
  - Encodes `0.25px` quarter-pixel steps in 2 Base-63 ASCII characters per vertex with collinear-preserving step subdivision.
  - Combined with chromatic halo filtering on the 90-frame *Test Video 7* benchmark (`1536×864`), reduced total 90-frame `.ncel` film size from **`6,704,285 bytes` (`4,249,852 tokens`) to `914,478 bytes` (`684,528 tokens` — `-86.4%` bytes / `7.33×` smaller)** while improving Global Windowed SSIM from `0.9719` to **`0.9756`** and Exact Canny Edge IoU from `0.4412` to **`0.4959`**.
- **Named Film/Scene Palettes (`palette { sky: #70CCF5, ... }` & `$name` references):**
  - Locks character and environment colors across an entire multi-frame film, eliminating per-frame color drift.
- **Coupled Fill + Ink Outline Primitive (`cel` and `outline: ($ink, Wpx)`):**
  - Eliminates duplicate coordinate tables when AI agents author 2D animation cels (where every colored shape has a black ink outline).
  - On the 8 AI-authored representative frames of *Test Video 7*, `cel` + `0.25px-b63` cut mean AI-authored source size from **`8,830 bytes` (`5,052 tokens`) to `4,718 bytes` (`3,303 tokens` — `-46.6%` bytes)** while preventing fill/stroke desynchronization.
- **Film Frame Deltas (`drop <layer>` & In-Place Named Layer Replacement):**
  - Inside `film` `frame k { ... }` blocks, redefining a named `layer`/`cel` replaces it in place at its original paint-order slot, and `drop <name>` removes an inherited layer (and its coupled outline).
- **Backward Compatibility:**
  - All `0.1.0-draft` files and the `0.1.0-draft` conformance suite remain 100% valid and byte-identical in `0.2.0`.

---

## [0.1.0] — Specification `0.1.0-draft` (2026-11-03)

### Added
- Initial Language Specification (`docs/northcel/spec/SPEC-0.1.0-draft.md`), pure-Python + NumPy 4×4 subpixel reference renderer, CLI (`northcel` / `ncel`), conformance suite, VS Code TextMate grammar, and `0.1.0` PyPI release.
