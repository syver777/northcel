# Homebrew tap for `northcel`

The public tap is **https://github.com/syver777/homebrew-northcel**; this
directory is the reviewed copy of the formula that ships with the language.

NorthCel itself lives at **https://github.com/syver777/northcel** (source, docs,
releases; also the formula's `homepage`), with the product page at
https://northnoir.com/northcel. This repository carries the reviewed formula; the tap carries the
published copy.

## Install (tested)

```sh
brew tap syver777/northcel
brew trust syver777/northcel        # Homebrew 7+ asks once for third-party taps
brew install northcel

northcel doctor          # MoonBit, Bend/HVM2, GLSL, exact versions
northcel verify          # conformance frame + 6-frame film, rendered twice
northcel render scene.ncel -o frame.png
```

`brew install syver777/northcel/northcel` is the same install without the
separate `brew tap` step (the `brew trust` step still applies). `ncel` is the same launcher under the package's short
name; `northcel` is the install name everywhere.

**`brew install ncel` / `brew install northcel` without the tap does not work**
and is not claimed: homebrew-core does not accept a new formula without
maintainer review, and there is no `northcel` formula there. The tap is the
supported Homebrew path.

## What the formula installs

Everything goes into a private Homebrew venv (`libexec`); **nothing is compiled
and nothing is downloaded on first run**:

| Artifact | Size | Role |
| --- | ---: | --- |
| `northcel` 0.2.1 (sdist) | 142 KB | Python reference parser/validator/formatter/renderer — the conformance oracle, `fmt`, `--no-native` |
| `ncel` 0.2.1 (wheel) | 50 KB | the launcher: platform verdict, native dispatch, doctor/verify/check/info/render/film |
| `ncel-native` 0.2.1 (`manylinux_2_39_x86_64`) | 2.8 MB | MoonBit stage, Bend 0.2.38, HVM 2.0.22, EGL GL host, GLSL shaders |
| `setuptools` 84.2.1, `wheel` 0.48.0 | 0.9 MB | build tools for the pinned sdist |
| `numpy` 2.5.4, `pillow` 13.0.0 | 22 MB | required by the reference renderer |

Dependencies: `python@3.12` (the pinned wheels are `cp312`), `mesa` (libEGL +
llvmpipe — the GL driver that compiles the GLSL), `linux`, `x86_64`.

The formula points `LD_LIBRARY_PATH` at `Formula["mesa"].opt_lib`, so the Mesa
that Homebrew installs is the one actually used (`doctor` reports Mesa 26.2.6,
GL 4.6, llvmpipe). It does not silently borrow the distribution's Mesa.

Installed size: **88.6 MB** in the Cellar for `northcel` (measured).

## Platform support

| Platform | Result |
| --- | --- |
| Linux x86_64, glibc >= 2.39 (Ubuntu 24.04+, Debian 13, Fedora 40+, RHEL 10) | installs and renders natively — **tested** |
| Linux x86_64, glibc < 2.39 | `ncel-native` is `manylinux_2_39`; pip refuses the wheel |
| Linux aarch64 | refused: `depends_on arch: :x86_64` |
| macOS | refused: `depends_on :linux` (and :x86_64). Native macOS is a later phase: Apple's OpenGL stops at 4.1, so the 4.30 shader cannot compile; it needs Vulkan/MoltenVK or a tested GL 4.1 path |
| Windows | n/a |

The tap deliberately fails on macOS rather than installing a launcher that could
only ever render through the labelled Python reference. `pip install ncel` still
works on macOS for that fallback.

## Tested reality (2026-11-04)

Executed on this VM (Ubuntu 24.04 x86_64, glibc 2.39, Homebrew 7.0.12 at
`/home/linuxbrew/.linuxbrew`, no sudo):

| Step | Result |
| --- | --- |
| `brew tap` + `brew install northcel` | pass, 17 s in the install step, 88.6 MB |
| `northcel version` / `ncel version` | `ncel 0.2.1 (native runtime 0.2.0, spec 0.2.0-draft, native)` |
| `northcel doctor` | exit 0 — every stage present, 13/13 bundle checksums, GL 4.6 Mesa 26.2.6 |
| `northcel verify` | **5/5 PASS**, conformance sha256 `be0eb036…` = pinned |
| `northcel render …starter.ncel -o /tmp/brew.png` | pass, 320×180, sha256 `b0bf8a78…` |
| `brew reinstall` | pass (idempotent, same result) |
| `brew uninstall` + fresh install | pass; uninstall leaves nothing in `$HOME` |
| `brew audit --strict --formula` | pass (run in the official `ghcr.io/homebrew/brew` container) |
| `brew style` | pass (same container) |
| `brew test northcel` | pass (same container) |

**Environment limit, stated plainly:** `brew audit`, `brew style` and `brew test`
are developer commands that install Homebrew's own gem bundle; `prism` and
`minitest` need a C compiler and Ruby dev headers, and this VM has no
`gcc`/`make`/`binutils`, no Ruby headers and no sudo. They were therefore run in
the project's official Homebrew container (`ghcr.io/homebrew/brew:latest`,
Homebrew 7.0.12). Install/upgrade/uninstall/render/doctor/verify were all run
natively against `/home/linuxbrew/.linuxbrew`. On a machine with
`build-essential` all four run natively too.

## Troubleshooting

`northcel doctor` says `no libEGL.so.1 found`: the launcher's platform probe in
`ncel` 0.2.1 only searches the distribution's standard library paths
(`/usr/lib/x86_64-linux-gnu`, `/usr/lib64`, `/usr/lib`, `/lib/x86_64-linux-gnu`)
and `ldconfig -p`. It does not read `LD_LIBRARY_PATH`, so Homebrew's Mesa under
the prefix is invisible to that probe even though the GL host itself uses it
(`northcel doctor` prints `GL runtime 4.6 Mesa 26.2.6` from it). Install the
distribution's EGL runtime once — `sudo apt install libegl1 libgl1`
(Debian/Ubuntu) or `sudo dnf install mesa-libEGL mesa-dri-drivers`
(Fedora/RHEL) — and the native path turns on with no other change. This is an
upstream `ncel` behaviour, not a formula choice; the fix is for
`ncel.platform_info.find_egl_runtime()` to also consult `LD_LIBRARY_PATH` and the
Homebrew prefix.

Without any EGL runtime at all, `brew install` still succeeds and `northcel`
degrades honestly: it prints the reason and renders through the labelled Python
reference, exactly as designed.

## Uninstall

```sh
brew uninstall northcel        # removes the venv, the Cellar entry and both commands
brew untap syver777/northcel   # optional: removes the tap checkout
```

Homebrew keeps the downloaded wheels in its own cache (`brew --cache`,
`brew cleanup` clears it). The formula writes nothing outside the Homebrew
prefix: no `~/.local/share/ncel`, no config in `$HOME`.

## Upgrading / maintenance

`Formula/northcel.rb` pins the version, the sdist and all six wheels by sha256.
A bump changes: `url`/`sha256` (the `northcel` sdist), the `ncel`,
`ncel-native`, `setuptools`, `wheel`, `numpy` and `pillow` resource hashes, and
the version assertion in `test do`. Run
`brew audit --strict --formula northcel` and `brew style Formula/northcel.rb`
before pushing.

### Renaming note (`northcel-native`)

The owner naming rule is **one install name: `northcel`**. The 0.2.1 artifacts
published before that decision are `ncel`, `ncel-native` and `northcel`; a
single-distribution `northcel` plus a `northcel-native` platform wheel is the
planned 0.2.2+ shape. No `northcel-native` 0.2.1 exists on PyPI today, so this
formula pins the three published 0.2.1 packages; when 0.2.2 is published the
formula collapses to `northcel` + `northcel-native` and the install command does
not change.

## Licence

The formula and this tap are MIT. The installed packages are dual licensed
`MIT OR Apache-2.0`; the formula declares `license any_of: ["MIT",
"Apache-2.0"]`. The 0.2.1 PyPI metadata still says `License: Proprietary`
because it predates the relicensing — the next release carries the dual licence.
