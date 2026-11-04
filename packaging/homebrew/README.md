# Homebrew tap for `ncel`

## The honest situation

`brew install ncel` on its own **does not work and cannot be promised**: Homebrew
core does not accept brand-new formulae without maintainer review, and no `ncel`
formula exists there. What this directory prepares is a **tap**:

```sh
brew tap syver777/ncel              # once the tap repository exists
brew install ncel                   # -> syver777/ncel/ncel
```

Before the tap exists (or to test the file as it is in this repository):

```sh
brew install --build-from-source ./packaging/homebrew/Formula/ncel.rb
```

The GitHub repository `syver777/homebrew-ncel` is intentionally **not** created
here. Creation steps for the planner:

```sh
# 1. create the repository (GitHub UI or gh) with this layout:
#      homebrew-ncel/Formula/ncel.rb
#      homebrew-ncel/README.md
# 2. copy the two files:
cp packaging/homebrew/Formula/ncel.rb <tap>/Formula/ncel.rb
cp packaging/homebrew/README.md       <tap>/README.md
# 3. check and install on a Linux machine with Homebrew:
brew audit --strict --formula <tap>/Formula/ncel.rb
brew install --build-from-source <tap>/Formula/ncel.rb
ncel doctor && ncel verify
```

## What the formula installs

Prebuilt, sha256-pinned wheels into a private Homebrew venv — **no compilation, no
download at first run**:

| Wheel | Size | Role |
| --- | ---: | --- |
| `ncel` 0.2.1 | 50 KB | the CLI (doctor/verify/check/info/render/film/fmt/guide) |
| `ncel-native` 0.2.1 (`manylinux_2_39_x86_64`) | 2.8 MB | MoonBit stage, Bend 0.2.38, HVM 2.0.22, GLSL shaders |
| `northcel` 0.2.1 | 140 KB | Python reference parser/validator/formatter |
| `numpy` 2.5.4, `pillow` 13.0.0 | 22 MB | required by the reference renderer |

Dependencies: `python@3.12` (the wheels are `cp312`), `mesa` (libEGL + llvmpipe —
GLSL is compiled by the GL driver, so this *is* the GLSL runtime), Linux only.

Requirements: **Linux x86_64, glibc >= 2.39** (Ubuntu 24.04+, Debian 13, Fedora 40+,
RHEL 10). The formula is not offered on macOS or Windows: the native runtime has
not been built or verified there, so `depends_on :linux` makes Homebrew refuse
rather than install something that cannot render.

## Status of testing

`brew` is **not installed on the North Noir VM**, so this formula has not been
executed with `brew install`. What *has* been verified is the artifact set it
installs: the five pinned wheels were downloaded from PyPI by exact URL, installed
offline (`pip --no-index`) into a fresh venv, and then `ncel doctor`, `ncel
render`, `ncel film` and `ncel verify` were run — see
`work/checks/ncel-packaging/logs/brew-artifacts-*`. The formula's DSL (resources,
`virtualenv_install_with_resources`, `bin.install_symlink`) follows the Homebrew
Python-formula pattern but still needs a real `brew install` on a Homebrew machine.
