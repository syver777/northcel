# NorthCel (`.ncel`) — Training Plan (Plan Only)

> **Status:** Design & Data Pipeline Plan (`2026-11-03`). No model training is executed in Phase A.

---

## 1. Objective

Train or fine-tune a code-drawing language model so that, given:
1. A section brief / story prompt,
2. Optional character/style reference art or previous frame context, and
3. Optional surgical `Adjust` instructions,

the model directly emits valid, compact **NorthCel (`.ncel`)** code that renders every frame deterministically with high visual fidelity and clean layer separation.

---

## 2. End-to-End Dataset Construction Pipeline

```text
Source Video / Ruvil 2.1 or 7.3 Teacher Frames
  -> (1) Frame Extraction (6 fps or 12 fps, 1024x1024 / 1920x1080)
  -> (2) Tonal & Semantic Layer Segmentation (Paper, Background Wash, Skin/Mid Wash, Dark Hair/Prop Wash, Ink Ribbons, Droplet/Bristle Swarms)
  -> (3) Multi-Tier .ncel Fitting (`precision: 1px` Base-63 + `precision: 0.25px` Subpixel + Parametric `stroke`/`ribbon`/`def`)
  -> (4) Reference Render (`northcel render` / `northcel film`)
  -> (5) Automated Quality Gate (SSIM >= 0.94, MAE <= 4.5, Edge IoU >= 0.45, `northcel check` == OK)
  -> (6) Banked `(prompt, teacher_frame, .ncel, rendered_png, metrics.json)` Training Tuple
```

---

## 3. Concrete Data Format (`JSONL` + Sidecar `.ncel` / `.png`)

Each training record in `dataset/train.jsonl` follows a strict schema:

```json
{
  "clip_id": "s02_shower",
  "frame_index": 0,
  "fps": 6,
  "width": 1024,
  "height": 1024,
  "teacher_source": "ruvil_7_3",
  "brief": "Medium profile shot of a man standing under a running shower, head bowed, wet hair fringe, beard stubble, water spray.",
  "precision_tier": "1px",
  "ncel_path": "ncel/s02_shower_f0001_compact.ncel",
  "teacher_image_path": "teachers/s02_shower_f0001.jpg",
  "rendered_image_path": "renders/s02_shower_f0001.png",
  "metrics": {
    "block_ssim": 0.9366,
    "window_ssim": 0.9156,
    "gray_mae": 4.61,
    "edge_iou": 0.3757,
    "bytes": 14686,
    "tokens_cl100k": 9465
  }
}
```

### How Existing Ruvil 2.1 and Ruvil 7.3 Outputs Serve as Teachers
- **Ruvil 7.3 (`images as frames`, 6 fps):** Provides high-craft 2D hand-drawn frame strips (`RF3_frames` / `s02_shower_f0001.jpg`..`f0012.jpg`) with classical animation timing. Fitting each frame into `.ncel` turns flat raster cels into named, surgically editable vector layers (`tile_wall`, `skin_envelope`, `hair_dome`, `ink_contours`, `water_droplets`, `beard_and_chest_bristles`).
- **Ruvil 2.1 (`.js`-drawn scenes, 30 fps):** Provides already-layered procedural scenes (`scene.html` with separate background, character rig, and foreground passes). Because Ruvil 2.1 can render each layer in isolation, we can extract ground-truth per-layer `.ncel` primitives without occlusion ambiguity.

---

## 4. What the Language Needs So a Model Can Learn to Emit It Cleanly

Our shower experiment exposed a critical lesson:
- **Raw 0.25px contour tables (`~44k tokens/frame`) are too long for a single LLM completion**, whereas
- **Parametric `def`/`use` + `stroke`/`ribbon` (`~458 tokens` for 6 frames in `lantern_film.ncel`) and `1px` Base-63 (`~9.4k tokens/frame`) fit comfortably inside standard context windows.**

Therefore, for training a generative model to emit `.ncel` from scratch or from a reference image, we use a **two-level curriculum**:
1. **Stage 1 (Structural & Parametric `.ncel`):** Train on compact scenes (`<= 4,096 tokens`) where washes are simplified (`eps=1.2..1.8`) and fine hair/beard/water are expressed as parametric `stroke`, `ribbon`, and `bend_swarm` generators rather than 10,000 raw vertices.
2. **Stage 2 (Surgical `Adjust` & Frame-to-Frame Delta Pairs):** Train on `(frame_t.ncel, instruction, frame_t+1.ncel)` triples where only the moving layer or `bend_swarm` changes between frames.

---

## 5. Evaluation Protocol & Storage Layout

- **Metrics:**
  1. **Syntactic & Semantic Validity Rate (`%` passing `northcel check`)** — target `>= 99%` after 1 self-repair turn.
  2. **Visual Reconstruction Fidelity (Block SSIM, Window SSIM, Gray/RGB MAE, Exact Canny Edge IoU)** on held-out clips (never training clips).
  3. **Fine-Detail Region SSIM** on bounding boxes (`hair_fringe`, `ear`, `brow_eye`, `beard_stubble`, `water_spray`).
  4. **Surgical Edit Isolation (`Adjust` Locality):** Verify that editing layer `X` produces `0.0` pixel difference outside layer `X`'s bounding mask.
  5. **Token Efficiency:** `cl100k` tokens per rendered second of video.
- **Storage:** Keep training artifacts in a dedicated bucket/directory (`work/training/northcel-dataset/` locally or a private Supabase/GCS bucket), storing compressed `.ncel` text alongside `metrics.json` manifests.
