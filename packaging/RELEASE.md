# Releasing NorthCel

The repository is the source; the registries are the distribution. A release is a
set of artifacts at one version, in a fixed order, plus optional deprecated aliases.

## Registry state

| Registry | Name | Latest | Notes |
| --- | --- | --- | --- |
| PyPI | `northcel` | **0.3.1** | the one package a user installs: reference + launcher, scripts `northcel` and `ncel` |
| PyPI | `northcel-native` | **0.3.1** | the Linux x86_64 platform wheel `northcel` depends on |
| PyPI | `ncel` | 0.3.1 (deprecated) | alias that depends on `northcel` |
| PyPI | `ncel-native` | 0.3.1 (deprecated) | alias that depends on `northcel-native` |
| npm | `northcel` | 0.3.0 (0.3.1 tarballs prepared) | the launcher + partial pre-check |
| npm | `northcel-linux-x64` | 0.3.0 (0.3.1 tarballs prepared) | the native bundle |
| npm | `@ncel/linux-x64` | 0.2.1 (deprecated) | alias for the bundle |

`0.3.1` was chosen because npm `0.3.0` already exists and cannot be replaced.

## 0.3.1 — published to PyPI on 2026-11-04

Uploaded, in this order, and verified afterwards:

| File | Bytes | sha256 |
| --- | ---: | --- |
| `northcel_native-0.3.1-py3-none-manylinux_2_39_x86_64.whl` | 2,815,158 | `bfa79300df1acbc200be245d64bbdcb7b057f22c2be40a5bda409fd90b9e6add` |
| `northcel-0.3.1-py3-none-any.whl` | 165,595 | `836e36f66c907317f0f6da44bb5eae0101ce0e8af652b3b36a369ef9b3b5afd8` |
| `northcel-0.3.1.tar.gz` | 164,430 | `57a90003b005864bdf033d686a89b33a3577a81be623a8ca4b6388c9566aeca5` |
| `ncel-0.3.1-py3-none-any.whl` (deprecated) | — | on PyPI |
| `ncel_native-0.3.1-py3-none-manylinux_2_39_x86_64.whl` (deprecated) | — | on PyPI |

Evidence: a fresh venv on the publishing VM, `pip install northcel==0.3.1` from the
public index with no local artifacts → `northcel doctor` exit 0 (native, 13/13
checksums, GL 4.5 Mesa 25.2.8 at homegrown homebrew paths), `ncel verify` 5/5
(conformance sha256 `be0eb036…` = pinned), and a real 1024×1024 native render whose
sha256 equals the pinned conformance hash. `pip install ncel==0.3.1` pulls
`northcel` + `northcel-native` and runs the same launcher.

npm 0.3.1 was **prepared, not published** (no npm token on that VM): tarballs and
checksums are recorded in that session's hand-off; the npm commands are below.

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

Expected artifacts (measured 2026-11-04, Linux x86_64):

| File | Bytes |
| --- | ---: |
| `northcel-0.3.1-py3-none-any.whl` | 165,595 |
| `northcel-0.3.1.tar.gz` | 164,430 |
| `northcel_native-0.3.1-py3-none-manylinux_2_39_x86_64.whl` | 2,815,158 |
| `northcel-0.3.1.tgz` (npm, 13 files) | 45,973 |
| `northcel-linux-x64-0.3.1.tgz` (npm, 16 files) | 2,849,183 |

## Publish, in this order

A platform artifact must exist before the package whose dependency points at it.

```sh
# 1. PyPI — the native bundle first
python3 -m twine upload --non-interactive \
  dist/python/northcel_native-0.3.1-py3-none-manylinux_2_39_x86_64.whl

# 2. PyPI — the reference + launcher
python3 -m twine upload --non-interactive \
  dist/python/northcel-0.3.1-py3-none-any.whl dist/python/northcel-0.3.1.tar.gz

# 3. npm — the platform bundle first
npm publish dist/npm/northcel-linux-x64-0.3.1.tgz --access public

# 4. npm — the launcher
npm publish dist/npm/northcel-0.3.1.tgz --access public

# 5. optional: the deprecated aliases (they only depend on the real packages)
python3 -m build --outdir dist/deprecated packaging/deprecated/pypi-ncel
python3 -m build --outdir dist/deprecated packaging/deprecated/pypi-ncel-native
python3 -m twine upload --non-interactive dist/deprecated/*
( cd packaging/deprecated/npm-ncel-linux-x64 && npm publish --access public )
npm deprecate "@ncel/linux-x64@0.3.1" "NorthCel is one package now: npm install -g northcel"
```

Credentials: `TWINE_USERNAME=__token__` + `TWINE_PASSWORD` (or `~/.pypirc`) for
PyPI, `NPM_TOKEN` or `npm login` for npm. On the North Noir VM,
`northnoir-env bash -c …` exposes the long-lived PyPI token as
`NORTH_NOIR_PYPI_API`, and `publish_0_3_1.sh` maps it to `TWINE_PASSWORD` (never
echoed, never written to disk). The script refuses to start from a dirty tree.

A note from the 0.3.1 run that is not obvious: the public simple index can serve a
stale page for a minute or two right after an upload. `pip install` said
"No matching distribution found for northcel==0.3.1" for the dependency of `ncel`
while `curl https://pypi.org/simple/northcel/` already listed the file; retrying
with `--no-cache-dir` a minute later worked. Retry before assuming a bad artifact.

## After publishing

```sh
python3 -m venv /tmp/nc && /tmp/nc/bin/pip install --no-cache-dir northcel==0.3.1
/tmp/nc/bin/northcel doctor && /tmp/nc/bin/northcel verify   # 5/5, hash be0eb036…
npm install -g northcel@0.3.1 && northcel verify

git tag -a v0.3.1 -m "NorthCel 0.3.1" && git push origin v0.3.1
```

## Homebrew formula

`packaging/homebrew/Formula/northcel.rb` pins the **published** artifacts: since
0.3.1 that is two of them — the `northcel` sdist (this formula's `url`) and the
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
  semantics change (`0.2.0-draft` today), and an archived draft is never edited.
- A packaging-only release keeps `spec_version` and the native runtime build
  identical; `northcel doctor` prints both numbers so they cannot be confused.
