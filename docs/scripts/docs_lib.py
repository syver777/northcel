"""Shared helpers for the NorthCel documentation build and check.

The docs are not allowed to invent anything: every ```ncel fence carries a
machine-readable marker saying either which image it renders to, or which exact
diagnostic it must reproduce.  This module finds those fences, runs the real
`northcel` CLI (the reference renderer, so the result is reproducible on every
platform and in CI) and hashes the pixels.

Only the standard library, Pillow and NumPy are required.  The reference
renderer itself is NumPy based, so that is the same dependency set.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

REPO = Path(__file__).resolve().parents[2]
DOCS = REPO / "docs"
PYTHON_DIR = REPO / "python"

RENDER_RE = re.compile(r"^<!--\s*render:\s*(?P<path>\S+)(?P<rest>[^>]*)-->\s*$")
ERROR_RE = re.compile(r"^<!--\s*expect-error:\s*(?P<text>.+?)\s*-->\s*$")
IMAGE_RE = re.compile(r"^<!--\s*image:\s*(?P<path>\S+)(?P<rest>[^>]*)-->\s*$")
SOURCE_RE = re.compile(r"^<!--\s*source:\s*(?P<path>\S+)\s*-->\s*$")
FENCE_RE = re.compile(r"^```(?P<lang>[A-Za-z0-9_-]*)\s*$")


@dataclass
class Block:
    page: str
    index: int
    code: str
    start_line: int
    marker: dict | None

    @property
    def kind(self) -> str:
        return self.marker["kind"] if self.marker else "none"


def rel(path: Path) -> str:
    try:
        return path.relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def _cli(args: list[str]) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(PYTHON_DIR) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env.setdefault("PYTHONIOENCODING", "utf-8")
    # --no-native keeps the renderer the pure-Python reference everywhere.  That
    # is the normative oracle, and unlike the GLSL path its pixels do not depend
    # on the host Mesa version, so a committed hash is reproducible in CI.
    cmd = [sys.executable, "-m", "northcel", *args, "--no-native"]
    return subprocess.run(cmd, cwd=str(REPO), env=env, capture_output=True, text=True)


def check_document(path: Path) -> dict:
    proc = _cli(["check", str(path), "--json"])
    try:
        receipt = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {
            "ok": False,
            "errors": [f"check produced no JSON (exit {proc.returncode}): {proc.stderr.strip()}"],
            "warnings": [],
        }
    receipt["exit_code"] = proc.returncode
    return receipt


def render_frame(path: Path, out: Path, frame: int = 0) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    proc = _cli(["render", str(path), "-o", str(out), "--frame", str(frame), "--json"])
    try:
        receipt = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"render of {rel(path)} frame {frame} produced no JSON "
            f"(exit {proc.returncode}): {proc.stderr.strip()}"
        ) from None
    if not receipt.get("ok") or not out.is_file():
        raise RuntimeError(
            f"render of {rel(path)} frame {frame} failed: {receipt.get('error') or proc.stderr.strip()}"
        )
    return receipt


def info_document(path: Path) -> dict:
    proc = _cli(["info", str(path), "--json"])
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(f"info of {rel(path)} produced no JSON: {proc.stderr.strip()}") from None


def pixel_sha256(path: Path) -> str:
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        return hashlib.sha256(rgb.tobytes()).hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as img:
        return img.size


def token_count(text: str) -> int:
    import tiktoken

    return len(tiktoken.get_encoding("cl100k_base").encode(text))


def contact_sheet(frames: list[Path], cols: int, gutter: int = 6, background: str = "#1b1b1b") -> Image.Image:
    """Compose frames left-to-right, top-to-bottom.  No text: font rendering is
    the one thing that is not stable across Pillow builds."""
    if not frames:
        raise ValueError("no frames for a contact sheet")
    tiles = []
    for f in frames:
        with Image.open(f) as img:
            tiles.append(img.convert("RGB"))
    w, h = tiles[0].size
    for tile in tiles:
        if tile.size != (w, h):
            raise ValueError("contact-sheet frames must share one size")
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new(
        "RGB",
        (cols * w + (cols + 1) * gutter, rows * h + (rows + 1) * gutter),
        background,
    )
    for i, tile in enumerate(tiles):
        r, c = divmod(i, cols)
        sheet.paste(tile, (gutter + c * (w + gutter), gutter + r * (h + gutter)))
    return sheet


def parse_marker(rest: str) -> dict:
    marker: dict = {}
    for part in rest.split():
        if "=" in part:
            key, value = part.split("=", 1)
            marker[key] = value
    return marker


def _next_fence(lines: list[str], start: int) -> tuple[int, int, int] | None:
    """Return (fence_open_line, code_start, code_end) of the next ```ncel fence."""
    i = start
    while i < len(lines):
        m = FENCE_RE.match(lines[i].strip())
        if m and m.group("lang") == "ncel":
            open_line = i
            j = i + 1
            body: list[str] = []
            while j < len(lines):
                if lines[j].strip() == "```":
                    return open_line, open_line + 1, j
                body.append(lines[j])
                j += 1
            raise ValueError(f"unclosed ncel fence at line {open_line + 1}")
        i += 1
    return None


def extract_blocks(page_path: Path) -> list[Block]:
    """Every ```ncel fence in a page, with the marker written just before it."""
    lines = page_path.read_text(encoding="utf-8").splitlines()
    page = rel(page_path)
    blocks: list[Block] = []
    pending: dict | None = None
    idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        m = RENDER_RE.match(stripped)
        if m:
            pending = {"kind": "render", "path": m.group("path"), **parse_marker(m.group("rest"))}
            continue
        m = ERROR_RE.match(stripped)
        if m:
            pending = {"kind": "error", "text": m.group("text")}
            continue
        m = SOURCE_RE.match(stripped)
        if m:
            pending = {"kind": "source", "path": m.group("path")}
            continue
        m = FENCE_RE.match(stripped)
        if m and m.group("lang") == "ncel":
            found = _next_fence(lines, i)
            assert found is not None
            _, code_start, code_end = found
            code = "\n".join(lines[code_start:code_end]) + "\n"
            blocks.append(
                Block(
                    page=page,
                    index=idx,
                    code=code,
                    start_line=code_start + 1,
                    marker=pending,
                )
            )
            idx += 1
            pending = None
    return blocks


def image_markers(page_path: Path) -> list[dict]:
    """`<!-- image: ... -->` markers used by the gallery page."""
    out = []
    for i, line in enumerate(page_path.read_text(encoding="utf-8").splitlines()):
        m = IMAGE_RE.match(line.strip())
        if m:
            out.append({"path": m.group("path"), "line": i + 1, **parse_marker(m.group("rest"))})
    return out


def markdown_files() -> list[Path]:
    files = [REPO / "README.md"]
    files += sorted(DOCS.rglob("*.md"))
    files += sorted((REPO / "examples").rglob("*.md")) if (REPO / "examples").exists() else []
    return [f for f in files if f.is_file()]


def load_manifest(path: Path | None = None) -> dict:
    path = path or DOCS / "scripts" / "expected.json"
    return json.loads(path.read_text(encoding="utf-8"))


def save_manifest(doc: dict, path: Path | None = None) -> None:
    path = path or DOCS / "scripts" / "expected.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clean_stderr(text: str) -> str:
    """Drop the launcher's two informational lines about the reference path."""
    keep = []
    for line in text.splitlines():
        if line.startswith("northcel: native runtime unavailable"):
            continue
        if line.startswith("northcel: using the non-native Python reference renderer"):
            continue
        keep.append(line)
    return "\n".join(keep).strip()


def find_markdown_links(page: Path) -> list[tuple[str, int]]:
    """Relative link/image targets in a markdown page (inline links only)."""
    text = page.read_text(encoding="utf-8")
    out: list[tuple[str, int]] = []
    for m in re.finditer(r"!?\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)", text):
        target = m.group(1)
        line = text[: m.start()].count("\n") + 1
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        if target.startswith("<") and target.endswith(">"):
            target = target[1:-1]
        out.append((target.split("#", 1)[0], line))
    return out
