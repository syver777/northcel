"""Verification tools for NorthCel: diff, onion skin, contact sheets, continuity, distinct.

These tools answer the questions an author (human or AI) asks after rendering:
* where does my frame differ from the reference, and by how much?
* how do two neighbouring frames line up?
* what does the whole film look like at a glance?
* is a group's size/position continuous from frame to frame?
* how many genuinely distinct frames per second does the film contain?

All rendering goes through :func:`northcel.renderer.render_document_frame` and
:func:`northcel.renderer.frame_paint_list`; nothing here re-implements the
renderer.  The functions return plain dictionaries so the CLI can print either a
readable table or JSON.
"""

from __future__ import annotations

import math
import tempfile
import time
from pathlib import Path
from typing import Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .ast_nodes import DocumentNode, FilmNode
from .renderer import frame_paint_list, render_document_frame, render_film_frames

#: Contact sheets and onion skins are written as PNG unless the caller names a
#: known image suffix.
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}

#: The film-proof metric: mean absolute RGB difference in 8-bit units at this
#: thumbnail size.  ``> 0.2`` is the same as ``> 0.2/255`` after normalisation.
DISTINCT_SIZE = (320, 180)
DISTINCT_THRESHOLD = 0.2

#: A bbox-height change larger than this between adjacent frames is flagged.
HEIGHT_JUMP_PCT = 8.0


class VerificationError(ValueError):
    """An actionable verification error, printable without a traceback."""


# --------------------------------------------------------------------- basics
def frame_count(doc: DocumentNode) -> int:
    """Number of frames in a document (1 for a scene)."""
    root = doc.root
    return max(1, int(root.frames)) if isinstance(root, FilmNode) else 1


def check_frame(doc: DocumentNode, frame: int) -> int:
    """Validate a frame index against the document and return it."""
    total = frame_count(doc)
    if not isinstance(frame, int) or frame < 0 or frame >= total:
        raise VerificationError(
            f"frame {frame} is out of range for a {total}-frame document (0..{total - 1})"
        )
    return frame


def load_rgb(image_path: str | Path) -> np.ndarray:
    """Read an image as an (H, W, 3) uint8 RGB array with an actionable error."""
    path = Path(image_path)
    if not path.is_file():
        raise VerificationError(f"image not found: {path}")
    try:
        with Image.open(path) as image:
            return np.array(image.convert("RGB"), dtype=np.uint8, copy=True)
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise VerificationError(f"cannot read image {path}: {exc}") from None


def _check_same_size(render: np.ndarray, reference: np.ndarray, label: str) -> None:
    rh, rw = render.shape[:2]
    ah, aw = reference.shape[:2]
    if (rw, rh) != (aw, ah):
        raise VerificationError(
            f"{label} is {aw}x{ah} but the rendered frame is {rw}x{rh}; "
            "resize the reference to the document size"
        )


def _metrics(render: np.ndarray, reference: np.ndarray, box: tuple[int, int, int, int] | None = None) -> dict:
    """MAE/RMSE/PSNR/max error over RGB channels, optionally inside a pixel box."""
    if box is None:
        a, b = render, reference
    else:
        x0, y0, x1, y1 = box
        a, b = render[y0:y1, x0:x1], reference[y0:y1, x0:x1]
    if a.size == 0:
        raise VerificationError("cannot measure an empty region")
    delta = a.astype(np.int16) - b.astype(np.int16)
    absolute = np.abs(delta)
    mae = float(absolute.mean())
    rmse = float(np.sqrt(np.mean(delta.astype(np.float64) ** 2)))
    psnr = None if rmse <= 0.0 else 20.0 * math.log10(255.0 / rmse)
    return {
        "mae": round(mae, 6),
        "rmse": round(rmse, 6),
        "psnr": None if psnr is None else round(psnr, 6),
        "max_abs": int(absolute.max()),
        "mae_normalized": round(mae / 255.0, 8),
        "pixels": int(a.shape[0] * a.shape[1]),
        "identical": int(absolute.max()) == 0,
    }


def _ensure_image_path(image_path: str | Path) -> Path:
    """Return an image path with a suffix and an existing parent directory."""
    path = Path(image_path)
    if not path.suffix:
        path = path.with_suffix(".png")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise VerificationError(f"cannot create directory {path.parent}: {exc}") from None
    return path


def _ensure_dir(directory: Path) -> None:
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise VerificationError(f"cannot create directory {directory}: {exc}") from None


def _save_image(image: Image.Image, image_path: str | Path, what: str) -> Path:
    path = _ensure_image_path(image_path)
    try:
        image.save(path)
    except (OSError, ValueError) as exc:
        raise VerificationError(f"cannot write {what} to {path}: {exc}") from None
    return path


# ----------------------------------------------------------------------- diff
def parse_regions(specs: Sequence[str], width: int, height: int) -> list[dict]:
    """Parse repeatable ``name:x0,y0,x1,y1`` region arguments."""
    regions: list[dict] = []
    seen: set[str] = set()
    for spec in specs:
        if ":" not in spec:
            raise VerificationError(
                f"region {spec!r} must be name:x0,y0,x1,y1 (for example face:10,20,90,80)"
            )
        name, coords = spec.split(":", 1)
        name = name.strip()
        if not name:
            raise VerificationError(f"region {spec!r} has an empty name")
        if name in seen:
            raise VerificationError(f"region {name!r} is named more than once")
        parts = [part.strip() for part in coords.split(",")]
        if len(parts) != 4:
            raise VerificationError(f"region {name!r} needs four numbers x0,y0,x1,y1")
        try:
            x0, y0, x1, y1 = (float(part) for part in parts)
        except ValueError:
            raise VerificationError(f"region {name!r} has a non-numeric coordinate") from None
        if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
            raise VerificationError(f"region {name!r} has a non-finite coordinate")
        if x0 >= x1 or y0 >= y1:
            raise VerificationError(
                f"region {name!r} needs x0 < x1 and y0 < y1 (got {x0:g},{y0:g},{x1:g},{y1:g})"
            )
        clipped = [
            max(0, min(width, int(math.floor(x0)))),
            max(0, min(height, int(math.floor(y0)))),
            max(0, min(width, int(math.ceil(x1)))),
            max(0, min(height, int(math.ceil(y1)))),
        ]
        if clipped[0] >= clipped[2] or clipped[1] >= clipped[3]:
            raise VerificationError(
                f"region {name!r} lies outside the {width}x{height} canvas"
            )
        seen.add(name)
        regions.append({"name": name, "bbox": clipped})
    return regions


def _paint_bbox(paints: list) -> list[float] | None:
    xs: list[float] = []
    ys: list[float] = []
    for paint in paints:
        for ring in paint.rings:
            for x, y in ring:
                xs.append(float(x))
                ys.append(float(y))
    if not xs:
        return None
    return [min(xs), min(ys), max(xs), max(ys)]


def _clip_bbox(bbox: list[float], width: int, height: int) -> list[int] | None:
    """Clip a geometric bbox to whole canvas pixels; include thin geometry."""
    if bbox[2] <= 0.0 or bbox[0] >= width or bbox[3] <= 0.0 or bbox[1] >= height:
        return None
    x0 = max(0, int(math.floor(bbox[0])))
    y0 = max(0, int(math.floor(bbox[1])))
    x1 = min(width, int(math.ceil(bbox[2])))
    y1 = min(height, int(math.ceil(bbox[3])))
    x1 = max(x1, x0 + 1)
    y1 = max(y1, y0 + 1)
    if x1 <= x0 or y1 <= y0:
        return None
    return [x0, y0, x1, y1]


def _group_paints(paints: list) -> dict[str, list]:
    groups: dict[str, list] = {}
    for paint in paints:
        for name in paint.path:
            groups.setdefault(name, []).append(paint)
    return groups


def _heatmap_image(render: np.ndarray, reference: np.ndarray) -> np.ndarray:
    """Black -> red -> orange -> yellow -> white map of the max channel error."""
    error = np.max(np.abs(render.astype(np.int16) - reference.astype(np.int16)), axis=2)
    error = error.astype(np.float64)
    stops = [0.0, 32.0, 64.0, 128.0, 192.0, 255.0]
    red = np.interp(error, stops, [0.0, 70.0, 160.0, 255.0, 255.0, 255.0])
    green = np.interp(error, stops, [0.0, 0.0, 20.0, 40.0, 180.0, 255.0])
    blue = np.interp(error, stops, [0.0, 40.0, 60.0, 0.0, 0.0, 255.0])
    return np.clip(np.floor(np.stack([red, green, blue], axis=2) + 0.5), 0, 255).astype(np.uint8)


def diff_report(
    doc: DocumentNode,
    against: str | Path,
    frame: int = 0,
    regions: Sequence[str] = (),
    heatmap_path: str | Path | None = None,
) -> dict:
    """Render one frame and compare it with a reference image."""
    started = time.monotonic()
    check_frame(doc, frame)
    render = render_document_frame(doc, frame)
    reference = load_rgb(against)
    _check_same_size(render, reference, f"reference image {Path(against)}")
    height, width = render.shape[:2]

    overall = _metrics(render, reference)
    manual = parse_regions(regions, width, height)
    region_rows = []
    for region in manual:
        box = tuple(region["bbox"])
        metrics = _metrics(render, reference, box)
        region_rows.append({"name": region["name"], "bbox": list(box), **metrics})

    _paper, _paper_color, paints = frame_paint_list(doc, frame)
    group_rows = []
    for name, group_paints in _group_paints(paints).items():
        raw_bbox = _paint_bbox(group_paints)
        if raw_bbox is None:
            continue
        box = _clip_bbox(raw_bbox, width, height)
        if box is None:
            continue
        metrics = _metrics(render, reference, tuple(box))
        group_rows.append(
            {
                "name": name,
                "bbox": box,
                "paints": len(group_paints),
                **metrics,
            }
        )
    group_rows.sort(key=lambda row: (-row["mae"], row["name"]))

    heatmap_file = None
    if heatmap_path is not None:
        image = Image.fromarray(_heatmap_image(render, reference), mode="RGB")
        heatmap_file = str(_save_image(image, heatmap_path, "heatmap"))

    return {
        "ok": True,
        "command": "diff",
        "file": str(doc.root.name),
        "frame": frame,
        "against": str(against),
        "width": width,
        "height": height,
        "mae": overall["mae"],
        "rmse": overall["rmse"],
        "psnr": overall["psnr"],
        "overall": overall,
        "groups": group_rows,
        "regions": region_rows,
        "heatmap": heatmap_file,
        "seconds": round(time.monotonic() - started, 4),
    }


# ---------------------------------------------------------------------- onion
def _luma(rgb: np.ndarray) -> np.ndarray:
    return (
        0.299 * rgb[:, :, 0].astype(np.float64)
        + 0.587 * rgb[:, :, 1].astype(np.float64)
        + 0.114 * rgb[:, :, 2].astype(np.float64)
    )


def _onion_rgb(earlier: np.ndarray, later: np.ndarray) -> np.ndarray:
    """Earlier frame red, later frame blue; matching ink stays dark/neutral."""
    a, b = _luma(earlier), _luma(later)
    out = np.stack([b, np.minimum(a, b), a], axis=2)
    return np.clip(np.floor(out + 0.5), 0, 255).astype(np.uint8)


def _default_font():
    try:
        return ImageFont.load_default(size=14)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def onion_report(
    doc: DocumentNode,
    out_path: str | Path,
    frame: int = 0,
    against: str | Path | None = None,
) -> dict:
    """Write an onion skin of neighbouring frames, or of a render vs a reference."""
    started = time.monotonic()
    check_frame(doc, frame)
    total = frame_count(doc)

    if against is not None:
        render = render_document_frame(doc, frame)
        reference = load_rgb(against)
        _check_same_size(render, reference, f"reference image {Path(against)}")
        image = Image.fromarray(_onion_rgb(render, reference), mode="RGB")
        mode = "against"
        frame_rows = [
            {"role": "render", "frame": frame, "tint": "red"},
            {"role": "reference", "path": str(against), "tint": "blue"},
        ]
    elif total == 1:
        render = render_document_frame(doc, frame)
        image = Image.fromarray(render, mode="RGB")
        mode = "single"
        frame_rows = [{"role": "frame", "frame": frame, "tint": None}]
    elif frame == 0:
        first = render_document_frame(doc, 0)
        second = render_document_frame(doc, 1)
        image = Image.fromarray(_onion_rgb(first, second), mode="RGB")
        mode = "neighbours"
        frame_rows = [
            {"role": "frame", "frame": 0, "tint": "red"},
            {"role": "frame", "frame": 1, "tint": "blue"},
        ]
    else:
        previous = render_document_frame(doc, frame - 1)
        current = render_document_frame(doc, frame)
        image = Image.fromarray(_onion_rgb(previous, current), mode="RGB")
        mode = "neighbours"
        frame_rows = [
            {"role": "frame", "frame": frame - 1, "tint": "red"},
            {"role": "frame", "frame": frame, "tint": "blue"},
        ]

    # Keep the image unobstructed. Frame identities and tints are in the receipt
    # and CLI output; burning a legend into the canvas can hide the very motion
    # being checked (especially on small scenes).
    out_file = _save_image(image, out_path, "onion skin")
    return {
        "ok": True,
        "command": "onion",
        "file": str(doc.root.name),
        "frame": frame,
        "mode": mode,
        "frames": frame_rows,
        "width": doc.root.width,
        "height": doc.root.height,
        "out": str(out_file),
        "seconds": round(time.monotonic() - started, 4),
    }


# -------------------------------------------------------------------- contact
def parse_frame_selection(text: str | None, total: int) -> list[int]:
    """Parse ``0..5`` or ``0,2,4`` into validated frame indices."""
    if text is None:
        return list(range(total))
    text = text.strip()
    if not text:
        raise VerificationError("--frames is empty; use 0..N or a comma list such as 0,2,4")
    if ".." in text:
        start_text, end_text = text.split("..", 1)
        try:
            start, end = int(start_text), int(end_text)
        except ValueError:
            raise VerificationError(f"--frames {text!r} needs integer bounds 0..N") from None
        if start > end:
            raise VerificationError(f"--frames {text!r} has a reversed range")
        if start < 0 or end >= total:
            raise VerificationError(
                f"--frames {text!r} is out of range for a {total}-frame document (0..{total - 1})"
            )
        indices = list(range(start, end + 1))
    else:
        parts = [part.strip() for part in text.split(",")]
        if not all(parts):
            raise VerificationError(f"--frames {text!r} has an empty entry; use a list such as 0,2,4")
        try:
            indices = [int(part) for part in parts]
        except ValueError:
            raise VerificationError(f"--frames {text!r} needs integers") from None
    if not indices:
        raise VerificationError("--frames selected no frames")
    for index in indices:
        if index < 0 or index >= total:
            raise VerificationError(
                f"frame {index} is out of range for a {total}-frame document (0..{total - 1})"
            )
    return indices


def _transition_windows(doc: DocumentNode) -> list[dict]:
    """One window per frame block, including its incoming neighbouring frame."""
    root = doc.root
    if not isinstance(root, FilmNode):
        return []
    total = max(1, int(root.frames))
    windows: list[dict] = []

    for lo, hi, _scene in root.frame_ranges:
        start = max(0, min(int(lo) - 1, total - 1))
        end = max(0, min(int(hi), total - 1))
        if start > end:
            continue
        label = f"frames {lo}..{hi}"
        windows.append(
            {
                "kind": "range",
                "declared_start": int(lo),
                "declared_end": int(hi),
                "start": start,
                "end": end,
                "label": label,
            }
        )

    for index in sorted(root.frame_overrides):
        windows.append(
            {
                "kind": "exact",
                "declared_start": index,
                "declared_end": index,
                "start": max(0, index - 1),
                "end": index,
                "label": f"frame {index}",
            }
        )
    return sorted(windows, key=lambda window: (window["declared_start"], window["declared_end"]))


def _contact_sheet(doc: DocumentNode, indices: list[int], title: str) -> Image.Image:
    root = doc.root
    thumb_width = 256
    thumb_height = max(1, int(round(thumb_width * root.height / max(1, root.width))))
    label_height = 20
    margin = 12
    gap = 8
    title_height = 26
    columns = min(6, len(indices))
    rows = int(math.ceil(len(indices) / columns))
    cell_width = thumb_width
    cell_height = thumb_height + label_height
    sheet_width = margin * 2 + columns * cell_width + (columns - 1) * gap
    sheet_height = margin * 2 + title_height + rows * cell_height + (rows - 1) * gap

    sheet = Image.new("RGB", (sheet_width, sheet_height), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    font = _default_font()
    draw.text((margin, 6), title, fill=(0, 0, 0), font=font)

    # Reuse the film renderer and spool full-resolution frames to temporary PNGs
    # rather than retaining a whole film's RGB arrays in memory.
    with tempfile.TemporaryDirectory(prefix="northcel-contact-") as directory:
        render_film_frames(doc, directory, frame_indices=sorted(set(indices)))
        for position, index in enumerate(indices):
            row, column = divmod(position, columns)
            x = margin + column * (cell_width + gap)
            y = margin + title_height + row * (cell_height + gap)
            with Image.open(Path(directory) / f"f{index:04d}.png") as frame:
                thumb = frame.convert("RGB").resize(
                    (thumb_width, thumb_height), Image.Resampling.LANCZOS
                )
            sheet.paste(thumb, (x, y))
            draw.rectangle(
                [x - 1, y - 1, x + thumb_width, y + thumb_height + label_height],
                outline=(200, 200, 200),
            )
            label = f"f{index:04d}"
            box = draw.textbbox((0, 0), label, font=font)
            draw.text(
                (x + (thumb_width - (box[2] - box[0])) // 2, y + thumb_height + 2),
                label,
                fill=(0, 0, 0),
                font=font,
            )
    return sheet


def contact_report(
    doc: DocumentNode,
    out_path: str | Path,
    frames: str | None = None,
    every: int = 1,
    transitions: bool = False,
) -> dict:
    """Write one contact sheet, or one per transition with ``transitions``."""
    started = time.monotonic()
    if every < 1:
        raise VerificationError("--every must be at least 1")
    total = frame_count(doc)
    root = doc.root
    sheets: list[dict] = []
    out = Path(out_path)

    if transitions:
        windows = _transition_windows(doc)
        if not windows:
            raise VerificationError(
                "no frame overrides or frame ranges to use with --transitions; "
                "use a normal contact sheet instead"
            )
        if frames is not None:
            raise VerificationError("--frames and --transitions cannot be combined; --every applies per transition")
        if out.suffix.lower() in IMAGE_SUFFIXES:
            out_dir = out.with_name(out.stem + "-transitions")
            prefix = out.stem
        else:
            out_dir = out
            prefix = "contact"
        _ensure_dir(out_dir)
        for position, window in enumerate(windows):
            indices = list(range(window["start"], window["end"] + 1))[::every]
            # Keep both declared endpoints even when a stride skips the key.
            indices = sorted(set(indices + [window["declared_start"]]))
            if indices[-1] != window["end"]:
                indices.append(window["end"])
            title = f"{root.name} - {window['label']} ({len(indices)} frames)"
            image = _contact_sheet(doc, indices, title)
            name = (
                f"{prefix}-t{position:02d}-f{window['start']:04d}-f{window['end']:04d}.png"
            )
            path = _save_image(image, out_dir / name, "contact sheet")
            sheets.append(
                {
                    "path": str(path),
                    "frames": indices,
                    "transition": window,
                }
            )
    else:
        indices = parse_frame_selection(frames, total)[::every]
        if not indices:
            raise VerificationError("--every selected no frames")
        if out.suffix.lower() in IMAGE_SUFFIXES:
            sheet_path = out
            _ensure_dir(out.parent)
        else:
            _ensure_dir(out)
            sheet_path = out / "contact.png"
        title = f"{root.name} - {len(indices)} frames at {root.fps} fps"
        image = _contact_sheet(doc, indices, title)
        path = _save_image(image, sheet_path, "contact sheet")
        sheets.append({"path": str(path), "frames": indices, "transition": None})

    return {
        "ok": True,
        "command": "contact",
        "file": str(root.name),
        "every": every,
        "transitions": transitions,
        "sheets": sheets,
        "seconds": round(time.monotonic() - started, 4),
    }


# ----------------------------------------------------------------- continuity
def _select_paints(paints: list, group: str | None, shape: str | None) -> list:
    return [
        paint
        for paint in paints
        if (not group or group in paint.path) and (not shape or paint.name == shape)
    ]


def _available_groups(paints: list) -> list[str]:
    return sorted({name for paint in paints for name in paint.path})


def _available_shapes(paints: list) -> list[str]:
    return sorted({paint.name for paint in paints})


def _short_list(values: Sequence[str], limit: int = 24) -> str:
    if not values:
        return "none"
    shown = ", ".join(values[:limit])
    return shown if len(values) <= limit else f"{shown}, …"


def _jump_row(previous: dict, current: dict) -> dict:
    row = {
        "from": previous["frame"],
        "to": current["frame"],
        "present_change": previous["present"] != current["present"],
        "width_change_pct": None,
        "height_change_pct": None,
        "centroid_dx": None,
        "centroid_dy": None,
        "centroid_distance": None,
        "position_change_pct": None,
        "height_jump": False,
    }
    if not previous["present"] or not current["present"]:
        return row

    previous_width, current_width = previous["width"], current["width"]
    previous_height, current_height = previous["height"], current["height"]
    if previous_width > 0.0:
        row["width_change_pct"] = round((current_width - previous_width) / previous_width * 100.0, 4)
    if previous_height > 0.0:
        height_change = (current_height - previous_height) / previous_height * 100.0
        row["height_change_pct"] = round(height_change, 4)
        row["height_jump"] = abs(height_change) > HEIGHT_JUMP_PCT and not math.isclose(
            abs(height_change), HEIGHT_JUMP_PCT, rel_tol=1e-12
        )
    else:
        row["height_jump"] = current_height > 0.0

    px, py = previous["centroid"]
    cx, cy = current["centroid"]
    dx, dy = cx - px, cy - py
    distance = math.hypot(dx, dy)
    row["centroid_dx"] = round(dx, 4)
    row["centroid_dy"] = round(dy, 4)
    row["centroid_distance"] = round(distance, 4)
    scale = max(previous_height, current_height)
    if scale > 0.0:
        row["position_change_pct"] = round(distance / scale * 100.0, 4)
    return row


def continuity_report(doc: DocumentNode, group: str | None = None, shape: str | None = None) -> dict:
    """Measure a group's or shape's bbox/centroid per frame and its jumps."""
    started = time.monotonic()
    if not group and not shape:
        raise VerificationError("choose --group NAME or --shape ID")
    total = frame_count(doc)
    raw_rows: list[dict] = []
    available_groups: set[str] = set()
    available_shapes: set[str] = set()

    for index in range(total):
        paints = frame_paint_list(doc, index)[2]
        available_groups.update(_available_groups(paints))
        available_shapes.update(_available_shapes(_select_paints(paints, group, None)))
        selected = _select_paints(paints, group, shape)
        if not selected:
            raw_rows.append(
                {
                    "frame": index,
                    "present": False,
                    "bbox": None,
                    "width": 0.0,
                    "height": 0.0,
                    "centroid": None,
                    "paints": 0,
                }
            )
            continue
        bbox = _paint_bbox(selected)
        if bbox is None:
            raw_rows.append(
                {
                    "frame": index,
                    "present": False,
                    "bbox": None,
                    "width": 0.0,
                    "height": 0.0,
                    "centroid": None,
                    "paints": len(selected),
                }
            )
            continue
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        raw_rows.append(
            {
                "frame": index,
                "present": True,
                "bbox": bbox,
                "width": width,
                "height": height,
                "centroid": [(bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0],
                "paints": len(selected),
            }
        )

    if not any(row["present"] for row in raw_rows):
        if group and group not in available_groups:
            kind, name, available = "group", group, sorted(available_groups)
        else:
            kind, name, available = "shape", shape, sorted(available_shapes)
        raise VerificationError(
            f"{kind} {name!r} was not found in any frame; available {kind}s: {_short_list(available)}"
        )

    jumps = [_jump_row(raw_rows[i - 1], raw_rows[i]) for i in range(1, len(raw_rows))]
    height_jumps = [jump for jump in jumps if jump["height_jump"]]
    max_height_jump = max(
        (abs(jump["height_change_pct"]) for jump in jumps if jump["height_change_pct"] is not None),
        default=0.0,
    )
    rows = []
    for row in raw_rows:
        rows.append(
            {
                "frame": row["frame"],
                "present": row["present"],
                "bbox": None if row["bbox"] is None else [round(value, 2) for value in row["bbox"]],
                "width": round(row["width"], 2),
                "height": round(row["height"], 2),
                "centroid": None
                if row["centroid"] is None
                else [round(value, 2) for value in row["centroid"]],
                "paints": row["paints"],
            }
        )

    return {
        "ok": True,
        "command": "continuity",
        "file": str(doc.root.name),
        "fps": doc.root.fps,
        "frames": total,
        "selection": {"group": group, "shape": shape},
        "rows": rows,
        "jumps": jumps,
        "height_jumps": height_jumps,
        "max_height_jump_pct": round(max_height_jump, 4),
        "thresholds": {"height_pct": HEIGHT_JUMP_PCT},
        "seconds": round(time.monotonic() - started, 4),
    }


# ------------------------------------------------------------------- distinct
def _distinct_frame(doc: DocumentNode, frame: int) -> np.ndarray:
    rgb = render_document_frame(doc, frame)
    image = Image.fromarray(rgb, mode="RGB").resize(DISTINCT_SIZE, Image.Resampling.LANCZOS)
    return np.asarray(image, dtype=np.float32)


def distinct_report(doc: DocumentNode, frames: str | None = None, every: int = 1) -> dict:
    """The film-proof distinct-frames metric at 320x180.

    Each frame is rendered at the film size, resized to 320x180 with LANCZOS,
    and compared with the previous frame by mean absolute RGB difference in
    8-bit units.  A frame counts as distinct when its difference from the
    previous frame is ``> 0.2`` (the same as ``> 0.2/255`` after normalisation).
    The first frame is not a change, so a still film reports zero. This is a
    count of changed adjacent samples, not globally unique images. The rate
    divides that count by the sampled timeline span, including the first frame.
    """
    started = time.monotonic()
    if every < 1:
        raise VerificationError("--every must be at least 1")
    total = frame_count(doc)
    indices = parse_frame_selection(frames, total)[::every]
    if not indices:
        raise VerificationError("--every selected no frames")
    if any(a >= b for a, b in zip(indices, indices[1:])):
        raise VerificationError("distinct --frames must be strictly increasing without duplicates")

    fps = int(doc.root.fps) if doc.root.fps else 0
    pairs: list[dict] = []
    changed_pairs = 0
    previous: np.ndarray | None = None
    previous_index: int | None = None
    for index in indices:
        current = _distinct_frame(doc, index)
        if previous is not None:
            difference = float(np.mean(np.abs(current - previous), dtype=np.float64))
            changed = difference > DISTINCT_THRESHOLD
            changed_pairs += int(changed)
            pairs.append(
                {
                    "from": previous_index,
                    "to": index,
                    "diff": round(difference, 6),
                    "changed": changed,
                }
            )
        previous = current
        previous_index = index

    seconds = ((indices[-1] - indices[0] + 1) / fps) if fps > 0 else 0.0
    distinct_frames = changed_pairs
    sampled = indices != list(range(total))
    return {
        "ok": True,
        "command": "distinct",
        "file": str(doc.root.name),
        "fps": fps,
        "frames": total,
        "sampled_frames": len(indices),
        "sampled": sampled,
        "first_frame": indices[0],
        "last_frame": indices[-1],
        "width": DISTINCT_SIZE[0],
        "height": DISTINCT_SIZE[1],
        "resample": "lanczos",
        "metric": "mean absolute RGB difference (0..255) at 320x180",
        "threshold": DISTINCT_THRESHOLD,
        "pair_count": len(pairs),
        "changed_pairs": changed_pairs,
        "changed_frames": changed_pairs,
        "distinct_frames": distinct_frames,
        "seconds": round(seconds, 6),
        "distinct_per_second": round(distinct_frames / seconds, 6) if seconds > 0.0 else 0.0,
        "distinct_fps": round(distinct_frames / seconds, 6) if seconds > 0.0 else 0.0,
        "pairs": pairs,
        "seconds_elapsed": round(time.monotonic() - started, 4),
    }
