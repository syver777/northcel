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
| write your first film | [Tutorial](tutorial.md) |
| look up a statement or attribute | [Format & tooling reference](reference.md) |
| read the normative grammar | [Specification `0.2.0-draft`](spec/SPEC-0.2.0-draft.md) (and the archival [`0.1.0-draft`](spec/SPEC-0.1.0-draft.md)) |
| have an AI agent author `.ncel` | [AI-agent guide](agent-guide.md) |
| see what the examples measure | [Examples & benchmarks](examples.md) |
| understand why it is built this way | [Decision log](DECISIONS.md) |
| know what is finished and what is not | [Readiness checklist](official-checklist.md) |
| train a model to emit `.ncel` | [Training plan](training-plan.md) |
| connect it to an editor, API or agent | [Integration plan](integration-plan.md) |
| get a short answer | [FAQ](faq.md) |

Project-level documents live in the repository root:
[README](../README.md) · [CHANGELOG](../CHANGELOG.md) ·
[CONTRIBUTING](../CONTRIBUTING.md) · [SECURITY](../SECURITY.md) ·
[Code of Conduct](../CODE_OF_CONDUCT.md) ·
[MIT](../LICENSE-MIT) OR [Apache-2.0](../LICENSE-APACHE).

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
