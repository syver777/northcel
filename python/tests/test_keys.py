"""Measured figure masks and outline backing for keys (`northcel.keys`)."""
from __future__ import annotations

import json

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("PIL")
pytest.importorskip("cv2")


def _drawing(size=(320, 240)):
    from PIL import Image, ImageDraw

    im = Image.new("RGB", size, (3, 185, 253))  # sky
    d = ImageDraw.Draw(im)
    # A white cloud whose ink outline touches the figure's feet.
    d.ellipse([40, 170, 280, 250], fill=(254, 254, 254), outline=(17, 20, 22), width=3)
    for x in (80, 140, 200, 250):
        d.ellipse([x - 35, 150, x + 35, 200], fill=(254, 254, 254), outline=(17, 20, 22), width=3)
    # The figure: red shirt, blue trousers, skin head.
    d.rectangle([145, 80, 185, 140], fill=(238, 44, 44), outline=(17, 20, 22), width=3)
    d.rectangle([150, 140, 160, 190], fill=(18, 121, 208), outline=(17, 20, 22), width=3)
    d.rectangle([170, 140, 180, 190], fill=(18, 121, 208), outline=(17, 20, 22), width=3)
    d.ellipse([140, 40, 190, 85], fill=(252, 200, 158), outline=(17, 20, 22), width=3)
    return im


def test_measure_figure_excludes_a_cloud_the_ink_touches():
    from northcel.keys import figure_box, measure_figure

    mask = measure_figure(_drawing())
    box = figure_box(mask)
    # Figure only: head to feet, not the 40..280 cloud.
    assert 130 < box[0] < 145 and 175 < box[2] < 195
    assert 30 < box[1] < 45 and 185 < box[3] < 210
    # The cloud interior stays outside the mask.
    assert not mask[220, 60]


def test_measure_figure_keeps_a_black_and_white_drawing():
    from PIL import Image, ImageDraw

    from northcel.keys import figure_box, measure_figure

    im = Image.new("RGB", (200, 200), "white")
    d = ImageDraw.Draw(im)
    d.ellipse([50, 40, 150, 140], outline=(0, 0, 0), width=4)
    d.line([100, 140, 100, 170], fill=(0, 0, 0), width=4)
    mask = measure_figure(im)
    box = figure_box(mask)
    assert 40 < box[0] < 55 and 145 < box[2] < 160


def test_prepare_key_masks_the_figure_and_adds_a_backing():
    from northcel.keys import prepare_key

    drawing, receipt = prepare_key(_drawing(), palette=None, colors=8, backing=4)
    assert drawing.shapes[0].kind == "backing"
    # No shape is the sky colour: the extra must not carry its own background.
    assert all(tuple(s.color) != (3, 185, 253) for s in drawing.shapes)
    box = receipt["figure_mask"]["material_box"]
    assert box[2] - box[0] < 80 and receipt["masked"] is True


def test_fit_figure_cli_writes_a_backed_scene(tmp_path):
    from northcel.fitting import main as fit_main

    image = _drawing()
    src = tmp_path / "key.png"
    image.save(src)
    out = tmp_path / "key.ncel"
    receipt = tmp_path / "key.json"
    assert fit_main([str(src), "-o", str(out), "--stacked", "--figure",
                     "--colors", "8", "--receipt", str(receipt)]) == 0
    text = out.read_text()
    assert text.startswith("northcel")
    data = json.loads(receipt.read_text())
    assert data["figure_mask"]["backing_px"] == 4
    assert data["shape_manifest"][0]["kind"] == "backing" or any(
        row.get("kind") == "backing" for row in data["shape_manifest"])
