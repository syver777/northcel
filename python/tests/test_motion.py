import os
import subprocess
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from northcel import parse_ncel, format_document, render_document_frame
from northcel.parser import NorthCelSyntaxError
from northcel.tween import align_ring, resample, tween_sources

FIXTURE = Path(__file__).parents[1]/"northcel/conformance/04_transforms_easing.ncel"


def test_motion_roundtrip_and_determinism():
    doc = parse_ncel(FIXTURE.read_text())
    formatted = format_document(doc)
    other = parse_ncel(formatted)
    for f in [4, 0, 2, 1, 3, 0]:
        assert np.array_equal(render_document_frame(doc, f), render_document_frame(other, f))
    assert not np.array_equal(render_document_frame(doc, 0), render_document_frame(doc, 4))


def test_grouped_attribute_expressions_roundtrip(tmp_path):
    source = 'northcel "0.3.0-draft" film X(width: 32,height: 24,frames: 3) { layer a(tone: 0) { "8,8 32,0 0,32 -32,0" } transform a(scale: (1 + t) * 2, translate: ((1 + t) * 3, 0)) }'
    doc = parse_ncel(source)
    other = parse_ncel(format_document(doc))
    for f in [0, 2, 1]:
        assert np.array_equal(render_document_frame(doc, f), render_document_frame(other, f))
        if os.environ.get("NCEL_NATIVE_BIN"):
            path = tmp_path/"grouped.ncel"
            path.write_text(format_document(doc))
            out = tmp_path/"grouped.png"
            subprocess.run([os.environ["NCEL_NATIVE_BIN"], "render", str(path), "--frame", str(f), "-o", str(out)], check=True, capture_output=True)
            assert np.array_equal(np.asarray(Image.open(out)), render_document_frame(doc, f))


@pytest.mark.parametrize("expr,want", [("ease(-1)", 0), ("ease(0.5)", 0.5), ("ease(2)", 1),
    ("smoothstep(2, 2, 1)", 0), ("smoothstep(2, 2, 2)", 1), ("smoothstep(1, 0, 0.5)", 0.5)])
def test_easing(expr, want):
    from northcel.parser import _Parser, tokenize
    assert _Parser(tokenize(expr)).parse_expr().eval({}) == want


@pytest.mark.parametrize("text,msg", [("transform all(anchor: 1)", "requires 2 components"),
    ("transform all(scale: (1,2,3))", "requires 2 components"),
    ("transform all(opacity: 1)", "Unknown transform attribute"),
    ("transform all(rotate: ease(1,2))", "ease expects 1 arguments"),
    ("transform all(rotate: smoothstep(0))", "smoothstep expects 3 arguments")])
def test_transform_diagnostics(text, msg):
    with pytest.raises(NorthCelSyntaxError, match=msg):
        parse_ncel("scene Bad { "+text+" }")


def test_missing_target_location():
    with pytest.raises(ValueError, match="2:3: Transform target 'absent' has not been painted"):
        render_document_frame(parse_ncel("scene X {\n  transform absent(scale: 2)\n}"))


def test_missing_target_cli_has_located_json_not_traceback(tmp_path, capsys):
    import json
    from northcel.launcher.cli import main
    path = tmp_path/"missing.ncel"
    path.write_text('scene X {\n  transform absent(scale: 2)\n}')
    assert main(["render", str(path), "--no-native", "--json"]) == 1
    captured = capsys.readouterr()
    assert json.loads(captured.out)["errors"] == ["2:3: error: Transform target 'absent' has not been painted"]
    assert "Traceback" not in captured.err


def test_named_transform_leaves_unrelated_layer_unchanged():
    prefix = 'scene X(width: 64, height: 32) { paper { tone: 255 } layer a(tone: 0) { "16,16 32,0 0,32 -32,0" } layer b(tone: 80) { "160,16 32,0 0,32 -32,0" } '
    before = render_document_frame(parse_ncel(prefix+"}"))
    after = render_document_frame(parse_ncel(prefix+"transform a(scale: 2, anchor: (8, 8)) }"))
    assert np.array_equal(before[:, 32:], after[:, 32:])
    assert not np.array_equal(before, after)


def test_arclength_and_winding():
    ring = [(0, 0), (4, 0), (4, 4), (0, 4)]
    a, b = align_ring(ring, list(reversed(ring)), 16)
    assert np.array_equal(a, b)
    assert len(resample([(1, 1)]*3, 8)) == 8


def test_tween_mismatch_is_explicit():
    a = 'scene X(width: 24, height: 24) { layer a(tone: 0) { "16,16 32,0 0,32 -32,0" } }'
    b = a.replace('layer a', 'layer b')
    with pytest.raises(ValueError, match="correspondence mismatch"):
        tween_sources(a, b)
    film, receipt = tween_sources(a, b, fallback="hold")
    assert receipt["mode"] == "hold"
    assert len(parse_ncel(film).root.frame_overrides) == 5
    film, receipt = tween_sources(a, a)
    assert receipt["mode"] == "contour"
    assert np.array_equal(render_document_frame(parse_ncel(film), 1), render_document_frame(parse_ncel(film), 3))


def test_tween_palette_paper_is_semantic_and_emits_self_contained_source():
    a = 'scene X(width: 24,height: 24) { palette { bg: #FEFEFE, ink: #123456 } paper { color: $bg } layer a(color: $ink) { "16,16 32,0 0,32 -32,0" } }'
    b = '\n\nscene Y(width: 24,height: 24) { palette { paper_name: #FEFEFE, other: #123456 }\n paper { color: $paper_name } layer a(color: $other) { "16,16 32,0 0,32 -32,0" } }'
    film, receipt = tween_sources(a, b)
    assert receipt["mode"] == "contour"
    doc = parse_ncel(film)
    assert "$" not in film
    assert np.array_equal(render_document_frame(doc, 0), render_document_frame(parse_ncel(a)))
    assert np.array_equal(render_document_frame(doc, 4), render_document_frame(parse_ncel(b)))
    changed = b.replace('#FEFEFE', '#EEEEEE')
    held, receipt = tween_sources(a, changed, fallback="hold")
    canonical = parse_ncel(format_document(parse_ncel(held)))
    assert receipt["mode"] == "hold"
    assert np.array_equal(render_document_frame(canonical, 4), render_document_frame(parse_ncel(changed)))


def test_formatter_retains_lexical_palette_frame_paper_and_float_precision():
    source = '''northcel "0.3.0-draft"
film X(width: 32,height: 24,frames: 2) {
  palette { ink: #FF0000 }
  paper { color: #FFFFFF }
  layer box(color: $ink) { "8,8 32,0 0,32 -32,0" }
  palette { ink: #0000FF }
  transform box(scale: 1.1234567891234567)
  frame 0 { paper { color: #FEFEFE } }
  frame 1 { palette { ink: #00FF00 } layer box(color: $ink) { "8,8 32,0 0,32 -32,0" } }
}'''
    doc = parse_ncel(source)
    formatted = format_document(doc)
    assert '1.1234567891234566' in formatted or '1.1234567891234567' in formatted
    other = parse_ncel(formatted)
    assert formatted == format_document(other)
    for f in [0, 1]:
        assert np.array_equal(render_document_frame(doc, f), render_document_frame(other, f))
    fixture = Path(__file__).parents[2]/"native/tests/fixtures/grammar/grammar_all.ncel"
    original = parse_ncel(fixture.read_text())
    canonical = parse_ncel(format_document(original))
    for f in [0, 2, 1]:
        assert np.array_equal(render_document_frame(original, f), render_document_frame(canonical, f))


def test_tween_rejects_films_and_unbaked_motion_cleanly():
    a = 'scene X { layer a(tone: 0) { "0,0 32,0 0,32" } }'
    with pytest.raises(ValueError, match="not films"):
        tween_sources(a, a.replace('scene X', 'film X'))
    with pytest.raises(ValueError, match="Bake input"):
        tween_sources(a, a.replace('tone: 0', 'tone: 0, translate: (t, 0)'))


def test_fitter_roundtrip_optional():
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    from northcel.fitting import fit_image
    image = Image.new("RGB", (32, 24), "white")
    for y in range(5, 18):
        for x in range(8, 24):
            image.putpixel((x, y), (20, 80, 160))
    source, receipt = fit_image(image, 4, tolerance=0, min_area=0)
    assert receipt["raster_embedded"] is False
    assert "data:" not in source
    out = render_document_frame(parse_ncel(source))
    assert np.abs(np.asarray(image).astype(float)-out).mean() < 1


def test_fitter_cell_corners_and_supplied_matte():
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    from northcel.fitting import fit_image
    a = np.full((12, 16, 3), 255, dtype=np.uint8)
    for y in range(2, 10):
        for x in range(3, 13):
            if (x+y) % 2:
                a[y, x] = [20, 80, 160]
    source, _ = fit_image(Image.fromarray(a), 2, 0.05, 0, cell_edges=True)
    assert np.array_equal(render_document_frame(parse_ncel(source)), a)
    mask = np.zeros(a.shape[:2], bool)
    mask[3:9, 4:12] = True
    source, receipt = fit_image(Image.fromarray(a), 2, 0.05, 0, cell_edges=True, mask=mask)
    rendered = render_document_frame(parse_ncel(source))
    assert np.array_equal(rendered[mask], a[mask])
    assert (rendered[~mask] == 255).all()
    assert receipt["masked"]


def test_fitter_preserves_all_256_greys_and_declared_paper():
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    from northcel.fitting import fit_image
    a = np.repeat(np.arange(256, dtype=np.uint8)[None, :, None], 12, axis=0)
    a = np.repeat(a, 3, axis=2)
    source, receipt = fit_image(Image.fromarray(a), 256, 0.05, 0, cell_edges=True)
    doc = parse_ncel(source)
    assert receipt["underpaint_rgb"] == list(doc.root.paper.color.as_rgb_tuple())
    assert np.array_equal(render_document_frame(doc), a)


@pytest.mark.parametrize("aa", [1, 2, 4, 8])
def test_native_spatial_cells_against_reference(tmp_path, aa):
    binary = os.environ.get("NCEL_NATIVE_BIN")
    if not binary:
        pytest.skip("native bundle not requested")
    import random
    from northcel.rings import encode_ring_q25
    rng = random.Random(742)
    layers = []
    # Deliberate out-of-canvas coordinates, vertical cell-boundary edges,
    # self-intersections, holes and very long spans across 32px cells.
    for j in range(12):
        points = [(rng.randrange(-30, 150), rng.randrange(-20, 100)) for _ in range(9)]
        layers.append(f'layer p{j}(color: #{rng.randrange(1<<24):06X}) {{ "{encode_ring_q25(points)}" }}')
    layers.append('layer bounds(tone: 31) { "128,-32 0,320 128,0 0,-320" }')
    source = f'northcel "0.3.0-draft"\nscene X(width: 96, height: 80) {{ paper {{ tone: 240, antialias_grid: {aa} }} '+"\n".join(layers)+" }"
    path = tmp_path/"cells.ncel"
    path.write_text(source)
    out = tmp_path/"cells.png"
    subprocess.run([binary, "render", str(path), "-o", str(out)], check=True, capture_output=True)
    want = render_document_frame(parse_ncel(source)).astype(float)
    got = np.asarray(Image.open(out)).astype(float)
    assert np.abs(want-got).mean() <= 0.05


def test_native_motion_if_requested(tmp_path):
    binary = os.environ.get("NCEL_NATIVE_BIN")
    if not binary:
        pytest.skip("native bundle not requested")
    doc = parse_ncel(FIXTURE.read_text())
    for f in [4, 0, 2, 3, 1, 0]:
        target = tmp_path/f"f{f}.png"
        subprocess.run([binary, "render", str(FIXTURE), "--frame", str(f), "-o", str(target)], check=True, capture_output=True)
        got = np.asarray(Image.open(target)).astype(float)
        want = render_document_frame(doc, f).astype(float)
        assert np.abs(got-want).mean() <= 0.05
