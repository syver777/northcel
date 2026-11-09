# Releasing NorthCel

## 0.5.0 candidate — spec 0.4.0-draft (tools only)

Only the tools move: `northcel` (PyPI) 0.5.0, `northcel` (npm) 0.5.0 and the
deprecated `ncel` PyPI alias 0.5.0 (`northcel==0.5.0`). The native runtime is not
rebuilt: `northcel-native`, `ncel-native`, `northcel-linux-x64`,
`native/toolchain.lock` and `python/northcel/data/pins.json` stay at 0.4.0 /
spec 0.3, and the 0.5.0 packages keep depending on `northcel-native==0.4.0` and
`northcel-linux-x64@0.4.0`. Spec 0.4 documents are routed to the Python reference
by both launchers (Decision 9).

Before publishing: the Python suite (with `northcel[fit]`), JS tests, conformance,
docs check, `make lint`, and a fresh-venv install whose `northcel render` of
`examples/patterns/12-polishing-ai-frames.ncel` prints the spec 0.4 routing reason
on Linux x86_64 with the native bundle present. Homebrew (`packaging/homebrew`) and
`packaging/install.sh` still pin 0.4.0; update their URLs/SHA-256 and default
version only from the published 0.5.0 artifacts.

## 0.4.0 candidate — spec 0.3.0-draft

Tools and native runtime both move to 0.4.0 for anchored transforms/easing and
offline fitting/tween authoring; 0.2 programs retain their pixels. The original
toolchain is now fetched from immutable official compiler-version URLs.

Release gates: reference + optional fitting tests; native build/tests; both-way
conformance and shuffled determinism; native `verify` from fresh built installs;
docs/lint/generated assets; green GitHub CI including the manual native job; and
the local code-only smoothing study's improved video. Never publish an unchecked
artifact. Version 0.4.0 publication receipts are added only after live verification.

Build with `packaging/scripts/build_python.sh`, `build_npm.sh` and `verify.sh`.
The deprecated PyPI aliases depend on the matching new packages. PyPI order is
`northcel-native`, then `northcel` wheel/sdist, then aliases. Credentials are passed
in the environment, never printed or written to artifacts.

**npm 0.4.0 is prepare/verify only. Do not publish it without the owner's separate
browser approval.** The two tarballs are `northcel-linux-x64-0.4.0.tgz` and
`northcel-0.4.0.tgz`. The old `publish_0_3_1.sh` is historical and publishes npm;
it MUST NOT be used for this task.

Homebrew must pin the actual published 0.4.0 sdist/native-wheel URLs and SHA-256,
and the tap mirror must match. Do not claim a brew install was tested merely
because the same wheels passed in a fresh venv.

The repository is the source; the registries are the distribution. A release is a
set of artifacts at one version, in a fixed order, plus optional deprecated aliases.

## Registry state

| Registry | Name | Latest | Notes |
| --- | --- | --- | --- |
| PyPI | `northcel` | **0.4.0** | the one package a user installs: reference + launcher, scripts `northcel` and `ncel` |
| PyPI | `northcel-native` | **0.4.0** | the Linux x86_64 platform wheel `northcel` depends on; unchanged for 0.5.0 |
| PyPI | `ncel` | 0.4.0 (deprecated) | alias that depends on `northcel`; publish 0.5.0 with this release |
| PyPI | `ncel-native` | 0.4.0 (deprecated) | alias that depends on `northcel-native`; unchanged |
| npm | `northcel` | **0.4.0** | the launcher + partial pre-check; 0.5.0 is the tools release |
| npm | `northcel-linux-x64` | **0.4.0** | the native bundle; unchanged |
| npm | `@ncel/linux-x64` | 0.2.1 (deprecated) | alias for the bundle; do not publish |

`0.3.1` was chosen for that historical release because npm `0.3.0` already existed. 0.5.0 is the tools-only release described at the top of this file.

## Historical — 0.3.1, published to PyPI on 2026-11-04

Uploaded, in this order, and verified afterwards:

| File | Bytes | sha256 |
| --- | ---: | --- |
| `northcel_native-0.3.1-py3-none-manylinux_2_39_x86_64.whl` | 2,815,158 | `bfa79300df1acbc200be245d64bbdcb7b057f22c2be40a5bda409fd90b9e6add` |
| `northcel-0.3.1-py3-none-any.whl` | 165,595 | `836e36f66c907317f0f6da44bb5eae0101ce0e8af652b3b36a369ef9b3b5afd8` |
| `northcel-0.3.1.tar.gz` | 164,430 | `57a90003b005864bdf033d686a89b33a3577a81be623a8ca4b6388c9566aeca5` |
| `ncel-0.3.1-py3-none-any.whl` (deprecated) | — | on PyPI |
| `ncel_native-0.3.1-py3-none-manylinux_2_39_x86_64.whl` (deprecated) | — | on PyPI |

Evidence: a fresh venv, `pip install northcel==0.3.1` from the
public index with no local artifacts → `northcel doctor` exit 0 (native, 13/13
checksums, GL 4.5 Mesa 25.2.8 at homegrown homebrew paths), `ncel verify` 5/5
(conformance sha256 `be0eb036…` = pinned), and a real 1024×1024 native render whose
sha256 equals the pinned conformance hash. `pip install ncel==0.3.1` pulls
`northcel` + `northcel-native` and runs the same launcher.

npm 0.3.1 is **published** (2026-11-04): `northcel` and `northcel-linux-x64` both resolve to 0.3.1, and install from the public registry with a global install.

## Build and prove

```sh
bash packaging/scripts/build_python.sh        # wheels + sdist -> dist/python
bash packaging/scripts/build_npm.sh           # tarballs        -> dist/npm
bash packaging/scripts/verify.sh              # installs both paths into /tmp and renders
python3 packaging/scripts/publish_0_3_1.sh --dry-run
```

`build_python.sh` needs `native/artifacts/ncel-native-0.2.0-linux-x86_64/` (the
native build for the pinned runtime). If it is absent it tries to build the native
tree, which needs the MoonBit compiler and a C toolchain — see `native/BUILD.md`.
`build_npm.sh` needs the same artifacts.

Expected artifacts (fill the sizes/SHA-256 from the actual build before publishing):

| File | Notes |
| --- | --- |
| `northcel-0.5.0-py3-none-any.whl` | reference + launcher (tools only) |
| `northcel-0.5.0.tar.gz` | sdist |
| `northcel-0.5.0.tgz` (npm) | launcher + pre-check |
| native artifacts | **do not rebuild**; `northcel-native` / `northcel-linux-x64` stay 0.4.0 |

## Publish, in this order

0.5.0 is tools-only: do not upload `northcel-native` or
`northcel-linux-x64` again. A platform artifact from 0.4.0 already satisfies the
dependency; verify it exists first.

```sh
# 1. PyPI — the reference + launcher (native 0.4.0 is already published)
python3 -m twine upload --non-interactive \
  dist/python/northcel-0.5.0-py3-none-any.whl dist/python/northcel-0.5.0.tar.gz

# 2. npm — the launcher only (northcel-linux-x64 stays 0.4.0)
npm publish dist/npm/northcel-0.5.0.tgz --access public

# 3. optional: the deprecated PyPI alias (it only depends on northcel==0.5.0)
python3 -m build --outdir dist/deprecated packaging/deprecated/pypi-ncel
python3 -m twine upload --non-interactive dist/deprecated/*
( cd packaging/deprecated/npm-ncel-linux-x64 && npm publish --access public )
npm deprecate "@ncel/linux-x64@0.2.1" "NorthCel is one package now: npm install -g northcel"
```

Credentials: `TWINE_USERNAME=__token__` + `TWINE_PASSWORD` (or `~/.pypirc`) for
PyPI, `NPM_TOKEN` or `npm login` for npm. `publish_0_3_1.sh` reads the PyPI token
from the `NORTH_NOIR_PYPI_API` environment variable, maps it to `TWINE_PASSWORD`
(never echoed, never written to disk) and refuses to start from a dirty tree.

A note from the 0.3.1 run that is not obvious: the public simple index can serve a
stale page for a minute or two right after an upload. `pip install` said
"No matching distribution found for northcel==0.3.1" for the dependency of `ncel`
while `curl https://pypi.org/simple/northcel/` already listed the file; retrying
with `--no-cache-dir` a minute later worked. Retry before assuming a bad artifact.

## After publishing

```sh
python3 -m venv /tmp/nc && /tmp/nc/bin/pip install --no-cache-dir northcel==0.5.0
/tmp/nc/bin/northcel doctor && /tmp/nc/bin/northcel verify   # 5/5, hash be0eb036…
npm install -g northcel@0.5.0 && northcel verify

git tag -a v0.5.0 -m "NorthCel 0.5.0" && git push origin v0.5.0
```

## Homebrew formula

`packaging/homebrew/Formula/northcel.rb` pins the **published** artifacts: since
0.4.0 that is two of them — the `northcel` sdist (this formula's `url`) and the
`northcel-native` platform wheel. To re-pin, take the `url`/`sha256` pairs from
`https://pypi.org/pypi/<name>/<version>/json`, bump `version` in `test do`, and run:

```sh
brew audit --strict --formula ./packaging/homebrew/Formula/northcel.rb
brew style ./packaging/homebrew/Formula/northcel.rb
brew install --build-from-source ./packaging/homebrew/Formula/northcel.rb
northcel doctor && northcel verify && brew test northcel
```

The tap repository `syver777/homebrew-northcel` is the published copy; commit the
same change there.

## Version policy

- The **tools** version moves (`0.3.1`, `0.3.2`, …).
- The **language specification** moves only when the grammar or rendering
  semantics change (`0.4.0-draft` today), and an archived draft is never edited.
- A packaging-only release keeps `spec_version` and the native runtime build
  identical; `northcel doctor` prints both numbers so they cannot be confused.
