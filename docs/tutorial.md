# Tutorial: Your First NorthCel (`.ncel`) Scene & Film

## 1. Install `northcel`

```sh
pipx install northcel
# or inside a virtual environment:
pip install northcel
```

Verify the installation:

```sh
northcel --version
# -> northcel 0.2.1 (spec 0.2.0-draft)
```

---

With only Node, run `npx northcel guide` first, then
`npx northcel check first_lantern.ncel --require-full --json`. Without Python,
this reports `partial: true, validator: "js"` and exits 2 when the JS pre-check
finds no errors (1 on detected errors). Normal JS `check` without `--require-full`
exits 0 on a clean **PARTIAL** result, not full validation. Install Python above,
expose its environment's Python on PATH, repeat and require exit 0. Only Python
provides full parsing/semantics and rendering; JS checks structural mistakes,
rings and palette references, not ranges, defs or expression evaluation.

## 2. Author a Compact Animated `.ncel` Film

Create a file named `first_lantern.ncel`:

```ncel
northcel "0.1.0-draft"

film FirstLantern(width: 512, height: 512, fps: 12, frames: 6, precision: 0.25px, seed: 108) {
  paper { color: #101824, antialias_grid: 4, grain: 0.012 }

  def SeaWave(dx: 0, dy: 0) {
    stroke crest(color: #6CCFF6, taper: (4.5, 1.5), boil: 0.75px) {
      (40, 410), (180, 398), (330, 412), (470, 402)
    }
  }

  layer sea_base(color: #1B3B5A, rings: 1) { "0,1520 2048,0 0,528 -2048,0" }
  layer lantern_halo(color: #F4A261, rings: 1, boil: 0.6px, translate: (sin(t * 6.28318) * 14, 0)) { "920,640 208,0 40,120 -40,120 -208,0 -40,-120" }
  ribbon post_ink(color: #F8F9FA, boil: 0.4px) { (256, 480, 12), (256 + sin(t * 6.28318) * 6, 320, 9), (256 + sin(t * 6.28318) * 14, 190, 6) }
  bend_swarm rain_streaks(agents: 4, color: #E0FBFC, boil: 0.35px, translate: (lerp(-18, 18, t), lerp(0, 48, t))) { "320,240 24,72 -8,4 -24,-72|840,300 24,72 -8,4 -24,-72|1420,220 24,72 -8,4 -24,-72|1760,340 24,72 -8,4 -24,-72" }

  use SeaWave(dx: sin(t * 6.28318) * 10, dy: 0)
  use SeaWave(dx: cos(t * 6.28318) * -12, dy: 42)
}
```

---

`use SeaWave(dx: ..., dy: ...)` auto-translates expanded geometry once. Do not
also add `dx`/`dy` to its point coordinates. This is a corrected tutorial example;
the historical packaged lantern fixture keeps its original pixels.

## 3. Validate, Format, and Inspect

```sh
northcel check first_lantern.ncel --require-full
northcel fmt -w first_lantern.ncel
northcel info first_lantern.ncel
```

---

## 4. Render Frame 0 (Still Check) and Full Film

```sh
# Render frame 0 to inspect composition first:
northcel render first_lantern.ncel -o frame0.png --frame 0

# Render all 6 frames (and an MP4 if ffmpeg is installed):
northcel film first_lantern.ncel -o frames/ --mp4 first_lantern.mp4
```
