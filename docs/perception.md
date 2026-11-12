# Optional perception helpers

**Tools 0.7.2.** These commands are in the package, but each backend remains a
separate optional install. `pip install "northcel[perceive]"` adds the
PyPI-installable pieces (VTracer, PyTorch/TorchVision, TensorFlow). SAM 2 itself
is installed from its upstream git repository because it is not on PyPI, and
model weights are always supplied as local paths. No ML dependency is required
to import NorthCel or render ordinary documents.

Tools suggest; the AI decides. Masks, vectors, motion hints and interpolation
guides are observations to inspect, not semantic truth, animation recipes or
quality approval. Nothing here changes parsing, rendering or verification.

## Safety and installation

- Pillow and NumPy handle image I/O. Inputs are converted to RGB, flattening
  alpha onto white, without resizing or changing EXIF orientation.
- Backend imports happen only inside the selected command. Importing the
  package, CLI or parser, and reading help, does not import any optional ML or
  tracing backend. Commands never install packages or download models.
- Obtain models explicitly, check the particular checkpoint's terms, and pass
  existing **local** paths. No hub identifiers, `from_pretrained`, remote model
  URLs or auto-selected pretrained weights are used. Only load trusted models;
  loading a local model is not a security sandbox.
- Use a fresh output path/directory. Generated files with the same names are
  overwritten; a failed command can leave partial artifacts. Only trust a
  successful receipt for a complete result.
- Install backend builds appropriate for your Python, OS and device. CPU is
  the default for SAM 2 and RAFT; `--device cuda` explicitly selects CUDA.
  Large images and models may need substantial memory and time.

### Licence audit

Upstream licence files and API sources were checked on **2026-11-10**. No
third-party code, binaries or weights are copied into this repository. The table
records the chosen backends and the explicitly excluded alternatives, not a
blanket licence grant for all transitive wheel contents or arbitrary checkpoints.
Keep upstream notices and audit the exact distributions/weights before any
redistribution. Permissively licensed code does not establish a dataset or
checkpoint's commercial terms.

| Component | Checked licence / source | Integration policy |
| --- | --- | --- |
| SAM 2 / SAM 2.1 | [Apache-2.0](https://github.com/facebookresearch/sam2/blob/main/LICENSE); upstream [README](https://github.com/facebookresearch/sam2#license) explicitly includes official checkpoints | Optional `sam2` image/video APIs; user installs `python3 -m pip install "git+https://github.com/facebookresearch/sam2.git"` and obtains matching weights separately. Demo fonts/assets are not used. |
| SAM 2 optional connected-component extension (`cc_torch`) | [BSD-3-Clause](https://github.com/facebookresearch/sam2/blob/main/LICENSE_cctorch) | Upstream optional post-processing; not vendored or built by NorthCel. |
| VTracer Python 0.6.11 | [MIT](https://github.com/visioncortex/vtracer/blob/0.6.12/LICENSE); [0.6.11 source distribution/API](https://pypi.org/project/vtracer/0.6.11/) | Optional `python3 -m pip install "vtracer==0.6.11"`; uses `convert_pixels_to_svg` with `hierarchical="stacked"`. The newer 1.x API is not targeted. |
| TorchVision RAFT / original RAFT | [BSD-3-Clause (TorchVision)](https://github.com/pytorch/vision/blob/main/LICENSE), [BSD-3-Clause (RAFT)](https://github.com/princeton-vl/RAFT/blob/master/LICENSE) | Optional TorchVision `raft_small` / `raft_large`, never implicit pretrained weights. Check the selected weight file's provenance/terms separately. |
| PyTorch | [BSD-style licence and notices](https://github.com/pytorch/pytorch/blob/main/LICENSE) | Optional SAM 2 / RAFT runtime. Install compatible `torch torchvision` builds using [upstream instructions](https://pytorch.org/get-started/locally/). |
| FILM | [Apache-2.0 code](https://github.com/google-research/frame-interpolation/blob/main/LICENSE); [SavedModel API](https://github.com/google-research/frame-interpolation/blob/main/eval/interpolator.py) | Optional local FILM SavedModel. No FILM source installation is needed for this direct callable adapter. The code licence alone is not proof of a separately distributed model archive's terms; the user must check that archive. |
| TensorFlow | [Apache-2.0 plus bundled notices](https://github.com/tensorflow/tensorflow/blob/master/LICENSE) | Optional `python3 -m pip install tensorflow` for loading FILM SavedModels; no TensorFlow Hub. |
| Existing `fit --stacked` fallback | NorthCel MIT OR Apache-2.0; [OpenCV Apache-2.0](https://github.com/opencv/opencv/blob/5.x/LICENSE); [scikit-image BSD notices](https://github.com/scikit-image/scikit-image/blob/v0.26.0/LICENSE.txt) | Runs only if the already-existing `northcel[fit]` libraries are importable. Nothing is auto-installed. |
| SEA-RAFT | [BSD-3-Clause](https://github.com/princeton-vl/SEA-RAFT/blob/main/LICENSE) | External alternative; no bundled adapter, weights or imports. |
| RIFE (ECCV2022 upstream) | [MIT](https://github.com/hzwer/ECCV2022-RIFE/blob/main/LICENSE), **not Apache-2.0** | External alternative; this implementation selects FILM instead. Other forks/models require separate checks. |
| SAM 3 | Meta's **SAM License** (custom, last updated 2025-11-19; not Apache/MIT): royalty-free use/modification/redistribution with a copy of the agreement, no military/ITAR/sanctions use, no reverse engineering, publication acknowledgement, no MAU threshold | Redistribution *is* permitted under the SAM License, but it is not an OSI open-source licence and imposes use restrictions. NorthCel therefore keeps SAM 3 **external opt-in only**: no imports, text-prompt flag, download, dependency or redistribution in this package. |
| Potrace / AutoTrace | GPL-family; see [Potrace](https://potrace.sourceforge.net/#license) and [AutoTrace](https://github.com/autotrace/autotrace) | External-only, never vendored, imported or invoked by these helpers. |
| DiffVG / LIVE | Not audited for this integration | Not integrated; no imports or installs. |

Pillow and NumPy are unchanged core requirements, not new optional dependencies.
SAM 2's package manager may install its upstream requirements when the **user**
explicitly installs it; NorthCel never does that itself.

## Commands

These work through `northcel` / `ncel` and the Python reference CLI. They do not
probe or use the native renderer and do not accept renderer-routing flags.

### Segment: point/box masks

```sh
northcel perceive segment IMAGE --points 12,18 --points 20,24 --out masks \
  --checkpoint /local/models/sam2.1_hiera_tiny.pt \
  --config configs/sam2.1/sam2.1_hiera_t.yaml --json
northcel perceive segment IMAGE --boxes 0,0,80,80 90,10,140,70 --out masks \
  --checkpoint /local/models/sam2.1_hiera_tiny.pt --json
```

Repeat `--points` for foreground clicks belonging to **one** object, or pass
one or more boxes (also repeatable) for separate objects. The two options are
mutually exclusive and one is required. Coordinates are finite input-image
pixels, with `(0,0)` at the top left. Clicks and box starts must lie inside the
image; a box's upper bounds may equal the image width/height. Require
`x0 < x1`, `y0 < y1`. No negative clicks, automatic mask generation or SAM 3
text prompts are exposed.

`--config` defaults to `configs/sam2.1/sam2.1_hiera_t.yaml`; it is SAM 2's
installed-package config name, not a URL. Select a config matching your
checkpoint. `NORTHCEL_SAM2_CHECKPOINT` and `NORTHCEL_SAM2_CONFIG` can provide
explicit local configuration; command-line options take precedence.

Outputs: `mask-001.png`, etc. (8-bit grayscale, foreground 255), plus
`perception.json` with object IDs, pixel areas, half-open bounding boxes and
SAM scores. Scores are backend predictions, not acceptance ratings. Masks can
be passed to the existing `fit --mask` command; the AI chooses grouping.

Add `--frames DIR` to request propagation with the installed SAM 2 video API:

```sh
northcel perceive segment keys/00000.jpg --points 12,18 --frames keys --out tracks \
  --checkpoint /local/models/sam2.1_hiera_tiny.pt --json
```

The directory must contain same-size, numerically named JPEGs (e.g. `00000.jpg`,
`00010.jpg`), with unique numeric stems. IMAGE must be the first JPEG. Prompts
seed frame index 0; frames are visited in numeric order and are **sequence
indices**, not time values inferred from filenames. Other file types are ignored.
Output names are `f00000-mask-001.png`, etc.; each receipt row records its source
path and sequence index. All frames/objects must be returned. An absent or
incompatible video API produces an actionable error, never a false propagation
claim. This wrapper loads the frame images in memory to validate dimensions.

### Vectorize: VTracer or a labelled fallback

```sh
northcel perceive vectorize IMAGE --out drawing.svg --mode stacked --json
```

VTracer writes **SVG**, not NorthCel source or a renderer preview. Pillow decodes
the source and passes RGBA pixels to VTracer. `stacked` is the only exposed mode
and the default; spline curve fitting is used. No SVG-to-NorthCel conversion or
automatic error comparison is claimed.

If VTracer cannot be imported but both existing fit libraries are available,
request the **different output format** explicitly:

```sh
northcel perceive vectorize IMAGE --out drawing.ncel --json
```

This runs existing `fit --stacked`, records `fallback.tool`,
`fallback.available: true`, `fallback.executed: true`, includes the fit receipt,
and leaves VTracer's top-level `available` / `executed` false. Text output also
names the fallback. It never puts NorthCel text in an `.svg` file. With VTracer
installed, `.svg` is required; without it, fallback requires `.ncel`. An installed
but incompatible/broken VTracer API is an error, not a silent fallback.

The receipt is `FILE.json` (for example `drawing.svg.json` or
`drawing.ncel.json`). No Potrace/AutoTrace subprocess is used.

### Flow: geometric motion hints

```sh
northcel perceive flow A B --out motion --checkpoint /local/models/raft-small.pth --json
```

Optional backend: TorchVision RAFT. `--model small` (default) or `--model large`
must match the provided **TorchVision state dict**. An original RAFT/SEA-RAFT
checkpoint is not automatically converted. `NORTHCEL_RAFT_CHECKPOINT` can supply
the local path. The model is constructed with `weights=None` and the state dict
is loaded with `weights_only=True`; no weight enumeration/default download runs.

Images must have identical dimensions. Inputs are mapped to `[-1,1]`, padded
on the right/bottom to multiples of 8 and at least 128 pixels per axis, then
cropped back, without flow-vector rescaling. Inference uses 12 updates.

Outputs: `flow.npy` (`H × W × 2`, `dx,dy`, **A → B**, input-pixel units),
`flow.png` (hue = direction, brightness = magnitude/max magnitude in this pair;
zero motion is black), and `perception.json`. Moving pixels have distance ≥1px.
For each 32×32 tile containing moving pixels, JSON reports a tile bbox, moving
pixel count and median moving-pixel displacement/distance. These tiles are
geometric hints, **not semantic objects or tracked shape IDs**. Brightness is
pair-relative, not comparable across pairs. Flow may be wrong around occlusions,
new content or large changes. SEA-RAFT remains an external alternative.

### Guide: a visual target only

```sh
northcel perceive guide A B --out guides --model-dir /local/models/film/saved_model --json
```

Optional backend: TensorFlow loading a local, official-API-compatible FILM
SavedModel (`saved_model.pb` plus its associated files). `NORTHCEL_FILM_MODEL`
can supply the directory. Inputs must have identical dimensions. The wrapper
uses float32 RGB `[0,1]`, symmetric zero-padding to multiples of 64 and the FILM
callable `{'x0', 'x1', 'time'} → {'image'}`, then crops back to the input size.

It produces **one midpoint** at `t=0.5`: `guide-only-t0500.png` plus
`perception.json`. The receipt, each frame row and PNG text metadata all carry
`guide_only: true` (the PNG text value is the string `"true"`). Text mode labels
the result GUIDE ONLY. These are visual targets for an AI to inspect, **never
output frames and never quality evidence**. No assembler, renderer or verifier
consumes them automatically. There is no RIFE adapter.

## Receipt and error contract

With `--json`, stdout is exactly one JSON object for a parsed command, including
runtime failures; backend banners/progress go to stderr, including native code
writing to file descriptor 1. Redirection is scoped to the CLI invocation, not a
thread-safe inference API. Successful commands also save the same receipt beside the outputs.
All receipts contain:

- `command`, `tool`, `version` (backend/distribution version or null when absent),
  `northcel_version`, `available`, `executed`;
- `input` paths, `output.requested` and, on success, actual output/receipt paths;
- `ok`, `suggestion_only: true`, `quality: "unreviewed"`, `errors`, `warnings`.

`version` for `raft` is the TorchVision version; for `film` it is the TensorFlow
version. `available` means the backend was successfully imported during this
invocation, not that model loading/inference succeeded. Inputs are validated
first, so an invalid input can leave it false without probing dependencies.
`executed` means requested-backend inference/conversion returned; it can be true
on a subsequent validation or output-write failure. Inspect **both** `ok` and the
process exit code. A successful fit fallback has `ok: true` but top-level
`executed: false`; its nested fallback record identifies what actually ran.

Exit codes: **0** completed, **1** unavailable backend, invalid data/model path,
backend failure or I/O error, **2** argparse usage errors. Usage errors print
normal argparse diagnostics to stderr, not a runtime JSON receipt. Runtime
`errors` contain `{ "location": "path-or-option-or-backend", "message": "..." }`;
text mode prints `LOCATION: error: MESSAGE`, without a traceback.

### Exact absent-dependency messages

These are the exact runtime `message` values (text adds the location prefix).
They are asserted literally by tests. VTracer's absence message is fatal when
fit is unavailable; with fit available it is recorded as a fallback warning.

**Location `sam2`:**

```text
SAM 2 is unavailable. Install with: python3 -m pip install "git+https://github.com/facebookresearch/sam2.git". Licence: Apache-2.0 (code and official checkpoints; optional cc_torch: BSD-3-Clause). Supply a local --checkpoint and --config; no model is downloaded by NorthCel.
```

**Location `vtracer`:**

```text
VTracer is unavailable. Install with: python3 -m pip install "vtracer==0.6.11". Licence: MIT. The fit --stacked fallback requires already-installed northcel[fit].
```

**Location `torchvision`:**

```text
RAFT is unavailable. Install with: python3 -m pip install torch torchvision (choose compatible builds at https://pytorch.org/get-started/locally/). Licence: BSD-3-Clause (TorchVision/RAFT), BSD-style (PyTorch). Supply a local --checkpoint; no model is downloaded by NorthCel.
```

**Location `tensorflow`:**

```text
FILM is unavailable. Install with: python3 -m pip install tensorflow. Licence: Apache-2.0 (TensorFlow and FILM code). Supply a local FILM SavedModel with --model-dir and check its weight licence; no model is downloaded by NorthCel. Guides are not output frames or quality evidence.
```

## Validation limits

Tests use fake optional modules and synthetic images; they cover import laziness,
literal absence errors, CLI parsing, local-path checks, backend call contracts,
propagation, image/JSON outputs and honest fallback/guide labels. No models are
downloaded for tests. Passing these tests does **not** establish real-model
accuracy, GPU compatibility or commercial terms of an arbitrary weight file.
Keep using the independent [verification commands](reference.md) to compare
AI-authored changes with real references, not with interpolation guides.
