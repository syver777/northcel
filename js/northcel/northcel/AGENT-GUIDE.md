# NorthCel quick agent guide — tools 0.6.0, spec 0.5.0-draft

Discover this guide offline with `northcel guide` (or `npx northcel guide`). The
npm package runs the native runtime on Linux x86_64 and otherwise falls back to the
Python reference, with a zero-dependency **partial JS pre-check** for `check` when
neither is available. There is no JavaScript renderer.

## Start here (a complete 3-second film)

```ncel
northcel "0.4.0-draft"
film Kite(width: 320, height: 180, fps: 12, frames: 36, precision: 0.25px, seed: 42) {
  palette { ink: #202830, red: #D65C52 }
  paper { color: #FFF8EC, antialias_grid: 4 }
  cel kite(color: $red, outline: ($ink, 2px), boil: 0.3px,
           translate: (lerp(0, 100, t), sin(t * 6.28318) * 10)) {
    "240,120 100,80 -100,140 -100,-140"
  }
  stroke string(color: $ink, taper: (1.5, 0.5)) {
    (60 + 100 * t, 85 + sin(t * 6.28318) * 10), (110, 160)
  }
}
```

Coordinates are pixels, origin top left. Quoted rings are **relative integer
quarter-pixel pairs**, NOT absolute pixel vertices: multiply vertices by 4,
write the first vertex then deltas; at least three vertices per ring. `|`
separates rings (even-odd holes). `precision: 1px` and `0.25px-b63` instead use
`x0,y0:ABCD...` Base-63 pairs; prefer plain quarter-pixel deltas for hand authoring.
Never put expressions inside a quoted ring: move it with `translate: (x, y)`.

## Five language features to combine

1. **Reusable shapes:** `def Mark(dx: 0, dy: 0) { stroke line(width: 2) { (0, 0), (8, 4) } }`
   then `use Mark(dx: 20, dy: 30)`. Only primitives inside `def`, not nested `use`.
   `dx/dy` auto-translate expanded geometry; don't also add them to coordinates.
   Same-named cels in repeated uses replace one another; use distinct named defs
   for independent cel instances (stroke/ribbon uses append).
2. **Film/time:** `frames` belongs in the film **header**, never `film X { frames: 36 }`.
   Duration = frames / fps. `t = f / max(1, frames - 1)`; `f` is zero-based.
   Expressions: numbers, parameters, `t`, `f`, `seed`, `+ - * /`, `sin(x)`,
   `cos(x)`, `lerp(a, b, t)`, `step(edge, x)`. Use spaces around minus.
   `frame 12 { ... }` affects exactly frame 12, not all subsequent frames.
3. **Deterministic line boil:** `boil: 0.3px` or `boil: (0.3, 1)`; keep it subtle.
   No randomness, wall clock or cross-frame state.
4. **Colour/cels:** `palette { ink: #202830 }` before `$ink` references; hex, `rgb(r,g,b)`
   or `tone: 0..255`. `cel name(color: $ink, outline: (#000, 2px)) { "..." }`
   couples fill and outline. `layer`/`wash` fills; `bend_swarm`/`swarm` adds detail rings.
5. **Tapered ink:** `stroke name(color: $ink, taper: (3, 1)) { (10, 10), (40, 20) }`;
   `ribbon name(color: $ink) { (10, 10, 3), (40, 20, 1) }` uses per-point widths.
   At least two points. Give every primitive a distinct name in each block.

## Honest validation and look-and-fix loop

1. Run `npx northcel check film.ncel --json`. Without Python it reports
   `partial: true`, `validator: "js"`, a reason and next command. `ok: true` and
   exit 0 mean **only that the JS pre-check found no error**, not full validity.
   Text says **PARTIAL**, never OK. Syntax/header/ring/palette checks help, but
   numeric ranges, expression evaluation, def resolution and render quality remain unchecked.
2. Run `npx northcel check film.ncel --require-full --json` before claiming full
   validation. Exit 2 = no full validator (clean partial); exit 1 = detected error;
   exit 0 = Python full check succeeded. Install `pipx install northcel` (or
   `pip install northcel` in a venv), expose its Python CLI on PATH, then repeat.
   The npm bridge finds importable Python modules or pipx-style Python entrypoints.
   Never suppress exit 2 or call a partial check fully validated.
3. Python: `northcel render film.ncel -o frame0.png --frame 0`, inspect the PNG;
   `northcel film film.ncel -o frames/ --mp4 preview.mp4`, inspect first/middle/last
   and transition frames. ffmpeg is required for MP4; verify the MP4 exists.
   Render samples in reverse order and compare native RGB hashes for determinism.
4. Fix the named block that is wrong, preserve good parts, render again; up to
   three look-and-fix rounds. `northcel fmt -w film.ncel` canonicalizes it.
   Full validation is not a visual-quality or runtime-expression guarantee.

Alternatively install `pip install "northnoir[ncel]"` and use
`northnoir init ink --language ncel --duration 3 --fps 24`,
`northnoir check ink/scene.ncel`, `northnoir render ink/scene.ncel -o ink/video.mp4`.
This is an explicit optional local path; JavaScript `scene.html` stays the default.
NorthCel films are silent; there is no native audio engine or hosted NorthCel API.

## Common mistakes

- No root, unclosed quote/brace, unknown statement: fix the reported line:column.
- `frames:` in the body: move it to `film Name(..., frames: N) { ... }`.
- Missing primitive attributes: `cel`, `layer`, `swarm`, `stroke` need `(...)`,
  even `()`. `ribbon`, `def` and `use` may omit it. Palette takes `{ key: value }`
  or `(key: value)`, not a name. `use Name(...)` has **no body**.
- Invalid/odd Base-63 tail: use only `0-9A-Za-z_`, two characters per delta.
  Quarter-pixel payloads need whole integer pairs, not decimals or suffixes.
- Undefined `$colour`: declare it earlier, including before `def` bodies.
- Duplicate names: intentional layer/cel replacement is legal (JS warns, not errors).
  Frame overrides replace named layers/cels; same-named strokes/ribbons append,
  leaving stale ink. For moving ink use cels or time expressions instead.
- Undefined def, bad sizes/fps, expression variable errors: JS may miss these;
  use Python full check **and real renders**. No JS success authorizes shipping.
## Existing drawings and intact-cel motion (spec 0.3)

`northcel fit drawing.png -o drawing.ncel` (pip `northcel[fit]`) traces ordinary
vector contours; it never embeds the image. Compare the round trip. For texture,
try `--colors 128 --cell-edges --tolerance 0.05 --min-area 0`; count the much larger
source. An author-supplied `--mask` selects one intact cel, not body parts.

After painting: `transform name(scale: 1.2, rotate: 10deg, anchor: (160,90),
translate: (20,0))`. `transform all` moves prior marks, not paper. Expanded ink
scales with geometry; later replacements are unaffected. `ease(u)` is bounded
quintic easing, `smoothstep(a,b,x)` bounded cubic. Keep constant-speed travel
linear instead of stopping at every key.

`northcel tween a.ncel b.ncel -o trial.ncel` is an explicit ordered-contour
experiment, not an anatomy judge. Topology mismatch errors unless `--fallback
hold` is requested; inspect every inserted frame and reject doubled/folded lines.
Matching topology alone proves nothing. Source endpoints remain original geometry.

## In-betweens for independently drawn keys (spec 0.4, Python reference)

Spec 0.4 adds `color: mix($a, $b, u)` (also outlines and paper; u clamped),
`morph name(color: $c, u: expr) { "ringsA" => "ringsB" }` (ring i pairs ring i,
vertex counts may differ, exact A at u<=0 and B at u>=1), `frame 12..18 { ... }`
(exact `frame N` wins, else the last range) and `opacity: expr` on primitives or
`use D(opacity: u)` for a group (dissolve: `use A` then `use B(opacity: u)`).
They need `northcel "0.4.0-draft"` and render with the labelled Python reference;
the native runtime implements spec 0.3, and the npm launcher without Python
refuses them (exit 3). `northcel fit img.png -o key.ncel --stacked --palette p.json`
writes painter's-order shapes; `northcel tween a.ncel b.ncel -o t.ncel --match
--steps 6` matches shapes across topology mismatch and writes one film. Read the
receipt: below `--min-match`/`--max-displacement` it cuts (or `--fallback
dissolve`). A match proves no anatomy: a crouch→jump needs a drawn key. Inspect
every in-between; unmatched shapes pop at u = 0.5.
