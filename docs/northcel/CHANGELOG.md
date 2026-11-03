# Changelog — NorthCel (`northcel` / `.ncel`)

All notable changes to the **NorthCel** language specification, reference implementation, CLI, and editor tooling are documented in this file.

---

## [0.1.0] — Specification `0.1.0-draft` (2026-11-03)

### Added
- **Language Specification (`docs/northcel/spec/SPEC-0.1.0-draft.md`):**
  - Normative EBNF grammar for `northcel "0.1.0-draft"`, `scene`, and `film` containers.
  - Quarter-pixel (`0.25px`) relative delta ring-chain encoding and compact 1-pixel (`1px`) Base-63 ring-chain encoding.
  - Normative `N×N` subpixel (`antialias_grid: 4`) even-odd winding rasterization semantics, paint order, and deterministic stateless vertex line boil.
- **v0.1 Language Additions for AI-Drawn Video:**
  - `film` timeline container with pure frame evaluation over `t ∈ [0..1]`, `f`, and `seed`, plus per-frame `frame N { ... }` overrides.
  - Reusable parameterized shape definitions (`def Name(dx: 0, dy: 0) { ... }` and `use Name(...)`).
  - Full RGB color (`color: #RRGGBB`, `color: #RGB`, `color: rgb(r,g,b)`) alongside greyscale `tone: 0..255`.
  - Tapered `stroke` (`width` or `taper: (w0, w1)`) and variable-width `ribbon` (`(x, y, width)`) primitives.
  - Deterministic stateless line `boil` (`boil: 0.5px` or `boil: (amp, freq)`).
- **Reference Implementation (`packages/northcel/`, PyPI `northcel` 0.1.0):**
  - Pure-Python + NumPy 4×4 subpixel renderer reproducing the OpenGL 4.3 (`llvmpipe`) GLSL shower renders within `0.0115` greyscale MAE (`0.999992+` SSIM).
  - Lexer and recursive-descent parser with exact 1-based `line:column` error diagnostics.
  - Semantic validator (`validate_document`) and idempotent canonical formatter (`format_document`).
  - CLI (`northcel` and alias `ncel`) with subcommands `check`, `fmt`, `info`, `render`, and `film`.
  - Conformance suite (`northcel/conformance/`) and 13 automated unit, round-trip, determinism, error, and golden tests.
- **JavaScript Validator & Editor Support:**
  - Zero-dependency JS validator/decoder (`packages/northcel/js/index.cjs`) and CLI bridge (`bin/northcel.js`).
  - VS Code extension and TextMate grammar (`source.northcel`) in `packages/northcel/editors/vscode/`.
- **Renamed from Prototype `NoirLang`/`.noir`:**
  - Replaced all `NoirLang`/`.noir`/`/noir-lang` references with `NorthCel`/`.ncel`/`/northcel` to avoid collision with Aztec's Noir language.
