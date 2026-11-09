"""Spec 0.5: addressable groups, group transforms, warp, clip, nudge and fit ids."""
from __future__ import annotations

from pathlib import Path
import json
import tempfile
import unittest

import numpy as np
from PIL import Image

from northcel import parse_ncel, render_document_frame, validate_document
from northcel.ast_nodes import GroupNode, NudgeNode, WarpNode
from northcel.fitting import fit_stacked
from northcel.formatter import format_document
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


if __name__ == "__main__":
    unittest.main()
