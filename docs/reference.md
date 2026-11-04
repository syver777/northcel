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
| `palette` | Shared named colours, declared before references | `palette { ink: #202830 }`, then `$ink` |
| `def` / `use` | Named reusable parameterized group | `def Name(dx: 0, dy: 0) { ... }` / `use Name(dx: expr, dy: expr)` |
| `layer` / `wash` | Even-odd winding contour wash layer | `tone` or `color`, `rings`, `boil: 0.5px`, `translate: (dx, dy)` |
| `cel` | Coupled fill and ink boundary | `color: $fill, outline: ($ink, 2px)` plus layer attributes |
| `drop` | Remove an inherited layer for exactly one override frame | `frame 12 { drop cloud }` |
| `bend_swarm` / `swarm` | Parallel agent detail swarm | `agents: N`, `tone` or `color`, `boil`, `translate` |
| `stroke` | Tapered polyline ink stroke | `tone` or `color`, `width: W` or `taper: (w0, w1)`, `boil` |
| `ribbon` | Variable-width `(x, y, w)` ink ribbon | `tone` or `color`, `boil` |

## 3. CLI Reference (`northcel` / `ncel`)

- `northcel guide` / `npx northcel guide` — Print the compact embedded agent guide offline.
- `northcel check <file.ncel> [--json] [--require-full]` — Python full parser/semantic validation; npm delegates when available, otherwise **partial JS pre-check only**.
- `northcel fmt <file.ncel> [-w] [--check]` — Format into canonical `.ncel` style.
- `northcel info <file.ncel>` — Output JSON metadata (bytes, layers, rings, vertices).
- `northcel render <file.ncel> [-o out.png] [-f FRAME] [--seed SEED] [--json]` — Render one frame to PNG.
- `northcel film <file.ncel> -o <out_dir/> [--frames 0..N] [--mp4 out.mp4]` — Render frame sequence and optional MP4.

### Validation contract

**Tools 0.2.1, unchanged spec 0.2.0-draft.** PyPI `northcel` is the reference
parser, semantic validator, formatter and CPU renderer. npm `northcel` is a
zero-dependency structural JS pre-check, embedded guide and Python CLI bridge;
it has no JS formatter or renderer. Both install `northcel` and `ncel`.

The npm wrapper probes `python3`, then `python`, on PATH for `northcel.cli`, then
looks for a Python-shebang `northcel`/`ncel` entrypoint on PATH (including pipx
installs). It skips its own npm entrypoints to prevent recursion.
Once a probe succeeds it delegates, preserving stdout, stderr and the exit code;
it never retries a failing Python check in JS. A terminated/unlaunchable Python
process is nonzero. `--require-full` is consumed by the bridge for compatibility
with older full Python CLIs. `guide` is always the npm-bundled guide. `--version`
still reports Python's version when delegated, otherwise the npm version with
`js-validator`. npm 0.2.1 does not require Python for guide/check/version/help.

| Path/result | Text / JSON | Exit |
|---|---|---:|
| Python valid | `OK (NorthCel <spec>)`; `ok: true, partial: false, validator: "python"` in Python 0.2.1 | 0 |
| Python invalid | Exact parser/semantic diagnostics; `ok: false` | 1 |
| JS clean | `PARTIAL (JS pre-check only; no pre-check errors found — install \`pipx install northcel\` for full validation)` | 0 |
| JS detected error or unreadable file | `PARTIAL ... errors found` plus line:column diagnostics | 1 |
| JS clean with `--require-full` | Same partial result plus full-validator-unavailable diagnostic | 2 |
| Invalid check arguments / unsupported flags | Usage (not a validation result) | 2 |
| Node-only `render` / `film` | Install Python guidance, no render claimed | 1 |

Every JS API result and `check --json` result contains `partial: true`,
`validator: "js"`, `reason`, `next`, `ok`, `errors`, `warnings`. CLI JSON additionally
has `file`, `spec_version`, `exit_code` (the API retains `specVersion`). `ok`
means *no errors found by this validator*, not full validity. Thus a clean
`--require-full --json` without Python has `ok: true, partial: true, exit_code: 2`.
Check the process exit code **and** partial marker; never treat `ok` alone as
full success. Older Python releases' JSON lacks markers and is passed unchanged.
Exit 2 also covers Python argparse usage errors, not language errors.

**Agent certainty command:** install `pipx install northcel` (or use a venv with
`pip install northcel` and put its Python on PATH), then run
`npx northcel check film.ncel --require-full --json`. Only exit 0 is full check
success. A normal pipx entrypoint on PATH also works without exposing pipx's
Python executable. Always render/inspect before claiming the film looks correct.

### JS pre-check coverage (not full grammar/conformance)

| Case | JS 0.2.1 | Python/reference or render still needed |
|---|---|---|
| Root, version, trailing tokens; balanced braces/quotes/parentheses; comments | Error on detected structural mistakes, multiline and single-line supported | Does not evaluate the document |
| Unknown statements in scene/film/frame/def | Error; allowed sets generated from reference parser methods | Reference parser remains authority |
| `frames:` in body, malformed palette/cel/stroke/ribbon/def/use headers | Error with line:column; attributes, tuples and point arities recognized | Attribute meaning, function names/arity, expression evaluation not checked |
| Ring characters, integer pairs, Base-63 odd tail, fewer than 3 decoded vertices | Error; same alphabet/precision dispatch as Python | Does not judge geometry, self-intersection, artistic suitability |
| Duplicate primitive/layer names in one block | **Warning** (legal layer/cel replacement; strokes/ribbons append) | Expanded def/use name collisions and paint-order intent need inspection |
| Unknown `$palette` names | Error; declaration order and frame-local scope followed | Palette value types/colour range evaluation not checked |
| Width/height/fps/frame-index ranges, agents, stroke widths/point minimum, undefined def | Not checked | Python semantic validator |
| Variable binding, time-dependent arithmetic, rendered quality, runtime function errors | Not checked | Real renders/visual review; full Python check itself is not a runtime/quality proof |

The structural scanner is intentionally not advertised as a complete JS parser.
An invalid file can pass the pre-check (e.g. `film F(fps: 0) { use Missing }`).
Generated `js/rules.json` takes version constants, statement sets and the Base-63
alphabet from Python. The compact packaged guide is extracted verbatim from
marked text in `docs/agent-guide.md`; `scripts/sync-assets.py --check`
and package tests prevent stale copies at release time. Run
`python3 js/northcel/scripts/sync-assets.py` after editing the source guide.

## 4. Editor Support, GitHub Linguist & Tree-Sitter Notes

- **VS Code / TextMate:** A highlighting grammar (`source.northcel`, not a validator) and VS Code extension manifest live in `editors/vscode/`.
- **GitHub Linguist requirements (when ready to submit a PR later):**
  1. Wide public usage across multiple repositories using `.ncel`.
  2. An entry in `languages.yml` mapping `.ncel` to `tm_scope: source.northcel`, `type: programming`, `color: "#8E24AA"`, and pointing to the TextMate grammar repository.
- **Tree-sitter requirements:** A `grammar.js` mirroring the EBNF in `docs/spec/SPEC-0.1.0-draft.md` (specifically `scene`/`film`, `paper`, `def`/`use`, `layer`/`bend_swarm`/`stroke`/`ribbon`, and `Expr`).
