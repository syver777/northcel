"""Spec 0.4 / tools 0.5: mix, morph, frame ranges, opacity, stacked fit and matching tween."""
from __future__ import annotations

import itertools
import json

import numpy as np
import pytest
from PIL import Image, ImageDraw

from northcel import format_document, parse_ncel, render_document_frame, validate_document
from northcel.parser import NorthCelSyntaxError
from northcel.renderer import morph_rings, resolve_color


def errors(src: str) -> list[str]:
    return [d.message for d in validate_document(parse_ncel(src)) if d.level == "error"]


def warnings(src: str) -> list[str]:
    return [d.message for d in validate_document(parse_ncel(src)) if d.level == "warning"]


def roundtrip(src: str) -> str:
    """fmt is idempotent and the formatted document renders the same pixels."""
    once = format_document(parse_ncel(src))
    twice = format_document(parse_ncel(once))
    assert once == twice
    a, b = parse_ncel(src), parse_ncel(once)
    for f in range(getattr(a.root, "frames", 1)):
        assert np.array_equal(render_document_frame(a, f), render_document_frame(b, f)), f
    return once


SQUARE = "40,40 80,0 0,80 -80,0"           # 10..30 px square, 4 vertices (quarter-pixel units)
OCTAGON = "100,60 40,0 30,30 0,40 -30,30 -40,0 -30,-30 0,-40"  # 8 vertices

FILM = f'''northcel "0.4.0-draft"
film Demo(width: 48, height: 40, fps: 12, frames: 9, precision: 0.25px) {{
  palette {{ sky: #70CCF5, ink: #0D0D0D, red: #EE2C2C }}
  paper {{ color: mix($sky, #FFFFFF, t), antialias_grid: 4 }}
  def Box(k: 0) {{
    layer box(color: mix($red, $ink, k), opacity: 0.5) {{ "{SQUARE}" }}
  }}
  layer bg(color: $ink, opacity: 0.25) {{ "0,0 64,0 0,64 -64,0" }}
  morph blob(color: mix(#FFFFFF, mix($red, $sky, 0.5), t), u: smoothstep(0, 8, f), samples: 32, outline: ($ink, 1.5px)) {{ "{SQUARE}" => "{OCTAGON}" }}
  frame 2..5 {{
    use Box(k: t, opacity: 0.75)
  }}
  frame 4..6 {{
    drop bg
  }}
  frame 4 {{
    stroke s(color: #00FF00, width: 2, opacity: 1 - t) {{ (2, 2), (40, 30) }}
    ribbon r(color: $red, opacity: 0.5) {{ (4, 30, 2), (30, 34, 4) }}
  }}
}}
'''


# ------------------------------------------------------------------ syntax
def test_all_new_syntax_parses_validates_and_formats():
    assert errors(FILM) == []
    out = roundtrip(FILM)
    for needle in ("mix($sky, #FFFFFF, t)", "morph blob(", '=> "', "frame 2..5 {", "frame 4..6 {",
                   "opacity: 0.5", "use Box(k: t, opacity: 0.75)", "samples: 32", "opacity: 1 - t"):
        assert needle in out, needle
    # Exact frames are listed first, ranges keep source order (later range wins).
    assert out.index("frame 4 {") < out.index("frame 2..5 {") < out.index("frame 4..6 {")


def test_film_is_deterministic_forward_and_reverse():
    doc = parse_ncel(FILM)
    forward = [render_document_frame(doc, f).tobytes() for f in range(9)]
    backward = [render_document_frame(doc, f).tobytes() for f in reversed(range(9))][::-1]
    assert forward == backward
    assert len(set(forward)) > 4


def test_syntax_errors_are_located():
    with pytest.raises(NorthCelSyntaxError, match="reversed"):
        parse_ncel("film F(frames: 9) { frame 5..2 { } }")
    with pytest.raises(NorthCelSyntaxError, match="cannot be a mix"):
        parse_ncel("scene S { palette { a: mix(#000, #FFF, 0.5) } }")
    with pytest.raises(NorthCelSyntaxError, match="requires a u"):
        parse_ncel(f'scene S {{ morph m(tone: 0) {{ "{SQUARE}" => "{SQUARE}" }} }}')
    with pytest.raises(NorthCelSyntaxError, match="Unknown morph attribute"):
        parse_ncel(f'scene S {{ morph m(u: 0, boil: 1) {{ "{SQUARE}" => "{SQUARE}" }} }}')
    with pytest.raises(NorthCelSyntaxError, match="mix\\(\\) expects two colours"):
        parse_ncel(f'scene S {{ layer a(color: mix(1, #FFF, 0)) {{ "{SQUARE}" }} }}')
    with pytest.raises(NorthCelSyntaxError, match="opacity must be"):
        parse_ncel(f'scene S {{ layer a(tone: 0, opacity: #FFF) {{ "{SQUARE}" }} }}')
    with pytest.raises(NorthCelSyntaxError):
        parse_ncel(f'scene S {{ morph m(u: 0) {{ "{SQUARE}" "{SQUARE}" }} }}')


def test_semantic_errors_and_warnings():
    assert any("pairs ring i with ring i" in e for e in
               errors(f'scene S {{ morph m(u: 0) {{ "{SQUARE}|{SQUARE}" => "{SQUARE}" }} }}'))
    assert any("samples must be" in e for e in
               errors(f'scene S {{ morph m(u: 0, samples: 2) {{ "{SQUARE}" => "{SQUARE}" }} }}'))
    assert any("Frame range 3..12 out of range" in e for e in errors("film F(frames: 10) { frame 3..12 { } }"))
    assert any("overlaps" in w for w in warnings("film F(frames: 10) { frame 1..4 { } frame 3..6 { } }"))


def test_spec_04_constructs_need_a_04_header():
    old = 'northcel "0.3.0-draft"\n'
    assert any("morph requires" in e for e in errors(old + f'scene S {{ morph m(u: 0) {{ "{SQUARE}" => "{SQUARE}" }} }}'))
    assert any("mix requires" in e for e in errors(old + f'scene S {{ layer a(color: mix(#000, #FFF, 0)) {{ "{SQUARE}" }} }}'))
    assert any("frame-range requires" in e for e in errors(old + "film F(frames: 4) { frame 1..2 { } }"))
    # opacity was silently ignored before 0.4; in an old document it still is, with a warning.
    src = old + f'scene S(width: 16, height: 16) {{ paper {{ tone: 255 }} layer a(tone: 0, opacity: 0.5) {{ "{SQUARE}" }} }}'
    assert errors(src) == [] and any("ignored" in w for w in warnings(src))
    assert render_document_frame(parse_ncel(src))[15, 15, 0] == 0
    # Headerless documents are spec 0.4 now.
    assert errors(f'scene S {{ morph m(u: 0) {{ "{SQUARE}" => "{SQUARE}" }} }}') == []


# --------------------------------------------------------------------- mix
def test_mix_clamps_and_rounds_in_srgb():
    def col(src):
        doc = parse_ncel(f'scene S(width: 4, height: 4) {{ paper {{ color: {src}, antialias_grid: 1 }} }}')
        return tuple(render_document_frame(doc)[0, 0])
    assert col("mix(#000000, #FFFFFF, -1)") == (0, 0, 0)
    assert col("mix(#000000, #FFFFFF, 2)") == (255, 255, 255)
    assert col("mix(#000000, #FFFFFF, 0.5)") == (128, 128, 128)          # floor(127.5 + 0.5)
    assert col("mix(#102030, #203040, 0.25)") == (20, 36, 52)
    assert col("mix(mix(#000000, #FF0000, 1), #0000FF, 0.5)") == (128, 0, 128)
    m = parse_ncel('scene S { layer a(color: mix(#000000, #FFFFFF, f / 10)) { "0,0 4,0 0,4" } }').root.items[0].color
    assert resolve_color(m, {"f": 5.0}).as_rgb_tuple() == (128, 128, 128)


def test_mix_on_outline_stroke_and_ribbon():
    src = '''scene S(width: 32, height: 32) {
  paper { tone: 255, antialias_grid: 1 }
  cel c(color: mix(#FF0000, #0000FF, 1), outline: (mix(#000000, #FFFFFF, 0), 2px)) { "16,16 64,0 0,64 -64,0" }
  stroke s(color: mix(#00FF00, #000000, 0), width: 2) { (0, 30), (31, 30) }
  ribbon r(color: mix(#000000, #FF00FF, 1)) { (30, 0, 2), (30, 20, 2) }
}'''
    assert errors(src) == []
    img = render_document_frame(parse_ncel(src))
    assert tuple(img[10, 10]) == (0, 0, 255)
    assert tuple(img[4, 10]) == (0, 0, 0)          # outline straddles the edge at y=4
    assert tuple(img[30, 10]) == (0, 255, 0)
    assert tuple(img[10, 30]) == (255, 0, 255)
    roundtrip(src)


# ------------------------------------------------------------------- morph
def test_morph_endpoints_are_exact_and_unequal_counts_interpolate():
    def scene(u):
        return parse_ncel(f'scene S(width: 48, height: 40) {{ paper {{ tone: 255 }} '
                          f'morph m(tone: 0, u: {u}) {{ "{SQUARE}" => "{OCTAGON}" }} }}')
    def plain(payload):
        return parse_ncel(f'scene S(width: 48, height: 40) {{ paper {{ tone: 255 }} layer m(tone: 0) {{ "{payload}" }} }}')
    assert np.array_equal(render_document_frame(scene(0)), render_document_frame(plain(SQUARE)))
    assert np.array_equal(render_document_frame(scene(-3)), render_document_frame(plain(SQUARE)))
    assert np.array_equal(render_document_frame(scene(1)), render_document_frame(plain(OCTAGON)))
    item = scene(0.5).root.items[0]
    rings = morph_rings(item, "0.25px", {})
    assert len(rings) == 1 and len(rings[0]) == 8     # default samples: the larger vertex count, at least 8
    mid = np.asarray(rings[0])
    # Square centre (20, 20), octagon centre (30, 27.5): the half-way centroid lies between.
    c = mid.mean(axis=0)
    assert 24.5 < c[0] < 25.5 and 23 < c[1] < 24.5
    a = render_document_frame(scene(0.5))
    assert not np.array_equal(a, render_document_frame(scene(0))) and np.array_equal(a, render_document_frame(scene(0.5)))


def test_morph_aligns_the_start_vertex():
    sq = "40,40 80,0 0,80 -80,0"
    other_start = "120,40 0,80 -80,0 0,-80"   # the same square from the top-right corner
    doc = parse_ncel(f'scene S(width: 48, height: 40) {{ morph m(tone: 0, u: 0.5, samples: 16) {{ "{sq}" => "{other_start}" }} }}')
    ring = np.asarray(morph_rings(doc.root.items[0], "0.25px", {})[0])
    # Aligned: every in-between point stays on the square's outline (no cut corners).
    on_edge = (np.isclose(ring[:, 0], 10) | np.isclose(ring[:, 0], 30)
               | np.isclose(ring[:, 1], 10) | np.isclose(ring[:, 1], 30))
    assert on_edge.all() and abs(_area(ring)) == pytest.approx(400.0)


def _area(r):
    x, y = r[:, 0], r[:, 1]
    return 0.5 * float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def test_morph_reversed_winding_never_folds():
    sq = "40,40 80,0 0,80 -80,0"
    reversed_sq = "40,40 0,80 80,0 0,-80"      # same square, opposite winding
    doc = parse_ncel(f'scene S(width: 48, height: 40) {{ morph m(tone: 0, u: 0.5, samples: 16) {{ "{sq}" => "{reversed_sq}" }} }}')
    ring = np.asarray(morph_rings(doc.root.items[0], "0.25px", {})[0])
    assert abs(_area(ring)) == pytest.approx(400.0)   # identical squares: the in-between is the square


def test_morph_inside_def_frame_and_transform():
    src = f'''northcel "0.4.0-draft"
film F(width: 48, height: 40, frames: 5) {{
  paper {{ tone: 255 }}
  def D(k: 0) {{
    morph m(tone: 0, u: k) {{ "{SQUARE}" => "{OCTAGON}" }}
  }}
  frame 0..4 {{
    use D(k: t)
    transform m(translate: (2, 0))
    drop nothing_here
  }}
}}'''
    assert errors(src) == []
    roundtrip(src)


# ------------------------------------------------------------- frame ranges
def test_frame_precedence_exact_then_later_range_then_base():
    src = '''northcel "0.4.0-draft"
film F(width: 8, height: 8, frames: 10) {
  paper { tone: 255, antialias_grid: 1 }
  layer base(tone: 200) { "0,0 32,0 0,32 -32,0" }
  frame 2..7 { layer base(tone: 100) { "0,0 32,0 0,32 -32,0" } }
  frame 5..8 { layer base(tone: 50) { "0,0 32,0 0,32 -32,0" } }
  frame 6 { layer base(tone: 10) { "0,0 32,0 0,32 -32,0" } }
}'''
    doc = parse_ncel(src)
    got = [int(render_document_frame(doc, f)[0, 0, 0]) for f in range(10)]
    assert got == [200, 200, 100, 100, 100, 50, 10, 50, 50, 200]
    assert doc.root.override_for(6).name == "frame_6"
    assert doc.root.override_for(3).name == "frames_2_7"
    assert doc.root.override_for(9) is None
    roundtrip(src)


# ----------------------------------------------------------------- opacity
def test_layer_opacity_blends_each_subpixel():
    def px(opacity, aa=1):
        src = (f'scene S(width: 8, height: 8) {{ paper {{ tone: 200, antialias_grid: {aa} }} '
               f'layer a(tone: 0{opacity}) {{ "0,0 32,0 0,32 -32,0" }} }}')
        return int(render_document_frame(parse_ncel(src))[3, 3, 0])
    assert px("") == 0
    assert px(", opacity: 1") == 0
    assert px(", opacity: 0") == 200
    assert px(", opacity: 0.25") == 150                   # floor(200 + (0 - 200) * 0.25 + 0.5)
    assert px(", opacity: 2") == 0 and px(", opacity: -1") == 200     # clamped
    assert px(", opacity: 0.25", aa=4) == 150
    rgb = parse_ncel('scene S(width: 4, height: 4) { paper { color: #102030, antialias_grid: 1 } '
                     'layer a(color: #FF0000, opacity: 0.5) { "0,0 16,0 0,16 -16,0" } }')
    assert tuple(render_document_frame(rgb)[1, 1]) == (136, 16, 24)


def test_group_opacity_does_not_compound_overlaps():
    src = '''scene S(width: 8, height: 8) {
  paper { tone: 255, antialias_grid: 1 }
  def G {
    layer back(tone: 100) { "0,0 32,0 0,32 -32,0" }
    layer front(tone: 0) { "0,0 16,0 0,32 -16,0" }
  }
  use G(opacity: 0.5)
}'''
    img = render_document_frame(parse_ncel(src))
    assert int(img[2, 1, 0]) == 128      # floor(255 + (0 - 255) * 0.5 + 0.5): front only, not front over back
    assert int(img[2, 6, 0]) == 178      # floor(255 + (100 - 255) * 0.5 + 0.5)
    layered = src.replace("use G(opacity: 0.5)", "use G(opacity: 0)")
    assert int(render_document_frame(parse_ncel(layered))[2, 1, 0]) == 255
    full = src.replace("use G(opacity: 0.5)", "use G(opacity: 1)")
    assert int(render_document_frame(parse_ncel(full))[2, 1, 0]) == 0
    roundtrip(src)


def test_dissolve_with_group_opacity_is_a_cross_fade():
    a = 'layer pa(tone: 0) { "0,0 32,0 0,32 -32,0" }'
    b = 'layer pb(tone: 255) { "0,0 32,0 0,32 -32,0" } layer dot(tone: 100) { "8,8 8,0 0,8 -8,0" }'
    src = (f'film F(width: 8, height: 8, frames: 5) {{ paper {{ tone: 50, antialias_grid: 1 }} '
           f'def A {{ {a} }} def B {{ {b} }} frame 0..4 {{ use A use B(opacity: t) }} }}')
    doc = parse_ncel(src)
    mid = render_document_frame(doc, 2)
    assert int(mid[0, 0, 0]) == 128 and int(mid[2, 2, 0]) == 50     # 0 -> 255 and 0 -> 100, half-way
    assert int(render_document_frame(doc, 0)[0, 0, 0]) == 0 and int(render_document_frame(doc, 4)[0, 0, 0]) == 255


# ------------------------------------------------------------------- launcher
def test_launcher_routes_spec04_documents_to_the_reference(tmp_path, monkeypatch):
    from northcel.launcher import cli as launcher, native

    new = tmp_path / "new.ncel"
    new.write_text(FILM)
    old = tmp_path / "old.ncel"
    old.write_text('northcel "0.3.0-draft"\nscene S { layer a(tone: 0) { "0,0 4,0 0,4" } }\n')
    header_only = tmp_path / "header.ncel"
    header_only.write_text('northcel "0.4.0-draft"\nscene S { layer a(tone: 0) { "0,0 4,0 0,4" } }\n')
    headerless = tmp_path / "headerless.ncel"
    headerless.write_text('scene S { layer a(tone: 0) { "0,0 4,0 0,4" } }\n')
    monkeypatch.setattr(native, "available", lambda: (True, None))
    usable, reason = launcher._native_or_reason([str(new)], "render")
    assert not usable and "spec 0.4 features" in reason and "morph" in reason
    usable, reason = launcher._native_or_reason([str(header_only)], "check")
    assert not usable and "declares spec 0.4.0-draft" in reason
    assert launcher._native_or_reason([str(old)], "render") == (True, None)
    usable, reason = launcher._native_or_reason([str(headerless)], "render")
    assert not usable and "defaults to spec 0.6.0-draft" in reason


# ------------------------------------------------------------ assignment
def test_linear_assignment_is_optimal_and_deterministic():
    from northcel.correspond import linear_assignment

    rng = np.random.default_rng(7)
    for shape in [(1, 1), (3, 3), (4, 6), (6, 4), (5, 5)]:
        for _ in range(5):
            c = rng.integers(0, 20, size=shape).astype(float)
            rows, cols = linear_assignment(c)
            k = min(shape)
            assert len(rows) == k and len(set(cols.tolist())) == k
            best = min(sum(c[i, j] for i, j in zip(r, p))
                       for r in itertools.combinations(range(shape[0]), k)
                       for p in itertools.permutations(range(shape[1]), k))
            assert c[rows, cols].sum() == pytest.approx(best)
            r2, c2 = linear_assignment(c)
            assert np.array_equal(rows, r2) and np.array_equal(cols, c2)


# ----------------------------------------------------- stacked fit / tween
def _figure(dx=0, split=False, size=(96, 64)):
    img = Image.new("RGB", size, (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([4 + dx, 34, 40 + dx, 58], fill=(30, 60, 220))                 # blue box
    d.ellipse([46 + dx, 6, 86 + dx, 46], fill=(10, 10, 10))                    # ink disc ...
    d.ellipse([56 + dx, 16, 76 + dx, 36], fill=(255, 255, 255))                # ... with a see-through hole
    d.ellipse([62 + dx, 22, 70 + dx, 30], fill=(230, 40, 40))                  # red dot in the hole
    d.rectangle([6 + dx, 4, 34 + dx, 28], fill=(10, 10, 10))                   # ink frame ...
    d.rectangle([12 + dx, 10, 28 + dx, 22], fill=(30, 60, 220))                # ... filled with blue
    if split:
        d.rectangle([16 + dx, 40, 18 + dx, 52], fill=(10, 10, 10))             # a new mark: topology change
    return img


PALETTE = [(255, 255, 255), (10, 10, 10), (30, 60, 220), (230, 40, 40)]


def test_fit_stacked_on_a_synthetic_drawing():
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    from northcel.fitting import fit_image, fit_stacked
    from northcel.shapes import stacked_source

    image = _figure()
    drawing, receipt = fit_stacked(image, palette=PALETTE, underpaint_min_area=50, name="Fig")
    kinds = [s.kind for s in drawing.shapes]
    assert [s.z if s.z is not None else s.area for s in drawing.shapes] == sorted([s.z if s.z is not None else s.area for s in drawing.shapes], reverse=True)
    assert kinds.count("gap") == 1 and kinds.count("underpaint") == 1
    gap = next(s for s in drawing.shapes if s.kind == "gap")
    under = next(s for s in drawing.shapes if s.kind == "underpaint")
    assert gap.color == (255, 255, 255) and under.color == (30, 60, 220)
    assert receipt["mode"] == "stacked" and receipt["shapes"] == len(drawing.shapes)
    src = stacked_source(drawing)
    assert src.startswith('northcel "0.3.0-draft"') and errors(src) == []
    stacked = render_document_frame(parse_ncel(src)).astype(int)
    planar_src, _ = fit_image(image, palette=PALETTE)
    planar = render_document_frame(parse_ncel(planar_src)).astype(int)
    assert np.abs(stacked - planar).mean() < 1.0        # the same picture, painted differently
    assert np.abs(stacked - np.asarray(image, dtype=int)).mean() < 6.0
    # Default `fit` output is unchanged by the stacked mode's existence.
    assert "layer color_" in planar_src and "layer s0" not in planar_src


def test_fit_cli_stacked(tmp_path):
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    from northcel.fitting import main

    img = tmp_path / "fig.png"
    _figure().save(img)
    pal = tmp_path / "pal.json"
    pal.write_text(json.dumps(PALETTE))
    out = tmp_path / "fig.ncel"
    assert main([str(img), "-o", str(out), "--stacked", "--palette", str(pal), "--ink", "#0A0A0A"]) == 0
    assert errors(out.read_text()) == [] and "layer s" in out.read_text()


def _stacked(image, name):
    from northcel.fitting import fit_stacked
    from northcel.shapes import stacked_source

    drawing, _ = fit_stacked(image, palette=PALETTE, underpaint_min_area=50, name=name)
    return drawing, stacked_source(drawing)


def test_matching_tween_across_topology_mismatch(tmp_path):
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    from northcel.correspond import match_drawings
    from northcel.tween import main as tween_main, match_tween, tween_sources

    a, src_a = _stacked(_figure(), "A")
    b, src_b = _stacked(_figure(dx=3, split=True), "B")
    assert len(a.shapes) != len(b.shapes)
    with pytest.raises(ValueError, match="mismatch"):
        tween_sources(src_a, src_b, steps=4)                         # explicit mode still refuses
    m = match_drawings(a, b)
    assert len(m.pairs) == len(a.shapes) and len(m.only_b) == 1
    assert m.matched_fraction > 0.9 and 2.5 < m.displacement < 3.5

    film, receipt = match_tween(src_a, src_b, steps=6, fps=12)
    t = receipt["transitions"][0]
    assert t["mode"] == "morph" and receipt["quality"] == "unreviewed"
    assert "morph t0_" in film and "frame 1..5 {" in film and "opacity: step(0.5, u)" in film
    doc = parse_ncel(film)
    assert errors(film) == []
    assert format_document(parse_ncel(format_document(doc))) == format_document(doc)
    forward = [render_document_frame(doc, f).tobytes() for f in range(7)]
    assert forward == [render_document_frame(doc, f).tobytes() for f in reversed(range(7))][::-1]
    assert forward[0] == render_document_frame(parse_ncel(src_a)).tobytes()
    assert forward[6] == render_document_frame(parse_ncel(src_b)).tobytes()
    assert len(set(forward)) == 7

    # Below the thresholds the transition is an explicit cut (or dissolve), and says why.
    _, cut = match_tween(src_a, src_b, steps=6, fps=12, max_displacement=1.0)
    assert cut["transitions"][0]["mode"] == "cut" and "displacement" in cut["transitions"][0]["reason"]
    dis_src, dis = match_tween(src_a, src_b, steps=6, fps=12, min_match=0.999, fallback="dissolve")
    assert dis["transitions"][0]["mode"] == "dissolve" and "use K1(opacity: smoothstep(0, 6, f))" in dis_src
    assert errors(dis_src) == []
    held, _ = match_tween(src_a, src_b, steps=6, fps=12, mode="hold")
    hd = parse_ncel(held)
    assert render_document_frame(hd, 5).tobytes() == forward[0]

    # The CLI writes the film and the receipt.
    fa, fb, out, rc = (tmp_path / n for n in ("a.ncel", "b.ncel", "t.ncel", "r.json"))
    fa.write_text(src_a)
    fb.write_text(src_b)
    assert tween_main([str(fa), str(fb), "-o", str(out), "--match", "--steps", "4", "--receipt", str(rc)]) == 0
    assert json.loads(rc.read_text())["mode"] == "match" and errors(out.read_text()) == []


def test_colour_changes_must_be_allowed():
    from northcel.correspond import MatchOptions, match_drawings
    from northcel.shapes import Shape, StackedDrawing

    sq = np.array([(10, 10), (30, 10), (30, 30), (10, 30)], dtype=float)
    a = StackedDrawing(64, 64, (255, 255, 255), [Shape((255, 255, 255), sq, 400.0)])
    b = StackedDrawing(64, 64, (255, 255, 255), [Shape((238, 44, 44), sq + 2, 400.0)])
    assert match_drawings(a, b).pairs == []
    allowed = MatchOptions(colour_changes=[((238, 44, 44), (255, 255, 255))])
    assert match_drawings(a, b, allowed).pairs == [(0, 0)]


def test_film_from_keys_api_holds_morphs_and_cuts():
    from northcel.correspond import FilmOptions, Key, MatchOptions, Transition, film_from_keys
    from northcel.shapes import Shape, StackedDrawing

    def drawing(dx, colour=(30, 60, 220)):
        sq = np.array([(10, 10), (30, 10), (30, 30), (10, 30)], dtype=float) + [dx, 0]
        tri = np.array([(40, 40), (60, 40), (50, 56)], dtype=float) + [dx, 0]
        return StackedDrawing(64, 64, (250, 250, 250), [Shape(colour, sq, 400.0), Shape((10, 10, 10), tri, 160.0)])

    keys = [Key(drawing(0), 0.0), Key(drawing(2, (220, 40, 40)), 0.5), Key(drawing(4), 1.0), Key(drawing(6), 1.5)]
    opts = FilmOptions(fps=10, frames=20, transition_seconds=0.3,
                       match=MatchOptions(colour_changes=[((30, 60, 220), (220, 40, 40))]))
    src, receipt = film_from_keys(keys, ["auto", Transition("cut"), Transition("dissolve", 0.2)], opts)
    modes = [t["mode"] for t in receipt["transitions"]]
    assert modes == ["morph", "cut", "dissolve"]
    assert "mix($c1, $c3, u)" in src or "mix($c3, $c1, u)" in src
    doc = parse_ncel(src)
    assert errors(src) == [] and doc.root.frames == 20
    lo_hi = [(lo, hi) for lo, hi, _ in doc.root.frame_ranges] + [(f, f) for f in doc.root.frame_overrides]
    covered = sorted(f for lo, hi in lo_hi for f in range(lo, hi + 1))
    assert covered == list(range(20))                  # every frame has exactly one block
    frames = [render_document_frame(doc, f).tobytes() for f in range(20)]
    assert frames == [render_document_frame(doc, f).tobytes() for f in reversed(range(20))][::-1]
    with pytest.raises(ValueError, match="increasing frames"):
        film_from_keys([Key(drawing(0), 0.0), Key(drawing(1), 0.01)], options=opts)
    with pytest.raises(ValueError, match="unknown transition mode"):
        film_from_keys(keys[:2], ["slide"], opts)
