# NorthCel (`.ncel`) — documentation

**NorthCel** is an open drawing language for AI-drawn video: a `.ncel` file is a
small program that describes an image or a frame sequence, and NorthCel computes
the frames.

- **Name:** NorthCel · **Extension:** `.ncel`
- **Commands:** `northcel` (short alias `ncel`)
- **Packages:** `northcel` on PyPI and npm (plus the `northcel-native` /
  `northcel-linux-x64` platform artifacts)
- **Version:** tools `0.3.1`; specification `0.2.0-draft` (backward compatible with
  `0.1.0-draft`)
- **Source:** <https://github.com/syver777/northcel>

## Start here

| If you want to… | Read |
| --- | --- |
| learn the language in order | **[The writing guide](guide/README.md)** — 14 numbered pages, every construct with a rendered example and its real diagnostic |
| copy a working animation | **[Patterns cookbook](patterns/README.md)** — ten complete programs with contact sheets, sizes and pitfalls |
| see what it looks like | **[Gallery](gallery.md)** |
| fix an error message | **[Common errors](errors.md)** — generated from the source, reproduced in CI |
| understand the runtime | **[Architecture](architecture.md)** — grammar → swarms → pixels, determinism, platforms |
| have an AI agent author `.ncel` | **[AI-agent guide](agent-guide.md)** |
| look up a CLI flag or the check contract | **[Format & tooling reference](reference.md)** |
| read the normative grammar | [Specification `0.2.0-draft`](spec/SPEC-0.2.0-draft.md) (and the archival [`0.1.0-draft`](spec/SPEC-0.1.0-draft.md)) |
| see what the examples measure | [Examples & measurements](examples.md) |
| understand why it is built this way | [Decision log](DECISIONS.md) |
| get a short answer | [FAQ](faq.md) |

Project-level documents live in the repository root:
[README](../README.md) · [CHANGELOG](../CHANGELOG.md) ·
[CONTRIBUTING](../CONTRIBUTING.md) · [SECURITY](../SECURITY.md) ·
[Code of Conduct](../CODE_OF_CONDUCT.md) ·
[MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE).

## The guide, page by page

| # | Page | Construct |
| ---: | --- | --- |
| 1 | [Getting started](guide/01-getting-started.md) | install, `doctor`, `verify`, first file |
| 2 | [The scene model](guide/02-the-scene-model.md) | `scene` vs `film`, header, paint order |
| 3 | [Paper and canvas](guide/03-paper-and-canvas.md) | `paper`, grid, grain |
| 4 | [Palette and colour](guide/04-palette-and-colour.md) | `palette`, `$ref`, hex/`rgb`/`tone` |
| 5 | [Cels, layers and outlines](guide/05-cels-layers-and-outlines.md) | `layer`/`wash`/`cel`, holes, `outline:` |
| 6 | [Strokes and ribbons](guide/06-strokes-and-ribbons.md) | `taper:`, per-point widths |
| 7 | [Definitions and parameters](guide/07-def-use-and-parameters.md) | `def`/`use`, `dx`/`dy` |
| 8 | [Films, frame overrides and `drop`](guide/08-films-and-frame-overrides.md) | `frames`, `frame k`, `drop` |
| 9 | [Boil and seeded variation](guide/09-boil-and-seeded-variation.md) | stateless wobble |
| 10 | [Contour encodings](guide/10-contour-encodings.md) | `0.25px`, `0.25px-b63`, `1px` |
| 11 | [`bend_swarm`](guide/11-bend-swarm.md) | many independent marks |
| 12 | [Diagnostics and errors](guide/12-diagnostics-and-errors.md) | the check contract |
| 13 | [Performance and limits](guide/13-performance-and-limits.md) | measured timings, limits |
| 14 | [Editing one frame surgically](guide/14-editing-one-frame.md) | the delta recipe |

[`tutorial.md`](tutorial.md) points to the matching guide pages.
[`reference.md`](reference.md) covers the CLI and the validation contract; the
grammar reference lives in the guide and the specification.

## Machine-checked docs

The documentation is part of CI, not a side folder:

```console
$ python docs/scripts/build_docs_assets.py   # render every image + write expected.json
$ python docs/scripts/check_docs.py          # verify snippets, images, errors, links
```

`check_docs.py` extracts every `.ncel` snippet from the guide, runs `northcel
check` and renders it, compares the pixels with the committed expectation,
renders every `examples/patterns/*.ncel` and its contact sheet, reproduces every
diagnostic in [errors.md](errors.md), and verifies every relative link and image
path. The `docs` job in CI runs it on every push, so a snippet that does not
render, an image that does not match its source, and a dead link all fail the
build. See [architecture](architecture.md#the-docs-check).

## One command, two implementations

`pip install northcel` and `npm install -g northcel` install the same CLI. It runs
the **native runtime** where it can (Linux x86_64: MoonBit typed AST, Bend/HVM2
swarms, GLSL 4.30 on Mesa/EGL) and the **Python reference implementation**
elsewhere, always labelled `python-reference` — never called native.

The npm package can also answer `check` with a zero-dependency **structural
pre-check**. That answer is always marked `PARTIAL`; it never claims a document is
valid. See the [validation contract](reference.md#validation-contract) and
[the npm package README](../js/northcel/README.md).

North Noir (the studio that uses NorthCel) is a separate product: no hosted
NorthCel Studio, API or MCP support is implied by this repository.
