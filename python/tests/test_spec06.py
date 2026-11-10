"""Spec 0.6: ARAP warp, NCIR v2 and the Vello tolerance tier."""
from __future__ import annotations

import json
import struct

import numpy as np
import pytest

pytest.importorskip("numpy")
pytest.importorskip("PIL")

from northcel import parse_ncel, render_document_frame, validate_document  # noqa: E402
from northcel.formatter import format_document  # noqa: E402
from northcel.ncir import NCIR_MAGIC, NCIR_VERSION, build_frame, read_frame  # noqa: E402

ARAP = '''northcel "0.6.0-draft"
scene W(width: 160, height: 120, fps: 1, precision: 0.25px, seed: 3) {
  paper { color: #FFFFFF, antialias_grid: 2 }
  layer blob(color: #CC2222) { "40,40 400,0 0,480 -400,0" }
  warp blob(handles: ((60, 50, 24, 0), (60, 100, 0, 12)), radius: 90, mode: arap)
}
'''


def errors(doc):
    return [d for d in validate_document(doc) if d.level == "error"]


def test_arap_parses_formats_and_validates():
    doc = parse_ncel(ARAP)
    assert errors(doc) == []
    text = format_document(doc)
    assert "mode: arap" in text
    again = parse_ncel(text)
    assert errors(again) == []
    assert np.array_equal(render_document_frame(doc, 0), render_document_frame(again, 0))


def test_arap_is_deterministic_and_differs_from_smooth():
    doc = parse_ncel(ARAP)
    first = render_document_frame(doc, 0)
    second = render_document_frame(doc, 0)
    assert np.array_equal(first, second)
    smooth = parse_ncel(ARAP.replace("mode: arap", "mode: smooth"))
    assert not np.array_equal(first, render_document_frame(smooth, 0))


def test_arap_requires_spec_06():
    doc = parse_ncel(ARAP.replace('"0.6.0-draft"', '"0.5.0-draft"'))
    messages = [d.message for d in errors(doc)]
    assert messages and "requires northcel" in messages[0] and "0.6.0-draft" in messages[0]


def test_arap_rejects_an_unknown_mode():
    from northcel.parser import NorthCelSyntaxError

    with pytest.raises(NorthCelSyntaxError):
        parse_ncel(ARAP.replace("mode: arap", "mode: rubber"))


def test_ncir_v2_round_trip_carries_groups_clips_opacity():
    src = '''northcel "0.6.0-draft"
film T(width: 120, height: 80, fps: 10, frames: 3, precision: 0.25px, seed: 7) {
  palette { red: #FF0000, blue: #0000FF }
  paper { color: #FFFFFF, antialias_grid: 4, grain: 0.01 }
  group cloud(opacity: 0.5) {
    layer a(color: $red) { "40,40 400,0 0,400 -400,0" }
  }
  transform a(translate: (f * 5, 0))
  frame 1..2 {
    group clipped(clip: a) {
      layer b(color: $blue) { "0,0 2400,0 0,2400 -2400,0" }
    }
  }
}
'''
    doc = parse_ncel(src)
    data = build_frame(doc, 1)
    assert data[:4] == NCIR_MAGIC
    assert struct.unpack_from("<H", data, 4)[0] == NCIR_VERSION
    parsed = read_frame(data)
    assert (parsed["width"], parsed["height"], parsed["frame"]) == (120, 80, 1)
    assert parsed["paper"] == [255, 255, 255]
    assert parsed["grain"] == pytest.approx(0.01)
    a = next(p for p in parsed["paints"] if p["name"] == "a")
    b = next(p for p in parsed["paints"] if p["name"] == "b")
    assert a["groups"] == [(1, 0.5)]
    assert a["path"] == ["cloud"]
    assert a["color"] == [255, 0, 0]
    assert len(a["rings"][0]) == 4
    assert len(b["clips"]) == 1 and len(b["clips"][0]) == 4
    # The frame-resolved translation is in the geometry, not the IR metadata.
    assert a["rings"][0][0][0] == pytest.approx(15.0)  # 40 quarter-px = 10 px, plus f*5


def test_vello_tier_matches_the_reference_within_tolerance(tmp_path):
    northcel_vello = pytest.importorskip("northcel_vello")
    doc = parse_ncel(ARAP.replace("mode: arap", "mode: smooth"))
    data = build_frame(doc, 0)
    out = tmp_path / "frame.png"
    stats = json.loads(northcel_vello.render_frame(data, str(out)))
    assert out.is_file() and stats["width"] == 160 and stats["height"] == 120
    from PIL import Image

    got = np.asarray(Image.open(out).convert("RGB"), dtype=np.int16)
    want = np.asarray(render_document_frame(doc, 0), dtype=np.int16)
    mae = float(np.abs(got - want).mean())
    assert mae <= 1.0, mae
