# Homebrew tap for `northcel`

The public tap is **https://github.com/syver777/homebrew-northcel**; this
directory is the reviewed copy of the formula that ships with the language. The tap
is the published copy — keep the two files identical.

NorthCel itself lives at **https://github.com/syver777/northcel** (source, docs,
releases; also the formula's `homepage`), with the product page at
https://northnoir.com/northcel.

## What the install gives you

| Piece | What it is | Where it runs |
| --- | --- | --- |
| **Native runtime** (the default) | MoonBit `ncel-ast` parses and builds the IR and the Bend program; **Bend 0.2.38 / HVM 2.0.22** evaluate every `bend_swarm` agent; **GLSL 4.30** on a Mesa/EGL **llvmpipe** context rasterises the frame | **Linux x86_64 only**, glibc ≥ 2.39 |
| **Python reference** (in the same package) | the normative **oracle** for the language and rasterisation, the only formatter (`northcel fmt`), and the **labelled fallback** (`--no-native`) — every receipt it produces says `"renderer": "python-reference"` | anywhere Python 3.10+ runs |

The formula is deliberately Linux/x86_64-only: on macOS and Windows it refuses to
install instead of shipping a launcher that could only ever use the reference path.
`northcel doctor` prints each stage with its exact version and exits `3` with the
reason when the native runtime is not usable.

## Install (tested)

```sh
brew tap syver777/northcel
brew trust syver777/northcel        # Homebrew 7+ asks once for third-party taps
brew install northcel

northcel doctor          # MoonBit, Bend/HVM2, GLSL, exact versions
northcel verify          # conformance frame + 6-frame film, rendered twice
northcel render scene.ncel -o frame.png
```

`brew install syver777/northcel/northcel` is the same install without the separate
`brew tap` step (the `brew trust` step still applies). `ncel` is the same launcher
under the package's short name; `northcel` is the install name everywhere.

**`brew install northcel` without the tap does not work** and is not claimed:
homebrew-core does not accept a new formula without maintainer review, and there is
no `northcel` formula there. The tap is the supported Homebrew path.

## What the formula installs

Since 0.3.1 there is **one Python distribution**, so the formula pins two
artifacts instead of three. Everything goes into a private Homebrew venv
(`libexec`); **nothing is compiled and nothing is downloaded on first run**:

| Artifact | Size | Role |
| --- | ---: | --- |
| `northcel` 0.3.1 (sdist, this formula's `url`) | 161 KB | the reference implementation (parser, validator, formatter, renderer — the conformance oracle, `fmt`, `--no-native`) **and** the launcher (doctor/verify/check/info/render/film/guide); scripts `northcel` and `ncel` |
| `northcel-native` 0.3.1 (`manylinux_2_39_x86_64`) | 2.8 MB | MoonBit stage, Bend 0.2.38, HVM 2.0.22, EGL GL host, GLSL shaders |
| `setuptools` 84.2.1, `wheel` 0.48.0 | 0.9 MB | build tools for the pinned sdist |
| `numpy` 2.5.4, `pillow` 13.0.0 | 22 MB | required by the reference renderer |

Dependencies: `python@3.12` (the pinned wheel is `cp312`), `mesa` (libEGL +
llvmpipe — the GL driver that compiles the GLSL), `linux`, `x86_64`.

The formula wraps the launcher with `LD_LIBRARY_PATH=#{formula_opt_lib("mesa")}`, so
the Mesa that Homebrew installs is the one actually used (`doctor` reports Mesa
26.2.6, GL 4.6, llvmpipe) instead of silently borrowing the distribution's Mesa.
Since 0.3.1 the launcher's own EGL probe reads `LD_LIBRARY_PATH` and
`HOMEBREW_PREFIX` too, so it sees that Mesa as well — see Troubleshooting.

Installed size: **≈89 MB** in the Cellar for `northcel` (measured at 0.2.1; the
0.3.1 layout has one distribution instead of two and is the same order of size).

## Platform support

| Platform | Result |
| --- | --- |
| Linux x86_64, glibc >= 2.39 (Ubuntu 24.04+, Debian 13, Fedora 40+, RHEL 10) | installs and renders natively — **tested** |
| Linux x86_64, glibc < 2.39 | `northcel-native` is `manylinux_2_39`; pip refuses the wheel |
| Linux aarch64 | refused: `depends_on arch: :x86_64` |
| macOS | refused: `depends_on :linux` (and :x86_64). Native macOS is a later phase: Apple's OpenGL stops at 4.1, so the 4.30 shader cannot compile; it needs Vulkan/MoltenVK or a tested GL 4.1 path |
| Windows | n/a |

The tap deliberately fails on macOS rather than installing a launcher that could
only ever render through the labelled Python reference. `pip install northcel`
still works on macOS for that fallback.

## Tested reality (2026-11-04, re-verified with this text)

Executed on a VM (Ubuntu 24.04 x86_64, glibc 2.39, Homebrew 7.0.12 at
`/home/linuxbrew/.linuxbrew`, no sudo):

| Step | Result |
| --- | --- |
| `brew tap` + `brew install northcel` | pass (0.2.1 and 0.3.1) |
| `brew reinstall northcel` with the formula as published here | pass — 1,508 files, 88.6 MB, 18 s |
| `northcel version` / `ncel version` | `northcel 0.3.1 (native runtime 0.2.0, spec 0.2.0-draft, native)` |
| `northcel doctor` | exit 0 — every stage present, 13/13 bundle checksums |
| `northcel doctor --json` | `"ok": true`; MoonBit `ncel-ast` compiled with `0.1.20261102 (ea07287 2026-11-02)`; **Bend 0.2.38**, **HVM 2.0.22**; GL `4.6 (Core Profile) Mesa 26.2.6`, llvmpipe, GLSL 4.60; shaders `draw430 14829a3c…`, `draw410 fe4d0c4f…` |
| `northcel verify` | **5/5 PASS**, conformance sha256 `be0eb036…` = pinned |
| `northcel render …starter.ncel -o /tmp/brew.png` | pass, 320×180, sha256 `b0bf8a78…` |
| `brew reinstall` / `brew uninstall` + fresh install | pass; uninstall leaves nothing in `$HOME` |
| `brew audit --strict --formula` | pass (run in the official `ghcr.io/homebrew/brew` container) |
| `brew style` | pass (same container) |
| `brew test northcel` | pass (same container) |

**Environment limit, stated plainly:** `brew audit`, `brew style` and `brew test`
are developer commands that install Homebrew's own gem bundle; `prism` and
`minitest` need a C compiler and Ruby dev headers, and the release VM has no
`gcc`/`make`/`binutils`, no Ruby headers and no sudo. They are therefore run in
the project's official Homebrew container (`ghcr.io/homebrew/brew:latest`,
Homebrew 7.0.12). Install/doctor/verify/render were also run natively against
`/home/linuxbrew/.linuxbrew`. On a machine with `build-essential` all four run
natively too.

## Troubleshooting

`northcel doctor` says `no libEGL.so.1 found`: since 0.3.1 the launcher searches
`LD_LIBRARY_PATH`, `$HOMEBREW_PREFIX`, `/home/linuxbrew/.linuxbrew`,
`~/.linuxbrew`, `/usr/local` (including keg-only `opt/*/lib`), the Python prefix,
and only then the distribution paths and `ldconfig -p`. This formula sets
`LD_LIBRARY_PATH` to its own Mesa, so the message should not appear on a Homebrew
install. If it still does, install the distribution's EGL runtime once —
`sudo apt install libegl1 libgl1` (Debian/Ubuntu) or
`sudo dnf install mesa-libEGL mesa-dri-drivers` (Fedora/RHEL). In `ncel` 0.2.1 and
earlier the probe only looked at the distribution paths, which is why the tap
README used to ask for that package; that is fixed in 0.3.1.

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

`Formula/northcel.rb` pins the version, the `northcel` sdist (`url`/`sha256`) and
the `northcel-native` wheel by sha256. A bump changes those two pairs, the
`setuptools`/`wheel`/`numpy`/`pillow` hashes if they move, and the version
assertion in `test do`. Run `brew audit --strict --formula northcel` and
`brew style Formula/northcel.rb` before pushing.

Take the `url`/`sha256` values from `https://pypi.org/pypi/northcel/<version>/json`
and `https://pypi.org/pypi/northcel-native/<version>/json` — never from a local
build, whose bytes can differ.

## Licence

The formula and this tap are MIT. The installed packages are dual licensed
`MIT OR Apache-2.0`; the formula declares `license any_of: ["MIT",
"Apache-2.0"]`. Every published 0.3.1 package carries the dual licence.
