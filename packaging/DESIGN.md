# ncel install graph — design

Status: **implemented for Linux x86_64**; macOS/Windows are a later phase and fail
honestly. `ncel` is the primary install name; `northcel` (PyPI/npm 0.2.1) stays
published and keeps working for existing users.

This note is the contract the packaging, the CLI and the installers implement. It
is deliberately concrete: every claim below was measured on the North Noir VM
(Ubuntu 24.04, x86_64, Mesa 25.2.8 llvmpipe) and re-verified from a clean install.

## 1. Which implementation runs

There is exactly **one** renderer implementation per artifact, and there is no
silent substitution:

| Stage | Implementation | Where it lives |
| --- | --- | --- |
| parse / typed AST / rings / frame expansion / boil | **MoonBit** (`moonbit/cmd/ncel_ast`), compiled to `ncel-ast` | `ncel-native` wheel, npm `@ncel/linux-x64`, Homebrew install, `~/.local/share/ncel` |
| `bend_swarm` agents | **Bend 0.2.38 + HVM 2.0.22**, prebuilt binaries | same bundle, `bin/bend`, `bin/hvm` |
| rasterisation | **GLSL 4.30** compiled by the **Mesa/EGL** runtime (`llvmpipe`, surfaceless) | system `libEGL.so.1` + `mesa-libgallium`; shaders in `share/ncel/` |
| reference parser/validator/formatter (oracle) | **Python** `northcel` 0.2.1 | pip dependency of `ncel` |

`ncel` **calls the native binary whenever it is present and the platform is
supported**. The Python reference is used only when the native runtime is
genuinely unavailable, and then the tool says so on stderr and in the receipt
(`"renderer": "python-reference"`). The native binary itself never calls Python
and never falls back (`native/ncel/BUILD.md` §7).

## 2. Packages, versions, contents

Language spec stays `0.2.0-draft`; the tools version stays **0.2.1** (aligned with
the already-published `northcel` 0.2.1). The bundled native runtime is the
`0.2.0` build from commit `3ad5f7e`; `ncel doctor` prints both numbers so they can
never be confused.

### 2.1 PyPI `ncel` 0.2.1 — pure Python launcher (`py3-none-any`)

Dependency direction: **`ncel` → `northcel` + `ncel-native`**. `ncel` owns the CLI
(dispatch, doctor, verify, toolchain), `northcel` owns the reference
parser/formatter/renderer, `ncel-native` owns the native binaries. Nothing is
duplicated: `ncel` never re-implements parsing, and `northcel` is untouched.

```
ncel/                 Python 3.10+, no compiled code
  cli.py              dispatch: doctor, check, info, render, film, fmt, guide,
                      verify, toolchain, version, uninstall
  native.py           locate + checksum-verify the bundle, exec the binary
  fallback.py         explicit, labelled use of northcel (Python reference)
  doctor.py           stage/version report, platform verdict
  toolchain.py        pinned-toolchain provisioning (MoonBit CLI + core)
  verify.py           starter + shower oracle + 6-frame film + determinism
  data/               starter.ncel, shower_f0001.ncel, lantern_film.ncel,
                      AGENT-GUIDE.md, oracle.json (pinned hashes/versions)
```

Dependencies:

```toml
dependencies = [
  "northcel==0.2.1",
  "ncel-native==0.2.1; sys_platform == 'linux' and platform_machine == 'x86_64'",
]
```

The marker is what makes the *same* wheel honest on macOS/Windows: pip installs
the launcher without a native bundle, and `ncel doctor`/`ncel render` report
"native stages unavailable on this platform" and use the labelled Python path.
There is no second "fallback wheel" with different code — one wheel, one honest
behaviour switch. (The brief allowed a separate pure-Python fallback wheel; a
single wheel with a platform marker is the same thing without a second code path
to drift.)

Estimated wheel size: **~70 KB** compressed (fixtures are 67 KB of `.ncel` text;
shower `f0001` is the only large one). Install footprint with dependencies:
**~24 MB** (numpy 18 MB + Pillow 4.5 MB, needed by the reference renderer and
`ncel fmt`).

### 2.2 PyPI `ncel-native` 0.2.1 — platform wheel (`py3-none-manylinux_2_39_x86_64`)

```
ncel_native_bundle/
  bin/ncel-native  ncel-ast  ncel-gl  bend  hvm
  share/ncel/draw430.glsl draw410.glsl
  bundle-manifest.json     sha256 + version of every file, toolchain pins
  LICENSE-NOTES.md, README.md
```

* No Python code is executed from this wheel; it is a bundle carrier
  (`ncel_native_bundle/__init__.py` exposes `bundle_dir()`).
* **Tagged `manylinux_2_39_x86_64` because that is the truth**: the pinned Bend
  and HVM binaries were built with a glibc-2.39 toolchain (they need
  `GLIBC_2.39`). Claiming `manylinux_2_17` would be a lie; Ubuntu 24.04, Debian 13,
  Fedora 40+, RHEL 10 satisfy 2.39 and older distros get a clear pip error plus the
  installer's explicit glibc message.
* Size: **~3.3 MB** compressed on disk (7.5 MB unpacked; Bend/HVM compress well).
  This is the whole runtime — no first-run download.

### 2.3 npm `ncel` 0.2.1 + `@ncel/linux-x64` 0.2.1

esbuild/swc layout:

```
ncel (main)                 bin/ncel.js launcher, lib/locate.js, data/AGENT-GUIDE.md
  optionalDependencies: { "@ncel/linux-x64": "0.2.1" }
@ncel/linux-x64             os:["linux"], cpu:["x64"], bundle/{bin,share,manifest}
```

The launcher resolves `@ncel/linux-x64/package.json`, spawns
`<bundle>/bin/ncel-native`, and passes argv/stdout/stderr/exit code through.
Missing optional dep → honest message (with the platform verdict) and exit 3.
`ncel doctor` merges the launcher view with the native receipt; `ncel guide`
prints the bundled guide; `ncel fmt` explains that formatting is the Python
reference (`pip install northcel`). The main tarball is **~15 KB**, the platform
tarball **~3.3 MB**.

npm publication is **prepared, not performed** (no npm token on the VM): the two
tarballs and their checksums are handed to the planner, publish order
`@ncel/linux-x64` first, then `ncel`.

### 2.4 Homebrew tap `syver777/ncel`

`packaging/homebrew/Formula/ncel.rb` is a tap formula (Homebrew core does not
accept brand-new formulas, so `brew install ncel` alone will not work until
acceptance). It installs the published PyPI artifacts into a formula venv:

* `url` = `ncel-0.2.1.tar.gz` from PyPI, `sha256` pinned;
* `resource` blocks for `ncel-native` (platform wheel), `numpy`, `Pillow` — all
  sha256-pinned, so `brew install` needs no network beyond the bottles/URLs it
  already fetches;
* `depends_on :linux`, `depends_on "python@3.12"`, `depends_on "mesa"` (the Linux
  GL runtime; Mesa ships `libEGL`/llvmpipe);
* links `libexec/bin/ncel` into `bin`.

The GitHub tap repository is **not** created here — the planner creates
`syver777/homebrew-ncel`, copies `Formula/ncel.rb` and its README, and only then
does `brew install syver777/ncel/ncel` work.

### 2.5 `curl … | bash` Linux installer

`packaging/install.sh`, served from the repo raw URL until a release asset exists:

```
curl -fsSL https://raw.githubusercontent.com/syver777/NorthNoir/main/packaging/install.sh | bash
```

Behaviour: detect OS/arch/glibc, verify the GL runtime, create
`~/.local/share/ncel/venv` with the system `python3`, `pip install --only-binary=:all: ncel==0.2.1`
(PyPI hashes are enforced by pip), checksum-verify the installed bundle against
`bundle-manifest.json`, link `~/.local/bin/ncel`, then run the real conformance
self-test. Idempotent; `--dry-run` prints every action without doing it;
`--uninstall` removes only what it created; `--with-moonbit` additionally
provisions the pinned MoonBit CLI into `~/.local/share/ncel/toolchain`; Mesa is
detected and, only with `--install-mesa`, installed through the distro package
manager (that is the single privileged step and it is opt-in).

## 3. Toolchain provisioning, honestly

Bundled per-platform artifacts are preferred over silent network installs (the
brief's preference), because the "toolchain" a *runtime* needs is:

| Tool | Needed to run? | How it is provided | Verified |
| --- | --- | --- | --- |
| MoonBit **compiled** stage (`ncel-ast`) | **yes** | bundled binary, 768 KB | `ncel-ast --version`/`check` in doctor |
| MoonBit **compiler** CLI + core (101 + 2.8 MB) | **no** — only to rebuild from source | `ncel toolchain install --moonbit`, sha256 from `toolchain.lock`, into `~/.local/share/ncel/toolchain/moon` | download + `moon version` |
| Bend 0.2.38 | **yes** | bundled binary 3.6 MB, sha256-pinned in `toolchain.lock` | `bend --version` |
| HVM 2.0.22 | **yes** | bundled binary 2.9 MB, sha256-pinned | `hvm --version` |
| Mesa/EGL + llvmpipe | **yes** | system package; installer *detects* it, `--install-mesa` installs it | EGL probe + real render |
| GLSL shaders | **yes** | bundled `share/ncel/*.glsl`, sha256 in `toolchain.lock` | shader compile+link in doctor |
| gcc | no (prebuilt) | source builds only | — |
| ffmpeg | optional (`--mp4`) | system | reported, not required |

"Installing GLSL" does not exist as a concept: GLSL is compiled by the GL driver.
The installer therefore provisions the **driver runtime** (Mesa + EGL), and
`ncel doctor` proves it by compiling and linking both shaders.

Every bundled file is listed in `bundle-manifest.json` with its sha256, and the
manifest's Bend/HVM/shader hashes are asserted equal to `toolchain.lock` at build
time (`packaging/scripts/build_python.sh`), so a bundle can never drift from the
pins it claims.

## 4. Updates

* pip/npm/brew resolve normal versions: `pip install -U ncel`,
  `npm i -g ncel@latest`, `brew upgrade ncel`.
* `ncel` never downloads anything at render time. `ncel toolchain install` is the
  only network operation, and it is explicit, sha256-pinned and resumable
  (partial download resumes through `curl -C -`).
* The pinned native runtime is tied to a `ncel-native` version, so a launcher
  upgrade pulls the matching runtime; a mismatch between launcher and bundle is
  reported by `ncel doctor` (never silently used).

## 5. `ncel doctor` contract

Human output plus `--json` with the same fields:

```json
{
  "ok": true, "ncel_version": "0.2.1", "platform": {"os":"linux","arch":"x86_64","glibc":"2.39","supported":true},
  "native": {"available": true, "runtime_version": "0.2.0", "spec_version": "0.2.0-draft",
             "bundle": "/…/ncel_native_bundle", "checksums": {"verified": 7, "failed": []},
             "stage": "MoonBit+Bend+GLSL"},
  "stages": {
    "moonbit": {"present": true, "binary": "ncel-ast", "compiled_with": "0.1.20261102 (ea07287 2026-11-02)", "compiler_installed": false},
    "bend": {"present": true, "version": "0.2.38", "path": "…/bin/bend"},
    "hvm":  {"present": true, "version": "2.0.22", "path": "…/bin/hvm"},
    "gl":   {"present": true, "version": "4.5 (Core Profile) Mesa 25.2.8…", "renderer": "llvmpipe (LLVM 20.1.2, 256 bits)", "glsl": "4.50"},
    "glsl_shaders": {"draw430": {"sha256": "14829a…", "compiles": true}, "draw410": {"sha256": "fe4d0c…", "compiles": true}},
    "ffmpeg": {"present": true, "optional": true}
  },
  "reference": {"package": "northcel", "version": "0.2.1", "role": "fallback only — non-native"},
  "errors": []
}
```

Exit codes: `0` native runtime usable, `3` native unavailable/unsupported
(doctor still prints the full, honest report), `1` internal failure.

## 6. macOS / Windows

Both are **not supported in this release**. The launcher and every installer say
so, by name, and never claim otherwise:

* `ncel doctor` → `platform supported: false`, reason
  `native stages require Linux x86_64 with glibc >= 2.39 and Mesa EGL; macOS needs
  Vulkan/MoltenVK or a tested GL 4.1 path (see native/ncel/BUILD.md §7)`.
* `ncel render/film/check/info` → Python reference renderer, labelled
  `"renderer": "python-reference"` (+ one stderr line). Not called "native".
* `ncel verify` → exits 3: the native runtime cannot be verified where it does not
  exist.
* npm: the main package installs (optional dep is Linux-only), the launcher prints
  the same verdict and exits 3 — no Node-only renderer exists and none is claimed.
* Homebrew: `depends_on :linux`; on macOS Homebrew refuses with its standard
  message.
* `install.sh`: exits 2 with the same explanation before touching anything.

## 7. Proof required per install path

Every path must, after installation, reproduce:

1. starter scene → PNG with the expected size;
2. shower `f0001` → `sha256 be0eb036…` (the pinned native value; the Python oracle
   is pixel-identical, MAE 0.0 — see `work/checks/ncel-packaging/oracle/`);
3. `lantern_film.ncel` (6 frames, boil + def/use + swarm) → 6 PNGs;
4. determinism: each render repeated → identical sha256.

`ncel verify` does exactly this with the installed bundle. The report records the
commands and results for pip, npm, the Homebrew formula layout and the curl
installer, all in clean directories/HOMEs.

## 8. What this design deliberately does not do

* No silent Python fallback inside the native binary (unchanged native contract).
* No download-on-first-run of the runtime.
* No `npm publish`, no new GitHub repository, no Homebrew core submission, no
  website deploy.
* No claim that macOS works, that every frame is byte-identical to Python
  (272/296 frames are; the rest are within 2.06e-4 MAE), or that GPU GL is
  verified.
