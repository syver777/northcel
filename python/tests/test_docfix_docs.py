"""Executable regression coverage for the independent Phase 1 docs review."""
from pathlib import Path
import re
import runpy
import shlex

import numpy as np
import pytest
from PIL import Image, ImageDraw

from northcel import parse_ncel, render_document_frame, validate_document
from northcel.formatter import format_document

REPO = Path(__file__).resolve().parents[2]
PAGES = [REPO / "README.md", REPO / "docs/agent-guide.md",
         REPO / "docs/spec/SPEC-0.5.0-draft.md"]


@pytest.fixture
def docs_checker():
    return runpy.run_path(str(REPO / "docs/scripts/check_docs.py"))


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.name)
def test_current_copyable_fences_validate_and_format_without_pixel_changes(page, docs_checker):
    blocks = docs_checker["lib"].extract_blocks(page)
    assert blocks
    for block in blocks:
        doc = parse_ncel(block.code)
        assert not [d for d in validate_document(doc) if d.level == "error"]
        formatted = parse_ncel(format_document(doc))
        for frame in range(getattr(doc.root, "frames", 1)):
            assert np.array_equal(render_document_frame(doc, frame), render_document_frame(formatted, frame))


def test_docs_checker_includes_current_spec_and_agent_guide(tmp_path, monkeypatch, docs_checker):
    seen = []

    def extract(page):
        seen.append(page)
        return []

    monkeypatch.setattr(docs_checker["lib"], "extract_blocks", extract)
    docs_checker["Checker"]().check_reference_examples(tmp_path)
    assert seen == PAGES


def test_spec_illustration_changes_per_frame_and_is_order_independent(docs_checker):
    doc = parse_ncel(docs_checker["lib"].extract_blocks(PAGES[2])[-1].code)
    forward = [render_document_frame(doc, frame).tobytes() for frame in range(doc.root.frames)]
    reverse = [render_document_frame(doc, frame).tobytes() for frame in reversed(range(doc.root.frames))]
    assert forward == reverse[::-1]
    assert len(set(forward)) > 2


def test_docs_checker_rejects_ellipsis_in_copyable_fence(tmp_path, docs_checker):
    page = tmp_path / "bad-spec.md"
    page.write_text('```ncel\nscene S { def Key { ... } }\n```\n')
    checker = docs_checker["Checker"]()
    checker.check_reference_examples(tmp_path, pages=[page])
    assert len(checker.failures) == 1
    assert "Unexpected character '.'" in checker.failures[0]


def test_docs_checker_renders_later_frames_not_only_frame_zero(tmp_path, docs_checker):
    page = tmp_path / "bad-film.md"
    page.write_text('''```ncel
film F(width: 8, height: 8, frames: 2) {
  frame 1 { nudge missing(vertex: 0) }
}
```
''')
    checker = docs_checker["Checker"]()
    checker.check_reference_examples(tmp_path, pages=[page])
    assert checker.counts["reference_frames"] == 1
    assert len(checker.failures) == 1
    assert "frame 1 failed" in checker.failures[0]


def test_spec_fit_command_is_copyable_and_receipt_matches_queries(tmp_path, monkeypatch, capsys):
    pytest.importorskip("cv2")
    pytest.importorskip("skimage")
    import json
    from northcel.cli import main as cli
    from northcel.fitting import main as fit

    spec = PAGES[2].read_text()
    command = re.search(r"`(northcel fit IMAGE --stacked[^`]+)`", spec).group(1)
    image = Image.new("RGB", (120, 100), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle([20, 20, 90, 80], fill=(200, 40, 40), outline=(0, 0, 0), width=3)
    image.save(tmp_path / "input.png")
    monkeypatch.chdir(tmp_path)
    args = shlex.split(command.replace("IMAGE", "input.png"))[2:]
    assert fit(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    out = args[args.index("-o") + 1]
    assert cli(["shapes", out]) == 0
    query = json.loads(capsys.readouterr().out)
    assert len(receipt["shape_manifest"]) == query["count"]
    for expected, actual in zip(receipt["shape_manifest"], query["shapes"]):
        for key in ("id", "area", "bbox", "centroid", "parent", "children", "neighbours"):
            assert expected[key] == actual[key], key


def test_offline_guide_teaches_current_constructs_and_stays_in_sync():
    guide = PAGES[1].read_text()
    compact = guide.split("<!-- npm-guide:start -->\n", 1)[1].split("<!-- npm-guide:end -->", 1)[0]
    assert (REPO / "python/northcel/AGENT-GUIDE.md").read_text() == compact
    # The npm launcher is not released in lockstep with the Python tools.
    js_guide = (REPO / "js/northcel/northcel/AGENT-GUIDE.md").read_text()
    assert js_guide.replace("tools 0.7.1", "tools 0.7.2") == compact
    for fragment in ('northcel "0.6.0-draft"', "group part", "warp part", "nudge mark",
                     "northcel shapes", "--stacked -o", "tools 0.7.2"):
        assert fragment in compact
    golden = guide.split("## 1. The Golden Rules", 1)[1]
    assert 'current `northcel "0.6.0-draft"`' in golden


def test_install_docs_name_the_current_version_and_have_no_unreleased_copy():
    for path in PAGES[:2] + [REPO / "docs/README.md", REPO / "docs/reference.md"]:
        text = path.read_text().lower()
        assert "0.7.2" in text
        assert "unreleased" not in text
        assert "source-only" not in text
    # The public starter must use the current header and pass the real check.
    starter = re.search(r"```ncel\n(.*?)```", PAGES[0].read_text(), re.S).group(1)
    assert parse_ncel(starter).spec_version == "0.6.0-draft"
    doc = parse_ncel(starter)
    assert not [d for d in validate_document(doc) if d.level == "error"]
