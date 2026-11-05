# NorthCel (`.ncel`) AI-Agent Authoring & Self-Review Guide

This guide instructs AI coding agents (Claude Code, OpenCode, Codex, Cursor, Gemini CLI) how to author, verify, and surgically edit AI-drawn images and videos in **NorthCel (`.ncel`)**.

## The first ten minutes

1. **Read three pages, in this order:** [getting started](guide/01-getting-started.md),
   [the scene model](guide/02-the-scene-model.md) and
   [films and frame overrides](guide/08-films-and-frame-overrides.md). They cover
   the root, paint order and the one construct that most edits use.
2. **Run the gates on the file you were given before editing it:**
   `northcel check file.ncel --json` then `northcel render file.ncel -o before.png`.
   Never start from a file you have not rendered.
3. **Copy a structure, not a drawing.** The
   [patterns cookbook](patterns/README.md) has ten complete programs; pick the
   one whose *motion* matches the request (head turn, blink, jump, colour beat,
   drift, assembly, walk, boil, crowd, two-shot).
4. **Edit one named block.** Find it with `northcel info file.ncel`; change only
   that block; render the edited frame and both neighbours.
5. **Only then run the full film.** `northcel film file.ncel -o frames/` and look
   at the first, middle, last and transition frames.

If a request is about a still, use `scene`; if it is about timing, use `film`.
If you are unsure, read the diagnostic — it gives an exact `line:column`.

## Verify a frame, not just the exit code

```console
$ northcel check file.ncel --json          # exit 0 = this validator found no error
$ northcel render file.ncel -o f3.png --frame 3
$ northcel film file.ncel -o frames/ --frames 0..5
```

Open the PNG with an image-reading tool and check, in this order: is the subject
present and where it should be; are the silhouettes closed; do holes read as
holes; is the ink attached to the fill; does the motion between sampled frames
read as the requested beat. A passing check proves none of that.

For determinism, render the same frame twice and compare the decoded RGB (the
reference and native encoders may differ in PNG bytes). A changed picture between
two renders of the same frame is a bug in your edit, not "randomness".

## Traps that still compile

| Trap | What you will see | What to do |
| --- | --- | --- |
| **Inherited strokes** | A `frame k` override that adds a `stroke` leaves the base stroke visible too, because strokes append rather than replace | Use a new name only when you want both; otherwise replace the geometry (a `cel`) or add the stroke to the base with a time expression |
| **Frame overrides are one frame** | The change disappears on frame `k+1` | Declare the override for each frame, or move the change into the base timeline |
| **A replacement loses `translate:`** | The replaced layer jumps to its raw coordinates | Repeat the position/translate expression in the override |
| **Palette scope** | `Undefined palette color '$x'` | Declare the palette before the first `$x`, including before a `def` that uses it; frame-local palettes are local |
| **Attributes are parse-time** | A `def` parameter in `taper:`, `width:` or `color:` raises `Undefined parameter or variable` | Parameters work in point coordinates and `translate:` only; widths/colours are constants |
| **`agents:` is a declaration** | A swarm with `agents: 8` and one ring draws one ring | Put one ring per agent in the payload and declare the same count |
| **Two-shot layers with one name** | The second replaces the first | Name each shot's layers distinctly |
| **`frames:` in the body** | `Unknown scene/film statement 'frames'` | It is a header attribute |

More: [common errors](errors.md) is generated from the source and every entry is
reproduced by CI. The [architecture page](architecture.md) explains why the
reference and native renderers can differ by a handful of edge pixels.

<!-- npm-guide:start -->
# NorthCel quick agent guide — tools 0.3.1, spec 0.2.0-draft

Discover this guide offline with `northcel guide` (or `npx northcel guide`). The
npm package runs the native runtime on Linux x86_64 and otherwise falls back to the
Python reference, with a zero-dependency **partial JS pre-check** for `check` when
neither is available. There is no JavaScript renderer.

## Start here (a complete 3-second film)

```ncel
northcel "0.2.0-draft"
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
<!-- npm-guide:end -->

---

## 1. The Golden Rules of Authoring `.ncel`

1. **Always Start with the Version Header:**
   Start new files with `northcel "0.2.0-draft"` (`0.1.0-draft` remains supported).
2. **Separate Washes, Ink Ribbons, and Parallel Swarms by Name:**
   - Use `layer` / `wash` for broad silhouette envelopes (`tile_wall`, `skin_envelope`, `hair_dome`).
   - Use `stroke` or `ribbon` for variable-width anatomical contours and props (`brow_eye`, `ear_loop`, `post_ink`).
   - Use `bend_swarm` for repetitive organic detail (`water_droplets`, `beard_and_chest_bristles`, `rain_streaks`, `foliage`).
   - Use `def` and `use` for repeated motifs across the canvas or timeline.
3. **Choose the Right Representation for the Task:**
   - **Direct AI Authoring (`film` + `def`/`use` + `stroke`/`ribbon`):** Keeps files tiny (`~1 KB` / `~460 tokens` for a 6-frame animated shot like `lantern_film.ncel`).
   - **Compact Traced Contours (`precision: 1px` Base-63):** Best when fitting existing reference frames under a strict token budget (`~14.7 KB` / `~9.5k tokens` per frame).
   - **Subpixel Traced Contours (`precision: 0.25px` Quarter-Pixel):** Best when maximum subpixel visual fidelity (`0.962–0.972` SSIM) is required (`~65 KB` / `~44k tokens` per frame).

---

## 2. The 4-Step Agent Verification Loop

Never claim a `.ncel` file is finished without running the gates and visually inspecting the rendered PNGs:

### Gate 1 · Syntax & Semantic Check (`northcel check`)
```sh
npx northcel check scene.ncel --require-full --json
```
If `ok` is `false`, read the exact `line:column` error and fix it immediately.
If `partial` is `true`, install/expose Python and repeat; a Node-only exit 0
without `--require-full` is not full validation. The exact tool contract is in
[reference.md](reference.md#validation-contract).

### Gate 2 · Still Check (`northcel render --frame 0`)
```sh
northcel render scene.ncel -o frame0.png --frame 0
```
View `frame0.png` with your image-reading tool. Check:
- Are silhouettes closed and properly layered?
- Do even-odd aperture cutouts (like water highlights or eye whites) read clearly?
- Are ink stroke widths balanced?

### Gate 3 · Motion & Determinism Check (`northcel film`)
```sh
northcel film scene.ncel -o frames/ --frames 0..5 --mp4 preview.mp4
```
Inspect sampled frames (`f0000.png`, `f0002.png`, `f0005.png`) to confirm smooth motion (`lerp`, `sin`, `cos`) and subtle `boil` (`0.3px .. 0.8px`).

### Gate 4 · Canonical Format (`northcel fmt -w`)
```sh
northcel fmt -w scene.ncel
```

---

## 3. Performing Surgical `Adjust` Edits

When a user asks to tweak a single detail (e.g., *"make the rain heavier"* or *"change the lantern glow to warm gold"*):
1. Run `northcel info scene.ncel` to locate the exact named layer or `bend_swarm`.
2. Edit **only** that named block (`lantern_halo` or `rain_streaks`).
3. Leave every unrelated `layer`, `def`, and `stroke` untouched. Verify unaffected
   regions after rendering: overlap/occlusion can change visible pixels even
   when unrelated geometry is unchanged.

---

## 4. Lessons from hand-authoring 8 frames of a 90-frame film

An AI agent authored 8 representative frames (`1536×864`) of a 90-frame AI-drawn film by hand across 3 look-and-fix rounds (`f0001`, `f0028`, `f0037`, `f0043`, `f0055`, `f0067`, `f0076`, `f0085`):

1. **Always use `cel` + `palette` (`v0.2`) instead of separate `layer` + `stroke` blocks:**
   In `v0.1`, writing a separate `layer` fill and `stroke` outline for every cloud, shirt, pant leg, and duck part doubled the token count (`8,830 B / 5,052 tok`) and caused gaps where the stroke drifted from the fill. Switching to `v0.2`'s `cel name(color: $shirt, outline: ($ink, 5px))` cut AI-authored file size by **46.6%** (`4,718 B / 3,303 tok`) and guaranteed zero fill-to-outline gaps.
2. **Beware the SSIM Trap on Hand-Authored Linework:**
   Adding fine interior lines in later rounds (cloud outlines, facial features, grass tufts) makes the drawing look **much** more like a real cartoon to a human eye, yet can lower pixel-level Block SSIM by `0.01–0.02` if a 5px black outline is shifted by 4–8 pixels from the source frame's exact line position (because a shifted black line on white paper incurs a double pixel penalty). Judge AI-authored frames by **structural completeness + Edge IoU + visual inspection**, not raw pixel SSIM alone.
3. **Where an Unassisted LLM Struggles Without a Fitter:**
   - **Easy for an LLM (`0.88–0.93` SSIM):** Isolated heads (`f0001`), simple frontal standing poses (`f0028`), flat sky/ground horizons, and reusable props (`clouds`, `grass_tufts`).
   - **Hard for an LLM (`0.70–0.75` SSIM):** Complex foreshortened limbs (`f0037` airborne bent knees), articulated hands with 5 spread fingers (`f0055`, `f0067`), and overlapping seated legs (`f0076`, `f0085`). For complex character poses, pair an LLM layout/rig planner with a contour/part template library or fitted keyframe cels.

| Diagnostic | Cause | Fix |
| --- | --- | --- |
| `Expected 'dx,dy' pair at token N` | Mixed Base-63 (`:`) syntax with space-separated quarter-pixel syntax | Use `x0,y0:c1c2...` for Base-63 (`precision: 1px`) or `qx0,qy0 dx1,dy1 ...` for `precision: 0.25px`. |
| `Decoded ring has only 2 vertices (< 3)` | Closed contour ring has fewer than 3 distinct points | Use `stroke` for 2-point lines, or provide at least 3 distinct vertices for a `layer` ring. |
| `Use of undefined def block 'X'` | `use X(...)` called before or without `def X(...)` | Declare `def X(...) { ... }` inside the `scene` or `film` block. |
