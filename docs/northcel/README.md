# NorthCel (`.ncel`) — Documentation Overview

**NorthCel** (`.ncel`) is North Noir's domain-specific programming language for AI-drawn images and frame-by-frame animated videos.

- **Name:** NorthCel
- **File Extension:** `.ncel`
- **CLI Commands:** `northcel` (short alias: `ncel`)
- **Packages:** PyPI `northcel`, npm `northcel`
- **Current Version:** `0.2.1` (Specification unchanged: `0.2.0-draft`, backward compatible with `0.1.0-draft`)
- **Public Documentation URL:** `https://northnoir.com/northcel`

---

## Two packages, different capabilities

- **PyPI `northcel`** (`pipx install northcel`): full reference parser/semantic
  validator, formatter and local CPU renderer; ffmpeg supplies optional MP4 encoding.
- **npm `northcel`** (`npx northcel guide`): offline compact guide, zero-dependency
  **partial JS structural pre-check**, and a bridge to Python if `northcel.cli`
  is importable by `python3` or `python` on PATH, or a pipx-style Python entrypoint
  is on PATH. Node alone cannot render.

`npx northcel check film.ncel --json` without Python always reports
`partial: true, validator: "js"` with `reason`/`next`; text says **PARTIAL**, never
OK. Exit 0 means only no JS pre-check errors; detected errors exit 1. Demand
certainty with **`npx northcel check film.ncel --require-full --json`**: a clean
partial exits **2**, not 0. With Python available, diagnostics/exit code pass
through (0 valid, 1 invalid); Python 0.2.1 JSON has `partial: false`.

JS checks roots/delimiters, statement and header structure, ring payload syntax,
duplicate-name warnings and unknown `$palette` references. It does **not** check
all grammar/semantics: ranges, expression evaluation, undefined defs and visual
quality need Python and real renders. See the exact [validation contract and
coverage table](reference.md#validation-contract). Full validation is not
artistic approval. `npx northcel guide` explains the complete look-and-fix loop.

North Noir CLI 1.4.0 also offers the optional local `northnoir[ncel]` path;
`scene.html` remains its default. This release does not add hosted NorthCel
Studio, API or MCP support. npm 0.2.1 publication is handled separately by the
owner; until then use the verified release tarball, not an older npm version.

## Documentation Index

1. **[Language Specification (`0.2.0-draft`)](spec/SPEC-0.2.0-draft.md)** (and archival [`0.1.0-draft`](spec/SPEC-0.1.0-draft.md)) — Normative EBNF grammar, coordinate/ring-chain encodings (`0.25px`, `0.25px-b63`, and `1px` Base-63), `palette`, coupled `cel` outlines, frame `drop` deltas, rendering semantics, error diagnostics, and conformance rules.
2. **[Tutorial: Your First `.ncel` Film](tutorial.md)** — Step-by-step guide to installing `northcel`, writing a scene with washes, strokes, ribbons, and parallel swarms, and rendering an animated film.
3. **[Format & Tooling Reference](reference.md)** — Complete attribute reference for `scene`, `film`, `paper`, `def`/`use`, `layer`/`wash`, `bend_swarm`, `stroke`, and `ribbon`, plus CLI flags and editor grammar notes.
4. **[AI-Agent Guide (`agent-guide.md`)](agent-guide.md)** — How coding agents (Claude Code, OpenCode, Codex, Cursor, Gemini CLI) should author `.ncel`, run self-review gates (`check`, `render`, diff), and perform surgical `Adjust` edits.
5. **[Examples & Measured Benchmarks](examples.md)** — Full byte, `cl100k` token, SSIM, MAE, and Edge IoU tables across authored films (`lantern_film.ncel`) and traced teacher reconstructions (`shower_f0001.ncel`, `shower_f0002.ncel`, `shower_f0001_compact.ncel`).
6. **[Decision Log (`DECISIONS.md`)](DECISIONS.md)** — Dated architectural record covering the 5-language shower experiment, the MoonBit + Bend + GLSL triad, the v0→v1 precision tradeoff, the Aztec Noir naming collision, and the rename to NorthCel (`.ncel`).
7. **[Changelog (`CHANGELOG.md`)](CHANGELOG.md)** — Versioned release and specification history.
8. **[Training Plan (`training-plan.md`)](training-plan.md)** — Concrete data pipeline and evaluation plan for training an AI model to emit `.ncel` frame-by-frame from video/Ruvil teachers.
9. **[Integration Plan (`integration-plan.md`)](integration-plan.md)** — How NorthCel plugs into the North Noir CLI and MCP server alongside Ruvil 2.1 (`.js`-drawn) and Ruvil 7.3 (images as frames).
10. **[Official Readiness Checklist (`official-checklist.md`)](official-checklist.md)** — Status of every requirement for an official programming language release.
11. **[FAQ](faq.md)** | **[Contributing](CONTRIBUTING.md)** | **[Security Policy](SECURITY.md)** | **[License](LICENSE)**
