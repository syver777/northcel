# NorthCel install graph — design

Status: **implemented and verified on Linux x86_64**; macOS/Windows are a later
phase and fail honestly.

Everything a user installs is called **`northcel`**. `ncel` is a short *command*
alias, never a package name: npm rejected the bare `ncel` name, and a scoped
`@ncel/...` or a `...-cli` suffix would make users learn a second name for no
reason.

This note is the contract that the packaging, the CLI and the installers implement.
Every figure was measured on the reference VM (Ubuntu 24.04, x86_64, Mesa 25.2.8
llvmpipe, Python 3.12, Node 24) and re-verified from a clean install.

## 1. Which implementation runs

There is exactly **one** renderer implementation per artifact, and no silent
substitution:

| Stage | Implementation | Where it lives |
| --- | --- | --- |
| parse / typed AST / rings / frame expansion / boil | **MoonBit** (`native/moonbit/cmd/ncel_ast`), compiled to `ncel-ast` | `northcel-native` wheel, npm `northcel-linux-x64`, Homebrew install |
| `bend_swarm` agents | **Bend 0.2.38 + HVM 2.0.22**, prebuilt binaries | same bundle, `bin/bend`, `bin/hvm` |
| rasterisation | **GLSL 4.30** compiled by the **Mesa/EGL** runtime (`llvmpipe`, surfaceless) | system `libEGL.so.1` + `mesa-libgallium`; shaders in `share/ncel/` |
| reference parser/validator/formatter/renderer (oracle) | **Python**, inside the `northcel` package itself | `python/northcel/` |

`northcel` **calls the native binary whenever it is present and the platform is
supported**. The Python reference is used only when the native runtime is
genuinely unavailable, and then the tool says so on stderr and in the receipt
(`"renderer": "python-reference"`). The native binary itself never calls Python and
never falls back (`native/BUILD.md` §7).

## 2. Packages, versions, contents

The language spec stays `0.2.0-draft`; the tools version is **0.3.1**. The bundled
native runtime is the `0.2.0` build from commit `3ad5f7e`; `northcel doctor` prints
both numbers so they can never be confused.

### 2.1 PyPI `northcel` 0.3.1 — reference + launcher (`py3-none-any`)

One distribution, two roles: the reference implementation *and* the launcher.
This replaces the old pair (`ncel` → `northcel` + `ncel-native`), which is why
there is no console-script collision any more: one package owns both entry points.

```
northcel/                Python 3.10+
  parser.py validator.py formatter.py renderer.py rings.py ast_nodes.py config.py
  cli.py                 the reference CLI (check/fmt/info/render/film/guide)
  __main__.py            `python -m northcel` → the launcher
  launcher/
    cli.py               dispatch: doctor, verify, check, info, render, film, fmt,
                         guide, toolchain, version
    native.py            locate + checksum-verify the bundle, exec the binary
    fallback.py          explicit, labelled use of the reference renderer
    doctor.py            stage/version report, platform verdict
    toolchain.py         pinned-toolchain provisioning (MoonBit CLI + core)
    verify.py            starter + shower oracle + 6-frame film + determinism
    paths.py             where examples/, data/pins.json and the guide live
  examples/              starter.ncel, shower_f0001.ncel, lantern_film.ncel, …
  conformance/           the conformance suite and manifest
  data/pins.json         generated from native/toolchain.lock
  AGENT-GUIDE.md         offline authoring guide
```

```toml
[project.scripts]
northcel = "northcel.launcher.cli:main"
ncel     = "northcel.launcher.cli:main"

dependencies = [
  "numpy>=1.24",
  "Pillow>=10.0",
  "northcel-native==0.3.1; sys_platform == 'linux' and platform_machine == 'x86_64'",
]
```

The marker is what makes the *same* wheel honest on macOS/Windows: pip installs the
launcher and the reference without a native bundle, and `doctor`/`render` report
"native stages unavailable on this platform" and use the labelled Python path.
There is no second "fallback wheel" with different code — one wheel, one honest
behaviour switch.

Measured (0.2.1 artifacts, identical content apart from the merged modules): the
launcher wheel was **49,709 B**; a full `pip install` downloads **26.8 MB**
(northcel 140 KB + northcel-native 2.8 MB + numpy 16.7 MB + Pillow 7.1 MB) and
occupies **58 MB** of site-packages (43 MB of it numpy), 110 MB for the whole venv.
Merging the launcher into `northcel` removes one distribution and one dependency
edge; the download size is unchanged.

### 2.2 PyPI `northcel-native` 0.3.1 — platform wheel (`py3-none-manylinux_2_39_x86_64`)

```
northcel_native_bundle/
  bin/ncel-native  ncel-ast  ncel-gl  bend  hvm
  share/ncel/draw430.glsl draw410.glsl
  bundle-manifest.json     sha256 + version of every file, toolchain pins
  LICENSE-NOTES.md, README.md, licenses/
```

* No Python code is executed from this wheel; it is a bundle carrier
  (`northcel_native_bundle/__init__.py` exposes `bundle_dir()`).
* **Tagged `manylinux_2_39_x86_64` because that is the truth**: the pinned Bend and
  HVM binaries were built with a glibc-2.39 toolchain (they need `GLIBC_2.39`).
  Claiming `manylinux_2_17` would be a lie; Ubuntu 24.04, Debian 13, Fedora 40+,
  RHEL 10 satisfy 2.39 and older distributions get a clear pip error plus the
  installer's explicit glibc message.
* Size: **~2.8 MB** compressed (7.4 MB unpacked, 13 files). This is the whole
  runtime — no first-run download.
* The `ncel-*` executable names are internal and unchanged.

### 2.3 npm `northcel` 0.3.1 + `northcel-linux-x64` 0.3.1

```
northcel                    bin/northcel.js (one CLI: northcel + ncel),
                            lib/locate.js, index.cjs + rules.json (JS pre-check),
                            northcel/AGENT-GUIDE.md, data/{pins,fixtures}
  optionalDependencies: { "northcel-linux-x64": "0.3.1" }
northcel-linux-x64          os:["linux"], cpu:["x64"], libc:["glibc"],
                            bundle/{bin,share,manifest}
```

The launcher resolves `northcel-linux-x64/package.json` (still honouring
`@ncel/linux-x64` if that is what is installed), spawns `<bundle>/bin/ncel-native`,
and passes argv/stdout/stderr/exit code through. Missing optional dep → honest
message with the platform verdict and exit 3. `check` falls back to the
zero-dependency **PARTIAL** pre-check when neither the bundle nor a Python
reference is reachable — it never claims a document is valid. `fmt` explains that
formatting is the Python reference (`pip install northcel`). The main tarball is
**~36 KB**, the platform tarball **~2.85 MB**.

Publish order: `northcel-linux-x64` first, then `northcel` (the optional
dependency must already resolve).

### 2.4 Homebrew tap `syver777/northcel`

`packaging/homebrew/Formula/northcel.rb` is a tap formula (homebrew-core does not
accept brand-new formulae, so `brew install northcel` alone will not work until
acceptance). It installs the published PyPI artifacts into a formula venv:

* `url` = the `northcel` sdist, `sha256` pinned;
* `resource` blocks for `northcel-native` (platform wheel), `numpy`, `Pillow` — all
  sha256-pinned;
* `depends_on :linux`, `depends_on "python@3.12"`, `depends_on "mesa"`;
* links `libexec/bin/northcel` (and `ncel`) into `bin`;
* `license any_of: ["MIT", "Apache-2.0"]`.

The tap repository itself (`syver777/homebrew-northcel`) lives outside this repo;
`packaging/homebrew/` holds the reviewed source of the formula.

### 2.5 `curl … | bash` Linux installer

`packaging/install.sh`. Public form — the file is attached to the release, so the URL
always serves the latest published version:

```
curl -fsSL https://github.com/syver777/northcel/releases/latest/download/install.sh | bash
```

(`raw.githubusercontent.com/…/main/packaging/install.sh` tracks `main` and may change
between releases; it is not the documented URL.)

Behaviour: detect OS/arch/glibc, verify the GL runtime, create
`~/.local/share/ncel/venv` with the system `python3`, `pip install
--only-binary=:all: northcel==0.3.1` (PyPI hashes are enforced by pip),
checksum-verify the installed bundle against `bundle-manifest.json`, link
`~/.local/bin/northcel` (and `ncel`), then run the real conformance self-test.
Idempotent; `--dry-run` prints every action without doing it; `--uninstall`
removes only what it created; `--with-moonbit` additionally provisions the pinned
MoonBit CLI; Mesa is detected and, only with `--install-mesa`, installed through
the distro package manager (the single privileged step, opt-in).

The install directory `~/.local/share/ncel` keeps its historical name so an
existing install upgrades in place; only the command and the package names are
`northcel`.

## 3. Toolchain provisioning, honestly

Bundled per-platform artifacts are preferred over silent network installs, because
the "toolchain" a *runtime* needs is:

| Tool | Needed to run? | How it is provided | Verified by |
| --- | --- | --- | --- |
| MoonBit **compiled** stage (`ncel-ast`) | **yes** | bundled binary, 768 KB | stage probe + real render |
| MoonBit **compiler** CLI + core (101 + 2.8 MB) | **no** — only to rebuild from source | `northcel toolchain install`, sha256 from `toolchain.lock` | download + `moon version` |
| Bend 0.2.38 | **yes** | bundled binary, sha256-pinned | `bend version` in doctor |
| HVM 2.0.22 | **yes** | bundled binary, sha256-pinned | `hvm version` in doctor |
| Mesa/EGL + llvmpipe | **yes** | system package; installer *detects* it, `--install-mesa` installs it | EGL probe + real render |
| GLSL shaders | **yes** | bundled `share/ncel/*.glsl`, sha256 in `toolchain.lock` | shader compile+link in doctor |
| gcc | no (prebuilt) | source builds only | — |
| ffmpeg | optional (`--mp4`) | system | reported, not required |

"Installing GLSL" does not exist as a concept: GLSL is compiled by the GL driver.
The installer therefore provisions the **driver runtime** (Mesa + EGL), and
`northcel doctor` proves it by compiling and linking both shaders.

Every bundled file is listed in `bundle-manifest.json` with its sha256, and the
manifest's Bend/HVM/shader hashes are asserted equal to `toolchain.lock` at build
time (`packaging/scripts/stage_bundle.py`), so a bundle can never drift from the
pins it claims.

## 4. Updates

* pip/npm/brew resolve normal versions: `pip install -U northcel`,
  `npm i -g northcel@latest`, `brew upgrade northcel`.
* `northcel` never downloads anything at render time. `northcel toolchain install`
  is the only network operation, and it is explicit, sha256-pinned and resumable.
* The pinned native runtime is tied to a `northcel-native` version, so a launcher
  upgrade pulls the matching runtime; a mismatch between launcher and bundle is
  reported by `northcel doctor` (never silently used).

## 5. `northcel doctor` contract

Human output plus `--json` with the same fields:

```json
{
  "ok": true, "northcel_version": "0.3.1",
  "platform": {"os":"linux","arch":"x86_64","glibc":"2.39","supported":true},
  "native": {"available": true, "runtime_version": "0.2.0", "spec_version": "0.2.0-draft",
             "bundle": "/…/northcel_native_bundle", "checksums": {"verified": 13, "failed": []},
             "stage": "MoonBit+Bend+GLSL"},
  "stages": {
    "moonbit": {"present": true, "binary": "ncel-ast", "compiled_with": "0.1.20261102 (ea07287 2026-11-02)", "compiler_installed": false},
    "bend": {"present": true, "version": "0.2.38"},
    "hvm":  {"present": true, "version": "2.0.22"},
    "gl":   {"present": true, "version": "4.5 (Core Profile) Mesa 25.2.8…", "renderer": "llvmpipe (LLVM 20.1.2, 256 bits)", "glsl": "4.50"},
    "glsl_shaders": {"draw430": {"sha256": "14829a…", "compiles": true}, "draw410": {"sha256": "fe4d0c…", "compiles": true}},
    "ffmpeg": {"present": true, "optional": true}
  },
  "reference": {"package": "northcel", "version": "0.3.1", "role": "fallback only — non-native"},
  "errors": []
}
```

Exit codes: `0` native runtime usable, `3` native unavailable/unsupported (doctor
still prints the full, honest report), `1` internal failure.

## 6. macOS / Windows

Both are **not supported natively in this release**. The launcher and every
installer say so, by name, and never claim otherwise:

* `northcel doctor` → `platform supported: false`, reason `native stages require
  Linux x86_64 with glibc >= 2.39 and Mesa EGL; macOS needs Vulkan/MoltenVK or a
  tested GL 4.1 path (see native/BUILD.md §7)`.
* `northcel render/film/check/info` → Python reference renderer, labelled
  `"renderer": "python-reference"` (+ one stderr line). Not called "native".
* `northcel verify` → exits 3: the native runtime cannot be verified where it does
  not exist.
* npm: the main package installs (the optional dep is Linux-only), the launcher
  prints the same verdict and exits 3 — no Node-only renderer exists and none is
  claimed.
* Homebrew: `depends_on :linux`; on macOS Homebrew refuses with its standard
  message.
* `install.sh`: exits with the same explanation before touching anything.

## 7. Proof required per install path

Every path must, after installation, reproduce:

1. starter scene → PNG with the expected size (320×180);
2. shower `f0001` → `sha256 be0eb036…` (the pinned native value; the Python oracle
   is pixel-identical, MAE 0.0);
3. `lantern_film.ncel` (6 frames, boil + def/use + swarm) → 6 distinct PNGs;
4. determinism: each render repeated → identical sha256.

`northcel verify` does exactly this with the installed bundle.
`bash packaging/scripts/verify.sh` does it for the built artifacts (pip wheels and
npm tarballs) in throwaway directories.
