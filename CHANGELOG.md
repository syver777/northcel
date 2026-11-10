# Changelog

All notable changes to the NorthCel language specification, the reference
implementation, the native runtime, the CLI and the editor tooling.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
The language specification has its own draft number (currently `0.5.0-draft`), which does not
move for packaging-only releases.

---

## [0.6.1] — 2026-11-10

### Added
- `northcel fit --figure [--backing PX] [--figure-mask FILE]`: fit one key as the
  **measured figure** — paper, sky and a cloud the ink touches are excluded — and
  paint an ink outline backing (default 4 px) underneath every fitted shape, so an
  anti-aliased crack shows ink instead of the background colour.
- `northcel.keys`: `measure_figure` (material fills + ink outline + white garments,
  never a full-width field), `figure_box`, `dilate_mask`, `outline_rings`,
  `add_outline_backing` and `prepare_key` (fit + backing + a receipt carrying both
  the figure box and the material-only box used for scale/position checks).

### Fixed
- A black-and-white key is measured from its dark strokes; reddish/blue fills are
  no longer mistaken for ink, and an anti-aliasing ring along a cloud or sky edge is
  no longer treated as figure material.

## [Unreleased]

### Planned 0.6.0 — Spec 0.5: addressable groups, warp, nudge and frame deltas (source-only)

Not published: PyPI/Homebrew/install.sh still ship tools 0.5.0 (spec 0.4), npm
ships 0.4.0. The 0.5-spec examples require this source checkout until Phase 7.

### Added
- Spec **0.5.0-draft** (`docs/spec/SPEC-0.5.0-draft.md`): named `group` blocks with
  pivot/opacity/clip/parent, group-wide `transform`, handle-based smooth `warp`,
  per-vertex `nudge`, and cheap key deltas via `use` plus nudges/transforms.
- `fit --stacked` gives every shape a stable `s<sha1>` id and a `shape_manifest`
  receipt (colour, area, kind, bbox, centroid, parent, children, neighbours).
- `northcel shapes FILE` region queries by id/colour/area/bbox/centroid/parent/mask.
- Groups, warps and nudges are Python-reference features; the native runtime stays
  at spec 0.3 and 0.4/0.5 documents are routed to the labelled reference.

### Compatibility
- 0.1–0.4 documents keep their pixels. Headerless documents are now
  `0.5.0-draft`; 0.5 constructs in an older header are located validation errors.

### Fixed
- Accept the launcher routing flags `--no-native` and `--python` for the
  reference-only `diff`, `onion`, `contact`, `continuity` and `distinct` commands.
- Scan definitions and nested groups for 0.5 features; route headerless documents
  to the reference in both launchers, including reference syntax diagnostics.
- Resolve late-declared parent pivots at transform time, reject fractional nudge
  indices, preserve single-handle warp tuples through `fmt`, and report located
  evaluation errors from `shapes` without tracebacks.
- Parse 0.5 group/delta structure in the PARTIAL JS pre-check, report the real
  source launcher version, and share evaluated geometry rows between fit receipts
  and shape queries.
- Separate published 0.5.0 install guidance from unreleased 0.6.0 examples; sync
  offline guides and check every current spec/agent-guide fence and frame in CI.


## [0.5.0] — Spec 0.4: colour expressions, morph, frame ranges, opacity; polishing tools (2026-11-09)

### Added
- Spec **0.4.0-draft** (complete document, `docs/spec/SPEC-0.4.0-draft.md`):
  - `mix(colourA, colourB, u)` wherever a colour is accepted (primitive colours,
    outline colours, paper); sRGB channels, `u` clamped, `floor(a + (b−a)u + 0.5)`.
  - `morph name(color, u[, samples, outline, opacity]) { "A" => "B" }`: ring i pairs
    with ring i; unequal vertex counts are resampled by arclength, winding is
    normalised and the start aligned by the least-squares cyclic shift; exact
    endpoints at `u ≤ 0` and `u ≥ 1`. Allowed in scenes, films, frame blocks and defs.
  - `frame A..B { ... }` inclusive ranges: an exact `frame N` wins, otherwise the
    last range in source order; blocks never merge; overlaps warn.
  - `opacity: expr` on layer/wash/cel/swarm/stroke/ribbon/morph and group opacity on
    `use D(opacity: expr)`, composited per 8-bit subpixel; a dissolve is
    `use A` then `use B(opacity: u)`.
- `northcel fit --stacked` (+ `--gap-fraction`, `--underpaint-min-area`, `--ink`):
  painter's-order solid shapes, see-through gaps checked against the source pixels
  kept as paper-coloured shapes, optional underpaint of large ink holes. Output is
  spec 0.3. The default planar output is byte-identical to 0.4.0.
- `northcel tween --match`: colour-aware Hungarian shape matching across topology
  mismatch, allowed colour changes (`--colour-changes`), motion propagation for
  unmatched shapes inside matched ones, huge-shape switching, a confidence report
  (matched fraction, weighted displacement) and an explicit cut/dissolve fallback
  (`--mode`, `--fallback`, `--min-match`, `--max-displacement`). Writes one
  spec 0.4 film (keys once as `def`s, `frame A..B` holds, `morph`/`mix`/`opacity`
  in-betweens).
- Python API `northcel.correspond` (`match_drawings`, `film_from_keys`, `Key`,
  `Transition`, `FilmOptions`, `MatchOptions`, `linear_assignment`),
  `northcel.shapes` (`StackedDrawing`, `Shape`, `drawing_from_source`,
  `stack_planar`, `stacked_source`) and `northcel.fitting.fit_stacked`; documented
  in `docs/reference.md`.
- Guide chapter 16, pattern 12 (polishing AI frames), conformance case
  `05_spec04_mix_morph_opacity` (reference-only), eight new reproduced diagnostics,
  Decision 9.
- JS pre-check accepts `mix(...)`, `morph ... { "A" => "B" }` (equal ring counts) and
  `frame A..B`; `spec04Features()` is exported.

### Changed
- The launchers never hand a spec 0.4 document (any 0.4 construct, or a 0.4
  header) to the native runtime 0.4.0, which implements spec 0.3: the Python
  launcher renders it with the labelled reference and says why; the npm launcher
  uses its Python bridge or exits 3 naming the features. `--version` states the
  native runtime's spec.
- Python reference fill vectorised (per-layer crossings at once, span painting)
  and a faster exact box filter: 1920×1080 fitted frames 0.75–1.93 s → 0.21–0.52 s
  on an Apple M1, pixels byte-identical.
- Headerless documents are spec `0.4.0-draft`.

### Fixed
- `test_platform_reason_names_the_places_that_were_searched` now pins
  `sys.platform`, so it also passes on macOS.

### Compatibility
- Valid 0.1–0.3 documents render with identical pixels; golden images, docs images
  and conformance probes are unchanged. `opacity` in a document declaring an older
  spec is still ignored (with a warning). `mix`, `morph` and frame ranges in such a
  document are validation errors that name the header to use.
- The native runtime, `northcel-native`, `northcel-linux-x64`, the toolchain lock
  and `pins.json` stay at 0.4.0 / spec 0.3; only the tools move to 0.5.0. Spec 0.4
  documents are Python-reference only until a native release passes case `05`.

## [0.4.0] — Intact drawing edits and offline fitting (2026-11-05)

### Added
- Spec **0.3.0-draft**: immediate `transform name(...)` / `transform all(...)`
  with uniform/nonuniform scale, reflection, clockwise rotation, anchors and
  translation; pure clamped `ease` and `smoothstep` expressions.
- Matching MoonBit AST/parser/geometry/NCIR and Python reference semantics,
  transformed fill/outline/stroke/ribbon/swarm conformance and shuffled-order tests.
- `northcel fit` optional offline palette/contour authoring tool, supplied palette
  and intact-cel matte support, compact or cell-corner-preserving tracing, honest
  geometry-size/configuration receipts. No embedded raster or runtime image input.
- `northcel tween`: explicit ordered vector correspondence, arclength resampling,
  winding/start alignment and opt-in hold fallback; never a visual quality judge.
- Guide chapter 15, intact-cel motion pattern, diagnostics and architectural
  decisions. The renderer remains MoonBit + Bend/HVM2 + GLSL.

### Fixed
- Exact 32px spatial cells + right-edge parity seeds avoid scanning an entire
  8-row edge band for every pixel in heavily textured fitted drawings. Both
  GLSL variants retain the same crossing/integration rule and old goldens.
- Canonical formatting retains binary-expression precedence and emits valid hex
  colours for unreferenced greyscale outlines.
- Formatting also retains frame-local paper/palettes, lexical colour snapshots
  and round-tripping float precision. Tween output resolves palette-bound paper
  to self-contained colour values and compares paint semantics, not source spans.
- Conformance now compares **every declared probe frame**, forward and reverse,
  in native and reference, rather than only native frame zero.
- Native tests resolve this standalone repository's root, so examples, grammar
  and oracle comparisons no longer silently skip after extraction from NorthNoir.
- Toolchain URLs pin the original compiler/core archives by immutable official
  `0.10.19+bee578715` URLs; no insecure checksum bypass or compiler redistribution.

### Compatibility
- No break: valid 0.1/0.2 drawing semantics and golden pixels are retained. The
  spec minor moves for additive syntax; the tools/native release moves to 0.4.0.
- A `scale` parameter in an old `use` remains an ordinary parameter, not a new
  automatic transform. Native platform support remains Linux x86_64 only.

### Earlier documentation work (included in this release)

### Added
- **A real writing guide** in `docs/guide/` (14 numbered pages): getting started,
  the scene model, paper, palette, cels/outlines, strokes/ribbons, `def`/`use`,
  films/overrides/`drop`, boil, contour encodings, `bend_swarm`, diagnostics,
  performance, and editing one frame. Every construct page has a complete
  `.ncel`, a rendered image of it, one deliberate mistake with the **real**
  diagnostic, and the command that reproduces it.
- **Patterns cookbook** in `docs/patterns/` + `examples/patterns/`: ten complete
  films (head turn, blink, jump, colour beat, cloud drift, progressive assembly,
  duck walk, line boil, crowd swarm, two-shot), each with a contact sheet, byte
  and `cl100k` token size, why it works and its pitfalls. Total: 19,821 bytes /
  9,616 tokens for all ten.
- **Gallery** (`docs/gallery.md`): the shower frames, the lantern film contact
  sheet, a 90-frame AI-drawn film recreated in `.ncel` (linked, not embedded) and
  the patterns.
- **`docs/errors.md`**, generated by `docs/scripts/gen_errors.py` from the parser,
  validator and ring decoder: message inventory plus 43 reproduced diagnostics.
- **`docs/architecture.md`**: the MoonBit → Bend/HVM2 → GLSL pipeline, what each
  stage owns, determinism measurements, the Python oracle and the honest platform
  matrix.
- **Machine-checked docs**: `docs/scripts/build_docs_assets.py` renders every
  guide snippet, pattern and contact sheet and writes `expected.json`;
  `docs/scripts/check_docs.py` renders them again, reproduces every diagnostic and
  verifies every relative link. CI has a new `docs` job.

### Changed
- `README.md` and `docs/README.md` now index the guide, patterns, gallery, errors
  and architecture; `docs/tutorial.md` is retired to a redirect, and
  `docs/reference.md` keeps only the CLI, validation contract and editor notes.
- `docs/agent-guide.md` starts with a "first ten minutes" loop, how to verify a
  frame, and the traps that still compile (inherited strokes, one-frame overrides,
  parse-time attributes, palette scope, `agents:` as a declaration).

### Changed — install URL and a machine-checked runtime claim
- **Every install one-liner now uses the release asset**, not `main`:
  `curl -fsSL https://github.com/syver777/northcel/releases/latest/download/install.sh | bash`
  (`README.md`, `packaging/README.md`, `packaging/DESIGN.md`,
  `docs/guide/01-getting-started.md` and the installer's own header). The raw URL
  stays only as a clearly labelled "tracks `main`, may change" alternative in
  `packaging/README.md`.
- **`docs/architecture.md` gained "Verify this yourself"**: the exact `doctor`,
  `verify`, `bend_swarm` receipt, shader/binary hash and negative-control commands
  with real 0.3.1 output, including what a native receipt does and does not name
  (there is no `renderer` key on the native path; it says
  `"stage": "MoonBit+Bend+GLSL"`, while the fallback says
  `"renderer": "python-reference"`).
- The README's Documentation section leads with the writing guide, patterns,
  common errors and architecture; the Homebrew README/formula now state the
  native stack (MoonBit + Bend/HVM2 + GLSL), Linux x86_64 only, and the Python
  reference as oracle and labelled fallback.

## [0.3.1] — One package name, one repository (2026-11-04)

NorthCel is now its own open-source project: this repository, dual licensed under
MIT OR Apache-2.0. Nothing in the language changed.

### Changed
- **One install name everywhere: `northcel`.** `pip install northcel` now installs
  the reference implementation *and* the native launcher as a single distribution
  with the console scripts `northcel` and `ncel`; it depends on the platform wheel
  `northcel-native`. `npm install -g northcel` installs the launcher plus the
  optional `northcel-linux-x64` bundle. `ncel` is the short command alias, not a
  package name.
- **PyPI was consolidated in one release.** Before 0.3.1 the package was split
  three ways (`ncel` = launcher, `ncel-native` = native runtime, `northcel` =
  reference only); installing one did not give you the others. Now `northcel` is
  the only package a user installs, it carries both entry points, and the old names
  are re-published as deprecation-only shells that depend on the new ones.
- The npm `northcel` package exposes a single merged CLI (`northcel` and `ncel`
  both run it) that dispatches native → Python reference → PARTIAL JS pre-check,
  instead of two separate scripts with two different behaviours.
- Package metadata points at `github.com/syver777/northcel`; `homepage`, `bugs`,
  `repository` and the documentation links moved with the code.
- Repository layout: `python/` (reference + launcher), `python/northcel-native/`,
  `js/northcel/`, `js/northcel-linux-x64/`, `native/`, `docs/`, `packaging/`,
  `editors/`.
- The Homebrew formula collapsed from three pinned resources to two
  (`northcel` 0.3.1 + `northcel-native` 0.3.1); the install command is unchanged.

### Licensed
- Dual **MIT OR Apache-2.0** (was proprietary). NorthNoir itself is unchanged.

### Added
- GitHub Actions CI: Python 3.10–3.13, JS on Node 20/22, `npm pack` (with a
  packed-file assertion), wheel build + clean-venv install smoke test, and a
  conformance job that renders the same frames with both implementations.
- `Makefile` with `make test`, `make lint`, `make dist`, `make verify`.
- `CODE_OF_CONDUCT.md`, and a rewritten `CONTRIBUTING.md` and `SECURITY.md`.
- `python/tests/test_launcher_platform.py`: EGL discovery regression cover (see the
  fix below), and an `info --json` CLI-parity test.

### Fixed
- **`find_egl_runtime()` now finds a non-distribution Mesa.** It only looked at the
  distribution's library directories and `ldconfig -p`, so a Homebrew (keg-only)
  Mesa, or one supplied purely through `LD_LIBRARY_PATH`, was invisible: `northcel`
  refused to use a native runtime that was installed and working, and fell back to
  the labelled Python reference. It now searches `LD_LIBRARY_PATH`, `$HOMEBREW_PREFIX`,
  `/home/linuxbrew/.linuxbrew`, `~/.linuxbrew`, `/usr/local` (including keg-only
  `opt/*/lib`), the Python prefix, then the distribution paths and `ldconfig -p` —
  the same order the dynamic loader uses. The honest failure message now names the
  places that were searched and still says how to install Mesa.
- **CI job failures on the first run are fixed at their cause, not by weakening
  tests.** The `node` jobs spawn the real Python reference in two delegation tests
  and never installed its `numpy`/`Pillow` dependencies; the `wheel` smoke test
  called `northcel info FILE --json`, which the reference CLI did not accept even
  though both the launcher usage and the native runtime document it. `info` now
  accepts `--json` (it only ever prints JSON) in every implementation.
- **`make lint` no longer runs `ruff format --check`.** The repository deliberately
  does not reformat the reference implementation (see `ruff.toml`), so that step
  failed on untouched files; CI and `make lint` now run the same check.
- `starter.ncel`, the fixture `northcel verify` renders, was previously generated
  into a git-ignored directory and therefore missing from a clean checkout. It is
  now a tracked example like every other fixture.
- The launcher no longer treats the Python reference as a separate distribution it
  must find by name: it imports the reference from its own package.
- `northcel guide` and the npm guide are the same generated text again: the wheel's
  copy still described the pre-merge npm package (`npx northcel guide` as a "Python
  CLI bridge") and said tools 0.2.1. `sync-assets.py --check` now guards both copies.

### Deprecated
- PyPI `ncel` and `ncel-native`, and npm `@ncel/linux-x64`, are deprecated aliases
  that now install/point at the `northcel` packages at 0.3.1. Existing installs keep
  working; the new names are what the documentation says.

---

## [0.2.1] — Tools only; specification remains `0.2.0-draft` (2026-11-04)

### Fixed
- macOS defect: npm 0.2.0 without Python printed `OK` and exited 0
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
  and a real Node-only authoring trial; the npm tarball is ready to publish.
- The Node-only trial found an old README/tutorial `def`/`use` example applying
  `dx`/`dy` twice. Corrected authoring snippets without changing historical
  fixtures or reference rendering semantics.

---

## [0.2.0] — Specification `0.2.0-draft` (2026-11-03)

### Added (derived from a 90-frame AI-drawn film)
- **Quarter-Pixel Base-63 Ring-Chain Encoding (`precision: 0.25px-b63`):**
  - Encodes `0.25px` quarter-pixel steps in 2 Base-63 ASCII characters per vertex with collinear-preserving step subdivision.
  - Combined with chromatic halo filtering on a 90-frame AI-drawn film (`1536×864`), reduced total 90-frame `.ncel` film size from **`6,704,285 bytes` (`4,249,852 tokens`) to `914,478 bytes` (`684,528 tokens` — `-86.4%` bytes / `7.33×` smaller)** while improving Global Windowed SSIM from `0.9719` to **`0.9756`** and Exact Canny Edge IoU from `0.4412` to **`0.4959`**.
- **Named Film/Scene Palettes (`palette { sky: #70CCF5, ... }` & `$name` references):**
  - Locks character and environment colors across an entire multi-frame film, eliminating per-frame color drift.
- **Coupled Fill + Ink Outline Primitive (`cel` and `outline: ($ink, Wpx)`):**
  - Eliminates duplicate coordinate tables when AI agents author 2D animation cels (where every colored shape has a black ink outline).
  - On 8 AI-authored representative frames of that film, `cel` + `0.25px-b63` cut mean AI-authored source size from **`8,830 bytes` (`5,052 tokens`) to `4,718 bytes` (`3,303 tokens` — `-46.6%` bytes)** while preventing fill/stroke desynchronization.
- **Film Frame Deltas (`drop <layer>` & In-Place Named Layer Replacement):**
  - Inside `film` `frame k { ... }` blocks, redefining a named `layer`/`cel` replaces it in place at its original paint-order slot, and `drop <name>` removes an inherited layer (and its coupled outline).
- **Backward Compatibility:**
  - All `0.1.0-draft` files and the `0.1.0-draft` conformance suite remain 100% valid and byte-identical in `0.2.0`.

---

## [0.1.0] — Specification `0.1.0-draft` (2026-11-03)

### Added
- Initial Language Specification (`docs/spec/SPEC-0.1.0-draft.md`), pure-Python + NumPy 4×4 subpixel reference renderer, CLI (`northcel` / `ncel`), conformance suite, VS Code TextMate grammar, and `0.1.0` PyPI release.
