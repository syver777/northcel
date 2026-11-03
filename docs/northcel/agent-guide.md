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

## 4. Common Errors & Fixes

| Diagnostic | Cause | Fix |
| --- | --- | --- |
| `Expected 'dx,dy' pair at token N` | Mixed Base-63 (`:`) syntax with space-separated quarter-pixel syntax | Use `x0,y0:c1c2...` for Base-63 (`precision: 1px`) or `qx0,qy0 dx1,dy1 ...` for `precision: 0.25px`. |
| `Decoded ring has only 2 vertices (< 3)` | Closed contour ring has fewer than 3 distinct points | Use `stroke` for 2-point lines, or provide at least 3 distinct vertices for a `layer` ring. |
| `Use of undefined def block 'X'` | `use X(...)` called before or without `def X(...)` | Declare `def X(...) { ... }` inside the `scene` or `film` block. |
