# NorthCel (`.ncel`)

**The open drawing language for AI-drawn video.** A `.ncel` file is a small,
human-readable program that describes a drawing — paper, palettes, washes, cels,
strokes, ribbons, parallel swarms, frame deltas — and NorthCel turns it into
frames. Nothing is baked into an opaque clip: a frame is *computed* from the
program, so a creator (or an AI model) can change one contour, one colour, or one
frame of timing and re-render only what changed.

[![CI](https://github.com/syver777/northcel/actions/workflows/ci.yml/badge.svg)](https://github.com/syver777/northcel/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/northcel.svg)](https://pypi.org/project/northcel/)
[![npm](https://img.shields.io/npm/v/northcel.svg)](https://www.npmjs.com/package/northcel)
[![License: MIT OR Apache-2.0](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](#licence)

```ncel
northcel "0.2.0-draft"

scene StarterScene(width: 320, height: 180, fps: 12, precision: 0.25px) {
  paper { color: #F6F1E7, antialias_grid: 4, grain: 0.01 }
  layer sky(color: #BFD8E8, rings: 1) { "0,0 1280,0 0,560 -1280,0" }
  layer ground(color: #D9C9A3, rings: 1) { "0,560 1280,0 0,160 -1280,0" }
  layer sun(color: #E8A33D, rings: 1, boil: 0.5px) { "640,440 96,0 0,96 -96,0" }
  stroke horizon_ink(color: #3A4A5A, taper: (3, 2)) { (0, 140), (320, 140) }
  ribbon path(color: #6E9A76) { (30, 168, 10), (160, 156, 6), (290, 166, 10) }
}
```

```console
$ northcel render starter.ncel -o frame.png
$ northcel film   lantern_film.ncel -o out/ --frames 0..5 --mp4 out.mp4
```

## What it is

NorthCel is a **drawing language**, not an image model. Two implementations read
the same program and must agree:

| Implementation | What it is | Where it runs |
| --- | --- | --- |
| **Native runtime** | MoonBit typed AST + ring decoders + NCIR, **Bend 0.2.38 / HVM 2.0.22** swarm evaluation, **GLSL 4.30** subpixel rasterisation on a Mesa/EGL context | Linux x86_64 today |
| **Python reference** | Pure Python + NumPy/SciPy-free renderer; the normative reference and conformance oracle, plus the parser, validator and formatter | Linux, macOS, Windows |

The native runtime never calls Python. The Python reference is a **labelled
fallback**, not a second native path: on a platform without the native bundle the
CLI prints one line to stderr and every receipt carries
`"renderer": "python-reference"`. It never claims a native render.

The native pipeline, stage by stage:

1. **MoonBit** (`ncel-ast`) lexes and parses the full `0.2` grammar, resolves
   `palette`/`$ref`, expands `def`/`use` and frame deltas, decodes every ring
   chain (`0.25px`, `0.25px-b63`, `1px` Base-63), builds closed ribbons for strokes
   and emits a compact binary IR plus the Bend program for `bend_swarm`s.
2. **Bend/HVM2** (`bend`, `hvm`) evaluates every swarm agent in an
   order-independent binary-fork tree; the host validates agent/ring/vertex counts
   before using the result.
3. **GLSL** (`ncel-gl`) opens a headless surfaceless Mesa/EGL OpenGL 4.5 context,
   compiles `draw430.glsl`, and performs the normative `aa×aa` even-odd subpixel
   integration. Software rasterisation (llvmpipe) means **no GPU is required**, and
   output is byte-identical on every repeat.

## Install

**One name everywhere: `northcel`.** The command `ncel` is a short alias for the
same binary — it is never a separate package.

| Path | Command | Native runtime? |
| --- | --- | --- |
| pip | `pip install northcel` | yes on Linux x86_64 (installs `northcel-native`); Python reference elsewhere |
| pipx | `pipx install northcel` | same as pip |
| npm | `npm install -g northcel` | yes on Linux x86_64 (installs `northcel-linux-x64`); honest error elsewhere |
| Homebrew | `brew tap syver777/northcel && brew install northcel` | yes on Linux; the formula refuses macOS |
| curl | `curl -fsSL https://raw.githubusercontent.com/syver777/northcel/main/packaging/install.sh \| bash` | yes on Linux x86_64 |

```console
$ northcel doctor     # every stage, version, shader hash and the platform verdict
$ northcel verify     # renders the conformance frame and a 6-frame film, twice
$ northcel guide      # offline authoring guide
```

`northcel doctor` exits `0` only when the native runtime is genuinely usable, and
`3` with the exact reason when it is not. `northcel verify` renders the pinned
conformance frame plus a six-frame film twice and compares hashes; a failure prints
both hashes and the GL renderer so it is diagnosable.

### Platform matrix

| Platform | `pip install northcel` | `npm install -g northcel` | Native render |
| --- | --- | --- | --- |
| Linux x86_64, glibc ≥ 2.39 (Ubuntu 24.04+, Debian 13, Fedora 40+, RHEL 10) | works | works | **yes — verified** |
| Linux x86_64, older glibc | launcher only, clear message | honest exit 3 | no (pinned Bend/HVM need `GLIBC_2.39`) |
| Linux aarch64 | launcher only | honest exit 3 | no |
| macOS | installs; `doctor` exit 3; renders labelled `python-reference` | honest exit 3 | no — Apple's GL stops at 4.1; needs Vulkan/MoltenVK or a tested GL 4.1 path |
| Windows | same as macOS | same | no |

The native runtime ships **inside** the package (≈2.8 MB compressed, 7.4 MB
unpacked): MoonBit-compiled stage, pinned `bend` + `hvm` binaries, shaders and a
`bundle-manifest.json` with a sha256 for every file. Nothing is downloaded at first
run. The MoonBit **compiler** (101 MB) is optional and only needed to rebuild the
native tree: `northcel toolchain install`.

## The language at a glance

| Construct | Purpose |
| --- | --- |
| `scene` / `film` | one frame, or a frame sequence with `fps` and per-frame overrides |
| `paper` | background colour, `antialias_grid` (subpixel grid), `grain` |
| `palette` + `$name` | shared colours, referenced by value instead of repeated hex |
| `def` / `use` | reusable groups with parameters and per-frame `dx`/`dy` |
| `layer` / `wash` / `cel` | filled shapes; `cel` draws a coupled `outline:`, `ink:`, `ink_width:` |
| `stroke` | tapered line: `taper: (start, end)` |
| `ribbon` | per-vertex width along a path — thickness that varies as it moves |
| `bend_swarm` / `swarm` | parallel agents evaluated by Bend/HVM2 (rings, iterations, transforms) |
| `boil` | stateless per-frame jitter with an exact 32-bit hash — hand-drawn wobble |
| `frame k { }` | in-place deltas for that frame only |
| `drop` | remove a shape for the frames where it should not exist |

Rings are stored as integer deltas at `0.25px` or as Base-63 strings at `0.25px` or
`1px`, so a 4-megapixel contour is a few hundred bytes of text. The full grammar,
the rendering semantics and the conformance rules are in
[`docs/spec/SPEC-0.2.0-draft.md`](docs/spec/SPEC-0.2.0-draft.md); `0.1.0-draft` is
archived alongside it.

## Repository layout

```
python/                 the `northcel` distribution: reference implementation +
                        launcher (console scripts `northcel` and `ncel`)
python/northcel-native/ the `northcel-native` platform wheel (native bundle carrier)
js/northcel/            the `northcel` npm package: launcher, JS pre-check, guide
js/northcel-linux-x64/  the platform bundle npm package
native/                 MoonBit AST stage, GL host, shaders, pinned toolchain
docs/                   specification, reference, tutorial, guide, decisions
editors/vscode/         TextMate grammar + VS Code language configuration
packaging/              install.sh, Homebrew formula, build and verify scripts
python/tests/           reference test suite        js/northcel/tests/  JS tests
tests/                  cross-implementation conformance runner
```

## Documentation

- [Documentation index](docs/README.md) — spec, tutorial, reference, FAQ
- [Tutorial: your first `.ncel` film](docs/tutorial.md)
- [Format & tooling reference](docs/reference.md)
- [AI-agent guide](docs/agent-guide.md) — how a coding agent authors and self-checks `.ncel`
- [Examples & measured benchmarks](docs/examples.md)
- [Decision log](docs/DECISIONS.md) · [Changelog](CHANGELOG.md)
- [Official readiness checklist](docs/official-checklist.md)

## Development

```console
$ make test           # Python reference suite + JS tests
$ make lint           # ruff (Python) + node --check
$ make dist           # wheels + sdist + npm tarballs into dist/
$ make verify         # install the built artifacts into fresh dirs and render
```

Requirements: Python ≥ 3.10, Node ≥ 16. The native tree additionally needs the
MoonBit compiler, a C compiler and Mesa/EGL headers — see
[`native/BUILD.md`](native/BUILD.md). A clean clone can run the Python reference
and the JS pre-check without any of that.

## Status

- **Version 0.3.1.** Language specification `0.2.0-draft` (backward compatible with
  `0.1.0-draft`).
- The native runtime is **verifiably deterministic** on Linux x86_64 with Mesa
  llvmpipe. Its output matches the Python reference on the conformance frame to
  0 differing pixels (PNG bytes differ only because the encoders differ).
- **No visual approval is implied by any test.** Passing conformance proves the
  renderers agree, not that a drawing is good.
- GPU GL is untested (everything here is software rasterisation); macOS/Windows
  native is a later phase; `ncel-*` binary names inside the native bundle are
  internal and unchanged.
- The npm `check` command without the native runtime or Python does a
  **structural pre-check only** and says `PARTIAL`; it never reports a document as
  valid. `--require-full` exits `2` instead of pretending.

## Deprecated names

Everything is `northcel` now. The older `ncel` / `ncel-native` names remain as
deprecated aliases so existing installations and scripts keep working:

| Old | Status |
| --- | --- |
| PyPI `ncel` | deprecated alias → installs `northcel`; use `pip install northcel` |
| PyPI `ncel-native` | deprecated alias → installs `northcel-native` |
| npm `@ncel/linux-x64` | deprecated alias → installs `northcel-linux-x64` |
| npm `ncel` | never published (npm rejected the bare name as too similar to others); the `ncel` **command** ships in `northcel` |

## Licence

Dual licensed under **[MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE)**, at your
option. Contributions are accepted under the same terms. The native tree vendors
`bend-lang 0.2.38` and `hvm 2.0.22`; their licences and attribution are recorded in
[`native/LICENSE-NOTES.md`](native/LICENSE-NOTES.md) and inside the published
bundle (`bundle/licenses/`).

NorthCel is developed alongside [North Noir](https://northnoir.com) — the studio
that uses it to author AI-drawn video — but it is an independent project with its
own specification, tests and release cycle.
