# NorthCel (`.ncel`) Examples & Measured Benchmarks

All example `.ncel` files ship inside `packages/northcel/northcel/examples/` and are verified by the automated test suite.

---

## 1. Byte & Token Counts Across Examples (`tiktoken cl100k_base`)

| Example File | Mode / Description | Bytes | `cl100k` Tokens | Frames |
| --- | --- | ---: | ---: | ---: |
| `lantern_film.ncel` | **AI-Authored Animated Film** (`film`, `def`/`use`, `stroke`, `ribbon`, `bend_swarm`, color, `boil`) | **1,068 B** | **458 tok** | 6 frames |
| `shower_f0001_compact.ncel` | **Compact 1px Base-63 Traced Still** (`precision: 1px`, 4 washes + 160 Bend swarm agents) | **14,686 B** | **9,465 tok** | 1 frame (`f0001`) |
| `shower_f0001.ncel` | **Subpixel 0.25px Traced Still** (`precision: 0.25px`, exact quarter-pixel relative chains) | **66,178 B** | **44,881 tok** | 1 frame (`f0001`) |
| `shower_f0002.ncel` | **Subpixel 0.25px Traced Still** (`precision: 0.25px`, exact quarter-pixel relative chains) | **65,082 B** | **43,828 tok** | 1 frame (`f0002`) |
| `shower_film_2f.ncel` | **2-Frame Subpixel Traced Film** (`film` container combining `f0001` and `f0002`) | **131,189 B** | **88,690 tok** | 2 frames |

### Honest Tradeoff: AI-Authored vs. Traced Teacher Contours
- **When AI authors a scene directly** using `def`/`use`, `stroke`, `ribbon`, and parametric `bend_swarm` rules (`lantern_film.ncel`), a 6-frame animated shot takes only **1,068 bytes (458 tokens)**.
- **When reconstructing a complex raster illustration by tracing every wet hair strand, beard bristle, and water droplet** (`shower_f0001` & `f0002`):
  - The **1px Base-63 mode** (`29.5 KB / 19.1k tokens` for both frames) is **20.4% smaller** than the `v7` JS+SVG baseline (`37.1 KB / 23.6k tokens`) while improving SSIM from `0.911` to `0.937–0.946`.
  - The **0.25px Subpixel mode** (`131.2 KB / 88.7k tokens` for both frames, `3.5×` the bytes of `v7` JS+SVG and `32%` smaller than raw uncompressed tables) achieves the full **`0.9617 / 0.9718` SSIM** and **`0.695 / 0.658` Edge IoU**.

---

## 2. Reproducibility Against Saved GLSL & Teacher Renders

The pure-Python + NumPy reference renderer (`northcel render`) reproduces the saved OpenGL 4.3 (`llvmpipe`) GLSL renders within **`0.0115` greyscale MAE (`0.999992+` SSIM)**:

| Frame | Reference Renderer vs. Saved GLSL SSIM | Reference Renderer vs. Saved GLSL MAE | Reference Renderer vs. Teacher SSIM | Reference Renderer vs. Teacher MAE | Reference Renderer vs. Teacher Edge IoU |
| --- | :---: | :---: | :---: | :---: | :---: |
| `shower_f0001.ncel` | `0.999992` | `0.0115` | **`0.961733`** | **`3.3014`** | **`0.6945`** |
| `shower_f0002.ncel` | `0.999993` | `0.0113` | **`0.971794`** | **`3.2989`** | **`0.6582`** |

Visual comparison artifacts are banked in `docs/northcel/assets/`:
- `docs/northcel/assets/side_by_side_all_variants.png`
- `docs/northcel/assets/northcel_vs_v7_and_teacher.png`
- `docs/northcel/assets/detail_face_f0001.png`
