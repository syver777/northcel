# @ncel/linux-x64

Native NorthCel runtime bundle for **Linux x86_64** — the platform package for
[`ncel`](https://www.npmjs.com/package/ncel). Install `ncel`, not this package.

```
bundle/bin/ncel-native   orchestration CLI (doctor/check/info/render/film)
bundle/bin/ncel-ast      MoonBit typed AST / ring decode / NCIR / Bend generator
bundle/bin/ncel-gl       EGL surfaceless OpenGL host + GLSL rasteriser
bundle/bin/bend          bend-lang 0.2.38 (sha256 pinned)
bundle/bin/hvm           hvm 2.0.22   (sha256 pinned)
bundle/share/ncel/       draw430.glsl, draw410.glsl
bundle/bundle-manifest.json  sha256 + version of every bundled file
```

Requires Linux x86_64, glibc >= 2.39 and a Mesa/EGL GL runtime. Taken unchanged
from `native/ncel/` (commit `3ad5f7e`); every hash is checked against
`native/ncel/toolchain.lock` at build time and by `ncel doctor`.

Licence: Proprietary, North Noir. Bundled third-party licences are in
`bundle/licenses/`.
