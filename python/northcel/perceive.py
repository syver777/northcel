"""Optional, offline perception suggestions. No optional imports or model downloads.

Only the command being executed imports its backend. Model paths must be local;
these helpers never use hub/from_pretrained APIs or install dependencies.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager, redirect_stdout
import importlib
from importlib import metadata
import json
import os
from pathlib import Path
import sys

import numpy as np
from PIL import Image

from .config import PACKAGE_VERSION


SAM2_HINT = (
    'SAM 2 is unavailable. Install with: python3 -m pip install '
    '"git+https://github.com/facebookresearch/sam2.git". '
    'Licence: Apache-2.0 (code and official checkpoints; optional cc_torch: BSD-3-Clause). '
    'Supply a local --checkpoint and --config; no model is downloaded by NorthCel.'
)
VTRACER_HINT = (
    'VTracer is unavailable. Install with: python3 -m pip install "vtracer==0.6.11". '
    'Licence: MIT. The fit --stacked fallback requires already-installed northcel[fit].'
)
RAFT_HINT = (
    'RAFT is unavailable. Install with: python3 -m pip install torch torchvision '
    '(choose compatible builds at https://pytorch.org/get-started/locally/). '
    'Licence: BSD-3-Clause (TorchVision/RAFT), BSD-style (PyTorch). '
    'Supply a local --checkpoint; no model is downloaded by NorthCel.'
)
FILM_HINT = (
    'FILM is unavailable. Install with: python3 -m pip install tensorflow. '
    'Licence: Apache-2.0 (TensorFlow and FILM code). '
    'Supply a local FILM SavedModel with --model-dir and check its weight licence; '
    'no model is downloaded by NorthCel. Guides are not output frames or quality evidence.'
)


class PerceptionError(Exception):
    """An actionable diagnostic located at an input, output, or option."""

    def __init__(self, location: str | Path, message: str):
        self.location = str(location)
        super().__init__(message)


def register_parser(subparsers) -> None:
    parser = subparsers.add_parser("perceive", help="Optional offline perception suggestions (JSON + images).")
    commands = parser.add_subparsers(dest="perception", required=True)
    segment = commands.add_parser("segment", help="SAM 2 point/box masks; optional propagation.")
    segment.add_argument("image")
    prompts = segment.add_mutually_exclusive_group(required=True)
    prompts.add_argument("--points", action="append", metavar="x,y", help="Foreground clicks for one object; repeatable")
    prompts.add_argument("--boxes", action="extend", nargs="+", metavar="x0,y0,x1,y1", help="One object per box")
    segment.add_argument("--frames", help="Numbered JPEG directory; IMAGE must be its first frame")
    segment.add_argument("--checkpoint", default=os.environ.get("NORTHCEL_SAM2_CHECKPOINT"))
    segment.add_argument("--config", default=os.environ.get("NORTHCEL_SAM2_CONFIG", "configs/sam2.1/sam2.1_hiera_t.yaml"))
    segment.add_argument("--device", default="cpu")

    vectorize = commands.add_parser("vectorize", help="VTracer SVG, or an explicitly labelled stacked-fit fallback.")
    vectorize.add_argument("image")
    vectorize.add_argument("--mode", choices=["stacked"], default="stacked")

    flow = commands.add_parser("flow", help="RAFT forward flow visualization and geometric motion hints.")
    flow.add_argument("a")
    flow.add_argument("b")
    flow.add_argument("--checkpoint", default=os.environ.get("NORTHCEL_RAFT_CHECKPOINT"))
    flow.add_argument("--model", choices=["small", "large"], default="small")
    flow.add_argument("--device", default="cpu")

    guide = commands.add_parser("guide", help="FILM midpoint guide; never an output frame or quality claim.")
    guide.add_argument("a")
    guide.add_argument("b")
    guide.add_argument("--model-dir", default=os.environ.get("NORTHCEL_FILM_MODEL"))

    for command in (segment, vectorize, flow, guide):
        command.add_argument("--out", required=True)
        command.add_argument("--json", action="store_true", help="One JSON receipt on stdout, including runtime errors")
        command.set_defaults(func=run_command)


def _version(module, distribution: str) -> str:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return str(getattr(module, "__version__", "unknown"))


def _backend(result: dict, module: str, distribution: str, hint: str):
    try:
        backend = importlib.import_module(module)
    except (ImportError, OSError) as exc:
        raise PerceptionError(module, hint) from exc
    result.update(available=True, version=_version(backend, distribution))
    return backend


def _local_path(value: str | None, option: str, *, directory: bool = False) -> Path:
    if not value or "://" in value:
        raise PerceptionError(option, "supply an existing local model path; downloads are never automatic")
    path = Path(value).expanduser()
    if not (path.is_dir() if directory else path.is_file()):
        raise PerceptionError(option, f"local model {'directory' if directory else 'file'} not found: {path}")
    return path


def _image(path: str | Path) -> np.ndarray:
    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            base = Image.new("RGBA", rgba.size, "white")
            base.alpha_composite(rgba)
            return np.array(base.convert("RGB"))
    except (OSError, ValueError) as exc:
        raise PerceptionError(path, f"cannot read image; supply a Pillow-readable image: {exc}") from exc


def _pair(args) -> tuple[np.ndarray, np.ndarray]:
    a, b = _image(args.a), _image(args.b)
    if a.shape != b.shape:
        raise PerceptionError(args.b, f"image dimensions differ from {args.a}; resize explicitly before perception")
    return a, b


def _numbers(values: list[str], count: int, option: str, width: int, height: int) -> np.ndarray:
    try:
        rows = np.asarray([[float(v) for v in row.split(",")] for row in values], dtype=np.float32)
    except ValueError as exc:
        raise PerceptionError(option, f"expected {count} finite comma-separated pixel coordinates per prompt") from exc
    if rows.shape != (len(values), count) or not np.isfinite(rows).all():
        raise PerceptionError(option, f"expected {count} finite comma-separated pixel coordinates per prompt")
    outside = (rows < 0).any() or (rows[:, 0] >= width).any() or (rows[:, 1] >= height).any()
    if count == 4:
        outside = outside or (rows[:, 2] > width).any() or (rows[:, 3] > height).any()
    if outside:
        raise PerceptionError(option, f"coordinates must lie inside the {width}x{height} image")
    if count == 4 and (rows[:, 2:] <= rows[:, :2]).any():
        raise PerceptionError(option, "boxes need x0 < x1 and y0 < y1")
    return rows


def _numpy(value) -> np.ndarray:
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    return np.asarray(value)


def _mask_row(value, image: np.ndarray, path: Path, object_id: int, *, logits: bool = False) -> dict:
    mask = _numpy(value)
    while mask.ndim > 2 and mask.shape[0] == 1:
        mask = mask[0]
    if mask.shape != image.shape[:2] or not np.isfinite(mask).all():
        raise PerceptionError("sam2", "backend returned an invalid mask; check model/API compatibility")
    mask = mask > (0 if logits else 0.5)
    Image.fromarray(mask.astype(np.uint8) * 255).save(path)
    ys, xs = np.nonzero(mask)
    return {"path": str(path), "object_id": object_id, "area_px": int(mask.sum()),
            "bbox": [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None}


def _segment(args, result: dict) -> None:
    image = _image(args.image)
    height, width = image.shape[:2]
    points = _numbers(args.points, 2, "--points", width, height) if args.points else None
    boxes = _numbers(args.boxes, 4, "--boxes", width, height) if args.boxes else None
    _backend(result, "sam2", "SAM-2", SAM2_HINT)
    try:
        build = importlib.import_module("sam2.build_sam")
        torch = importlib.import_module("torch")
        predictor_module = importlib.import_module("sam2.sam2_image_predictor") if not args.frames else None
    except (ImportError, OSError) as exc:
        result["available"] = False
        raise PerceptionError("sam2", SAM2_HINT) from exc
    checkpoint = _local_path(args.checkpoint, "--checkpoint")
    if not args.config or "://" in args.config:
        raise PerceptionError("--config", "supply a local SAM 2 package config name, not a remote URL")
    result["model"] = {"checkpoint": str(checkpoint), "config": args.config, "device": args.device}
    out = Path(args.out)
    if args.frames:
        _segment_frames(args, result, build, torch, checkpoint, points, boxes)
        return
    with torch.inference_mode():
        predictor = predictor_module.SAM2ImagePredictor(build.build_sam2(args.config, str(checkpoint), device=args.device))
        predictor.set_image(image)
        rows = []
        out.mkdir(parents=True, exist_ok=True)
        for index, box in enumerate(boxes if boxes is not None else [None], 1):
            masks, scores, _ = predictor.predict(
                point_coords=points, point_labels=np.ones(len(points), dtype=np.int32) if points is not None else None,
                box=box, multimask_output=False,
            )
            result["executed"] = True
            row = _mask_row(masks, image, out / f"mask-{index:03d}.png", index)
            row["score"] = float(_numpy(scores).reshape(-1)[0])
            if not np.isfinite(row["score"]):
                raise PerceptionError("sam2", "backend returned a non-finite mask score")
            rows.append(row)
    result["output"]["masks"] = rows
    result["propagation"] = {"requested": False, "executed": False}


def _segment_frames(args, result, build, torch, checkpoint, points, boxes) -> None:
    result["propagation"] = {"requested": True, "executed": False}
    builder = getattr(build, "build_sam2_video_predictor", None)
    if not callable(builder):
        raise PerceptionError("--frames", "installed SAM 2 has no video predictor API; upgrade SAM 2 or omit --frames")
    directory = Path(args.frames)
    if not directory.is_dir():
        raise PerceptionError(directory, "frame directory not found; supply numbered JPEG frames")
    frames = [p for p in directory.iterdir() if p.suffix.lower() in {".jpg", ".jpeg"}]
    if not frames or any(not p.stem.isdecimal() for p in frames):
        raise PerceptionError(directory, "SAM 2 propagation requires numerically named JPEG frames (00000.jpg, ...)")
    frames.sort(key=lambda p: (int(p.stem), p.name))
    if len({int(p.stem) for p in frames}) != len(frames):
        raise PerceptionError(directory, "frame numbers must be unique")
    if Path(args.image).resolve() != frames[0].resolve():
        raise PerceptionError(args.image, "IMAGE must be the first numbered JPEG in --frames; prompts seed frame 0")
    images = [_image(p) for p in frames]
    if any(image.shape != images[0].shape for image in images):
        raise PerceptionError(directory, "all propagation frames must have the same dimensions")
    with torch.inference_mode():
        predictor = builder(args.config, str(checkpoint), device=args.device)
        if not all(callable(getattr(predictor, name, None)) for name in
                   ("init_state", "add_new_points_or_box", "propagate_in_video")):
            raise PerceptionError("--frames", "installed SAM 2 video API is incompatible; upgrade SAM 2 or omit --frames")
        state = predictor.init_state(video_path=str(directory))
        for index, box in enumerate(boxes if boxes is not None else [None], 1):
            predictor.add_new_points_or_box(
                inference_state=state, frame_idx=0, obj_id=index, points=points,
                labels=np.ones(len(points), dtype=np.int32) if points is not None else None, box=box,
            )
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        rows = []
        seen = set()
        for frame_index, ids, logits in predictor.propagate_in_video(state):
            frame_index = int(frame_index)
            if not 0 <= frame_index < len(frames):
                raise PerceptionError("sam2", "video API returned an out-of-range frame index")
            for object_id, mask in zip(ids, logits):
                object_id = int(object_id)
                row = _mask_row(mask, images[frame_index], out / f"f{frame_index:05d}-mask-{object_id:03d}.png",
                                object_id, logits=True)
                row.update(frame=frame_index, input=str(frames[frame_index]))
                rows.append(row)
                seen.add((frame_index, object_id))
        result["executed"] = True
    expected = {(frame, obj) for frame in range(len(frames)) for obj in range(1, len(boxes) + 1 if boxes is not None else 2)}
    if seen != expected:
        raise PerceptionError("sam2", "video API returned incomplete propagation; no complete sequence is claimed")
    result["output"]["masks"] = rows
    result["propagation"]["executed"] = True
    result["input"] = [str(p) for p in frames]


def _vectorize(args, result: dict) -> None:
    image = _image(args.image)
    out = Path(args.out)
    try:
        vtracer = _backend(result, "vtracer", "vtracer", VTRACER_HINT)
    except PerceptionError:
        _fit_fallback(args, result, image)
        return
    if out.suffix.lower() != ".svg":
        raise PerceptionError("--out", "VTracer writes SVG; use an .svg output path")
    # 0.6.11's pixel API avoids backend image decoders and extra temporary files.
    pixels = Image.fromarray(image).convert("RGBA")
    data = pixels.get_flattened_data() if hasattr(pixels, "get_flattened_data") else pixels.getdata()
    svg = vtracer.convert_pixels_to_svg(list(data), pixels.size,
                                      colormode="color", hierarchical="stacked", mode="spline")
    result["executed"] = True
    if not isinstance(svg, str) or "<svg" not in svg:
        raise PerceptionError("vtracer", "backend did not return SVG; install the documented API version")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(svg, encoding="utf-8")
    result["output"].update(vector=str(out), format="svg")
    result["fallback"] = None


def _fit_fallback(args, result: dict, image: np.ndarray) -> None:
    try:
        importlib.import_module("cv2")
        importlib.import_module("skimage.measure")
    except (ImportError, OSError) as exc:
        raise PerceptionError("vtracer", VTRACER_HINT) from exc
    result["fallback"] = {"tool": "northcel fit --stacked", "version": PACKAGE_VERSION,
                          "available": True, "executed": False}
    result["warnings"].append(VTRACER_HINT)
    out = Path(args.out)
    if out.suffix.lower() != ".ncel":
        raise PerceptionError("--out", "VTracer is unavailable; fit --stacked writes NorthCel, not SVG. Use --out FILE.ncel for the labelled fallback")
    from .fitting import fit_stacked
    from .shapes import stacked_source

    drawing, receipt = fit_stacked(Image.fromarray(image))
    source = stacked_source(drawing)
    result["fallback"]["executed"] = True
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(source, encoding="utf-8")
    # executed describes the requested tool; VTracer did NOT run.
    result["output"].update(vector=str(out), format="northcel")
    result["fit_receipt"] = receipt


def _flow(args, result: dict) -> None:
    a, b = _pair(args)
    _backend(result, "torchvision", "torchvision", RAFT_HINT)
    try:
        torch = importlib.import_module("torch")
        optical_flow = importlib.import_module("torchvision.models.optical_flow")
    except (ImportError, OSError) as exc:
        result["available"] = False
        raise PerceptionError("torchvision", RAFT_HINT) from exc
    checkpoint = _local_path(args.checkpoint, "--checkpoint")
    model = getattr(optical_flow, f"raft_{args.model}")(weights=None, progress=False)
    state = torch.load(str(checkpoint), map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    model = model.to(args.device).eval()
    height, width = a.shape[:2]
    pad_h, pad_w = max(128, (height + 7) // 8 * 8) - height, max(128, (width + 7) // 8 * 8) - width

    def tensor(image):
        value = torch.from_numpy(image.transpose(2, 0, 1).copy()).float().unsqueeze(0).to(args.device) / 127.5 - 1
        return torch.nn.functional.pad(value, (0, pad_w, 0, pad_h), mode="replicate")

    with torch.inference_mode():
        flow = _numpy(model(tensor(a), tensor(b), num_flow_updates=12)[-1][0]).transpose(1, 2, 0)[:height, :width]
    result["executed"] = True
    if flow.shape != (height, width, 2) or not np.isfinite(flow).all():
        raise PerceptionError("raft", "backend returned invalid flow; check model/API compatibility")
    # Float32 squared norms can overflow even when both flow components are
    # finite. Keep all JSON statistics finite, including pathological models.
    vectors = flow.astype(np.float64)
    magnitude = np.hypot(vectors[:, :, 0], vectors[:, :, 1])
    if not np.isfinite(magnitude).all():
        raise PerceptionError("raft", "backend returned flow too large for finite motion hints; check the checkpoint")
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    np.save(out / "flow.npy", flow)
    scale = float(magnitude.max())
    hsv = np.zeros((height, width, 3), dtype=np.uint8)
    hsv[:, :, 0] = ((np.arctan2(flow[:, :, 1], flow[:, :, 0]) / (2 * np.pi) + 1) % 1 * 255).astype(np.uint8)
    hsv[:, :, 1] = 255
    hsv[:, :, 2] = (magnitude / scale * 255).astype(np.uint8) if scale else 0
    Image.fromarray(hsv, mode="HSV").convert("RGB").save(out / "flow.png")
    regions = []
    for y in range(0, height, 32):
        for x in range(0, width, 32):
            region = vectors[y:y + 32, x:x + 32]
            moved = magnitude[y:y + 32, x:x + 32] >= 1.0
            if moved.any():
                vector = np.median(region[moved], axis=0)
                regions.append({"bbox": [x, y, min(x + 32, width), min(y + 32, height)],
                                "dx_px": float(vector[0]), "dy_px": float(vector[1]),
                                "distance_px": float(np.hypot(vector[0], vector[1])), "moving_pixels": int(moved.sum())})
    result["motion"] = {"direction": "A_to_B", "units": "input_pixels", "threshold_px": 1.0,
                        "moving_pixels": int((magnitude >= 1).sum()), "max_distance_px": scale,
                        "regions": regions, "semantic_labels": False}
    result["model"] = {"checkpoint": str(checkpoint), "architecture": f"raft_{args.model}", "device": args.device}
    result["output"].update(visualization=str(out / "flow.png"), flow=str(out / "flow.npy"))


def _guide(args, result: dict) -> None:
    a, b = _pair(args)
    tf = _backend(result, "tensorflow", "tensorflow", FILM_HINT)
    model_dir = _local_path(args.model_dir, "--model-dir", directory=True)
    if not (model_dir / "saved_model.pb").is_file():
        raise PerceptionError(model_dir, "FILM model directory must contain saved_model.pb; export/download it explicitly first")
    # Official FILM SavedModel callable: {'x0', 'x1', 'time'} -> {'image'}.
    # Pad symmetrically to 64, then crop, like FILM's eval.interpolator.
    height, width = a.shape[:2]
    pad_h, pad_w = (-height) % 64, (-width) % 64
    top, left = pad_h // 2, pad_w // 2

    def batch(image):
        return np.pad(image.astype(np.float32) / 255, ((top, pad_h - top), (left, pad_w - left), (0, 0)))[None]

    model = tf.saved_model.load(str(model_dir))
    prediction = model({"x0": batch(a), "x1": batch(b), "time": np.array([[0.5]], dtype=np.float32)}, training=False)
    result["executed"] = True
    image = _numpy(prediction["image"])
    if image.shape != (1, height + pad_h, width + pad_w, 3) or not np.isfinite(image).all():
        raise PerceptionError("film", "backend returned an invalid guide image; check the FILM SavedModel signature")
    image = image[0, top:top + height, left:left + width]
    image = np.floor(np.clip(image, 0, 1) * 255 + 0.5).astype(np.uint8)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "guide-only-t0500.png"
    from PIL.PngImagePlugin import PngInfo

    info = PngInfo()
    info.add_text("guide_only", "true")
    info.add_text("usage", "visual target only; not an output frame or quality evidence")
    Image.fromarray(image).save(path, pnginfo=info)
    result["model"] = {"directory": str(model_dir), "backend": "FILM SavedModel"}
    result["output"]["frames"] = [{"path": str(path), "t": 0.5, "guide_only": True}]


@contextmanager
def _backend_output():
    """Reserve stdout for receipts, including native extensions' fd-1 banners.

    This is a CLI boundary, not a thread-safe library inference context.
    """
    sys.stdout.flush()
    saved = os.dup(1)
    try:
        os.dup2(2, 1)
        with redirect_stdout(sys.stderr):
            try:
                yield
            finally:
                sys.stdout.flush()
    finally:
        os.dup2(saved, 1)
        os.close(saved)


def run_command(args: argparse.Namespace) -> int:
    names = {"segment": "sam2", "vectorize": "vtracer", "flow": "raft", "guide": "film"}
    inputs = [args.image] if hasattr(args, "image") else [args.a, args.b]
    result = {"ok": False, "command": f"perceive {args.perception}", "tool": names[args.perception],
              "version": None, "northcel_version": PACKAGE_VERSION, "available": False, "executed": False,
              "input": inputs, "output": {"requested": args.out}, "suggestion_only": True,
              "quality": "unreviewed", "errors": [], "warnings": []}
    if args.perception == "guide":
        result["guide_only"] = True
    try:
        # Backends sometimes print progress/version banners. JSON stdout is ours.
        with _backend_output():
            {"segment": _segment, "vectorize": _vectorize, "flow": _flow, "guide": _guide}[args.perception](args, result)
        result["ok"] = True
        if args.perception == "vectorize":
            receipt = Path(str(args.out) + ".json")
        else:
            receipt = Path(args.out) / "perception.json"
        result["output"]["receipt"] = str(receipt)
        receipt.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    except PerceptionError as exc:
        result["ok"] = False
        result["errors"].append({"location": exc.location, "message": str(exc)})
    except Exception as exc:
        # Optional native/ML libraries also raise RuntimeError/AssertionError and
        # vendor-specific exception classes. Keep the command boundary traceback-free.
        result["ok"] = False
        result["errors"].append({"location": args.out, "message": (
            f"cannot complete {result['command']}: {type(exc).__name__}: {exc}; "
            "check local model/API compatibility, device and writable output paths (docs/perception.md)"
        )})
    if args.json:
        print(json.dumps(result, indent=2, allow_nan=False))
    elif result["ok"]:
        fallback = " (fit --stacked fallback; VTracer did not run)" if result.get("fallback") else ""
        label = " (GUIDE ONLY; not output or quality evidence)" if result.get("guide_only") else ""
        print(f"{result['command']}{fallback}{label}: {result['output']['receipt']}")
    else:
        for error in result["errors"]:
            print(f"{error['location']}: error: {error['message']}", file=sys.stderr)
    return 0 if result["ok"] else 1
