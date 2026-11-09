"""Spec 0.5: addressable groups, group transforms, warp, clip, nudge and fit ids."""
from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

import numpy as np
import pytest
from PIL import Image

from northcel import parse_ncel, render_document_frame, validate_document
from northcel.ast_nodes import GroupNode, NudgeNode, WarpNode
from northcel.fitting import fit_stacked
from northcel.formatter import format_document
from northcel.parser import NorthCelSyntaxError
from northcel.renderer import NorthCelEvaluationError, frame_paint_list
from northcel.validator import spec05_features


def errors(doc):
    return [d for d in validate_document(doc) if d.level == "error"]


def red_bbox(rgb):
    mask = (rgb[:, :, 0] > 180) & (rgb[:, :, 1] < 90) & (rgb[:, :, 2] < 90)
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return None, 0
    return (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())), int(mask.sum())


class TestSpec05Parse(unittest.TestCase):
    def test_group_transform_clip_warp_nudge_parse_and_validate(self):
        doc = parse_ncel('''northcel "0.5.0-draft"
scene S(width: 100, height: 100) {
  paper { color: #FFFFFF }
  layer mask(color: #000000, opacity: 0) { "40,40 320,0 0,320 -320,0" }
  group box(pivot: (50, 50), clip: mask) {
    layer a(color: #FF0000) { "80,80 160,0 0,160 -160,0" }
    group inner { layer b(color: #00FF00) { "120,120 40,0 0,40 -40,0" } }
  }
  transform box(rotate: 15)
  warp box(handles: ((50, 50, 5, 0), (20, 20, -5, 0)), radius: 80)
  nudge a(vertex: 0, dx: 2px, dy: 1px)
}
''')
        self.assertEqual(errors(doc), [])
        self.assertTrue(any(isinstance(i, GroupNode) for i in doc.root.items))
        self.assertTrue(any(isinstance(i, WarpNode) for i in doc.root.items))
        self.assertTrue(any(isinstance(i, NudgeNode) for i in doc.root.items))
        self.assertEqual(len(spec05_features(doc)), 4)  # outer group, inner group, warp, nudge

    def test_group_is_a_spec05_error_in_04(self):
        doc = parse_ncel('''northcel "0.4.0-draft"
scene S(width: 100, height: 100) {
  group g { layer a(color: #FF0000) { "40,40 80,0 0,80 -80,0" } }
}
''')
        msgs = [d.message for d in errors(doc)]
        self.assertTrue(any("requires northcel" in m and "group" in m for m in msgs), msgs)

    def test_formatter_roundtrip_preserves_group_semantics(self):
        source = '''northcel "0.5.0-draft"
scene S(width: 100, height: 100) {
  paper { color: #FFFFFF }
  group g(pivot: (50, 50)) {
    layer a(color: #FF0000) { "40,40 80,0 0,80 -80,0" }
  }
  transform g(rotate: 20)
}
'''
        doc = parse_ncel(source)
        formatted = format_document(doc)
        doc2 = parse_ncel(formatted)
        self.assertEqual(errors(doc2), [])
        self.assertEqual(render_document_frame(doc, 0).tolist(), render_document_frame(doc2, 0).tolist())


class TestSpec05Render(unittest.TestCase):
    def test_group_rotation_about_pivot(self):
        doc = parse_ncel('''northcel "0.5.0-draft"
scene S(width: 100, height: 100) {
  paper { color: #FFFFFF }
  group g(pivot: (50, 50)) {
    layer a(color: #FF0000) { "80,80 160,0 0,160 -160,0" }
  }
  transform g(rotate: 45)
}
''')
        rgb = render_document_frame(doc, 0)
        self.assertEqual(tuple(rgb[50, 50]), (255, 0, 0))
        # a corner of the unrotated square (20,20) moves outside the diamond
        self.assertEqual(tuple(rgb[20, 20]), (255, 255, 255))

    def test_group_clip_limits_paint(self):
        doc = parse_ncel('''northcel "0.5.0-draft"
scene S(width: 100, height: 100) {
  paper { color: #FFFFFF }
  layer mask(color: #000000, opacity: 0) { "0,0 120,0 0,120 -120,0" }
  group g(clip: mask) {
    layer a(color: #FF0000) { "40,40 280,0 0,280 -280,0" }
  }
}
''')
        rgb = render_document_frame(doc, 0)
        self.assertEqual(tuple(rgb[15, 15]), (255, 0, 0))
        self.assertEqual(tuple(rgb[45, 45]), (255, 255, 255))

    def test_warp_moves_points_and_nudge_extends_bbox(self):
        base = parse_ncel('''northcel "0.5.0-draft"
scene S(width: 100, height: 100) {
  paper { color: #FFFFFF }
  group g { layer a(color: #FF0000) { "40,40 160,0 0,160 -160,0" } }
}
''')
        warped = parse_ncel('''northcel "0.5.0-draft"
scene S(width: 100, height: 100) {
  paper { color: #FFFFFF }
  group g { layer a(color: #FF0000) { "40,40 160,0 0,160 -160,0" } }
  warp g(handles: ((50, 50, 12, 0),), radius: 100)
  nudge a(vertex: 0, dx: 4px, dy: 0)
}
''')
        b0, _ = red_bbox(render_document_frame(base, 0))
        b1, _ = red_bbox(render_document_frame(warped, 0))
        self.assertIsNotNone(b0)
        self.assertIsNotNone(b1)
        self.assertGreater(b1[2], b0[2] + 4)  # right edge moved by the handle
        self.assertGreaterEqual(b1[2] - b1[0], b0[2] - b0[0])

    def test_group_opacity_blends_once(self):
        doc = parse_ncel('''northcel "0.5.0-draft"
scene S(width: 100, height: 100) {
  paper { color: #FFFFFF }
  group g(opacity: 0.5) {
    layer a(color: #FF0000) { "40,40 80,0 0,80 -80,0" }
    layer b(color: #0000FF) { "40,40 80,0 0,80 -80,0" }
  }
}
''')
        rgb = render_document_frame(doc, 0)
        # the blue top layer covers the red inside the group; then the whole
        # group is blended once towards white, not twice.
        self.assertEqual(tuple(rgb[15, 15]), (128, 128, 255))

    def test_parent_group_follows_parent_transform(self):
        doc = parse_ncel('''northcel "0.5.0-draft"
scene S(width: 100, height: 100) {
  paper { color: #FFFFFF }
  group arm(pivot: (50, 50)) {
    layer p(color: #FF0000) { "180,180 40,0 0,40 -40,0" }
  }
  group hand(parent: arm, pivot: (50, 50)) {
    layer c(color: #0000FF) { "280,180 40,0 0,40 -40,0" }
  }
  transform arm(rotate: 90)
}
''')
        rgb = render_document_frame(doc, 0)
        self.assertEqual(tuple(rgb[75, 50]), (0, 0, 255))
        self.assertEqual(tuple(rgb[50, 75]), (255, 255, 255))

    def test_frame_delta_nudge_only_changes_named_shape(self):
        doc = parse_ncel('''northcel "0.5.0-draft"
film F(width: 100, height: 100, fps: 10, frames: 3) {
  paper { color: #FFFFFF }
  def Key {
    layer a(color: #FF0000) { "40,40 80,0 -40,40" }
    layer b(color: #0000FF) { "200,40 80,0 -40,40" }
  }
  frame 0..1 { use Key }
  frame 2 { use Key; nudge a(vertex: 0, dx: 8px, dy: 0) }
}
''')
        self.assertEqual(errors(doc), [])
        r0 = render_document_frame(doc, 0)
        r2 = render_document_frame(doc, 2)
        b0, _ = red_bbox(r0)
        b2, _ = red_bbox(r2)
        self.assertNotEqual(b0, b2)
        # the blue shape is unchanged
        blue0 = (r0[:, :, 2] > 180) & (r0[:, :, 0] < 90)
        blue2 = (r2[:, :, 2] > 180) & (r2[:, :, 0] < 90)
        self.assertTrue(np.array_equal(blue0, blue2))


class TestFitIdsAndQueries(unittest.TestCase):
    def test_fit_assigns_stable_ids_and_manifest_geometry(self):
        im = Image.new("RGB", (120, 100), "white")
        from PIL import ImageDraw
        ImageDraw.Draw(im).rectangle([20, 20, 90, 80], fill=(200, 40, 40), outline=(0, 0, 0), width=3)
        a, ra = fit_stacked(im, colors=4)
        b, rb = fit_stacked(im, colors=4)
        self.assertTrue(a.shapes and all(s.id for s in a.shapes))
        self.assertEqual([s.id for s in a.shapes], [s.id for s in b.shapes])
        manifest = ra["shape_manifest"]
        self.assertTrue(manifest)
        for row in manifest:
            self.assertTrue(row["id"])
            self.assertEqual(len(row["bbox"]), 4)
            self.assertEqual(len(row["centroid"]), 2)
            self.assertIn("parent", row)
            self.assertIn("children", row)
            self.assertIn("neighbours", row)

    def test_shapes_cli_query(self):
        from northcel.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.ncel"
            path.write_text('''northcel "0.5.0-draft"
scene S(width: 100, height: 100) {
  paper { color: #FFFFFF }
  layer a(color: #FF0000) { "40,40 80,0 0,80 -80,0" }
  layer b(color: #0000FF) { "200,40 80,0 0,80 -80,0" }
}
''')
            import contextlib
            import io
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                code = main(["shapes", str(path), "--color", "#FF0000"])
            self.assertEqual(code, 0)
            data = json.loads(out.getvalue())
            self.assertEqual(data["count"], 1)
            self.assertEqual(data["shapes"][0]["id"], "a")


@pytest.mark.parametrize("scope", ["scene", "film", "exact-frame", "frame-range"])
@pytest.mark.parametrize("statement,feature", [
    ('group inner { layer a(tone: 0) { "0,0 4,0 0,4" } }', "group"),
    ('warp a(handles: ((0, 0, 1, 0),))', "warp"),
    ('nudge a(vertex: 0, dx: 1)', "nudge"),
])
def test_spec05_detection_in_all_def_scopes(scope, statement, feature):
    body = f"def D {{\n    {statement}\n  }}"
    root = "scene" if scope == "scene" else "film"
    if scope in ("exact-frame", "frame-range"):
        body = f"frame {'0' if scope == 'exact-frame' else '0..1'} {{ {body} }}"
    source = f'northcel "0.4.0-draft"\n{root} S(frames: 2) {{\n  {body}\n}}'
    doc = parse_ncel(source)
    located = [d for d in errors(doc) if d.message.startswith(f"{feature} requires northcel")]
    assert len(located) == 1
    assert (located[0].line, located[0].column) == (4, 5)
    assert '"0.5.0-draft"' in located[0].message


def test_spec05_detection_recurses_into_nested_def_groups():
    doc = parse_ncel('''northcel "0.4.0-draft"
scene S { def D { group outer { group inner {
  warp a(handles: ((0, 0, 1, 0),))
  nudge a(vertex: 0)
} } } }''')
    assert [name for name, _, _ in spec05_features(doc)] == ["group", "group", "warp", "nudge"]
    assert len(errors(doc)) == 4


@pytest.mark.parametrize("attribute,value", [("vertex", "1.9"), ("ring", "0.7"),
                                            ("vertex", "3 / 2"), ("ring", "(0, 1)")])
def test_fractional_or_nonnumeric_nudge_index_is_located(attribute, value):
    attrs = f"vertex: {value}" if attribute == "vertex" else f"vertex: 0, ring: {value}"
    with pytest.raises(NorthCelSyntaxError, match=f"nudge {attribute} must be an integer") as exc:
        parse_ncel(f"scene S {{\n  nudge a({attrs})\n}}")
    assert (exc.value.line, exc.value.column) == (2, 3)


@pytest.mark.parametrize("attrs", ["vertex: -1", "vertex: 0, ring: -1"])
def test_negative_nudge_index_is_located(attrs):
    diagnostics = errors(parse_ncel(f"scene S {{\n  nudge a({attrs})\n}}"))
    assert len(diagnostics) == 1
    assert (diagnostics[0].line, diagnostics[0].column) == (2, 3)
    assert "ring/vertex must be >= 0" in diagnostics[0].message


@pytest.mark.parametrize("body,feature", [
    ('layer a(tone: 0) { "0,0 4,0 0,4" }', "defaults to spec 0.5.0-draft"),
    ('def D { group g {} }', "group"),
    ('def D { warp a(handles: ((0, 0, 1, 0),)) }', "warp"),
    ('def D { nudge a(vertex: 0) }', "nudge"),
])
@pytest.mark.parametrize("command", ["check", "info", "render", "film"])
def test_headerless_spec05_routes_to_reference(tmp_path, monkeypatch, body, feature, command):
    from northcel.launcher import cli as launcher, native

    path = tmp_path / "headerless.ncel"
    path.write_text(f"scene S {{ {body} }}")
    monkeypatch.setattr(native, "available", lambda: (True, None))
    usable, reason = launcher._native_or_reason([str(path)], command)
    assert not usable
    assert feature in reason
    assert "implements spec 0.3 only" in reason


@pytest.mark.parametrize("header", ['', 'northcel "0.5.0-draft"\n'])
def test_launcher_keeps_fractional_nudge_reference_diagnostic(tmp_path, monkeypatch, capsys, header):
    from northcel.launcher import cli as launcher, native

    path = tmp_path / "fractional.ncel"
    path.write_text(header + "scene S {\n  nudge a(vertex: 1.9)\n}")
    monkeypatch.setattr(native, "available", lambda: (True, None))

    def no_native(*_args, **_kwargs):
        pytest.fail("newer malformed document was sent to native")

    monkeypatch.setattr(native, "run", no_native)
    assert launcher.main(["check", str(path), "--json"]) == 1
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["validator"] == "python"
    assert receipt["errors"] == [f"{3 if header else 2}:3: error: nudge vertex must be an integer"]


@pytest.mark.parametrize("in_def", [False, True])
@pytest.mark.parametrize("anchor", ["", ", anchor: (25, 25)"])
def test_parent_pivot_is_independent_of_sibling_declaration_order(in_def, anchor):
    parent = 'group arm(pivot: (50, 50)) { layer p(tone: 0) { "180,180 40,0 0,40 -40,0" } }'
    child = 'group hand(parent: arm) { layer c(color: #0000FF) { "280,180 40,0 0,40 -40,0" } }'

    def document(parts):
        body = "\n".join(parts) + f"\ntransform arm(rotate: 90{anchor})"
        if in_def:
            body = f"def D {{ {body} }} use D"
        return parse_ncel(f"scene S(width: 100, height: 100) {{ paper {{ color: #FFFFFF }} {body} }}")

    first, last = document([parent, child]), document([child, parent])
    def paints(doc):
        return {p.name: p.rings for p in frame_paint_list(doc)[2]}
    assert paints(first) == paints(last)
    assert np.array_equal(render_document_frame(first), render_document_frame(last))
    if not anchor:
        assert tuple(render_document_frame(last)[75, 50]) == (0, 0, 255)


@pytest.mark.parametrize("command", ["shapes", "render"])
@pytest.mark.parametrize("as_json", [False, True])
@pytest.mark.parametrize("bad", ["clip", "nudge"])
def test_evaluation_errors_are_located_without_tracebacks(tmp_path, capsys, command, as_json, bad):
    from northcel.cli import main

    path = tmp_path / "bad.ncel"
    body = ('group g(clip: missing) { layer a(tone: 0) { "0,0 4,0 0,4" } }' if bad == "clip"
            else 'layer a(tone: 0) { "0,0 4,0 0,4" }\n  nudge a(vertex: 99)')
    path.write_text(f"scene S {{\n  {body}\n}}")
    args = [command, str(path)] + (["--json"] if as_json else [])
    assert main(args) == 1
    captured = capsys.readouterr()
    message = ("2:3: error: Clip target 'missing' has not been painted" if bad == "clip"
               else "3:3: error: Nudge vertex 99 is out of range for 'a'")
    if as_json:
        assert json.loads(captured.out)["errors"] == [message]
    else:
        assert f"{path}:{message}" in captured.err
    assert "Traceback" not in captured.err + captured.out


def test_nested_clip_error_keeps_declaring_group_location():
    doc = parse_ncel('''scene S {
  group outer(clip: missing) {
    group inner { layer a(tone: 0) { "0,0 4,0 0,4" } }
  }
}''')
    with pytest.raises(NorthCelEvaluationError) as exc:
        frame_paint_list(doc)
    assert (exc.value.line, exc.value.column) == (2, 3)


@pytest.mark.parametrize("handles", ["((4, 4, 1, 0),)", "((4, 4, 1, 0), (8, 8, 0, 1))"])
def test_warp_formatter_preserves_handle_tuple_and_pixels(handles):
    doc = parse_ncel(f'''scene S(width: 16, height: 16) {{
  group g {{ layer a(tone: 0) {{ "0,0 32,0 0,32 -32,0" }} }}
  warp g(handles: {handles}, radius: 20)
}}''')
    text = format_document(doc)
    roundtrip = parse_ncel(text)
    assert text == format_document(roundtrip)
    assert len(roundtrip.root.items[1].handles) == len(doc.root.items[1].handles)
    assert np.array_equal(render_document_frame(doc), render_document_frame(roundtrip))


def test_fit_manifest_and_shapes_query_share_emitted_geometry(tmp_path, capsys):
    from northcel.cli import main
    from northcel.shapes import Shape, StackedDrawing, shape_manifest, stacked_source

    # Non-bbox-centred triangle, fractional coordinates and a synthetic ordering
    # area: receipts must describe emitted geometry, not fitting bookkeeping.
    drawing = StackedDrawing(100, 100, (255, 255, 255), [
        Shape((0, 0, 0), np.array([[0.1, 0.1], [90.1, 0.1], [0.1, 90.1]]), 5000, id="outer"),
        Shape((255, 0, 0), np.array([[8.1, 8.1], [20.1, 8.1], [8.1, 20.1]]), 4999.5, "gap", id="inner"),
    ])
    path = tmp_path / "fitted.ncel"
    path.write_text(stacked_source(drawing))
    assert main(["shapes", str(path)]) == 0
    actual = json.loads(capsys.readouterr().out)["shapes"]
    expected = shape_manifest(drawing)
    for a, e in zip(actual, expected):
        for key in ("id", "area", "bbox", "centroid", "parent", "children", "neighbours"):
            assert a[key] == e[key], key
    assert actual[0]["centroid"] == [30, 30]
    assert actual[1]["parent"] == "outer"


if __name__ == "__main__":
    unittest.main()
