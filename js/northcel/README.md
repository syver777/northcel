# `northcel` (npm) — the NorthCel launcher and pre-check

**Source/unreleased version 0.6.0** accepts spec 0.4 (`mix`, `morph`, `frame A..B`,
`opacity`) and spec 0.5 (`group` bodies, `warp`, `nudge`) structurally in its
partial pre-check. Published npm is still **0.4.0**; published pip/Homebrew/install.sh
are **0.5.0** (spec 0.4). Spec 0.5 rendering/full validation needs the Python source
checkout (`python3 -m pip install -e './python[fit]'` in a venv at the repo root).
The bundled native runtime 0.4.0 implements spec 0.3 (anchored
`transform`, `ease`, `smoothstep` and everything before), so a spec 0.4/0.5 document is
never handed to it: the launcher uses the Python reference when it can reach it and
otherwise exits 3 naming the features. Optional `fit` and `tween` authoring tools
live in `pip install 'northcel[fit]'`, not this npm package; `fit` output is spec 0.3
and renders natively, `tween --match` output is spec 0.4 and needs Python.
Headerless documents default to spec 0.5 in this checkout and also route to Python,
even if their statements happen to exist in spec 0.3. Node-only `check` stays PARTIAL.

Installs the `northcel` command (short alias `ncel`) for the
[NorthCel drawing language](https://github.com/syver777/northcel).

On **Linux x86_64** it runs the real **native runtime** — MoonBit typed AST,
Bend 0.2.38 / HVM 2.0.22 swarms, GLSL 4.30 through Mesa/EGL — shipped as the
`northcel-linux-x64` optional dependency. Everywhere else it says exactly what is
missing and never pretends to render.

```
npm install -g northcel
northcel doctor          # stages, versions, checksums, platform verdict
northcel verify          # renders the conformance frame + a 6-frame film, twice
northcel guide           # offline authoring guide
```

## What this package can and cannot do

| Command | Needs | Notes |
| --- | --- | --- |
| `doctor`, `verify` | the `northcel-linux-x64` bundle | exit `3` with the reason when it is absent |
| `render`, `film`, `info` | the bundle, or a Python reference on PATH | never renders in JavaScript |
| `check` | the bundle, or a Python reference, or nothing | falls back to the **PARTIAL** JS pre-check |
| `fmt` | the Python reference (`pip install northcel`) | the native runtime has no formatter |

There is **no JavaScript renderer here and none is claimed.**

## The pre-check contract, stated plainly

Without a native bundle or a Python reference, `check` runs a zero-dependency
structural pre-check. Its text output always says **PARTIAL (JS pre-check only)**
and never `OK`; its JSON carries `partial: true`, `validator: "js"`, `reason` and
`next`.

- exit **0** — the pre-check found no structural error. This is **not** full
  validation.
- exit **1** — a pre-check error, or an unreadable file.
- exit **2** — the pre-check was clean but `--require-full` was given, i.e. full
  validation was demanded and could not be performed.

So:

```sh
npx northcel check film.ncel --json                   # partial, exit 0 if clean
npx northcel check film.ncel --require-full --json    # exit 2 unless it is fully validated
```

The pre-check catches missing roots, unbalanced delimiters and quotes, unknown
scene/film statements (including `frames:` wrongly placed in the body), malformed
headers and point structure, invalid ring integer/Base-63 payloads, and unknown
`$palette` references. Duplicate primitive names only warn — legal layer/cel
replacement is not banned. It does **not** evaluate numeric ranges, variable
bindings, function arity, `def` resolution, render-time expressions or visual
quality. It is not a JS grammar implementation and not a conformance validator.

When a Python implementation is present, this package probes `python3` / `python`
for `northcel.cli`, then looks for a pipx-style `northcel`/`ncel` Python
entrypoint on PATH, and delegates every check/render/film to it — passing
diagnostics and exit status through, and never masking a failed Python check
behind the JS pre-check. A Python child that dies is a non-zero exit, never a
success.

## Platform

| Platform | `npm install -g northcel` | Native render |
| --- | --- | --- |
| Linux x86_64, glibc ≥ 2.39 | works (bundle installed) | **yes, verified** |
| older glibc / arm64 Linux | installs; exit 3 with the reason | no |
| macOS / Windows | installs; exit 3 with the reason | no |

`northcel-linux-x64` (the ~2.9 MB bundle: MoonBit stage, Bend, HVM2, shaders,
`bundle-manifest.json` with a sha256 per file) is an `optionalDependency`, so npm
installs it automatically only where its `os`/`cpu`/`libc` fields match.

## Licence

Dual licensed under **MIT OR Apache-2.0**. See `LICENSE-MIT` and `LICENSE-APACHE`.
