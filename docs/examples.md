# NorthCel (`.ncel`) — Examples & measurements

All example `.ncel` files ship inside `python/northcel/examples/` and are verified
by the automated test suite.

## 1. Byte and token counts

Counts use the `tiktoken` `cl100k_base` vocabulary.

| Example file | What it is | Bytes | `cl100k` tokens | Frames |
| --- | --- | ---: | ---: | ---: |
| `tv7_f0076_ai_cel.ncel` | a hand-authored colour cel scene (a seated man with a walking duck) using `palette`, `cel`, `outline` and `0.25px-b63` | **6,306 B** | **4,438 tok** | 1 (`1536×864`) |
| `lantern_film.ncel` | a hand-authored animated film (`film`, `def`/`use`, `stroke`, `ribbon`, `bend_swarm`, colour, `boil`) | **1,068 B** | **458 tok** | 6 |
| `shower_f0001_compact.ncel` | a compact 1px Base-63 traced still (`precision: 1px`, 4 washes + 160 Bend swarm agents) | **14,686 B** | **9,465 tok** | 1 (`f0001`) |
| `shower_f0001.ncel` | a subpixel 0.25px traced still (exact quarter-pixel relative chains) | **66,178 B** | **44,881 tok** | 1 (`f0001`) |
| `shower_f0002.ncel` | a subpixel 0.25px traced still (exact quarter-pixel relative chains) | **65,082 B** | **43,828 tok** | 1 (`f0002`) |
| `shower_film_2f.ncel` | a 2-frame subpixel traced film (`film` combining `f0001` and `f0002`) | **131,189 B** | **88,690 tok** | 2 |

## 2. Hand-authored vs traced

- A hand-authored 6-frame animated shot using `def`/`use`, `stroke`, `ribbon` and
  parametric `bend_swarm` rules (`lantern_film.ncel`) takes **1,068 bytes
  (458 tokens)**.
- Reconstructing a complex raster illustration by tracing every wet hair strand,
  beard bristle and water droplet (`shower_f0001` and `f0002`) stores every
  contour, so the files are much larger:
  - **`precision: 1px` (Base-63):** both 1024×1024 frames take **29,560 bytes
    (19,123 tokens)**, with SSIM `0.937–0.946` against the source photograph.
  - **`precision: 0.25px` (subpixel):** both frames take **131,240 bytes
    (88,703 tokens)** — `32%` smaller than raw uncompressed coordinate tables —
    and reach SSIM `0.9617 / 0.9718` and Edge IoU `0.695 / 0.658`.

## 3. Agreement between the two implementations

The pure-Python + NumPy reference renderer reproduces the saved OpenGL 4.3
(`llvmpipe`) GLSL renders within **`0.0115` greyscale MAE (`0.999992+` SSIM)**:

| Frame | Reference vs. saved GLSL SSIM | Reference vs. saved GLSL MAE | Reference vs. source SSIM | Reference vs. source MAE | Reference vs. source Edge IoU |
| --- | :---: | :---: | :---: | :---: | :---: |
| `shower_f0001.ncel` | `0.999992` | `0.0115` | **`0.961733`** | **`3.3014`** | **`0.6945`** |
| `shower_f0002.ncel` | `0.999993` | `0.0113` | **`0.971794`** | **`3.2989`** | **`0.6582`** |

Visual comparison artifacts are in `docs/assets/`:

- `docs/assets/side_by_side_all_variants.png`
- `docs/assets/northcel_vs_source.png`
- `docs/assets/detail_face_f0001.png`
