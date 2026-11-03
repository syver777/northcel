# Changelog — NorthCel (`northcel` / `.ncel`)

All notable changes to the **NorthCel** language specification, reference implementation, CLI, and editor tooling are documented in this file.

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
