# northcel-native

Platform wheel: the **native NorthCel runtime** for **Linux x86_64**, taken
unchanged from `native/` (commit `3ad5f7e`).

```
northcel_native_bundle/
  bin/ncel-native      orchestration CLI (doctor/check/info/render/film)
  bin/ncel-ast         MoonBit typed AST / ring decoder / NCIR / Bend generator
  bin/ncel-gl          EGL surfaceless OpenGL host + GLSL rasteriser
  bin/bend             bend-lang 0.2.38        (sha256 pinned)
  bin/hvm              hvm 2.0.22              (sha256 pinned)
  share/ncel/draw430.glsl, draw410.glsl
  bundle-manifest.json sha256 + version of every file and the toolchain pins
```

Requirements: Linux x86_64, glibc ≥ 2.39 (the pinned Bend/HVM binaries need
`GLIBC_2.39`), and a Mesa/EGL GL runtime (`libegl1`, `libgl1`,
`mesa-libgallium`). GLSL is compiled by the GL driver at run time, not installed.

This package is installed automatically as a dependency of `northcel` on matching
platforms; use the `northcel` command, not this package. `northcel doctor` proves
the stages and versions, and `northcel verify` renders the bundled fixtures
(including the shower `f0001` conformance frame) twice to prove determinism.

Nothing here falls back to Python. The Python reference renderer is used only by
the `northcel` launcher, only where this runtime cannot run, and it says so.

The `ncel-*` executable names are internal to the bundle and unchanged; the
distribution is called `northcel-native`.

Licence: MIT OR Apache-2.0. Bundled third-party licences are in `licenses/` and
described in `LICENSE-NOTES.md`.
