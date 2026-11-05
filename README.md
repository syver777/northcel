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

NorthCel is a **drawing language**, not an image model. A program is parsed and
turned into a compact intermediate representation by a MoonBit stage, `bend_swarm`
agents are evaluated by Bend/HVM2, and GLSL rasterises the result on a headless
Mesa/EGL context. The same file also runs through a pure-Python + NumPy reference
implementation, which is the conformance oracle and the fallback on platforms
without the native bundle; every render it produces is labelled
`"renderer": "python-reference"` in the receipt.

Because a frame is computed from the program, a film can be edited surgically: a
named `layer`, `stroke`, `ribbon` or `bend_swarm` changes in place, and only the
frames that depend on it need re-rendering. The same input always produces the
same bytes, independent of frame order or thread count.

## Install

**One name everywhere: `northcel`.** The command `ncel` is a short alias for the
same binary — it is never a separate package.

```console
$ pip install northcel
$ npm install -g northcel
$ brew tap syver777/northcel && brew install northcel
$ curl -fsSL https://github.com/syver777/northcel/releases/latest/download/install.sh | bash
```

All four install the same CLI, which uses the native runtime where it can and the
labelled Python reference everywhere else.

## First steps

```console
$ northcel doctor     # every stage, version, shader hash and the platform verdict
$ northcel verify     # renders the conformance frame and a 6-frame film, twice
$ northcel guide      # offline authoring guide
$ northcel render starter.ncel -o frame.png
$ northcel film lantern_film.ncel -o out/ --frames 0..5 --mp4 out.mp4
```

`northcel doctor` exits `0` only when the native runtime is genuinely usable, and
`3` with the exact reason when it is not. `northcel verify` renders the pinned
conformance frame plus a six-frame film twice and compares hashes; a failure prints
both hashes and the GL renderer so it is diagnosable.

**Platforms:** the native runtime is supported on Linux x86_64 (glibc ≥ 2.39:
Ubuntu 24.04+, Debian 13, Fedora 40+, RHEL 10). On macOS, Windows and other Linux
architectures, `pip install northcel` installs the CLI and every render goes
through the labelled Python reference.

## Documentation

- **[The writing guide](docs/guide/README.md)** — start here: install, first file,
  then every construct with a rendered example and its real diagnostic.
- **[Patterns cookbook](docs/patterns/README.md)** — ten complete animated
  programs with contact sheets, sizes and pitfalls.
- **[Common errors](docs/errors.md)** — every diagnostic, generated from the
  source and reproduced in CI.
- **[Architecture](docs/architecture.md)** — what the stages own, the pipeline
  order, determinism and the platform matrix.
- **[Gallery](docs/gallery.md)** — a 90-frame AI-drawn film recreated in `.ncel`,
  the lantern film and the pattern examples.
- **[AI-agent guide](docs/agent-guide.md)** — the first ten minutes, the
  look-and-fix loop, and the traps that still compile.
- **[Documentation index](docs/README.md)** — the full map.
- [Format & tooling reference](docs/reference.md) — the CLI and the validation
  contract.
- [Specification](docs/spec/SPEC-0.2.0-draft.md) · [changelog](CHANGELOG.md) ·
  [decision log](docs/DECISIONS.md).

## Contributing

Building, testing, the repository layout and the release process are documented in
[`CONTRIBUTING.md`](CONTRIBUTING.md). The native tree additionally needs the
MoonBit compiler, a C compiler and Mesa/EGL headers — see
[`native/BUILD.md`](native/BUILD.md).

## Licence

Dual licensed under **[MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE)**, at your
option. Contributions are accepted under the same terms. The native tree vendors
`bend-lang 0.2.38` and `hvm 2.0.22`; their licences and attribution are recorded in
[`native/LICENSE-NOTES.md`](native/LICENSE-NOTES.md) and inside the published
bundle (`bundle/licenses/`).

NorthCel is developed alongside [North Noir](https://northnoir.com) — the studio
that uses it to author AI-drawn video — but it is an independent project with its
own specification, tests and release cycle.
