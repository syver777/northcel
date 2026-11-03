# NorthCel (`.ncel`) AI-Agent Authoring & Self-Review Guide

This guide instructs AI coding agents (Claude Code, OpenCode, Codex, Cursor, Gemini CLI) how to author, verify, and surgically edit AI-drawn images and videos in **NorthCel (`.ncel`)**.

---

## 1. The Golden Rules of Authoring `.ncel`

1. **Always Start with the Version Header:**
   Every file must open with `northcel "0.1.0-draft"`.
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
northcel check scene.ncel --json
```
If `ok` is `false`, read the exact `line:column` error and fix it immediately.

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
3. Leave every other `layer`, `def`, and `stroke` untouched so the rest of the frame is guaranteed byte-identical.

---

## 4. Lessons from Phase B: Authoring 8 Frames of *Test Video 7* by Hand

In Phase B, an AI agent authored 8 representative frames (`1536×864`) of *Test Video 7* by hand across 3 look-and-fix rounds (`f0001`, `f0028`, `f0037`, `f0043`, `f0055`, `f0067`, `f0076`, `f0085`):

1. **Always use `cel` + `palette` (`v0.2`) instead of separate `layer` + `stroke` blocks:**
   In `v0.1`, writing a separate `layer` fill and `stroke` outline for every cloud, shirt, pant leg, and duck part doubled the token count (`8,830 B / 5,052 tok`) and caused gaps where the stroke drifted from the fill. Switching to `v0.2`'s `cel name(color: $shirt, outline: ($ink, 5px))` cut AI-authored file size by **46.6%** (`4,718 B / 3,303 tok`) and guaranteed zero fill-to-outline gaps.
2. **Beware the SSIM Trap on Hand-Authored Linework:**
   Adding fine interior lines in Round 2 and Round 3 (cloud outlines, facial features, grass tufts) makes the drawing look **much** more like a real cartoon to a human eye, yet can lower pixel-level Block SSIM by `0.01–0.02` if a 5px black outline is shifted by 4–8 pixels from the teacher's exact line position (because a shifted black line on white paper incurs a double pixel penalty). Judge AI-authored frames by **structural completeness + Edge IoU + visual inspection**, not raw pixel SSIM alone.
3. **Where an Unassisted LLM Struggles Without a Fitter:**
   - **Easy for an LLM (`0.88–0.93` SSIM):** Isolated heads (`f0001`), simple frontal standing poses (`f0028`), flat sky/ground horizons, and reusable props (`clouds`, `grass_tufts`).
   - **Hard for an LLM (`0.70–0.75` SSIM):** Complex foreshortened limbs (`f0037` airborne bent knees), articulated hands with 5 spread fingers (`f0055`, `f0067`), and overlapping seated legs (`f0076`, `f0085`). For complex character poses, pair an LLM layout/rig planner with a contour/part template library or fitted keyframe cels.

| Diagnostic | Cause | Fix |
| --- | --- | --- |
| `Expected 'dx,dy' pair at token N` | Mixed Base-63 (`:`) syntax with space-separated quarter-pixel syntax | Use `x0,y0:c1c2...` for Base-63 (`precision: 1px`) or `qx0,qy0 dx1,dy1 ...` for `precision: 0.25px`. |
| `Decoded ring has only 2 vertices (< 3)` | Closed contour ring has fewer than 3 distinct points | Use `stroke` for 2-point lines, or provide at least 3 distinct vertices for a `layer` ring. |
| `Use of undefined def block 'X'` | `use X(...)` called before or without `def X(...)` | Declare `def X(...) { ... }` inside the `scene` or `film` block. |
