# Format & tooling reference: CLI, check contract, editors

This page is the short lookup. The language itself is taught in the
[writing guide](guide/README.md); the normative grammar is
[SPEC-0.5.0-draft](spec/SPEC-0.5.0-draft.md).

For the default authoring approach, read [editable drawings](guide/17-editable-drawings.md):
observe → decompose → decide → edit the delta → verify → iterate. The five worked
illustrations use different general mechanisms, not subject templates. Start
with copies of good geometry; automatic `tween --match` is an optional alternative.

**Version scope:** tools **0.6.0 in this checkout**, spec **0.5.0-draft**, are
**source / unreleased**. PyPI, Homebrew and install.sh publish **0.5.0** (spec 0.4);
npm publishes **0.4.0**. `shapes`, fit ids and the spec-0.5 syntax below need this
checkout (`python3 -m pip install -e './python[fit]'` in a venv), not a published
0.5.0 install. [Release copy](release-0.6.0.md) is reserved for Phase 7.

## CLI (`northcel` / `ncel`)

| Command | What it does |
| --- | --- |
| `northcel doctor [--json]` | every stage, version, shader hash and the platform verdict; exit `0` only when native is usable, `3` with the reason otherwise |
| `northcel verify [--json]` | renders the pinned conformance frame and a 6-frame film twice, compares hashes |
| `northcel check FILE [--json] [--require-full]` | parse + validate; exit `1` on an error |
| `northcel info FILE [--json]` | metadata: bytes, kind, size, frames, fps, layers, rings, vertices |
| `northcel render FILE [-o OUT.png] [--frame N] [--seed N] [--json]` | one frame to PNG |
| `northcel film FILE -o OUTDIR [--frames 0..N] [--mp4 OUT.mp4] [--json]` | frame sequence and optional MP4 |
| `northcel fmt FILE [-w] [--check]` | canonical formatting (reference only); round-trips every spec 0.4 and 0.5 construct |
| `northcel shapes FILE [--frame N] [--ids …] [--color #RRGGBB] [--area-min N] [--area-max N] [--bbox x0,y0,x1,y1] [--centroid x,y,r] [--parent ID] [--mask IMAGE]` | JSON ids, colours, areas, bboxes, centroids, parents, children and neighbours of evaluated shapes |
| `northcel diff FILE --against IMAGE [--frame N] [-o HEATMAP.png] [--region NAME:x0,y0,x1,y1]… [--json]` | reference render vs same-size image: overall and per-group/per-region MAE, RMSE and PSNR; group errors measure the canvas-clipped geometric bbox, not a coverage mask; optional error heatmap |
| `northcel onion FILE -o OUT.png [--frame N] [--against IMAGE] [--json]` | previous frame (red) and this frame (blue); frame 0 uses frames 0/1, a scene uses its only frame; optionally compare against a same-size reference |
| `northcel contact FILE -o OUT.png\|OUTDIR [--frames 0..N\|0,2,4] [--every N] [--transitions] [--json]` | labelled contact sheet(s); `--transitions` writes one per `frame N` / `frame A..B` block including its preceding frame when available, preserving key endpoints under `--every`; a PNG output becomes `OUT-transitions/`; cannot combine `--frames` with `--transitions` |
| `northcel continuity FILE --group NAME [--shape ID] [--json]` | per-frame geometric bbox, width, height and bbox-centre centroid (before clipping/occlusion); adjacent scale/position changes, flagging a >8% bbox-height jump |
| `northcel distinct FILE [--frames 0..N\|0,2,4] [--every N] [--json]` | reference render resized to 320×180 (LANCZOS); count changed adjacent samples above mean absolute RGB difference 0.2/255, excluding the first frame; rate uses sampled timeline duration at film fps, not globally unique images |
| `northcel perceive segment IMAGE --points x,y [--points …] --out DIR [--frames DIR] [--checkpoint FILE] [--config NAME] [--json]` | optional SAM 2 masks; alternatively `--boxes x0,y0,x1,y1 …`; propagation requires the installed video API and numbered JPEGs; local weights only |
| `northcel perceive vectorize IMAGE --out FILE [--mode stacked] [--json]` | optional VTracer SVG; when absent, explicitly labelled `fit --stacked` fallback only with already-installed fit libraries and `.ncel` output |
| `northcel perceive flow A B --out DIR [--checkpoint FILE] [--model small\|large] [--json]` | optional TorchVision RAFT forward-flow PNG/NumPy array and geometric JSON motion hints; local weights only |
| `northcel perceive guide A B --out DIR [--model-dir DIR] [--json]` | optional FILM midpoint visual target; JSON and PNG metadata say `guide_only: true`; never output or quality evidence |
| `northcel fit IMAGE -o FILE [--palette P.json] [--stacked] [--figure [--backing PX] [--figure-mask FILE]] [--receipt R.json]` | offline contour fitting (`pip install 'northcel[fit]'`). Default: a planar map. `--stacked`: painter's-order solid shapes with `--gap-fraction` (0.5), `--underpaint-min-area` (300 px², 0 = off), `--ink #RRGGBB`. `--figure`: fit the measured figure only (paper/sky/cloud excluded) plus an ink outline backing, useful for an AI in-between key |
| `northcel tween A B -o FILE [--steps N] [--fallback error\|hold]` | ordered-ring in-betweens; identical topology required |
| `northcel tween A B -o FILE --match [--steps N] [--fps N] [--mode auto\|morph\|cut\|dissolve\|hold] [--fallback cut\|dissolve] [--min-match 0.5] [--max-displacement 32] [--colour-changes C.json] [--image-a A.png --image-b B.png] [--receipt R.json]` | shape matching across topology mismatch; writes one spec 0.4 film; below the thresholds an explicit cut or dissolve |
| `northcel guide` | the compact offline agent guide |
| `northcel toolchain <status\|install>` | the optional MoonBit compiler for rebuilding the native tree |

Global `--no-native` (before or after the command) forces the labelled Python
reference path for `check`, `info`, `render` and `film`; `fit`, `tween` and `fmt`
are Python-only authoring tools and do not take it. On a platform without a native bundle, the launcher prints a
two-line notice and labels the receipt `"renderer": "python-reference"`; it never
claims a native render.

**Spec 0.4/0.5 routing.** The native runtime 0.4.0 implements spec 0.3. When a
document uses `mix`, `morph`, `frame A..B` or `opacity` (0.4), or `group`,
`warp` or `nudge` (0.5), or declares a 0.4/0.5 header, `check`, `info`, `render`
and `film` use the Python reference even where native is available, print why
(`… uses spec 0.4/0.5 features (group); the native runtime 0.4.0 implements spec
0.3 only`) and label the receipt `python-reference`. The npm launcher does the same through its Python bridge.
Without Python, `render`/`film`/`info` exit `3` naming the features instead of
calling native; `check` falls back to the PARTIAL JS pre-check instead.
Headerless files default to spec 0.5 in this checkout and also use the reference,
including files whose statements happen to exist in spec 0.3.

## Optional perception

The source-only `perceive` helpers return JSON receipts and artifacts for the AI
to inspect: tools suggest, the AI decides. Backends are lazy, optional user
installs; no heavyweight core dependency or automatic model download is added.
See [perception.md](perception.md) for local-model configuration, output formats,
licences, exact absent-dependency messages and limitations. SAM 3, SEA-RAFT,
RIFE and GPL tracing tools remain external alternatives, not bundled backends.

## Validation contract

**Tools 0.6.0 from source (unreleased), spec 0.5.0-draft** (contract as of published
0.5.0; 0.6.0 adds groups, warp, nudge and shape queries). Use PyPI or, on Linux
x86_64 only, Homebrew for published **0.5.0**, which supports spec 0.4 only;
macOS uses pipx/pip. The `northcel` distribution is the reference
parser, validator, formatter and CPU renderer *and* the launcher that runs the
native runtime. The npm `northcel` package runs the same launcher and adds a
zero-dependency structural JS pre-check, the embedded guide and a Python bridge;
it has no JS formatter or renderer.

The npm wrapper probes `python3`, then `python`, on PATH for `northcel.cli`, then
looks for a Python-shebang `northcel`/`ncel` entrypoint on PATH (including pipx
installs). It skips its own npm entrypoints to prevent recursion. Once a probe
succeeds it delegates, preserving stdout, stderr and the exit code; it never
retries a failing Python check in JS. A terminated/unlaunchable Python process is
nonzero. `--require-full` is consumed by the bridge for compatibility with older
full Python CLIs. `guide` is always the npm-bundled guide. `--version` reports the
launcher version and the native-runtime state. The npm package does not require
Python for guide/doctor/version/help, and `check` falls back to the partial
pre-check when neither the native bundle nor Python is available.

| Path/result | Text / JSON | Exit |
| --- | --- | ---: |
| Python/native valid | `OK (NorthCel <spec>)`; `ok: true, partial: false` | 0 |
| Invalid | Exact parser/semantic diagnostics; `ok: false` | 1 |
| JS clean | `PARTIAL (JS pre-check only; no pre-check errors found — install \`pipx install northcel\` for full validation)` | 0 |
| JS detected error or unreadable file | `PARTIAL ... errors found` plus line:column diagnostics | 1 |
| JS clean with `--require-full` | The partial result plus a full-validator-unavailable diagnostic | 2 |
| Invalid check arguments / unsupported flags | Usage (not a validation result) | 2 |
| Node-only `render` / `film` / `info` | Install-Python guidance, no render claimed | 3 |

Every JS API result and `check --json` result contains `partial: true`,
`validator: "js"`, `reason`, `next`, `ok`, `errors`, `warnings`. CLI JSON
additionally has `file`, `spec_version`, `exit_code` (the API retains
`specVersion`). `ok` means *no errors found by this validator*, not full validity.
Thus a clean `--require-full --json` without Python has
`ok: true, partial: true, exit_code: 2`. Check the process exit code **and** the
partial marker; never treat `ok` alone as full success.

### JS pre-check coverage (not full grammar/conformance)

| Case | JS pre-check | Python/reference or render still needed |
|---|---|---|
| Root, version, trailing tokens; balanced braces/quotes/parentheses; comments | Error on detected structural mistakes | Does not evaluate the document |
| Unknown statements in scene/film/frame/def | Error; allowed sets generated from the reference parser | Reference parser remains authority |
| `frames:` in body, malformed palette/cel/stroke/ribbon/def/use headers | Error with line:column | Attribute meaning, function arity, expression evaluation |
| Ring characters, integer pairs, Base-63 odd tail, fewer than 3 vertices | Error | Does not judge geometry or artistic suitability |
| Duplicate primitive/layer names in one block | **Warning** (replacement is legal) | Expanded def/use collisions and paint order need inspection |
| Unknown `$palette` names | Error; declaration order and frame-local scope followed | Palette value types/colour range |
| Width/height/fps/frame ranges, agents, stroke widths, undefined def | Not checked | Python semantic validator |
| Variable binding, time-dependent arithmetic, rendered quality | Not checked | Real renders and visual review |
| Spec 0.4: `mix(…)` shape, `morph … { "A" => "B" }`, `frame A..B` (reversed bounds), equal ring counts on both morph sides | Error with line:column | `u`/`opacity` values, `samples` range, overlapping-range warning, header/feature agreement |
| Spec 0.5 (source launcher): `group` bodies (including nested groups/defs), `warp`/`nudge` statement headers and tuples | Structural errors with line:column | Attribute meaning, integer indices, target resolution, header/feature agreement, pivots, clipping and deformation need Python and renders |

The structural scanner is intentionally not advertised as a complete JS parser.
An invalid file can pass the pre-check (e.g. `film F(fps: 0) { use Missing }`).
Generated `js/rules.json` takes version constants, statement sets and the Base-63
alphabet from Python. The compact packaged guide is extracted verbatim from
marked text in [agent-guide.md](agent-guide.md); `scripts/sync-assets.py --check`
and package tests prevent stale copies at release time. Run
`python3 js/northcel/scripts/sync-assets.py` after editing the marked section.

## Python API for polishing

`northcel tween --match` is a thin CLI over three modules that other tools may
import. They are part of the tools release (semantic versioning applies to these
names and signatures from 0.5.0). Everything is offline NumPy arithmetic; `cv2`
and `scikit-image` (`northcel[fit]`) are only needed to trace images.

```python
from northcel.fitting import fit_stacked
from northcel.shapes import StackedDrawing, Shape, drawing_from_source, stack_planar, stacked_source
from northcel.keys import measure_figure, figure_box, prepare_key, add_outline_backing
from northcel.correspond import (Key, Transition, FilmOptions, MatchOptions, Match,
                                 match_drawings, film_from_keys, linear_assignment)
```

| Function | Signature (keyword defaults) | Returns |
| --- | --- | --- |
| `fit_stacked` | `fit_stacked(image, colors=32, tolerance=0.6, min_area=2.0, palette=None, name="StackedDrawing", cell_edges=False, mask=None, *, gap_fraction=0.5, underpaint_min_area=300.0, ink=None, hole_min_area=30.0, min_shape_area=4.0)` | `(StackedDrawing, receipt dict)` — tracing as `fit`, then stacking with the gap test on the image's own palette labels |
| `drawing_from_source` | `drawing_from_source(source, image=None, *, stack="auto", gap_fraction=0.5, underpaint_min_area=300.0, ink=None)` | `StackedDrawing` from a plain scene (planar fit or already stacked); `image` (path or PIL image) supplies source pixels for the gap test |
| `measure_figure` | `measure_figure(image, *, background=None, tolerance=42.0, min_component=1200, attach_px=14, max_hole=18000, white_min=400, white_max=26000, with_core=False)` | boolean raster mask of the drawing's figure without paper/sky/clouds; `with_core=True` also returns the material-only mask whose box is the accurate figure extent |
| `prepare_key` | `prepare_key(image, *, palette=None, colors=32, tolerance=0.6, min_area=2.0, gap_fraction=0.5, underpaint_min_area=300.0, backing=4, mask=None, name="Key")` | `(StackedDrawing, receipt)` — masked stacked fit plus an ink outline backing; the receipt records `figure_mask.box` and `figure_mask.material_box` |
| `add_outline_backing` | `add_outline_backing(drawing, mask, *, width=4, color=None, name="backing")` | copy of `drawing` painting the expanded figure silhouette in ink under every shape |
| `stack_planar` | `stack_planar(layers, paper, width, height, labels=None, label_colors=None, *, gap_fraction=0.5, underpaint_min_area=300.0, ink=None, min_shape_area=4.0, hole_min_area=30.0, name="Drawing")` | `StackedDrawing`; `layers` is `[(rgb, [ring arrays])]` in paint order |
| `stacked_source` | `stacked_source(drawing, *, spec="0.3.0-draft", antialias_grid=4, fps=24)` | `.ncel` scene text, one `layer` per shape |
| `match_drawings` | `match_drawings(a, b, options=None)` (defaults to `MatchOptions()`) | `Match(pairs, only_a, only_b, displacement, matched_fraction)`; `match.confident(min_match, max_displacement)` |
| `film_from_keys` | `film_from_keys(keys, transitions=None, options=None)` (defaults to `FilmOptions()`) | `(film source, receipt dict)` |
| `linear_assignment` | `linear_assignment(cost)` | `(rows, cols)` minimum-cost assignment, deterministic |

Data types: `Shape(color, ring, area, kind)` (`kind` is `region`, `gap` or
`underpaint`; optional `id=""`, `z=None` in this checkout); `StackedDrawing(width, height, paper, shapes, name)`;
`Key(drawing, time, name=None)` (time in seconds);
`Transition(mode="auto", seconds=None)` with `mode` one of `auto`, `morph`,
`cut`, `dissolve`, `hold`; `MatchOptions(colour_changes=(), match_cost=2.0,
background_fraction=0.35)`; `FilmOptions(fps=20, frames=None, width=None,
height=None, antialias_grid=4, transition_seconds=1/3, easing="smooth",
min_match=0.5, max_displacement=32.0, fallback="cut", switch_area_fraction=0.095,
ink_switch_area_fraction=0.0127, ink=None, samples_per_px=3.5, max_samples=480,
name="Polished", match=MatchOptions())`. Colours are `(r, g, b)` tuples.

A minimal film from a list of drawings:

```python
from pathlib import Path
from northcel.correspond import FilmOptions, Key, film_from_keys
from northcel.shapes import drawing_from_source

times = {"d01": 0.0, "d03": 0.333, "d04": 0.5}
keys = [Key(drawing_from_source(Path(f"fit/{n}.ncel").read_text(), f"cels/{n}.png"), t, n)
        for n, t in times.items()]
source, receipt = film_from_keys(keys, ["auto", "cut"], FilmOptions(fps=20, frames=20))
Path("polished.ncel").write_text(source)
for t in receipt["transitions"]:
    print(t["from"], t["to"], t["mode"], t["reason"], t.get("matched_fraction"))
```

Timing: key `i` is on frame `round(time × fps)`; each transition uses at most
`seconds` (default `transition_seconds`) before the next key, and earlier frames
hold. `cut` switches half-way through that window, `hold` on the next key's
frame. `auto` morphs when `match.confident(min_match, max_displacement)` and
otherwise uses `fallback`. Keys of a different size from the canvas are fitted
inside it with `transform all`. The receipt's `quality` is always
`"unreviewed"`: the API proves geometry, not that the in-betweens look right.

## Editor support, GitHub Linguist and Tree-sitter

- **VS Code / TextMate:** a highlighting grammar (`source.northcel`, not a
  validator) and a VS Code extension manifest live in `editors/vscode/`.
- **GitHub Linguist requirements:** wide public usage across multiple
  repositories; then an entry in `languages.yml` mapping `.ncel` to
  `tm_scope: source.northcel`, `type: programming`, `color: "#8E24AA"`, pointing
  at the grammar repository.
- **Tree-sitter:** a `grammar.js` mirroring the EBNF in the spec (`scene`/`film`,
  `paper`, `def`/`use`, `layer`/`bend_swarm`/`stroke`/`ribbon`, `Expr`).
