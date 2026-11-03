# `northcel` — The AI-Drawn Video Programming Language (`.ncel`)

**NorthCel** (`.ncel`) is North Noir's domain-specific programming language for AI-drawn images and frame-by-frame animation.

It combines the best properties of three complementary execution models into a single compact, deterministic format:

1. **MoonBit-style typed, declarative scene structure** — algebraic scene layers (`paper`, `def`/`use`, `layer`/`wash`, `stroke`, `ribbon`, `bend_swarm`), compact relative contour encodings (`0.25px` quarter-pixel deltas and `1px` Base-63 deltas), and strict `line:column` diagnostics that an AI coding agent can read and fix.
2. **Bend-style deterministic parallel evaluation** — repetitive organic marks (water droplets, beard bristles, wet hair strands, rain streaks, and line boil) are modeled as stateless agents whose output is a pure function of `(seed, frame_index, agent_id)`, independent of evaluation order.
3. **GLSL-style per-pixel supersampled rendering** — every frame is a pure function of `(time, seed, coordinates)` evaluated with even-odd winding parity on an `N×N` subpixel grid (default `4×4`, i.e., `0.25px` resolution) and box-integrated to 8-bit RGB/greyscale.

The reference implementation in this package (`northcel`) is a **pure-Python + NumPy renderer** requiring no GPU or external language compilers at user install time. MoonBit, Bend, and OpenGL/EGL GLSL remain optional documented backends.

## Install

```sh
pipx install northcel
# or
pip install northcel
```

Both `northcel` and the short alias `ncel` are installed on your `PATH`.

## CLI Commands

```sh
northcel check scene.ncel [--json]          # Parse and validate with line:column diagnostics
northcel fmt scene.ncel [-w] [--check]      # Canonical formatter
northcel info scene.ncel                    # JSON summary of layers, rings, vertices, and bytes
northcel render scene.ncel -o frame0.png    # Render a single frame (--frame N, --seed S)
northcel film film.ncel -o frames/ --mp4 out.mp4  # Render frame sequence + optional MP4 via ffmpeg
```

## Example (`lantern_film.ncel`)

```ncel
northcel "0.1.0-draft"

film LanternFilm(width: 512, height: 512, fps: 12, frames: 6, precision: 0.25px, seed: 108) {
  paper { color: #101824, antialias_grid: 4, grain: 0.012 }

  def SeaWave(dx: 0, dy: 0) {
    stroke crest(color: #6CCFF6, taper: (4.5, 1.5), boil: 0.75px) {
      (40 + dx, 410 + dy), (180 + dx, 398 + dy), (330 + dx, 412 + dy), (470 + dx, 402 + dy)
    }
  }

  layer sea_base(color: #1B3B5A, rings: 1) { "0,1520 2048,0 0,528 -2048,0" }
  layer lantern_halo(color: #F4A261, rings: 1, boil: 0.6px, translate: (sin(t * 6.28318) * 14, 0)) {
    "920,640 208,0 40,120 -40,120 -208,0 -40,-120"
  }
  ribbon post_ink(color: #F8F9FA, boil: 0.4px) {
    (256, 480, 12), (256 + sin(t * 6.28318) * 6, 320, 9), (256 + sin(t * 6.28318) * 14, 190, 6)
  }
  bend_swarm rain_streaks(agents: 4, color: #E0FBFC, boil: 0.35px, translate: (lerp(-18, 18, t), lerp(0, 48, t))) {
    "320,240 24,72 -8,4 -24,-72|840,300 24,72 -8,4 -24,-72|1420,220 24,72 -8,4 -24,-72|1760,340 24,72 -8,4 -24,-72"
  }

  use SeaWave(dx: sin(t * 6.28318) * 10, dy: 0)
  use SeaWave(dx: cos(t * 6.28318) * -12, dy: 42)
}
```

## Documentation

Full language specification (`0.1.0-draft`), AI-agent guide, benchmarks, and tutorials live at:
- Website: https://northnoir.com/northcel
- Repository docs: `docs/northcel/`
