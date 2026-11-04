# NorthCel (`.ncel`) — Frequently Asked Questions

### 1. Why did you rename the language from NoirLang (`.noir`) to NorthCel (`.ncel`)?
The name `Noir` and extension `.noir` collide with Aztec's zero-knowledge domain-specific language (`noir-lang.org`). **NorthCel** (`.ncel`, CLI `northcel` / `ncel`) is uniquely tied to North Noir and classical animation *cels*, and both `northcel` on PyPI and `northcel` on npm were verified unoccupied.

### 2. Do I need MoonBit, Bend, or a GPU installed to run `northcel`?
**No.** While NorthCel's design combines MoonBit's typed AST, Bend's stateless parallel agent swarms, and GLSL's 4×4 subpixel winding rasterization, the reference package (`pip install northcel`) includes a fast **pure-Python + NumPy 4×4 subpixel renderer** that reproduces the OpenGL 4.3 GLSL output within `0.0115` greyscale MAE (`0.999992+` SSIM) on any CPU.

### 3. Why are traced `.ncel` files larger than hand-authored `.ncel` files?
When an AI agent authors a scene directly using `def`/`use`, `stroke`, `ribbon`, and parametric `bend_swarm` rules (`lantern_film.ncel`), a 6-frame animated film is only **1,068 bytes (458 tokens)**. When reconstructing a complex raster illustration by tracing 440+ rings and 10,900+ vertices (`shower_f0001.ncel`), the file stores every individual wet hair strand and beard bristle contour:
- In **`precision: 1px` (Base-63)** mode, two 1024×1024 frames take **29,560 bytes (19,123 tokens)** — **20.4% smaller** than the `v7` JS+SVG baseline (`37,120 bytes`) while raising SSIM from `0.911` to `0.937–0.946`.
- In **`precision: 0.25px` (Subpixel)** mode, two frames take **131,240 bytes (88,703 tokens)** (`3.5×` `v7` bytes, `32%` smaller than raw uncompressed tables) and achieve **`0.9617 / 0.9718` SSIM** and **`0.695 / 0.658` Edge IoU**.
