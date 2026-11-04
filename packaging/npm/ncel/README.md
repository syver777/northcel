# ncel (npm) — NorthCel native runtime launcher

`ncel` runs the **native NorthCel runtime** for `.ncel` files: a MoonBit typed-AST
stage, Bend 0.2.38 / HVM 2.0.22 for `bend_swarm` agents, and GLSL 4.30 rasterised
by a Mesa/EGL (llvmpipe) context. The runtime ships in the platform package
`@ncel/linux-x64` (an `optionalDependency`), so there is no download on first run.

```
npm install -g ncel
npx ncel doctor
npx ncel verify
npx ncel render scene.ncel -o frame.png --json
npx ncel film film.ncel -o out/ --frames 0..5 --mp4 out.mp4 --json
npx ncel guide
```

## Platform support, stated plainly

**Linux x86_64 only** in this release, glibc >= 2.39 (`manylinux_2_39`), with Mesa
`libegl1`/`libgl1`/`mesa-libgallium` for the GL runtime. GLSL is compiled by the
driver, not installed.

On macOS, Windows or linux-aarch64 the optional platform package is skipped, and
this launcher then prints the exact reason and exits 3. **It does not render.** No
Node-only renderer exists in this package and none is claimed — for a labelled
non-native fallback use the Python package (`pip install ncel`), which uses the
`northcel` reference renderer and marks it `python-reference`.

## What it does not include

* `fmt` — formatting is the Python reference (`pip install northcel`).
* the native runtime itself — that is `@ncel/linux-x64`, installed automatically
  on a supported platform.
* anything that calls `python`: this launcher only spawns the bundled binary.

`npx ncel verify` renders the bundled starter scene, the shower `f0001`
conformance frame and a 6-frame film twice, and checks the pinned sha256 values —
the same proof the pip package runs.

Licence: Proprietary, North Noir. Source: `packaging/` in the NorthNoir repository.
