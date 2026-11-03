"""NorthCel ring-chain encoders and decoders (0.25px, 0.25px Base-63, and 1px Base-63)."""

from __future__ import annotations

from typing import Sequence

B63_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_"
B63_MAP = {ch: i - 31 for i, ch in enumerate(B63_ALPHABET)}


class RingEncodingError(ValueError):
    """Raised when a ring-chain payload is malformed."""


def encode_ring_q25(ring: Sequence[Sequence[float]]) -> str:
    """Encodes a closed polygon ring into exact quarter-pixel (0.25px) relative deltas.

    Format: `x0,y0 dx1,dy1 dx2,dy2 ...` where coordinates are integers in 0.25px units.
    """
    if len(ring) < 3:
        raise RingEncodingError("A polygon ring requires at least 3 vertices.")
    pts = [(int(round(float(p[0]) * 4.0)), int(round(float(p[1]) * 4.0))) for p in ring]
    dedup = [pts[0]]
    for pt in pts[1:]:
        if pt != dedup[-1]:
            dedup.append(pt)
    if len(dedup) < 3:
        raise RingEncodingError("Ring collapses to fewer than 3 distinct quarter-pixel vertices.")
    out = [f"{dedup[0][0]},{dedup[0][1]}"]
    px, py = dedup[0]
    for x, y in dedup[1:]:
        out.append(f"{x - px},{y - py}")
        px, py = x, y
    return " ".join(out)


def decode_ring_q25(ring_str: str) -> list[tuple[float, float]]:
    """Decodes a quarter-pixel (0.25px) relative delta chain into (x, y) pixel coordinates."""
    s = ring_str.strip()
    if not s:
        raise RingEncodingError("Empty quarter-pixel ring string.")
    x, y = 0, 0
    pts: list[tuple[float, float]] = []
    for idx, token in enumerate(s.split()):
        if "," not in token:
            raise RingEncodingError(f"Expected 'dx,dy' pair at token {idx} ('{token}').")
        dxs, dys = token.split(",", 1)
        try:
            dx = int(dxs)
            dy = int(dys)
        except ValueError as exc:
            raise RingEncodingError(f"Non-integer quarter-pixel delta '{token}'.") from exc
        x += dx
        y += dy
        pts.append((x * 0.25, y * 0.25))
    if len(pts) < 3:
        raise RingEncodingError(f"Decoded ring has only {len(pts)} vertices (< 3).")
    return pts


def _encode_b63_scaled(ring: Sequence[Sequence[float]], scale: float) -> str:
    if len(ring) < 3:
        raise RingEncodingError("A polygon ring requires at least 3 vertices.")
    pts = [(int(round(float(p[0]) * scale)), int(round(float(p[1]) * scale))) for p in ring]
    dedup = [pts[0]]
    for pt in pts[1:]:
        if pt != dedup[-1]:
            dedup.append(pt)
    if len(dedup) < 3:
        raise RingEncodingError("Ring collapses to fewer than 3 distinct vertices.")
    expanded = [dedup[0]]
    for nx, ny in dedup[1:]:
        cx, cy = expanded[-1]
        while abs(nx - cx) > 31 or abs(ny - cy) > 31:
            dx_rem = nx - cx
            dy_rem = ny - cy
            dist = max(abs(dx_rem), abs(dy_rem))
            steps = (dist + 30) // 31
            sx = int(round(dx_rem / float(steps)))
            sy = int(round(dy_rem / float(steps)))
            sx = max(-31, min(31, sx))
            sy = max(-31, min(31, sy))
            cx += sx
            cy += sy
            expanded.append((cx, cy))
        if (nx, ny) != expanded[-1]:
            expanded.append((nx, ny))
    out = [f"{expanded[0][0]},{expanded[0][1]}:"]
    px, py = expanded[0]
    for x, y in expanded[1:]:
        dx, dy = x - px, y - py
        out.append(B63_ALPHABET[dx + 31] + B63_ALPHABET[dy + 31])
        px, py = x, y
    return "".join(out)


def _decode_b63_scaled(ring_str: str, inv_scale: float) -> list[tuple[float, float]]:
    s = ring_str.strip()
    if ":" not in s:
        raise RingEncodingError("Base-63 ring string must contain ':' after 'x0,y0'.")
    head, tail = s.split(":", 1)
    if "," not in head:
        raise RingEncodingError("Base-63 ring header must be 'x0,y0'.")
    x0s, y0s = head.split(",", 1)
    try:
        x = int(x0s)
        y = int(y0s)
    except ValueError as exc:
        raise RingEncodingError(f"Invalid Base-63 start coordinates '{head}'.") from exc
    if len(tail) % 2 != 0:
        raise RingEncodingError("Base-63 delta tail must have an even number of characters.")
    pts: list[tuple[float, float]] = [(x * inv_scale, y * inv_scale)]
    for i in range(0, len(tail), 2):
        c1, c2 = tail[i], tail[i + 1]
        if c1 not in B63_MAP or c2 not in B63_MAP:
            raise RingEncodingError(f"Invalid Base-63 character pair '{c1}{c2}' at offset {i}.")
        x += B63_MAP[c1]
        y += B63_MAP[c2]
        pts.append((x * inv_scale, y * inv_scale))
    if len(pts) < 3:
        raise RingEncodingError(f"Decoded Base-63 ring has only {len(pts)} vertices (< 3).")
    return pts


def encode_ring_b63_1px(ring: Sequence[Sequence[float]]) -> str:
    """Encodes a closed polygon ring into 1-pixel Base-63 relative deltas (`x0,y0:c1c2...`)."""
    return _encode_b63_scaled(ring, scale=1.0)


def decode_ring_b63_1px(ring_str: str) -> list[tuple[float, float]]:
    """Decodes a 1-pixel Base-63 relative delta chain (`x0,y0:c1c2...`)."""
    return _decode_b63_scaled(ring_str, inv_scale=1.0)


def encode_ring_b63_q25(ring: Sequence[Sequence[float]]) -> str:
    """Encodes a closed polygon ring into quarter-pixel (0.25px) Base-63 relative deltas (`qx0,qy0:c1c2...`)."""
    return _encode_b63_scaled(ring, scale=4.0)


def decode_ring_b63_q25(ring_str: str) -> list[tuple[float, float]]:
    """Decodes a quarter-pixel (0.25px) Base-63 relative delta chain (`qx0,qy0:c1c2...`)."""
    return _decode_b63_scaled(ring_str, inv_scale=0.25)


def decode_rings_payload(payload: str, precision: str = "0.25px") -> list[list[tuple[float, float]]]:
    """Decodes a `|`-separated multi-ring payload string according to scene precision."""
    raw = payload.strip()
    if not raw:
        return []
    rings: list[list[tuple[float, float]]] = []
    for idx, part in enumerate(raw.split("|")):
        part_s = part.strip()
        if not part_s:
            continue
        try:
            if ":" in part_s and " " not in part_s:
                if precision == "0.25px-b63":
                    rings.append(decode_ring_b63_q25(part_s))
                else:
                    rings.append(decode_ring_b63_1px(part_s))
            elif precision == "1px" and ":" in part_s:
                rings.append(decode_ring_b63_1px(part_s))
            else:
                rings.append(decode_ring_q25(part_s))
        except RingEncodingError as exc:
            raise RingEncodingError(f"Ring {idx}: {exc}") from exc
    return rings


def encode_rings_payload(rings: Sequence[Sequence[Sequence[float]]], precision: str = "0.25px") -> str:
    """Encodes a list of polygon rings into a `|`-separated payload string."""
    encoded: list[str] = []
    for r in rings:
        if precision == "1px":
            encoded.append(encode_ring_b63_1px(r))
        elif precision == "0.25px-b63":
            encoded.append(encode_ring_b63_q25(r))
        else:
            encoded.append(encode_ring_q25(r))
    return "|".join(encoded)
