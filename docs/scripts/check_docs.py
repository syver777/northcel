"""Check that the documentation is true.

Run from the repository root:

    python docs/scripts/check_docs.py

What it proves:

* every ```ncel fence in the guide carries a marker and does what it claims:
  errors reproduce the exact diagnostic, sources equal their file, rendered
  snippets match their committed image and the manifest;
* every `examples/patterns/*.ncel` compiles, renders every frame and matches the
  committed contact sheet;
* the gallery images are the renders of the files and frames they name;
* every relative link and image path resolves;
* `docs/errors.md` is current (regenerated from the source and compared).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import docs_lib as lib  # noqa: E402


class Checker:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.counts = {
            "markdown": 0,
            "links": 0,
            "snippets": 0,
            "renders": 0,
            "errors": 0,
            "sources": 0,
            "patterns": 0,
            "pattern_frames": 0,
            "gallery": 0,
        }

    def fail(self, message: str) -> None:
        self.failures.append(message)

    # ------------------------------------------------------------------ links
    def check_links(self) -> None:
        for page in lib.markdown_files():
            self.counts["markdown"] += 1
            for target, line in lib.find_markdown_links(page):
                if not target:
                    continue
                # Normalise URL-encoded paths such as spaces in file names.
                from urllib.parse import unquote

                target = unquote(target)
                dest = (page.parent / target).resolve()
                ok = dest.exists()
                if ok and dest.is_dir():
                    ok = (dest / "README.md").exists()
                self.counts["links"] += 1
                if not ok:
                    self.fail(f"{lib.rel(page)}:{line}: dead link/image: {target}")

    # ------------------------------------------------------------------ guide
    def _render_matches(self, block: lib.Block, asset: str, entry: dict, tmp: Path) -> None:
        frames = [int(x) for x in block.marker.get("frames", "0").split(",") if x]
        cols = int(block.marker.get("cols", min(4, len(frames))))
        src = tmp / f"check-{block.page.replace('/', '-')}-{block.index}.ncel"
        src.write_text(block.code)
        rendered = []
        for idx in frames:
            png = tmp / f"{src.stem}-{idx}.png"
            try:
                lib.render_frame(src, png, frame=idx)
            except RuntimeError as exc:
                self.fail(f"{block.page}#{block.index}: {exc}")
                return
            rendered.append(png)
        manifest_frames = {f["index"]: f["pixel_sha256"] for f in entry.get("frames", [])}
        for idx, png in zip(frames, rendered):
            got = lib.pixel_sha256(png)
            want = manifest_frames.get(idx)
            if want != got:
                self.fail(
                    f"{block.page}#{block.index}: frame {idx} pixel hash changed "
                    f"(manifest {want}, rendered {got})"
                )
        out = lib.DOCS / asset
        if not out.is_file():
            self.fail(f"{block.page}#{block.index}: missing image {asset}")
            return
        if len(rendered) == 1:
            expected_pixels = lib.pixel_sha256(rendered[0])
        else:
            sheet = lib.contact_sheet(rendered, cols=cols)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
                sheet_path = Path(fh.name)
            sheet.save(sheet_path, optimize=True)
            expected_pixels = lib.pixel_sha256(sheet_path)
        committed = lib.pixel_sha256(out)
        if committed != expected_pixels:
            self.fail(f"{lib.rel(out)}: pixels do not match the rendered snippet")
        if committed != entry.get("pixel_sha256"):
            self.fail(f"{lib.rel(out)}: pixels do not match expected.json")
        # The image must actually appear on the page.
        page = lib.REPO / block.page
        referenced = set()
        for target, _ in lib.find_markdown_links(page):
            try:
                referenced.add((page.parent / target).resolve())
            except OSError:
                pass
        if (lib.DOCS / asset).resolve() not in referenced:
            self.fail(f"{block.page}: rendered image {asset} is not referenced on the page")

    def check_guide(self, manifest: dict, tmp: Path) -> None:
        seen: set[str] = set()
        for page in sorted((lib.DOCS / "guide").glob("*.md")):
            for block in lib.extract_blocks(page):
                self.counts["snippets"] += 1
                marker = block.marker
                if marker is None:
                    self.fail(f"{block.page}#{block.index}: ncel fence without a marker")
                    continue
                if marker["kind"] == "render":
                    self.counts["renders"] += 1
                    asset = marker["path"]
                    seen.add(asset)
                    entry = manifest.get("guide", {}).get(asset)
                    if entry is None:
                        self.fail(f"{block.page}#{block.index}: no manifest entry for {asset}")
                        continue
                    if entry.get("page") != block.page or entry.get("block") != block.index:
                        self.fail(f"{block.page}#{block.index}: manifest entry points elsewhere")
                    self._render_matches(block, asset, entry, tmp)
                elif marker["kind"] == "error":
                    self.counts["errors"] += 1
                    src = tmp / f"check-err-{block.page.replace('/', '-')}-{block.index}.ncel"
                    src.write_text(block.code)
                    receipt = lib.check_document(src)
                    actual = receipt.get("errors", []) + receipt.get("warnings", [])
                    if marker["text"] not in actual:
                        self.fail(
                            f"{block.page}#{block.index}: documented error does not reproduce\n"
                            f"  expected: {marker['text']}\n  actual:   {actual}"
                        )
                    if receipt.get("exit_code") == 0:
                        self.fail(f"{block.page}#{block.index}: error case exits 0")
                elif marker["kind"] == "source":
                    self.counts["sources"] += 1
                    target = lib.REPO / marker["path"]
                    if not target.is_file():
                        self.fail(f"{block.page}#{block.index}: missing source {marker['path']}")
                    elif block.code.rstrip("\n") != target.read_text().rstrip("\n"):
                        self.fail(f"{block.page}#{block.index}: inlined source differs from {marker['path']}")
        for asset in manifest.get("guide", {}):
            if asset not in seen:
                self.fail(f"expected.json lists {asset}, but no guide fence renders it")

    # --------------------------------------------------------------- patterns
    def check_patterns(self, manifest: dict, tmp: Path) -> None:
        files = sorted((lib.REPO / "examples" / "patterns").glob("*.ncel"))
        entries = manifest.get("patterns", {})
        if len(files) < 10:
            self.fail(f"only {len(files)} pattern files (at least 10 required)")
        for path in files:
            self.counts["patterns"] += 1
            entry = entries.get(path.stem)
            if entry is None:
                self.fail(f"{lib.rel(path)}: no manifest entry")
                continue
            receipt = lib.check_document(path)
            if not receipt.get("ok"):
                self.fail(f"{lib.rel(path)}: check failed: {receipt.get('errors')}")
                continue
            info = lib.info_document(path)
            frames = int(info.get("frames") or 1)
            expected = {f["index"]: f["pixel_sha256"] for f in entry.get("frames", [])}
            rendered = []
            for idx in range(frames):
                png = tmp / f"check-{path.stem}-{idx}.png"
                try:
                    lib.render_frame(path, png, frame=idx)
                except RuntimeError as exc:
                    self.fail(f"{lib.rel(path)} frame {idx}: {exc}")
                    break
                self.counts["pattern_frames"] += 1
                got = lib.pixel_sha256(png)
                if expected.get(idx) != got:
                    self.fail(
                        f"{lib.rel(path)} frame {idx}: pixel hash changed "
                        f"(manifest {expected.get(idx)}, rendered {got})"
                    )
                rendered.append(png)
            if len(rendered) != frames:
                continue
            cols = min(4, frames) if frames > 1 else 1
            if frames == 1:
                expected_sheet = lib.pixel_sha256(rendered[0])
            else:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
                    sheet_path = Path(fh.name)
                lib.contact_sheet(rendered, cols=cols).save(sheet_path, optimize=True)
                expected_sheet = lib.pixel_sha256(sheet_path)
            sheet = lib.REPO / entry["sheet"]
            if not sheet.is_file():
                self.fail(f"{lib.rel(path)}: missing contact sheet {entry['sheet']}")
            elif lib.pixel_sha256(sheet) != expected_sheet:
                self.fail(f"{lib.rel(sheet)}: contact sheet does not match the rendered frames")
            page = lib.DOCS / "patterns" / f"{path.stem}.md"
            if not page.is_file():
                self.fail(f"{lib.rel(path)}: no pattern page docs/patterns/{path.stem}.md")
            else:
                blocks = lib.extract_blocks(page)
                sources = [b for b in blocks if b.marker and b.marker["kind"] == "source"]
                if len(sources) != 1:
                    self.fail(f"{lib.rel(page)}: expected exactly one source: block, found {len(sources)}")
                else:
                    block = sources[0]
                    self.counts["sources"] += 1
                    if block.marker["path"] != lib.rel(path):
                        self.fail(f"{lib.rel(page)}: source marker points at {block.marker['path']}")
                    elif block.code.rstrip("\n") != path.read_text().rstrip("\n"):
                        self.fail(f"{lib.rel(page)}: inlined source differs from {lib.rel(path)}")
                for block in blocks:
                    if block.marker is None:
                        self.fail(f"{lib.rel(page)}#{block.index}: ncel fence without a marker")
        for stem in entries:
            if not (lib.REPO / entries[stem]["file"]).is_file():
                self.fail(f"expected.json lists pattern {stem} with a missing file")

    # ---------------------------------------------------------------- gallery
    def check_gallery(self, manifest: dict, tmp: Path) -> None:
        gallery = manifest.get("gallery", {})
        pages = lib.DOCS / "gallery.md"
        markers = {m["path"]: m for m in lib.image_markers(pages)}
        for asset, entry in gallery.items():
            self.counts["gallery"] += 1
            path = lib.DOCS / asset
            if not path.is_file():
                self.fail(f"gallery image missing: {asset}")
                continue
            if asset not in markers:
                self.fail(f"gallery.md does not reference {asset} with an <!-- image: --> marker")
            if lib.pixel_sha256(path) != entry.get("pixel_sha256"):
                self.fail(f"{asset}: pixels do not match expected.json")
            if "source" not in entry:
                continue
            src = lib.REPO / entry["source"]
            if "frames" in entry and entry.get("sheet"):
                rendered = []
                for f in entry["frames"]:
                    png = tmp / f"gallery-{path.stem}-{f['index']}.png"
                    lib.render_frame(src, png, frame=f["index"])
                    if lib.pixel_sha256(png) != f["pixel_sha256"]:
                        self.fail(f"{lib.rel(src)} frame {f['index']}: pixel hash changed")
                    rendered.append(png)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as fh:
                    sheet_path = Path(fh.name)
                lib.contact_sheet(rendered, cols=3).save(sheet_path, optimize=True)
                if lib.pixel_sha256(sheet_path) != entry["pixel_sha256"]:
                    self.fail(f"{asset}: contact sheet does not match the rendered frames")
            else:
                png = tmp / f"gallery-{path.stem}.png"
                lib.render_frame(src, png, frame=int(entry.get("frame", 0)))
                if lib.pixel_sha256(png) != entry.get("pixel_sha256"):
                    self.fail(f"{asset}: does not match a fresh render of {entry['source']}")
        for asset in markers:
            if asset not in gallery:
                self.fail(f"gallery.md references {asset}, which has no manifest entry")

    # ----------------------------------------------------------------- errors
    def check_errors(self) -> None:
        gen = lib.DOCS / "scripts" / "gen_errors.py"
        proc = subprocess.run(
            [sys.executable, str(gen), "--check"], cwd=str(lib.REPO), capture_output=True, text=True
        )
        if proc.returncode != 0:
            self.fail(f"errors.md is stale: {proc.stderr.strip() or proc.stdout.strip()}")

    def report(self) -> int:
        if self.failures:
            print(f"docs check FAILED ({len(self.failures)} problem(s)):", file=sys.stderr)
            for f in self.failures:
                print(f"  - {f}", file=sys.stderr)
            return 1
        print(
            "docs check passed: "
            + ", ".join(f"{k} {v}" for k, v in self.counts.items())
        )
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-errors", action="store_true", help="do not regenerate docs/errors.md")
    args = ap.parse_args()
    manifest = lib.load_manifest()
    checker = Checker()
    checker.check_links()
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        checker.check_guide(manifest, tmp)
        checker.check_patterns(manifest, tmp)
        checker.check_gallery(manifest, tmp)
    if not args.skip_errors:
        checker.check_errors()
    return checker.report()


if __name__ == "__main__":
    raise SystemExit(main())
