# Contributing to NorthCel (`.ncel`)

Thanks for helping. NorthCel is a language with two implementations that must
agree, so the bar for a change is: **it parses, it renders the same in both
implementations, and the tests say so.**

## Ground rules

1. **Specification changes come first.** Any change to the lexical grammar, the
   EBNF, ring-chain encoding, or rendering semantics must be proposed against
    [`docs/spec/SPEC-0.6.0-draft.md`](docs/spec/SPEC-0.6.0-draft.md) (never edit an
   archived spec in place — add a new draft) and recorded in
   [`docs/DECISIONS.md`](docs/DECISIONS.md) and [`CHANGELOG.md`](CHANGELOG.md).
2. **Determinism is not negotiable.** Every change to
   `python/northcel/renderer.py` or `native/src/gl/` must keep
   `test_out_of_order_film_determinism` and `test_conformance_suite` green: the
   same input must produce identical bytes regardless of frame order, thread count
   or repeat count.
3. **Two implementations, one truth.** If you change a rendering rule, change it in
   both the Python reference and the native stage (MoonBit/GLSL) and prove they
   still agree on the conformance frame. A change that only lands in one of them is
   a bug, even if the tests of that one pass. The one documented exception is
   spec 0.4 (Decision 9): it is reference-only until a native release passes
   conformance case `05`, and the launchers route spec 0.4 documents to the
   reference rather than to native.
4. **Never claim more than you measured.** Diagnostics say `PARTIAL` when they are
   partial; a render says `python-reference` when it is not native. Passing the
   conformance suite proves agreement, not visual quality.

## Setup

```console
$ git clone https://github.com/syver777/northcel
$ cd northcel
$ python3 -m pip install -e ./python[dev]     # reference + CLI
$ npm --prefix js/northcel install            # JS pre-check (zero dependencies)
```

Requirements: Python ≥ 3.10 and Node ≥ 16. The native tree additionally needs the
MoonBit compiler (101 MB), a C compiler and Mesa/EGL headers — see
[`native/BUILD.md`](native/BUILD.md). A clean clone can run the Python reference
and the JS pre-check without any of that.

## Repository layout

```
python/                 the `northcel` distribution: reference implementation +
                        launcher (console scripts `northcel` and `ncel`)
python/northcel-native/ the `northcel-native` platform wheel (native bundle carrier)
js/northcel/            the `northcel` npm package: launcher, JS pre-check, guide
js/northcel-linux-x64/  the platform bundle npm package
native/                 MoonBit AST stage, GL host, shaders, pinned toolchain
docs/                   writing guide, patterns, gallery, errors, architecture, spec
editors/vscode/         TextMate grammar + VS Code language configuration
packaging/              install.sh, Homebrew formula, build and verify scripts
python/tests/           reference test suite        js/northcel/tests/  JS tests
tests/                  cross-implementation conformance runner
```

## Running the tests

```console
$ make test                # everything below
$ python3 -m pytest python/tests -q
$ npm --prefix js/northcel test
$ python3 js/northcel/scripts/sync-assets.py --check   # generated assets in sync
$ python3 tests/conformance.py                          # both implementations, both directions
$ python3 -m pip install opencv-python-headless==5.0.0.93 scikit-image==0.26.0  # tracing tests; Python 3.11+
```

The native tree has its own suite (needs the MoonBit compiler and a C toolchain):

```console
$ cd native && make && bash tests/run-tests.sh
```

## Development commands

```console
$ make test           # Python reference suite + JS tests + conformance
$ make lint           # ruff, node --check, generated-asset check, licence copies
$ make dist           # wheels + sdist + npm tarballs into dist/
$ make verify         # install the built artifacts into fresh dirs and render
```

## Continuous integration

CI lives at [`.github/workflows/ci.yml`](.github/workflows/ci.yml) and runs on
every push to `main`, on every pull request, and on demand
(`workflow_dispatch`) from the Actions tab.

| Job | Runner | What it proves |
| --- | --- | --- |
| `python 3.10` / `3.11` / `3.12` / `3.13` | ubuntu-latest | the reference implementation imports, lints (3.12 only: ruff) and passes its suite on every supported Python |
| `node 20` / `node 22` | ubuntu-latest | generated assets are in sync, the launcher/pre-check tests pass — including the two that spawn the *real* Python reference, so numpy and Pillow are installed for them — and `npm pack` ships exactly the expected files |
| `wheel build + install smoke test` | ubuntu-latest | sdist + wheel build, `twine check`, install into a clean venv, and `northcel`/`ncel`/`check`/`info`/`render` behave; the render receipt says `python-reference` / `native: false` |
| `conformance (both implementations)` | ubuntu-latest | reference probes and forward/reverse determinism; native agreement is reported as **SKIP**, never as a pass, because no native bundle ships in CI |
| `licence copies in sync` | ubuntu-latest | every `LICENSE-MIT`/`LICENSE-APACHE` copy is byte-identical to the root texts |
| `docs (snippets render, images match, errors reproduce)` | ubuntu-latest | every guide snippet checks and renders to the committed pixels, every `examples/patterns/*.ncel` renders and its contact sheet matches, every diagnostic in `docs/errors.md` is regenerated from the source, and every relative link/image resolves |
| `native build + conformance (manual)` | ubuntu-24.04 | provisions the MoonBit toolchain, builds the C GL host with Mesa/EGL, runs `native/tests/run-tests.sh` and compares native frames to the reference |

The native job only runs when asked, because it downloads a large toolchain and
builds C:

```console
$ gh workflow run ci.yml                       # Actions → CI → Run workflow also works
$ gh run watch "$(gh run list --workflow ci.yml --limit 1 --json databaseId -q '.[0].databaseId')"
```

## Generated files — do not hand-edit

| File | Generated by | Source of truth |
| --- | --- | --- |
| `js/northcel/rules.json` | `js/northcel/scripts/sync-assets.py` | `python/northcel/{config,parser,rings}.py` |
| `js/northcel/northcel/AGENT-GUIDE.md` | `js/northcel/scripts/sync-assets.py` | the `npm-guide:start/end` section of `docs/agent-guide.md` |
| `python/northcel/data/pins.json` | `packaging/scripts/gen_pins.py` | `native/toolchain.lock` |
| `*/LICENSE-MIT`, `*/LICENSE-APACHE` | copies | the two files in the repository root (CI compares bytes) |

## Pull requests

- One topic per pull request; keep the diff readable.
- Add a test that fails before your change and passes after it.
- Update `CHANGELOG.md` under `## [Unreleased]`.
- CI must be green: Python 3.10–3.13, JS on Node 20 and 22, `npm pack`, wheel build
  + install test, conformance. The native build job is manual
  (`workflow_dispatch`) because it downloads a 101 MB toolchain.

## Commits

Plain, imperative subject lines (`python: reject a zero-radius ring`). No
`git add -A` in a shared checkout, no force-push to `main`.

## Releases

The repository is the source; the registries are the distribution. The build,
publish order, deprecation aliases and the Homebrew formula bump are documented in
[`packaging/RELEASE.md`](packaging/RELEASE.md), and the install graph contract is
in [`packaging/DESIGN.md`](packaging/DESIGN.md).

- The **tools** version moves (`0.7.2`, `0.7.3`, …).
- The **language specification** moves only when the grammar or rendering
  semantics change (`0.6.0-draft` today), and an archived draft is never edited.
- A packaging-only release keeps `spec_version` and the native runtime build
  identical; `northcel doctor` prints both numbers so they cannot be confused.

## Licence

By contributing you agree that your contribution is dual licensed under
[MIT](LICENSE-MIT) OR [Apache-2.0](LICENSE-APACHE), at the user's option, and that
you have the right to license it that way.

## Code of conduct

Participation is covered by the [Code of Conduct](CODE_OF_CONDUCT.md).
