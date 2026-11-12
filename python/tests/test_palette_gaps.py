"""Palette-gap reporting: regions a shared palette has no colour for."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("PIL")

FILM = Path.home() / "its-fix" / "final"
F0062 = FILM / "sources" / "cels" / "f0062.jpg"
FILM_PALETTE = FILM / "process" / "polish" / "palette.json"
PINK = [250, 140, 130]


def _real_drawing():
    from PIL import Image

    if not F0062.is_file() or not FILM_PALETTE.is_file():
        pytest.skip("film repository not checked out at ~/its-fix/final")
    return Image.open(F0062), json.loads(FILM_PALETTE.read_text())


def _gap_drawing():
    """White page, black border, and a pink rectangle absent from the palette."""
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (160, 120), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([12, 12, 147, 107], outline=(10, 10, 10), width=2)
    draw.rectangle([40, 35, 110, 85], fill=(250, 140, 130))
    return image


def _antialiased_outline():
    """A palette rectangle with a blended black outline, drawn at 4x then reduced."""
    from PIL import Image, ImageDraw

    scale = 4
    image = Image.new("RGB", (200 * scale, 150 * scale), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    draw.rectangle([40 * scale, 30 * scale, 160 * scale, 120 * scale],
                   fill=(220, 40, 40), outline=(10, 10, 10), width=3 * scale)
    return image.resize((200, 150), Image.Resampling.LANCZOS)


def test_palette_gaps_finds_the_pink_mouth_in_f0062():
    from northcel.fitting import palette_gaps

    image, palette = _real_drawing()
    gaps = palette_gaps(image, palette)
    assert gaps["threshold"] == 60 and gaps["min_area_px2"] == 150
    assert gaps["count"] >= 1
    region = min(gaps["regions"], key=lambda row: math.dist(row["rgb"], PINK))
    assert math.dist(region["rgb"], PINK) <= 25
    x0, y0, x1, y1 = region["bbox"]
    # The open mouth sits in the lower half of the face; allow the stated range
    # rather than one exact quantiser/version bbox.
    assert x1 > 690 and x0 < 750 and y1 > 520 and y0 < 570
    assert region["nearest"] in palette
    assert region["distance"] > 60
    assert any(math.dist(suggested, PINK) <= 25 for suggested in gaps["suggested"])


def test_palette_gaps_clear_when_the_missing_colour_is_added():
    from northcel.fitting import palette_gaps

    image, palette = _real_drawing()
    assert palette_gaps(image, palette + [PINK])["count"] == 0


def test_antialiased_ink_edge_is_not_a_palette_gap():
    from northcel.fitting import palette_gaps

    palette = [(255, 255, 255), (220, 40, 40), (10, 10, 10)]
    gaps = palette_gaps(_antialiased_outline(), palette)
    assert gaps["count"] == 0
    assert gaps["regions"] == [] and gaps["suggested"] == []


def test_off_palette_lines_up_to_four_pixels_are_ignored():
    from PIL import Image, ImageDraw

    from northcel.fitting import palette_gaps

    for height, expected in ((4, 0), (5, 1)):
        image = Image.new("RGB", (120, 60), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        draw.rectangle([10, 28, 109, 27 + height], fill=(250, 140, 130))
        assert palette_gaps(image, [(255, 255, 255)])["count"] == expected


def test_close_suggestions_merge_to_the_largest_region():
    from PIL import Image, ImageDraw

    from northcel.fitting import palette_gaps

    image = Image.new("RGB", (400, 200), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    # A chain: each neighbour is 40 apart, the ends 80 apart, so a transitive
    # merge below threshold 60 keeps only the largest region's colour.
    draw.rectangle([10, 10, 90, 70], fill=(250, 140, 130))
    draw.rectangle([150, 10, 220, 60], fill=(250, 180, 130))
    draw.rectangle([300, 10, 360, 50], fill=(250, 220, 130))
    gaps = palette_gaps(image, [(255, 255, 255)])
    assert gaps["count"] == 3
    assert gaps["suggested"] == [[250, 140, 130]]


def test_fit_reports_a_gap_without_changing_the_fitted_source(tmp_path, capsys):
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    from northcel.fitting import fit_image, main

    palette = [(255, 255, 255), (10, 10, 10)]
    image = _gap_drawing()
    source, _ = fit_image(image, palette=palette)
    image_path = tmp_path / "gap.png"
    palette_path = tmp_path / "palette.json"
    out = tmp_path / "gap.ncel"
    receipt_path = tmp_path / "gap.json"
    image.save(image_path)
    palette_path.write_text(json.dumps(palette))

    assert main([str(image_path), "-o", str(out), "--palette", str(palette_path),
                 "--receipt", str(receipt_path)]) == 0
    assert out.read_text() == source
    receipt = json.loads(receipt_path.read_text())
    gaps = receipt["palette_gaps"]
    assert gaps["count"] >= 1
    assert any(math.dist(row["rgb"], PINK) <= 25 for row in gaps["regions"])
    assert any(math.dist(row, PINK) <= 25 for row in gaps["suggested"])
    stderr = capsys.readouterr().err
    assert stderr.count("\n") == 1 and "palette_gaps" in stderr


def test_fit_stacked_and_figure_also_report_palette_gaps(tmp_path):
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    from northcel.fitting import main

    image = _gap_drawing()
    image_path = tmp_path / "gap.png"
    palette_path = tmp_path / "palette.json"
    image.save(image_path)
    palette_path.write_text(json.dumps([(255, 255, 255), (10, 10, 10)]))
    for name, mode in (("stacked", ["--stacked"]), ("figure", ["--stacked", "--figure"])):
        receipt_path = tmp_path / f"{name}.json"
        assert main([str(image_path), "-o", str(tmp_path / f"{name}.ncel"),
                     "--palette", str(palette_path), "--receipt", str(receipt_path),
                     *mode]) == 0
        gaps = json.loads(receipt_path.read_text())["palette_gaps"]
        assert gaps["count"] >= 1
        assert any(math.dist(row["rgb"], PINK) <= 25 for row in gaps["regions"])


def test_fit_without_a_palette_has_no_gap_report(tmp_path, capsys):
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    from northcel.fitting import main

    image_path = tmp_path / "gap.png"
    receipt_path = tmp_path / "gap.json"
    _gap_drawing().save(image_path)
    assert main([str(image_path), "-o", str(tmp_path / "gap.ncel"),
                 "--receipt", str(receipt_path)]) == 0
    assert "palette_gaps" not in json.loads(receipt_path.read_text())
    assert capsys.readouterr().err == ""
