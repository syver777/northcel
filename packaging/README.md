# NorthCel (`northcel`) — install

`northcel` runs the **native NorthCel runtime**: a MoonBit typed-AST/geometry stage,
Bend 0.2.38 / HVM 2.0.22 for `bend_swarm` agents, and GLSL 4.30 rasterised by a
Mesa/EGL (llvmpipe) context. One command should be enough.

**One name everywhere: `northcel`.** `ncel` is the short command alias.

| Path | Command | Status |
| --- | --- | --- |
| PyPI (primary) | `pip install northcel` | **0.5.0 published** — one distribution with the reference implementation and the launcher, depending on `northcel-native` 0.4.0 (tools-only release) |
| npm | `npm install -g northcel` | **0.5.0 published** — same launcher; the native bundle stays 0.4.0 |
| Homebrew tap | `brew tap syver777/northcel && brew install northcel` | formula in `packaging/homebrew/`; the tap repository is `syver777/homebrew-northcel` |
| One-line curl | `curl -fsSL https://github.com/syver777/northcel/releases/latest/download/install.sh \| bash` | the URL is a release asset of the latest published release |

`brew install northcel` on its own is **not** available: homebrew-core does not
accept brand-new formulae without maintainer review. The honest command is the tap
one.

## Deprecated names

The old package names still install and point at the current packages: `ncel` and
`ncel-native` on PyPI and `@ncel/linux-x64` on npm are aliases that depend on
`northcel` / `northcel-native` / `northcel-linux-x64`.

## Platform support

| Platform | Native runtime | What the install does |
| --- | --- | --- |
| Linux x86_64, glibc ≥ 2.39 (Ubuntu 24.04+, Debian 13, Fedora 40+, RHEL 10) | **yes** | installs and runs MoonBit + Bend/HVM2 + GLSL via Mesa/EGL |
| Linux x86_64, glibc < 2.39 | no | pip finds no matching `northcel-native` wheel; the installer says why and changes nothing |
| Linux aarch64 | no | honest message; no artifact exists |
| macOS, Windows | **no** | `pip install northcel` installs the CLI + Python reference; `doctor` says why; renders are labelled `python-reference`. npm/brew/install.sh refuse with the same explanation |

macOS needs Vulkan/MoltenVK or a tested GL 4.1 path (`native/BUILD.md` §7) — a later
phase, not a packaging toggle.

## What gets installed, and how big it is

Sizes are for the published artifacts; the 0.5.0 layout merges the launcher into
`northcel`, which removes one distribution without changing the download.

| Artifact | Size | Contents |
| --- | ---: | --- |
| `northcel` wheel (PyPI) | ~200 KB | reference implementation *and* the CLI: doctor/verify/check/info/render/film/fmt/guide, fixtures, pins |
| `northcel-native` wheel (PyPI, manylinux_2_39_x86_64) | 2.8 MB | `ncel-native`, `ncel-ast` (MoonBit), `ncel-gl`, `bend`, `hvm`, GLSL shaders, manifest |
| numpy + Pillow (PyPI, for the reference) | 23.8 MB download (50 MB installed) | required by the Python reference; total `pip install northcel`: 26.8 MB download, 58 MB installed |
| npm `northcel` tarball | ~23 KB | one launcher (`northcel` + `ncel`), JS pre-check, guide, fixtures, pins |
| npm `northcel-linux-x64` tarball | 2.85 MB | the same native bundle |
| `install.sh` | 12 KB | provisioning script |

The native runtime itself is **bundled** — nothing is downloaded on first run.

## Toolchain provisioning (what "installing MoonBit and GLSL" means)

- **MoonBit** — the compiler is *not* needed to run: the MoonBit-compiled `ncel-ast`
  stage (768 KB) is in the bundle, built with MoonBit `0.1.20261102 (ea07287)`. The
  101 MB MoonBit CLI is only needed to rebuild from source:
  `northcel toolchain install` (sha256-pinned by `native/toolchain.lock`).
- **Bend 0.2.38 + HVM 2.0.22** — prebuilt binaries (3.6 MB + 2.9 MB) in the bundle,
  sha256-pinned; `northcel doctor` prints their versions and paths.
- **GLSL** — not an installable package: it is compiled by the GL driver. What is
  installed is the **GL runtime** (Mesa `libEGL` + `llvmpipe`). `northcel doctor`
  compiles and links both shaders as proof.
- Every bundled file is listed in `bundle-manifest.json`; the installer, `doctor` and
  the npm launcher all verify those sha256 values, and the build fails if a hash
  disagrees with `toolchain.lock`.

## After installing: prove it

```
northcel doctor        # stages, exact versions, platform verdict
northcel verify        # starter + shower f0001 conformance + 6-frame film, twice
```

`northcel verify` exits 0 only if all five checks pass: starter render, shower
`f0001` sha256 `be0eb036…` (identical to the Python oracle, MAE 0.0), a 6-frame film
with 6 distinct frames, determinism, and distinct frames.

## The one-line installer

```
curl -fsSL https://github.com/syver777/northcel/releases/latest/download/install.sh | bash
```

That URL is the `install.sh` asset of the latest published release (`v0.5.0` today,
12,193 bytes, sha256 `0f8875e9…`), so it keeps working when `main` moves. The raw URL
`raw.githubusercontent.com/syver777/northcel/main/packaging/install.sh` tracks `main`
and may change between releases; use it only if you deliberately want the development
copy. From a checkout you can also run
`bash packaging/install.sh` (add `--dry-run` to see every action first).

The script checks arch/glibc, checks the Mesa/EGL runtime, creates
`~/.local/share/ncel/venv`, `pip install northcel==0.5.0` (pip verifies the index
hashes), verifies the bundle manifest itself, links `~/.local/bin/northcel` and
`ncel`, and runs `northcel verify`. Non-root; the only privileged action is
`--install-mesa`, which is opt-in.

```
--dry-run          print every action, change nothing
--uninstall        remove the venv, the marker and the symlink it created
--no-verify        skip the render self-test
--with-moonbit     also install the pinned MoonBit compiler (101 MB)
--install-mesa     let the script install Mesa/EGL with sudo
--version X.Y.Z    install another published version
--prefix/--bin-dir custom locations
```

The install directory keeps its historical name (`~/.local/share/ncel`) so an
existing install upgrades in place; only the command and package names are
`northcel`.

## Uninstall

```
pip uninstall northcel northcel-native          # pip path
npm uninstall -g northcel                       # npm path
brew uninstall northcel                         # brew path
bash packaging/install.sh --uninstall           # curl path (removes its venv + symlink)
rm -rf ~/.local/share/ncel                      # only if you ran `northcel toolchain install`
```

User caches (`~/.cache/pip`, `~/.cache/mesa_shader_cache`) are left alone; they are
shared with everything else on the machine.

## Working on the packaging

```
bash packaging/scripts/build_python.sh    # wheels + sdist   -> dist/python
bash packaging/scripts/build_npm.sh       # npm tarballs      -> dist/npm
bash packaging/scripts/verify.sh          # install both into throwaway dirs
python3 packaging/scripts/gen_pins.py     # pins.json from native/toolchain.lock
```

`packaging/DESIGN.md` is the install-graph contract (what each package contains, how
the toolchain is provisioned, what `doctor` guarantees, and what is deliberately not
claimed).
