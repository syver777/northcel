"""Shape correspondence between independently drawn frames, and films made from it.

This is the library behind `northcel tween --match`. It is offline authoring
arithmetic on vector shapes, not a renderer, an image model or a judge:

1. Each key drawing is a `StackedDrawing` (painter's-order solid shapes, see
   `northcel.shapes` and `northcel.fitting.fit_stacked`).
2. `match_drawings` pairs shapes of two drawings by a Hungarian assignment on
   centroid distance, log area ratio and colour, where a colour may only change
   along an explicitly allowed pair. A second pass matches leftover shapes that
   sit inside a matched shape, predicting their position from that shape's
   motion. It reports how much of the drawing matched and how far it moved.
3. `film_from_keys` writes one `film` that holds every key once (as a `def`),
   holds keys with `frame A..B`, and fills each transition with `morph`, `mix`
   and `opacity` (spec 0.4) — or with a cut or a dissolve when the match is not
   confident enough or when the author says so.

A match is evidence that contours can be interpolated without folding, not
that the in-betweens are anatomically right. Large pose changes (a crouch, a
spin, a landing) need a real drawing in between; the receipt marks every
transition it did not morph so a person can review it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable, Sequence

import numpy as np

from .shapes import RGB, Shape, StackedDrawing, _hex, encode_ring, palette_names, ring_centroid, \
    point_in_ring, darkest

MODES = ("auto", "morph", "cut", "dissolve", "hold")
_FORBIDDEN = 1e3
_NO_MATCH = 1e6


# ---------------------------------------------------------------- assignment
def linear_assignment(cost: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Minimum-cost assignment for a rectangular matrix (Hungarian / Jonker-Volgenant style).

    Deterministic: ties resolve to the lowest column index. Returns (rows, cols)
    sorted by row, like `scipy.optimize.linear_sum_assignment`. Pure NumPy.
    """
    c = np.asarray(cost, dtype=np.float64)
    if c.size == 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64)
    transposed = c.shape[0] > c.shape[1]
    if transposed:
        c = c.T
    n, m = c.shape
    u = np.zeros(n + 1)
    v = np.zeros(m + 1)
    p = np.zeros(m + 1, dtype=np.int64)   # p[j]: row (1-based) assigned to column j
    way = np.zeros(m + 1, dtype=np.int64)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = np.full(m + 1, np.inf)
        used = np.zeros(m + 1, dtype=bool)
        while True:
            used[j0] = True
            i0 = p[j0]
            free = ~used[1:]
            cur = c[i0 - 1] - u[i0] - v[1:]
            better = free & (cur < minv[1:])
            minv[1:][better] = cur[better]
            way[1:][better] = j0
            cand = np.where(free, minv[1:], np.inf)
            j1 = int(np.argmin(cand)) + 1
            delta = cand[j1 - 1]
            u[p[used]] += delta
            v[used] -= delta
            minv[1:][free] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    cols = np.flatnonzero(p[1:])
    rows = p[1:][cols] - 1
    if transposed:
        rows, cols = cols, rows
    order = np.argsort(rows, kind="stable")
    return rows[order].astype(np.int64), cols[order].astype(np.int64)


# ------------------------------------------------------------------ matching
@dataclass
class MatchOptions:
    """Knobs for `match_drawings`. Defaults are those of the film study that motivated it."""

    #: Unordered colour pairs a shape may change between (e.g. white -> red as colour floods in).
    colour_changes: Iterable[tuple[RGB, RGB]] = ()
    #: A pair is accepted when its cost is below this.
    match_cost: float = 2.0
    #: Shapes larger than this fraction of the canvas are background fields: matched, but not
    #: counted in the confidence numbers.
    background_fraction: float = 0.35


@dataclass
class Match:
    """Correspondence between the shapes of two drawings (indices into `.shapes`)."""

    pairs: list[tuple[int, int]]
    only_a: list[int]
    only_b: list[int]
    #: sqrt(area)-weighted mean centroid displacement of matched non-background shapes, px.
    displacement: float
    #: Matched area / total area over non-background shapes of both drawings.
    matched_fraction: float

    def confident(self, min_match: float, max_displacement: float) -> bool:
        return self.matched_fraction >= min_match and self.displacement <= max_displacement

    def as_dict(self) -> dict:
        return {"pairs": len(self.pairs), "only_a": len(self.only_a), "only_b": len(self.only_b),
                "matched_fraction": round(self.matched_fraction, 4),
                "displacement_px": round(self.displacement, 2)}


def _colour_cost(c1: RGB, c2: RGB, allowed: set[frozenset]) -> float:
    if c1 == c2:
        return 0.0
    if frozenset((c1, c2)) not in allowed:
        return _FORBIDDEN
    return math.dist(c1, c2) / 441.0


def _pair_cost(ca, aa, cb, ab, colour_cost) -> float:
    d = float(np.linalg.norm(ca - cb)) / (math.sqrt(max(aa, ab)) + 25.0)
    return d + 0.8 * abs(math.log((aa + 1.0) / (ab + 1.0))) + 1.2 * colour_cost


def _cost_matrix(fa, colours_a, fb, colours_b, allowed) -> np.ndarray:
    """Vectorised `_pair_cost` for all pairs; forbidden colour changes cost _NO_MATCH."""
    if not fa or not fb:
        return np.full((len(fa), len(fb)), _NO_MATCH)
    ca = np.array([c for c, _ in fa], dtype=np.float64)
    cb = np.array([c for c, _ in fb], dtype=np.float64)
    aa = np.array([a for _, a in fa], dtype=np.float64)[:, None]
    ab = np.array([a for _, a in fb], dtype=np.float64)[None, :]
    dist = np.sqrt(((ca[:, None, :] - cb[None, :, :]) ** 2).sum(axis=2))
    cost = dist / (np.sqrt(np.maximum(aa, ab)) + 25.0) + 0.8 * np.abs(np.log((aa + 1.0) / (ab + 1.0)))
    uniq_a = sorted(set(colours_a))
    uniq_b = sorted(set(colours_b))
    cc = np.array([[_colour_cost(x, y, allowed) for y in uniq_b] for x in uniq_a], dtype=np.float64)
    ia = np.array([uniq_a.index(c) for c in colours_a])
    ib = np.array([uniq_b.index(c) for c in colours_b])
    col = cc[ia][:, ib]
    cost = cost + 1.2 * col
    cost[col >= _FORBIDDEN] = _NO_MATCH
    return cost


def match_drawings(a: StackedDrawing, b: StackedDrawing, options: MatchOptions | None = None) -> Match:
    """Pair the shapes of `a` with those of `b`. See the module docstring for the method."""
    opt = options or MatchOptions()
    allowed = {frozenset((tuple(x), tuple(y))) for x, y in opt.colour_changes}
    A, B = a.shapes, b.shapes
    fa = [(ring_centroid(s.ring), s.area) for s in A]
    fb = [(ring_centroid(s.ring), s.area) for s in B]
    cost = _cost_matrix(fa, [s.color for s in A], fb, [s.color for s in B], allowed)
    lim = opt.match_cost
    ii, jj = linear_assignment(cost) if len(A) and len(B) else ([], [])
    accepted = [(int(i), int(j)) for i, j in zip(ii, jj) if cost[i, j] < lim]

    # Pass 2, motion propagation: an unmatched shape of A inherits the offset of
    # the smallest matched shape of A that contains its centroid.
    used_a = {i for i, _ in accepted}
    used_b = {j for _, j in accepted}
    rest_a = [i for i in range(len(A)) if i not in used_a]
    rest_b = [j for j in range(len(B)) if j not in used_b]
    if rest_a and rest_b and accepted:
        cost2 = np.full((len(rest_a), len(rest_b)), _NO_MATCH)
        for x, i in enumerate(rest_a):
            best = None
            for pi, pj in accepted:
                if fa[pi][1] > fa[i][1] and point_in_ring(fa[i][0], A[pi].ring) and (best is None or fa[pi][1] < best[0]):
                    best = (fa[pi][1], fb[pj][0] - fa[pi][0])
            if best is None:
                continue
            pred, aa = fa[i][0] + best[1], fa[i][1]
            for y, j in enumerate(rest_b):
                cc = _colour_cost(A[i].color, B[j].color, allowed)
                if cc < _FORBIDDEN:
                    cost2[x, y] = _pair_cost(pred, aa, fb[j][0], fb[j][1], cc)
        xi, yj = linear_assignment(cost2)
        accepted += [(rest_a[x], rest_b[y]) for x, y in zip(xi, yj) if cost2[x, y] < lim]

    big = opt.background_fraction * max(a.width * a.height, b.width * b.height)
    disp, weights = [], []
    matched = total = 0.0
    for i, j in accepted:
        aa, ab = A[i].area, B[j].area
        if max(aa, ab) < big:
            disp.append(float(np.linalg.norm(fa[i][0] - fb[j][0])))
            weights.append(math.sqrt(aa))
            matched += aa + ab
    for s in list(A) + list(B):
        if s.area < big:
            total += s.area
    used_a = {i for i, _ in accepted}
    used_b = {j for _, j in accepted}
    return Match(
        pairs=sorted(accepted),
        only_a=[i for i in range(len(A)) if i not in used_a],
        only_b=[j for j in range(len(B)) if j not in used_b],
        displacement=float(np.average(disp, weights=weights)) if disp else 0.0,
        matched_fraction=(matched / total) if total else 1.0,
    )


# ---------------------------------------------------------------------- film
@dataclass
class Key:
    """A key drawing shown from `time` seconds."""

    drawing: StackedDrawing
    time: float
    name: str | None = None


@dataclass
class Transition:
    """How to get from one key to the next.

    `mode`: "auto" (morph when the match is confident, else the film's fallback),
    "morph", "cut" (switch half-way through the window), "dissolve" (group
    opacity cross-fade) or "hold" (switch on the next key's frame).
    `seconds`: window length before the next key (default: FilmOptions.transition_seconds).
    """

    mode: str = "auto"
    seconds: float | None = None


@dataclass
class FilmOptions:
    fps: int = 20
    #: Total frames; default: last key frame + 1.
    frames: int | None = None
    width: int | None = None
    height: int | None = None
    antialias_grid: int = 4
    #: Each transition uses at most this long before the next key; earlier frames hold.
    transition_seconds: float = 1.0 / 3.0
    #: "smooth" (cubic smoothstep), "linear" or "ease" (quintic).
    easing: str = "smooth"
    #: Confidence thresholds for "auto".
    min_match: float = 0.5
    max_displacement: float = 32.0
    #: What "auto" does when the match is not confident: "cut" or "dissolve".
    fallback: str = "cut"
    #: Same-colour pairs bigger than this canvas fraction switch half-way instead of morphing
    #: (background fields bulge around a moving figure when morphed).
    switch_area_fraction: float = 0.095
    #: Same, for the ink colour (big connected outlines fold when morphed).
    ink_switch_area_fraction: float = 0.0127
    ink: RGB | None = None
    #: Morph resampling: clamp(max perimeter / samples_per_px, 24, max_samples).
    samples_per_px: float = 3.5
    max_samples: int = 480
    name: str = "Polished"
    match: MatchOptions = field(default_factory=MatchOptions)


def _u_expr(lo: int, hi: int, easing: str) -> str:
    """u for frames lo..hi: strictly between 0 and 1, reaching neither key exactly."""
    a, b = lo - 1, hi + 1
    if easing == "linear":
        return f"(f - {a}) / {b - a}"
    if easing == "ease":
        return f"ease((f - {a}) / {b - a})"
    if easing == "smooth":
        return f"smoothstep({a}, {b}, f)"
    raise ValueError("easing must be smooth, linear or ease")


def _samples(sa: Shape, sb: Shape, opt: FilmOptions) -> int:
    return int(min(opt.max_samples, max(24, max(sa.perimeter, sb.perimeter) / opt.samples_per_px)))


def film_from_keys(keys: Sequence[Key], transitions: Sequence[Transition | str] | None = None,
                   options: FilmOptions | None = None) -> tuple[str, dict]:
    """Write one spec 0.4 `film` from ordered keys. Returns (source, receipt).

    Each key's shapes are written once, as `def K<i>`. Frames between transitions
    hold a key with `frame A..B { use K<i> }`. A morph transition is a `def T<i>(u: 0)`
    of `morph`/`layer` items used over its window with an eased `u`; colour
    changes use `mix`, shapes without a partner (and very large fields) switch at
    u = 0.5 with `opacity: step(...)`. A dissolve uses `use K<j>(opacity: u)` over
    the previous key. The receipt lists every transition with its match numbers
    and the mode actually used.
    """
    opt = options or FilmOptions()
    if len(keys) < 1:
        raise ValueError("film_from_keys needs at least one key")
    if opt.fallback not in ("cut", "dissolve"):
        raise ValueError("fallback must be cut or dissolve")
    trans = list(transitions) if transitions is not None else ["auto"] * (len(keys) - 1)
    if len(trans) != len(keys) - 1:
        raise ValueError("need exactly one transition per pair of consecutive keys")
    trans = [Transition(t) if isinstance(t, str) else t for t in trans]
    for t in trans:
        if t.mode not in MODES:
            raise ValueError(f"unknown transition mode {t.mode!r}; use one of {', '.join(MODES)}")
    width = opt.width or keys[0].drawing.width
    height = opt.height or keys[0].drawing.height
    frame_of = [max(0, int(round(k.time * opt.fps))) for k in keys]
    for i in range(1, len(keys)):
        if frame_of[i] <= frame_of[i - 1]:
            raise ValueError(f"keys {i - 1} and {i} land on frames {frame_of[i - 1]} and {frame_of[i]}; "
                             "keys must be at increasing frames")
    total = opt.frames if opt.frames is not None else frame_of[-1] + 1
    if total <= frame_of[-1]:
        raise ValueError(f"frames={total} does not reach the last key (frame {frame_of[-1]})")

    colours: list[RGB] = []
    for k in keys:
        colours.extend(k.drawing.colors())
    names = palette_names(colours)
    film_paper = keys[0].drawing.paper

    def framing(d: StackedDrawing) -> tuple[float, float, float] | None:
        if (d.width, d.height) == (width, height):
            return None
        s = min(width / d.width, height / d.height)
        return s, (width - d.width * s) / 2.0, (height - d.height * s) / 2.0

    def camera(t, indent="    ") -> list[str]:
        if t is None:
            return []
        s, ox, oy = t
        return [f"{indent}transform all(scale: {s:.6g}, translate: ({ox:.6g}, {oy:.6g}))"]

    ink = opt.ink or darkest(colours)
    receipt_transitions = []
    plans = []  # (i, mode, s, e, match)
    for i, t in enumerate(trans):
        a, b = keys[i].drawing, keys[i + 1].drawing
        gap = frame_of[i + 1] - frame_of[i] - 1
        seconds = opt.transition_seconds if t.seconds is None else t.seconds
        n = max(0, min(gap, int(round(seconds * opt.fps))))
        s, e = frame_of[i + 1] - n, frame_of[i + 1] - 1
        match = None
        mode = t.mode
        reason = "requested"
        if mode in ("auto", "morph") and n > 0:
            match = match_drawings(a, b, opt.match)
        if mode == "auto":
            if n == 0:
                mode, reason = "hold", "no frames between the keys"
            elif match.confident(opt.min_match, opt.max_displacement):
                mode, reason = "morph", "match above thresholds"
            else:
                mode = opt.fallback
                reason = (f"match below thresholds (matched {match.matched_fraction:.2f} < {opt.min_match}"
                          if match.matched_fraction < opt.min_match else
                          f"match below thresholds (displacement {match.displacement:.1f}px > {opt.max_displacement}")
                reason += ")"
        if n == 0 and mode in ("morph", "dissolve", "cut"):
            mode, reason = "hold", "no frames between the keys"
        plans.append((i, mode, s, e, match))
        entry = {"from": i, "to": i + 1, "key_frames": [frame_of[i], frame_of[i + 1]],
                 "window": [s, e] if n else None, "requested": t.mode, "mode": mode, "reason": reason}
        if match is not None:
            entry.update(match.as_dict())
        receipt_transitions.append(entry)

    # Which keys need a paper rectangle (dissolve targets cover the previous key fully).
    dissolve_targets = {i + 1 for i, mode, *_ in plans if mode == "dissolve"}

    lines = [
        'northcel "0.4.0-draft"',
        "",
        f"film {opt.name}(width: {width}, height: {height}, fps: {opt.fps}, frames: {total}, precision: 0.25px-b63) {{",
        "  palette { " + ", ".join(f"{nm}: {_hex(c)}" for c, nm in names.items()) + " }",
        f"  paper {{ color: ${names[film_paper]}, antialias_grid: {opt.antialias_grid} }}",
    ]

    # --- one def per key
    for i, k in enumerate(keys):
        d = k.drawing
        lines.append(f"  def K{i} {{")
        if i in dissolve_targets:
            w4, h4 = d.width * 4, d.height * 4
            lines.append(f'    layer k{i}_paper(color: ${names[d.paper]}) {{ "0,0 {w4},0 0,{h4} -{w4},0" }}')
        for n_s, shp in enumerate(d.shapes):
            text = encode_ring(shp.ring)
            if text:
                lines.append(f'    layer k{i}_{n_s}(color: ${names[shp.color]}) {{ "{text}" }}')
        lines.append("  }")

    # --- one def per morph transition
    big_area = opt.switch_area_fraction * width * height
    ink_area = opt.ink_switch_area_fraction * width * height
    for i, mode, s, e, match in plans:
        if mode != "morph":
            continue
        A, B = keys[i].drawing.shapes, keys[i + 1].drawing.shapes
        items = []  # (order area, seq, line)
        for seq, (pi, pj) in enumerate(match.pairs):
            sa, sb = A[pi], B[pj]
            ta, tb = encode_ring(sa.ring), encode_ring(sb.ring)
            if not ta or not tb:
                continue
            if sa.color == sb.color and (max(sa.area, sb.area) > big_area or
                                         (sa.color == ink and max(sa.area, sb.area) > ink_area)):
                items.append((sa.area, seq, f'    layer t{i}_{seq}a(color: ${names[sa.color]}, opacity: 1 - step(0.5, u)) {{ "{ta}" }}'))
                items.append((sb.area, seq, f'    layer t{i}_{seq}b(color: ${names[sb.color]}, opacity: step(0.5, u)) {{ "{tb}" }}'))
                continue
            colour = f"${names[sa.color]}" if sa.color == sb.color else f"mix(${names[sa.color]}, ${names[sb.color]}, u)"
            items.append(((sa.area + sb.area) / 2.0, seq,
                          f'    morph t{i}_{seq}(color: {colour}, u: u, samples: {_samples(sa, sb, opt)}) {{ "{ta}" => "{tb}" }}'))
        base = len(match.pairs)
        for n_o, pi in enumerate(match.only_a):
            text = encode_ring(A[pi].ring)
            if text:
                items.append((A[pi].area, base + n_o, f'    layer t{i}_a{pi}(color: ${names[A[pi].color]}, opacity: 1 - step(0.5, u)) {{ "{text}" }}'))
        base += len(match.only_a)
        for n_o, pj in enumerate(match.only_b):
            text = encode_ring(B[pj].ring)
            if text:
                items.append((B[pj].area, base + n_o, f'    layer t{i}_b{pj}(color: ${names[B[pj].color]}, opacity: step(0.5, u)) {{ "{text}" }}'))
        items.sort(key=lambda it: (-it[0], it[1]))
        lines.append(f"  def T{i}(u: 0) {{")
        lines.extend(line for _area, _seq, line in items)
        lines.append("  }")

    # --- frame blocks
    def block(lo: int, hi: int, body: list[str]) -> None:
        if lo > hi:
            return
        label = f"{lo}" if lo == hi else f"{lo}..{hi}"
        lines.append(f"  frame {label} {{")
        lines.extend(body)
        lines.append("  }")

    def paper_line(colour_text: str) -> str:
        return f"    paper {{ color: {colour_text}, antialias_grid: {opt.antialias_grid} }}"

    def hold_body(i: int) -> list[str]:
        d = keys[i].drawing
        body = [] if d.paper == film_paper else [paper_line(f"${names[d.paper]}")]
        return body + [f"    use K{i}"] + camera(framing(d))

    start = 0
    for i, mode, s, e, match in plans:
        nxt = frame_of[i + 1]
        if mode == "hold":
            block(start, nxt - 1, hold_body(i))
            start = nxt
        elif mode == "cut":
            n = e - s + 1
            cut = s + n // 2   # first frame of the next key; earlier frames have u < 0.5
            block(start, cut - 1, hold_body(i))
            start = cut
        else:
            block(start, s - 1, hold_body(i))
            u = _u_expr(s, e, opt.easing)
            da, db = keys[i].drawing, keys[i + 1].drawing
            body = []
            if da.paper != db.paper:
                body.append(paper_line(f"mix(${names[da.paper]}, ${names[db.paper]}, {u})"))
            elif da.paper != film_paper:
                body.append(paper_line(f"${names[da.paper]}"))
            if mode == "morph":
                body.append(f"    use T{i}(u: {u})")
                fa_, fb_ = framing(da), framing(db)
                if fa_ or fb_:
                    fa_ = fa_ or (1.0, 0.0, 0.0)
                    fb_ = fb_ or (1.0, 0.0, 0.0)
                    body.append(f"    transform all(scale: lerp({fa_[0]:.6g}, {fb_[0]:.6g}, {u}), translate: "
                                f"(lerp({fa_[1]:.6g}, {fb_[1]:.6g}, {u}), lerp({fa_[2]:.6g}, {fb_[2]:.6g}, {u})))")
            else:  # dissolve
                body.append(f"    use K{i}")
                body.extend(camera(framing(da)))
                body.append(f"    use K{i + 1}(opacity: {u})")
                if framing(db) is not None:
                    raise ValueError("a dissolve between keys of different sizes is not supported; "
                                     "give the keys the film's canvas size")
            block(s, e, body)
            start = nxt
    block(start, total - 1, hold_body(len(keys) - 1))
    lines.append("}")
    source = "\n".join(lines) + "\n"
    modes: dict[str, int] = {}
    for entry in receipt_transitions:
        modes[entry["mode"]] = modes.get(entry["mode"], 0) + 1
    receipt = {"tool": "northcel-tween/2", "mode": "match", "frames": total, "fps": opt.fps,
               "keys": [{"frame": f, "time": k.time, "name": k.name or k.drawing.name,
                         "shapes": len(k.drawing.shapes)} for f, k in zip(frame_of, keys)],
               "transitions": receipt_transitions, "modes": modes,
               "thresholds": {"min_match": opt.min_match, "max_displacement_px": opt.max_displacement,
                              "fallback": opt.fallback},
               "bytes": len(source.encode()), "quality": "unreviewed"}
    return source, receipt


__all__ = [
    "Key", "Transition", "FilmOptions", "MatchOptions", "Match", "MODES",
    "linear_assignment", "match_drawings", "film_from_keys",
]
