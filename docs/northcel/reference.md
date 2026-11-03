# NorthCel (`.ncel`) Format & Tooling Reference

## 1. Root Containers: `scene` and `film`

- **`scene Name(width: 1024, height: 1024, fps: 6, precision: 0.25px, seed: 42) { ... }`**
  Declares a single static frame (`t = 0.0`).
- **`film Name(width: 1024, height: 1024, fps: 12, frames: 24, precision: 0.25px, seed: 42) { ... }`**
  Declares a multi-frame timeline where each frame `f ∈ [0..frames-1]` is a pure function of `t = f / max(1, frames - 1)` and `seed`. May also contain explicit `frame N { ... }` overrides.

## 2. Primitives & Blocks

| Block | Purpose | Key Attributes |
| --- | --- | --- |
| `paper` | Canvas background, supersampling & grain | `tone: 0..255` or `color: #RRGGBB`, `antialias_grid: 1\|2\|4\|8`, `grain: 0.0..0.1` |
| `def` / `use` | Named reusable parameterized group | `def Name(dx: 0, dy: 0) { ... }` / `use Name(dx: expr, dy: expr)` |
| `layer` / `wash` | Even-odd winding contour wash layer | `tone` or `color`, `rings`, `boil: 0.5px`, `translate: (dx, dy)` |
| `bend_swarm` / `swarm` | Parallel agent detail swarm | `agents: N`, `tone` or `color`, `boil`, `translate` |
| `stroke` | Tapered polyline ink stroke | `tone` or `color`, `width: W` or `taper: (w0, w1)`, `boil` |
| `ribbon` | Variable-width `(x, y, w)` ink ribbon | `tone` or `color`, `boil` |

## 3. CLI Reference (`northcel` / `ncel`)

- `northcel check <file.ncel> [--json]` — Parse and validate with `line:column` diagnostics.
- `northcel fmt <file.ncel> [-w] [--check]` — Format into canonical `.ncel` style.
- `northcel info <file.ncel>` — Output JSON metadata (bytes, layers, rings, vertices).
- `northcel render <file.ncel> [-o out.png] [-f FRAME] [--seed SEED] [--json]` — Render one frame to PNG.
- `northcel film <file.ncel> -o <out_dir/> [--frames 0..N] [--mp4 out.mp4]` — Render frame sequence and optional MP4.

## 4. Editor Support, GitHub Linguist & Tree-Sitter Notes

- **VS Code / TextMate:** A complete TextMate grammar (`source.northcel`) and VS Code extension manifest live in `packages/northcel/editors/vscode/`.
- **GitHub Linguist requirements (when ready to submit a PR later):**
  1. Wide public usage across multiple repositories using `.ncel`.
  2. An entry in `languages.yml` mapping `.ncel` to `tm_scope: source.northcel`, `type: programming`, `color: "#8E24AA"`, and pointing to the TextMate grammar repository.
- **Tree-sitter requirements:** A `grammar.js` mirroring the EBNF in `docs/northcel/spec/SPEC-0.1.0-draft.md` (specifically `scene`/`film`, `paper`, `def`/`use`, `layer`/`bend_swarm`/`stroke`/`ribbon`, and `Expr`).
