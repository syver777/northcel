"""NCIR v2: one evaluated frame as a compact binary paint list.

NCIR v2 is the renderer hand-off between the Python evaluator and accelerated
backends (the built-in Vello tier).  It carries the semantics the Phase 4
prototype could not: ring topology per paint, group membership and opacity
scopes, resolved clip rings and per-paint opacity.  Geometry is already
frame-resolved by :func:`northcel.renderer.frame_paint_list`; the IR is not a
second evaluator.

Layout (little-endian)::

    "NCIR"  u16 version=2  u16 flags
    u32 width  u32 height  u32 frame  u32 fps  u32 seed
    u8 paper_r  u8 paper_g  u8 paper_b  u8 antialias_grid
    f32 grain
    u32 paint_count
    paint:
      u16 name_len  name bytes
      u8 r u8 g u8 b
      f32 opacity
      u16 group_count  (u32 id, f32 opacity)*
      u16 path_count   (u16 len, bytes)*
      u32 ring_count   ring*
      u16 clip_ring_count ring*
    ring: u32 vertex_count  (f32 x, f32 y)*
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

NCIR_MAGIC = b"NCIR"
NCIR_VERSION = 2
NCIR_FLAG_EMPTY = 0


class NCIRError(ValueError):
    """Raised for a truncated or malformed NCIR v2 file."""


def _rings_bytes(rings) -> bytes:
    out = [struct.pack("<I", len(rings))]
    for ring in rings:
        arr = np.asarray(ring, dtype="<f4").reshape(-1, 2)
        out.append(struct.pack("<I", arr.shape[0]))
        out.append(arr.tobytes(order="C"))
    return b"".join(out)


def build_frame(doc, frame_index: int = 0, seed_override: int | None = None) -> bytes:
    """Serialize one evaluated frame of a scene/film document to NCIR v2 bytes."""
    from .renderer import frame_paint_list

    paper, paper_color, paints = frame_paint_list(doc, frame_index, seed_override)
    seed = seed_override if seed_override is not None else doc.root.seed
    return _rebuild(doc, frame_index, seed, paper, paper_color, paints)


def _rebuild(doc, frame_index, seed, paper, paper_color, paints) -> bytes:
    root = doc.root
    fps = int(getattr(root, "fps", 1) or 1)
    out = [
        NCIR_MAGIC,
        struct.pack("<HHIIIII", NCIR_VERSION, NCIR_FLAG_EMPTY,
                    int(root.width), int(root.height), int(frame_index), fps, int(seed)),
        struct.pack("<BBBBf", int(paper_color.r), int(paper_color.g), int(paper_color.b),
                    int(paper.antialias_grid), float(getattr(paper, "grain", 0.0))),
        struct.pack("<I", len(paints)),
    ]
    for paint in paints:
        name = str(paint.name).encode("utf-8")[:65535]
        c = paint.color
        out.append(struct.pack("<H", len(name)))
        out.append(name)
        out.append(struct.pack("<BBBf", int(c.r), int(c.g), int(c.b), float(paint.opacity)))
        groups = list(paint.groups or ())
        out.append(struct.pack("<H", len(groups)))
        for gid, gop in groups:
            out.append(struct.pack("<If", int(gid), float(gop)))
        path = [str(p).encode("utf-8")[:65535] for p in (paint.path or ())]
        out.append(struct.pack("<H", len(path)))
        for piece in path:
            out.append(struct.pack("<H", len(piece)))
            out.append(piece)
        clip_rings = [ring for target in (paint.clip_shapes or []) for ring in target]
        out.append(struct.pack("<I", len(paint.rings)))
        out.append(_rings_bytes(paint.rings)[4:])
        out.append(struct.pack("<H", len(clip_rings)))
        out.append(_rings_bytes(clip_rings)[4:])
    return b"".join(out)


def write_frame(doc, frame_index: int, path, seed_override: int | None = None) -> int:
    data = build_frame(doc, frame_index, seed_override)
    Path(path).write_bytes(data)
    return len(data)


def read_frame(data: bytes) -> dict:
    """Parse NCIR v2 bytes (reference for tests and diagnostics)."""
    try:
        if data[:4] != NCIR_MAGIC:
            raise NCIRError("not an NCIR file (bad magic)")
        version, flags, width, height, frame, fps, seed = struct.unpack_from("<HHIIIII", data, 4)
        if version != NCIR_VERSION:
            raise NCIRError(f"unsupported NCIR version {version}")
        offset = 4 + struct.calcsize("<HHIIIII")
        pr, pg, pb, aa, grain = struct.unpack_from("<BBBBf", data, offset)
        offset += struct.calcsize("<BBBBf")
        (count,) = struct.unpack_from("<I", data, offset)
        offset += 4
        paints = []
        for _ in range(count):
            (nlen,) = struct.unpack_from("<H", data, offset)
            offset += 2
            name = data[offset:offset + nlen].decode("utf-8")
            offset += nlen
            r, g, b, opacity = struct.unpack_from("<BBBf", data, offset)
            offset += struct.calcsize("<BBBf")
            (gcount,) = struct.unpack_from("<H", data, offset)
            offset += 2
            groups = []
            for _ in range(gcount):
                gid, gop = struct.unpack_from("<If", data, offset)
                offset += struct.calcsize("<If")
                groups.append((gid, gop))
            (pcount,) = struct.unpack_from("<H", data, offset)
            offset += 2
            path = []
            for _ in range(pcount):
                (plen,) = struct.unpack_from("<H", data, offset)
                offset += 2
                path.append(data[offset:offset + plen].decode("utf-8"))
                offset += plen
            ring_count = struct.unpack_from("<I", data, offset)[0]
            offset += 4
            rings, offset = _read_rings(data, offset, ring_count)
            clip_count = struct.unpack_from("<H", data, offset)[0]
            offset += 2
            clips, offset = _read_rings(data, offset, clip_count)
            paints.append({"name": name, "color": [r, g, b], "opacity": opacity,
                           "groups": groups, "path": path, "rings": rings, "clips": clips})
        return {"version": version, "flags": flags, "width": width, "height": height,
                "frame": frame, "fps": fps, "seed": seed,
                "paper": [pr, pg, pb], "antialias_grid": aa, "grain": grain,
                "paints": paints}
    except struct.error as exc:
        raise NCIRError(f"truncated NCIR data: {exc}") from None


def _read_rings(data: bytes, offset: int, count: int):
    rings = []
    for _ in range(count):
        (n,) = struct.unpack_from("<I", data, offset)
        offset += 4
        arr = np.frombuffer(data, dtype="<f4", count=n * 2, offset=offset).reshape(n, 2)
        offset += n * 8
        rings.append(arr.astype(float).tolist())
    return rings, offset


def paint_list_for_frame(doc, frame_index: int = 0, seed_override: int | None = None):
    """The evaluated ``(paper, paper_color, paints)`` triple (shared with tests)."""
    from .renderer import frame_paint_list

    return frame_paint_list(doc, frame_index, seed_override)


__all__ = ["NCIR_MAGIC", "NCIR_VERSION", "NCIRError", "build_frame", "write_frame",
           "read_frame", "paint_list_for_frame"]
