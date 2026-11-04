# `northcel` — The AI-Drawn Video Programming Language (`.ncel`)

**NorthCel** (`.ncel`) is North Noir's domain-specific programming language for AI-drawn images and frame-by-frame animation.

It combines the best properties of three complementary execution models into a single compact, deterministic format:

1. **MoonBit-style typed, declarative scene structure** — algebraic scene layers (`paper`, `def`/`use`, `layer`/`wash`, `stroke`, `ribbon`, `bend_swarm`), compact relative contour encodings (`0.25px` quarter-pixel deltas and `1px` Base-63 deltas), and strict `line:column` diagnostics that an AI coding agent can read and fix.
2. **Bend-style deterministic parallel evaluation** — repetitive organic marks (water droplets, beard bristles, wet hair strands, rain streaks, and line boil) are modeled as stateless agents whose output is a pure function of `(seed, frame_index, agent_id)`, independent of evaluation order.
3. **GLSL-style per-pixel supersampled rendering** — every frame is a pure function of `(time, seed, coordinates)` evaluated with even-odd winding parity on an `N×N` subpixel grid (default `4×4`, i.e., `0.25px` resolution) and box-integrated to 8-bit RGB/greyscale.

The reference implementation in this package (`northcel`) is a **pure-Python + NumPy renderer** requiring no GPU or external language compilers at user install time. MoonBit, Bend, and OpenGL/EGL GLSL remain optional documented backends.

**Tool version 0.2.1; language specification unchanged at 0.2.0-draft** (0.1 files
remain supported). Two packages share the name, not the same capabilities:

| Package | Includes | Does not include |
|---|---|---|
| PyPI `northcel` | Full reference parser/semantic validator, formatter, CPU renderer, guide | Native audio or a prompt-to-video model |
| npm `northcel` | Zero-dependency **partial** JS structural pre-check, offline guide, Python CLI bridge | JS renderer/formatter or full validation without Python |

## Node-only / npm quick start

```sh
npx northcel guide
npx northcel check film.ncel --json
npx northcel check film.ncel --require-full --json
```

Without Python, text output always says **PARTIAL (JS pre-check only)**, never
OK. JSON has `partial: true`, `validator: "js"`, `reason` and `next`. `ok: true`
means only that the pre-check found no error. Exit **0** = clean partial;
**1** = detected error/unreadable file; **2** = clean partial with
`--require-full` (or invalid check arguments). Thus the last command above
**cannot succeed fully in a Node-only environment**. Never ship on `ok` alone.

The JS pre-check catches missing roots/unbalanced delimiters, unknown
scene/film statements (including `frames:` wrongly placed in the body), malformed
headers/point structure, invalid ring integer/Base-63 payloads and unknown
`$palette` references. Duplicate primitive names warn: legal layer/cel replacement
is not banned. It does **not** evaluate numeric ranges, variable bindings,
function names/arity, def resolution, render-time expressions or visual quality.
It is not a full JS grammar implementation or a conformance validator.

For certainty, install the Python package below and expose that environment's
`python3` or `python` on PATH, or the Python `northcel` entrypoint installed by
pipx. npm probes Python modules first, then Python-shebang CLI scripts on PATH,
delegates all validation/rendering to the first available reference CLI, and
passes through diagnostics and exit status (0 valid, 1 invalid). It never hides
a failed Python check behind JS. A terminated Python child is nonzero.
Python 0.2.1 JSON adds `partial: false, validator: "python"`; older Python JSON
is passed through unchanged. The wrapper consumes `--require-full` for older
Python compatibility. Run **`npx northcel check film.ncel --require-full --json`**
and require exit 0 before claiming full validation, then render and inspect.
Node-only `render`/`film` fail with exit 1 and install guidance.

`npx northcel guide` prints the compact authoring skeleton, five language
features, common mistakes and look-and-fix loop offline; it is generated verbatim
from `docs/northcel/agent-guide.md` and shipped in the package. `--version`
reports the Python version when delegated, otherwise npm's version marked
`js-validator`. The full validation/coverage contract is in
`docs/northcel/reference.md` in the repository.

## Install

```sh
pipx install northcel
# or
pip install northcel
```

Both `northcel` and the short alias `ncel` are installed on your `PATH`.

## CLI Commands

```sh
northcel guide                              # Compact offline authoring guide
northcel check scene.ncel [--json] [--require-full] # Python full check / npm partial fallback
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
      (40, 410), (180, 398), (330, 412), (470, 402)
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

`use` applies `dx`/`dy` once automatically. Keep those offsets out of the
definition's coordinates, or it moves twice. Other named parameters can appear
in expressions normally. The banked historical lantern fixture retains its
original pixels; this corrected authoring example avoids that trap.

## Documentation

Full language specification (`0.2.0-draft`), AI-agent guide, benchmarks, and tutorials live at:
- Website: https://northnoir.com/northcel
- Repository docs: `docs/northcel/`

An alternative local film workflow is `pip install "northnoir[ncel]"`, then
`northnoir init ink --language ncel --duration 3 --fps 24`,
`northnoir check ink/scene.ncel`, `northnoir render ink/scene.ncel -o ink/video.mp4`.
North Noir CLI keeps `scene.html` as default; `.ncel` is explicit and optional.
NorthCel output is silent; no hosted NorthCel Studio/API/MCP support is implied.
