"""Build every rendered image used by the documentation, from the real tool.

Run from the repository root:

    python docs/scripts/build_docs_assets.py

It renders the snippet annotated with a `<!-- render: -->` marker on every guide
page, every `examples/patterns/*.ncel` and its contact sheet, the gallery frames,
and writes `docs/scripts/expected.json`. The renderer is the Python reference
(`--no-native`) because that is the normative oracle and its pixels do not depend
on the host Mesa version, so the committed hashes are reproducible in CI.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))

import docs_lib as lib  # noqa: E402
sys.path.insert(0, str(lib.PYTHON_DIR))
from northcel.config import PACKAGE_VERSION  # noqa: E402

GUIDE = lib.DOCS / "guide"
PATTERNS_DOC = lib.DOCS / "patterns"
ASSETS = lib.DOCS / "assets"

GALLERY = [
    dict(
        asset="assets/gallery/shower_f0001.png",
        source="python/northcel/examples/shower_f0001.ncel",
        frame=0,
    ),
    dict(
        asset="assets/gallery/shower_f0002.png",
        source="python/northcel/examples/shower_f0002.ncel",
        frame=0,
    ),
    dict(
        asset="assets/gallery/shower_f0001_compact.png",
        source="python/northcel/examples/shower_f0001_compact.ncel",
        frame=0,
    ),
]


def _sheet_from_paths(paths: list[Path], cols: int) -> Image.Image:
    return lib.contact_sheet(paths, cols=cols)


def build_guide(manifest: dict, tmp: Path) -> int:
    count = 0
    guide = {}
    for page in sorted(GUIDE.glob("*.md")):
        for block in lib.extract_blocks(page):
            marker = block.marker
            if marker is None:
                raise SystemExit(
                    f"{block.page}#{block.index} (line {block.start_line}): "
                    "every ```ncel fence needs a render:, expect-error: or source: marker"
                )
            if marker["kind"] == "render":
                asset = marker["path"]
                out = lib.DOCS / asset
                out.parent.mkdir(parents=True, exist_ok=True)
                frames = [int(x) for x in marker.get("frames", "0").split(",") if x]
                cols = int(marker.get("cols", min(4, len(frames))))
                src = tmp / f"guide-{block.page.replace('/', '-')}-{block.index}.ncel"
                src.write_text(block.code)
                rendered = []
                per_frame = []
                for idx in frames:
                    frame_png = tmp / f"{src.stem}-{idx}.png"
                    lib.render_frame(src, frame_png, frame=idx)
                    rendered.append(frame_png)
                    per_frame.append({"index": idx, "pixel_sha256": lib.pixel_sha256(frame_png)})
                if len(rendered) == 1:
                    shutil.copyfile(rendered[0], out)
                else:
                    sheet = _sheet_from_paths(rendered, cols)
                    sheet.save(out, optimize=True)
                w, h = lib.image_size(out)
                guide[asset] = {
                    "page": block.page,
                    "block": block.index,
                    "frames": per_frame,
                    "width": w,
                    "height": h,
                    "pixel_sha256": lib.pixel_sha256(out),
                }
                count += 1
            elif marker["kind"] == "error":
                src = tmp / f"err-{block.page.replace('/', '-')}-{block.index}.ncel"
                src.write_text(block.code)
                receipt = lib.check_document(src)
                expected = marker["text"]
                actual = receipt.get("errors", []) + receipt.get("warnings", [])
                if expected not in actual:
                    raise SystemExit(
                        f"{block.page}#{block.index}: documented error does not reproduce.\n"
                        f"expected: {expected}\nactual:   {actual}"
                    )
                if receipt.get("exit_code") == 0:
                    raise SystemExit(f"{block.page}#{block.index}: error case exited 0")
                count += 1
            elif marker["kind"] == "source":
                target = lib.REPO / marker["path"]
                if not target.is_file():
                    raise SystemExit(f"{block.page}#{block.index}: source file missing: {marker['path']}")
                if block.code.rstrip("\n") != target.read_text().rstrip("\n"):
                    raise SystemExit(
                        f"{block.page}#{block.index}: inlined source differs from {marker['path']}"
                    )
                count += 1
    manifest["guide"] = guide
    return count


def build_patterns(manifest: dict, tmp: Path) -> int:
    patterns = {}
    files = sorted((lib.REPO / "examples" / "patterns").glob("*.ncel"))
    if len(files) < 10:
        raise SystemExit(f"expected at least 10 patterns, found {len(files)}")
    for path in files:
        receipt = lib.check_document(path)
        if not receipt.get("ok"):
            raise SystemExit(f"{lib.rel(path)} does not check: {receipt.get('errors')}")
        info = lib.info_document(path)
        frames = int(info.get("frames") or 1)
        rendered = []
        per_frame = []
        for idx in range(frames):
            png = tmp / f"{path.stem}-{idx}.png"
            lib.render_frame(path, png, frame=idx)
            rendered.append(png)
            per_frame.append({"index": idx, "pixel_sha256": lib.pixel_sha256(png)})
        cols = min(4, frames) if frames > 1 else 1
        sheet_path = ASSETS / "patterns" / f"{path.stem}.png"
        sheet_path.parent.mkdir(parents=True, exist_ok=True)
        if frames == 1:
            shutil.copyfile(rendered[0], sheet_path)
        else:
            _sheet_from_paths(rendered, cols).save(sheet_path, optimize=True)
        w, h = lib.image_size(sheet_path)
        patterns[path.stem] = {
            "file": lib.rel(path),
            "kind": info["kind"],
            "width": info["width"],
            "height": info["height"],
            "fps": info.get("fps"),
            "frames": per_frame,
            "sheet": lib.rel(sheet_path.relative_to(lib.REPO)),
            "sheet_width": w,
            "sheet_height": h,
            "sheet_pixel_sha256": lib.pixel_sha256(sheet_path),
            "bytes": path.stat().st_size,
        }
    manifest["patterns"] = patterns
    return len(files)


def build_gallery(manifest: dict, tmp: Path) -> int:
    gallery = {}
    for item in GALLERY:
        src = lib.REPO / item["source"]
        out = lib.DOCS / item["asset"]
        out.parent.mkdir(parents=True, exist_ok=True)
        lib.render_frame(src, out, frame=item["frame"])
        w, h = lib.image_size(out)
        gallery[item["asset"]] = {
            "source": item["source"],
            "frame": item["frame"],
            "width": w,
            "height": h,
            "pixel_sha256": lib.pixel_sha256(out),
        }

    # The lantern film gets one contact sheet, not six pages.
    lant = lib.REPO / "python" / "northcel" / "examples" / "lantern_film.ncel"
    info = lib.info_document(lant)
    rendered = []
    per_frame = []
    for idx in range(int(info["frames"])):
        png = tmp / f"lantern-{idx}.png"
        lib.render_frame(lant, png, frame=idx)
        rendered.append(png)
        per_frame.append({"index": idx, "pixel_sha256": lib.pixel_sha256(png)})
    out = lib.DOCS / "assets" / "gallery" / "lantern_film_sheet.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    _sheet_from_paths(rendered, cols=3).save(out, optimize=True)
    w, h = lib.image_size(out)
    gallery["assets/gallery/lantern_film_sheet.png"] = {
        "source": lib.rel(lant),
        "frames": per_frame,
        "sheet": True,
        "width": w,
        "height": h,
        "pixel_sha256": lib.pixel_sha256(out),
    }

    manifest["gallery"] = gallery
    return len(gallery)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        manifest = {
            "generated_by": "docs/scripts/build_docs_assets.py",
            "renderer": "python-reference",
            "tool": f"northcel {PACKAGE_VERSION}",
        }
        guide = build_guide(manifest, tmp)
        patterns = build_patterns(manifest, tmp)
        gallery = build_gallery(manifest, tmp)
        lib.save_manifest(manifest)
    if not args.quiet:
        print(f"guide: {guide} annotated fences")
        print(f"patterns: {patterns} (frames + contact sheet)")
        print(f"gallery: {gallery} images")
        print(f"wrote {lib.rel(lib.DOCS / 'scripts' / 'expected.json')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
