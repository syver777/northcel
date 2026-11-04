# northcel-linux-x64

Native NorthCel runtime bundle for **Linux x86_64** — the platform package for
[`northcel`](https://www.npmjs.com/package/northcel). Install `northcel`, not this
package.

```
bundle/bin/ncel-native   orchestration CLI (doctor/check/info/render/film)
bundle/bin/ncel-ast      MoonBit typed AST / ring decode / NCIR / Bend generator
bundle/bin/ncel-gl       EGL surfaceless OpenGL host + GLSL rasteriser
bundle/bin/bend          bend-lang 0.2.38 (sha256 pinned)
bundle/bin/hvm           hvm 2.0.22   (sha256 pinned)
bundle/share/ncel/       draw430.glsl, draw410.glsl
bundle/bundle-manifest.json  sha256 + version of every bundled file
```

Requires Linux x86_64, glibc ≥ 2.39 and a Mesa/EGL GL runtime. Taken unchanged
from `native/` (commit `3ad5f7e`); every hash is checked against
`native/toolchain.lock` at build time and again by `northcel doctor`.

The `ncel-*` executable names are internal to the native bundle and unchanged; the
package and its launcher are called `northcel`.

Licence: MIT OR Apache-2.0. Bundled third-party licences (Bend, HVM, MoonBit core,
stb) are in `bundle/licenses/` and in `native/LICENSE-NOTES.md`.
