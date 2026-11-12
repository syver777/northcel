# Releasing NorthCel

## 0.7.2 — spec 0.6.0-draft

Tools release `northcel` 0.7.2, built from `main`. The native runtime stays
0.4.0 and is not rebuilt. `northcel-vello` stays 0.7.0, so `northcel[vello]`
keeps `northcel-vello==0.7.0`. The deprecated `ncel` alias stays at 0.7.1 until
it is re-pinned after publication.

Order:

1. `bash packaging/scripts/build_python.sh` for `northcel` 0.7.2 (native 0.4.0 is
   already published; do not rebuild it).
2. `python -m twine check dist/python/*`; install the wheel in a fresh venv and
   run `northcel --version`, `northcel doctor` and a render from the examples.
3. Upload `northcel` wheel/sdist. Do not upload an `ncel` alias: it stays at
   0.7.1 until it is re-pinned after publication.
4. Publish the GitHub release `v0.7.2` with `packaging/install.sh`. The script is
   re-pinned to 0.7.2 after publication. The CI publish job uses PyPI **trusted
   publishing** (`id-token: write`) on that release. Until a trusted publisher is
   configured for the repository and workflow, publish with
   `NORTH_NOIR_PYPI_API`/twine credentials from a machine.
5. Fresh-venv proof: `pip install northcel==0.7.2`; `northcel --version` reports
   0.7.2 / spec 0.6.0-draft; `northcel render
   examples/patterns/12-polishing-ai-frames.ncel` works. Compare the artifact
   sha256 with the PyPI JSON.
6. Re-pin `packaging/install.sh`, `packaging/deprecated/pypi-ncel` and the
   Homebrew formula only from the published 0.7.2 sdist URL/SHA-256. npm remains
   with the owner; do not publish it here.

## Registry state

| Registry | Name | Latest | Notes |
| --- | --- | --- | --- |
| PyPI | `northcel` | **0.7.1** | the one package a user installs: reference + launcher, scripts `northcel` and `ncel`; 0.7.2 prepared |
| PyPI | `northcel-native` | **0.4.0** | the Linux x86_64 platform wheel `northcel` depends on; unchanged |
| PyPI | `northcel-vello` | **0.7.0** | optional tolerance-tier renderer for `northcel[vello]`; unchanged |
| PyPI | `ncel` | **0.7.1** (deprecated) | alias that depends on `northcel`; re-pinned after 0.7.2 is published |
| PyPI | `ncel-native` | 0.4.0 (deprecated) | alias that depends on `northcel-native`; unchanged |
| npm | `northcel` | launcher | the launcher + structural pre-check; the owner publishes it |
| npm | `northcel-linux-x64` | 0.4.0 | the native bundle; unchanged |
| npm | `@ncel/linux-x64` | 0.2.1 (deprecated) | alias for the bundle; do not publish |

## Build and prove

```sh
bash packaging/scripts/build_python.sh        # wheels + sdist -> dist/python
bash packaging/scripts/build_npm.sh           # tarballs        -> dist/npm
bash packaging/scripts/verify.sh              # installs both paths into /tmp and renders
python -m twine check dist/python/* dist/deprecated/*
```

`build_python.sh` needs `native/artifacts/ncel-native-0.2.0-linux-x86_64/` (the
native build for the pinned runtime). If it is absent it tries to build the native
tree, which needs the MoonBit compiler and a C toolchain — see `native/BUILD.md`.
`build_npm.sh` needs the same artifacts. Record the verified 0.7.2 values here
after upload:

| File | sha256 |
| --- | --- |
| `northcel-0.7.2-py3-none-any.whl` | _filled after upload_ |
| `northcel-0.7.2.tar.gz` | _filled after upload_ |

## Published 0.7.1 artifacts

| File | sha256 |
| --- | --- |
| `northcel-0.7.1-py3-none-any.whl` | `1e209376236bb5c8dede48f08ae7dd6633dd27c1d09691139410a152003cd565` |
| `northcel-0.7.1.tar.gz` | `5a6c1c6b3362d4309a1ce2222d0267e677566fc301aa810e64a41f9806a6b5f7` |
| `ncel-0.7.1` wheel/sdist (deprecated) | `b51e68ae34dffaba75f30b806e2e02528d164773b5cdba77001ad31c3602cdf3` / `2d5eac1c642bc69cc8362221413d01ac5628fe801e95de4e6d494affc73d82b3` |

## Publish, in this order

0.7.2 is tools-only: do not upload `northcel-native`, `northcel-vello` or
`northcel-linux-x64` again. A platform artifact from 0.4.0 already satisfies the
dependency; verify it exists first.

```sh
# 1. PyPI — the reference + launcher (native 0.4.0 is already published)
python3 -m twine upload --non-interactive \
  dist/python/northcel-0.7.2-py3-none-any.whl dist/python/northcel-0.7.2.tar.gz

# 2. the GitHub release that serves install.sh
gh release create v0.7.2 packaging/install.sh --repo syver777/northcel \
  --title "NorthCel 0.7.2" --notes "Tools release: fit palette-gap receipt."
```

Credentials: `TWINE_USERNAME=__token__` + `TWINE_PASSWORD` (or `~/.pypirc`) for
PyPI. The other release scripts read the PyPI token from the
`NORTH_NOIR_PYPI_API` environment variable, map it to `TWINE_PASSWORD` (never
echoed, never written to disk) and refuse to start from a dirty tree.

If the public simple index lags right after an upload, `pip install` can report
"No matching distribution found" while the file is already listed. Retry with
`--no-cache-dir` after a minute before assuming a bad artifact.

## After publishing

```sh
python3 -m venv /tmp/nc && /tmp/nc/bin/pip install --no-cache-dir northcel==0.7.2
/tmp/nc/bin/northcel doctor && /tmp/nc/bin/northcel verify

git tag -a v0.7.2 -m "NorthCel 0.7.2" && git push origin v0.7.2
curl -fsSL https://github.com/syver777/northcel/releases/latest/download/install.sh | grep NCEL_VERSION
```

## Homebrew formula

`packaging/homebrew/Formula/northcel.rb` pins the **published** artifacts: the
`northcel` sdist (this formula's `url`) and the `northcel-native` platform wheel.
To re-pin, take the `url`/`sha256` pairs from
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

- The **tools** version moves for any release (`0.7.2`, `0.7.3`, …).
- The **language specification** moves only when the grammar or rendering
  semantics change (`0.6.0-draft` today), and an archived draft is never edited.
- A packaging-only or documentation-only release keeps `spec_version` and the
  native runtime build identical; `northcel doctor` prints both numbers so they
  cannot be confused.
