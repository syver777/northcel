# Releasing NorthCel

The repository is the source; the registries are the distribution. A release is
four artifacts at one version, in a fixed order, plus optional deprecated aliases.

## Version 0.3.1 — prepared, not published

Everything below is prepared and verified on Linux x86_64. **Nothing in 0.3.1 has
been published by the extraction that created this repository.**

Current registry state when this was written (2026-11-04):

| Registry | Name | Latest |
| --- | --- | --- |
| PyPI | `northcel` | 0.2.1 |
| PyPI | `ncel` (deprecated alias) | 0.2.1 |
| PyPI | `ncel-native` (deprecated alias) | 0.2.1 |
| PyPI | `northcel-native` | **not published** |
| npm | `northcel` | 0.3.0 (pre-merge layout, published from NorthNoir) |
| npm | `northcel-linux-x64` | 0.3.0 |
| npm | `@ncel/linux-x64` (deprecated alias) | 0.2.1 |

`0.3.1` was chosen because npm `0.3.0` already exists and cannot be replaced.

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
| `northcel-0.3.1-py3-none-any.whl` | 164,169 |
| `northcel-0.3.1.tar.gz` | 161,197 |
| `northcel_native-0.3.1-py3-none-manylinux_2_39_x86_64.whl` | 2,815,158 |
| `northcel-0.3.1.tgz` (npm) | 45,355 |
| `northcel-linux-x64-0.3.1.tgz` (npm) | 2,849,183 |

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
PyPI, `NPM_TOKEN` or `npm login` for npm. `packaging/scripts/publish_0_3_1.sh`
does all of the above and refuses to start from a dirty tree.

## After publishing

```sh
python3 -m venv /tmp/nc && /tmp/nc/bin/pip install northcel==0.3.1
/tmp/nc/bin/northcel doctor && /tmp/nc/bin/northcel verify   # 5/5, hash be0eb036…
npm install -g northcel@0.3.1 && northcel verify

git tag -a v0.3.1 -m "NorthCel 0.3.1" && git push origin v0.3.1
```

## Version policy

- The **tools** version moves (`0.3.1`, `0.3.2`, …).
- The **language specification** moves only when the grammar or rendering
  semantics change (`0.2.0-draft` today), and an archived draft is never edited.
- A packaging-only release keeps `spec_version` and the native runtime build
  identical; `northcel doctor` prints both numbers so they cannot be confused.
