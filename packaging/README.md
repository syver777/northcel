# NorthCel (`ncel`) — install

`ncel` runs the **native NorthCel runtime**: a MoonBit typed-AST/geometry stage, Bend
0.2.38 / HVM 2.0.22 for `bend_swarm` agents, and GLSL 4.30 rasterised by a
Mesa/EGL (llvmpipe) context. One command should be enough:

| Path | Command | Status |
| --- | --- | --- |
| PyPI (primary) | `pip install ncel` | **published** (`ncel` 0.2.1, `ncel-native` 0.2.1) |
| npm (primary) | `npm install -g ncel` | **prepared**, tarballs + checksums in `work/checks/ncel-packaging/npm/` — not published |
| Homebrew tap | `brew tap syver777/ncel && brew install ncel` | **prepared** (`packaging/homebrew/`), tap repository not created |
| One-line curl | `curl -fsSL …/packaging/install.sh \| bash` | **tested here**, script in this folder |

`brew install ncel` on its own is **not** available: homebrew-core does not accept
brand-new formulae without maintainer review. The honest command is the tap one.

## Platform support

| Platform | Native runtime | What the install does |
| --- | --- | --- |
| Linux x86_64, glibc ≥ 2.39 (Ubuntu 24.04+, Debian 13, Fedora 40+, RHEL 10) | **yes** | installs and runs MoonBit + Bend/HVM2 + GLSL via Mesa/EGL |
| Linux x86_64, glibc < 2.39 | no | pip finds no matching `ncel-native` wheel; the installer says why and changes nothing |
| Linux aarch64 | no | honest message; no artifact exists |
| macOS, Windows | **no** | `pip install ncel` installs the CLI + Python reference; `doctor` says why; renders are labelled `python-reference`. npm/brew/install.sh refuse with the same explanation |

macOS needs Vulkan/MoltenVK or a tested GL 4.1 path (`native/ncel/BUILD.md` §7) —
that is a later phase, not a packaging toggle.

## What gets installed, and how big it is

| Artifact | Size | Contents |
| --- | ---: | --- |
| `ncel` wheel (PyPI) | 50 KB | CLI: doctor/verify/check/info/render/film/fmt/guide + fixtures + pins |
| `ncel-native` wheel (PyPI, manylinux_2_39_x86_64) | 2.8 MB | `ncel-native`, `ncel-ast` (MoonBit), `ncel-gl`, `bend`, `hvm`, GLSL shaders, manifest |
| `northcel` wheel (PyPI) | 140 KB | Python reference parser/validator/formatter (oracle + labelled fallback) |
| numpy + Pillow (PyPI, for the reference) | ~22 MB | required by `northcel` |
| npm `ncel` tarball | 36 KB | launcher + guide + fixtures + pins |
| npm `@ncel/linux-x64` tarball | 2.85 MB | the same native bundle |
| `install.sh` | 12 KB | provisioning script |

The native runtime itself is **bundled** — nothing is downloaded on first run.

## Toolchain provisioning (what "installing MoonBit and GLSL" means)

* **MoonBit** — the compiler is *not* needed to run: the MoonBit-compiled `ncel-ast`
  stage (768 KB) is in the bundle, built with MoonBit `0.1.20261102 (ea07287)`. The
  101 MB MoonBit CLI is only needed to rebuild from source:
  `ncel toolchain install` (sha256-pinned by `native/ncel/toolchain.lock`).
* **Bend 0.2.38 + HVM 2.0.22** — prebuilt binaries (3.6 MB + 2.9 MB) in the bundle,
  sha256-pinned; `ncel doctor` prints their versions and paths.
* **GLSL** — not an installable package: it is compiled by the GL driver. What is
  installed is the **GL runtime** (Mesa `libEGL` + `llvmpipe`). `ncel doctor`
  compiles and links both shaders as proof.
* Every bundled file is listed in `bundle-manifest.json`; the installer, `ncel
  doctor` and the npm launcher all verify those sha256 values, and the build fails
  if a hash disagrees with `toolchain.lock`.

## After installing: prove it

```
ncel doctor        # stages, exact versions, platform verdict
ncel verify        # starter + shower f0001 conformance + 6-frame film, twice
```

`ncel verify` exits 0 only if all five checks pass: starter render, shower `f0001`
sha256 `be0eb036…` (identical to the Python oracle, MAE 0.0), a 6-frame film with 6
distinct frames, and byte-identical repeats.

## The one-line installer

```
curl -fsSL https://raw.githubusercontent.com/syver777/NorthNoir/main/packaging/install.sh | bash
```

**Hosting caveat, stated plainly:** that URL only works once the script is publicly
reachable. The `syver777/NorthNoir` repository is **private today** (anonymous
`raw.githubusercontent.com` answers 404), so right now use one of:

```
bash packaging/install.sh                                        # from the checkout
gh api repos/syver777/NorthNoir/contents/packaging/install.sh \
  -H "Accept: application/vnd.github.raw" | bash                 # authenticated
```

or the already-public one-command path `pip install ncel`. Making the repository
public (or attaching the script to a GitHub release) turns the `curl` form into a
true one-liner with no change to the script.

The script checks arch/glibc, checks the Mesa/EGL runtime, creates
`~/.local/share/ncel/venv`, `pip install ncel==0.2.1` (pip verifies the index
hashes), verifies the bundle manifest itself, links `~/.local/bin/ncel`, and runs
`ncel verify`. Non-root; the only privileged action is `--install-mesa`, which is
opt-in.

```
--dry-run          print every action, change nothing
--uninstall        remove the venv, the marker and the symlink it created
--no-verify        skip the render self-test
--with-moonbit     also install the pinned MoonBit compiler (101 MB)
--install-mesa     let the script install Mesa/EGL with sudo
--version X.Y.Z    install another published version
--prefix/--bin-dir custom locations
```

Hosting: until a GitHub release asset exists, the script is served from the repo's
raw URL on `main`. It is self-contained (no repo files needed at run time).

## Uninstall

```
pip uninstall ncel ncel-native northcel        # pip path
npm uninstall -g ncel                          # npm path
brew uninstall ncel                            # brew path
bash install.sh --uninstall                    # curl path (removes its venv + symlink)
rm -rf ~/.local/share/ncel                     # only if you ran `ncel toolchain install`
```

User caches (`~/.cache/pip`, `~/.cache/mesa_shader_cache`) are left alone; they are
shared with everything else on the machine.

## Working on the packaging

```
bash packaging/scripts/build_python.sh    # wheels + sdist -> work/checks/ncel-packaging/wheels
bash packaging/scripts/build_npm.sh       # tarballs        -> work/checks/ncel-packaging/npm
python3 packaging/scripts/gen_pins.py     # pins.json from native/ncel/toolchain.lock
```

`packaging/DESIGN.md` is the install-graph contract (what each package contains, how
the toolchain is provisioned, what `doctor` guarantees, and what is deliberately not
claimed).
