"""Comprehensive test suite for NorthCel (.ncel):
- Unit tests (rings encoder/decoder, AST, parser, validator, formatter, CLI)
- Error-case tests with exact line:column diagnostics
- Round-trip formatting & ring encoding tests
- Determinism & out-of-order frame rendering tests
- Golden tests against saved GLSL shower_f0001/f0002 renders
- Conformance suite verification
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from PIL import Image

from northcel import (
    CLI_COMMAND,
    CLI_SHORT_ALIAS,
    FILE_EXTENSION,
    LANGUAGE_NAME,
    NorthCelSyntaxError,
    SPEC_VERSION,
    decode_ring_b63_1px,
    decode_ring_b63_q25,
    decode_ring_q25,
    encode_ring_b63_1px,
    encode_ring_b63_q25,
    encode_ring_q25,
    format_document,
    parse_ncel,
    render_document_frame,
    validate_document,
)
from northcel.cli import main as cli_main
from northcel.rings import RingEncodingError

PKG_DIR = Path(__file__).resolve().parents[1]          # <repo>/python
EXAMPLES_DIR = PKG_DIR / "northcel" / "examples"
CONFORMANCE_DIR = PKG_DIR / "northcel" / "conformance"
REPO_ROOT = PKG_DIR.parent                              # <repo>
GOLDEN_DIR = REPO_ROOT / "tests" / "golden"


class TestConfigAndRings(unittest.TestCase):
    def test_single_config_constants(self) -> None:
        self.assertEqual(LANGUAGE_NAME, "NorthCel")
        self.assertEqual(FILE_EXTENSION, ".ncel")
        self.assertEqual(CLI_COMMAND, "northcel")
        self.assertEqual(CLI_SHORT_ALIAS, "ncel")
        self.assertEqual(SPEC_VERSION, "0.6.0-draft")

    def test_ring_b63_q25_roundtrip(self) -> None:
        ring = [(12.25, 40.5), (18.75, 40.5), (18.75, 46.25), (12.25, 46.25)]
        enc = encode_ring_b63_q25(ring)
        dec = decode_ring_b63_q25(enc)
        self.assertEqual(dec, ring)

    def test_ring_q25_roundtrip(self) -> None:
        ring = [(10.25, 20.5), (30.75, 20.5), (30.75, 45.0), (10.25, 45.0)]
        enc = encode_ring_q25(ring)
        dec = decode_ring_q25(enc)
        self.assertEqual(dec, ring)

    def test_ring_b63_1px_roundtrip(self) -> None:
        ring = [(100.0, 200.0), (115.0, 205.0), (110.0, 225.0), (95.0, 215.0)]
        enc = encode_ring_b63_1px(ring)
        dec = decode_ring_b63_1px(enc)
        self.assertEqual(dec, ring)

    def test_ring_encoding_errors(self) -> None:
        with self.assertRaises(RingEncodingError):
            encode_ring_q25([(0, 0), (1, 1)])
        with self.assertRaises(RingEncodingError):
            decode_ring_q25("10,20 bad_token 5,5")
        with self.assertRaises(RingEncodingError):
            decode_ring_b63_1px("10,20:A")  # odd length tail


class TestParserAndDiagnostics(unittest.TestCase):
    def test_syntax_error_line_column(self) -> None:
        bad_src = 'northcel "0.1.0-draft"\n\nscene Broken(width: 100) {\n  unknown_stmt foo\n}\n'
        with self.assertRaises(NorthCelSyntaxError) as ctx:
            parse_ncel(bad_src)
        self.assertEqual(ctx.exception.line, 4)
        self.assertEqual(ctx.exception.column, 3)
        self.assertIn("Unknown scene statement", ctx.exception.message)

    def test_unexpected_character_line_column(self) -> None:
        bad_src = 'scene S(width: 64) {\n  paper { tone: 239 }\n  $invalid\n}\n'
        with self.assertRaises(NorthCelSyntaxError) as ctx:
            parse_ncel(bad_src)
        self.assertEqual(ctx.exception.line, 3)
        self.assertEqual(ctx.exception.column, 3)

    def test_validator_catches_semantic_errors(self) -> None:
        src = '''northcel "9.9.9"
scene BadSem(width: 10000, height: 64, fps: 0, precision: 2px) {
  paper { tone: 300, antialias_grid: 3 }
  use MissingDef(dx: 10)
  stroke s(tone: 14, width: -2) { (10, 10) }
}
'''
        doc = parse_ncel(src)
        diags = validate_document(doc)
        errors = [d for d in diags if d.level == "error"]
        self.assertGreaterEqual(len(errors), 6)
        msgs = "\n".join(d.format() for d in errors)
        self.assertIn("Unsupported NorthCel version", msgs)
        self.assertIn("Canvas dimensions", msgs)
        self.assertIn("FPS 0 out of valid range", msgs)
        self.assertIn("Unsupported precision", msgs)
        self.assertIn("Use of undefined def block 'MissingDef'", msgs)


class TestFormatterRoundTrip(unittest.TestCase):
    def test_all_examples_roundtrip_canonical(self) -> None:
        for p in sorted(EXAMPLES_DIR.glob("*.ncel")):
            raw = p.read_text(encoding="utf-8")
            doc1 = parse_ncel(raw)
            fmt1 = format_document(doc1, include_version_header=True)
            doc2 = parse_ncel(fmt1)
            fmt2 = format_document(doc2, include_version_header=True)
            self.assertEqual(fmt1, fmt2, f"Formatter idempotence failed on {p.name}")
            diags = validate_document(doc2)
            errs = [d for d in diags if d.level == "error"]
            self.assertEqual(errs, [], f"Validation errors on {p.name}: {errs}")


class TestDeterminismAndV01Features(unittest.TestCase):
    def test_out_of_order_film_determinism(self) -> None:
        doc = parse_ncel((EXAMPLES_DIR / "lantern_film.ncel").read_text(encoding="utf-8"))
        forward = {i: hashlib.sha256(render_document_frame(doc, i).tobytes()).hexdigest() for i in range(6)}
        reverse = {i: hashlib.sha256(render_document_frame(doc, i).tobytes()).hexdigest() for i in reversed(range(6))}
        shuffled_order = [4, 1, 5, 0, 3, 2]
        shuffled = {i: hashlib.sha256(render_document_frame(doc, i).tobytes()).hexdigest() for i in shuffled_order}
        self.assertEqual(forward, reverse)
        self.assertEqual(forward, shuffled)
        # Ensure frames actually animate (frame 0 != frame 2)
        self.assertNotEqual(forward[0], forward[2])

    def test_v02_palette_cel_outline_and_frame_deltas(self) -> None:
        sky_ring = encode_ring_b63_q25([(0, 0), (64, 0), (64, 64), (0, 64)])
        box_ring = encode_ring_b63_q25([(12, 12), (40, 12), (40, 40), (12, 40)])
        hill_ring = encode_ring_b63_q25([(0, 44), (64, 44), (64, 64), (0, 64)])
        src = f'''northcel "0.2.0-draft"

film DeltaCelTest(width: 64, height: 64, fps: 6, frames: 2, precision: 0.25px-b63, seed: 42) {{
  palette {{ sky: #70CCF5, grass: #62AC56, white: #FAFAFA, ink: #0D0D0D }}
  paper {{ color: #FAFAFA, antialias_grid: 4 }}
  layer sky_bg(color: $sky, rings: 1) {{ "{sky_ring}" }}
  cel cloud_box(color: $white, rings: 1, outline: ($ink, 4px)) {{ "{box_ring}" }}
  frame 1 {{
    drop cloud_box
    layer grass_hill(color: $grass, rings: 1) {{ "{hill_ring}" }}
  }}
}}
'''
        doc = parse_ncel(src)
        self.assertEqual([d for d in validate_document(doc) if d.level == "error"], [])
        canon = format_document(doc, include_version_header=True)
        doc2 = parse_ncel(canon)
        self.assertEqual(canon, format_document(doc2, include_version_header=True))
        f0 = render_document_frame(doc, 0)
        f1 = render_document_frame(doc, 1)
        self.assertEqual(f0.shape, (64, 64, 3))
        self.assertEqual(f1.shape, (64, 64, 3))
        # In frame 0, pixel (24, 24) is inside white cloud_box; in frame 1 cloud_box was dropped!
        self.assertEqual(f0[24, 24].tolist(), [250, 250, 250])
        self.assertEqual(f1[24, 24].tolist(), [112, 204, 245])
        self.assertEqual(f1[52, 24].tolist(), [98, 172, 86])

    def test_cli_check_fmt_info_render_film(self) -> None:
        sample = EXAMPLES_DIR / "lantern_film.ncel"
        self.assertEqual(cli_main(["check", str(sample)]), 0)
        self.assertEqual(cli_main(["fmt", "--check", str(sample)]), 0)
        self.assertEqual(cli_main(["info", str(sample)]), 0)
        with tempfile.TemporaryDirectory() as tmp:
            out_png = Path(tmp) / "frame0.png"
            self.assertEqual(cli_main(["render", str(sample), "-o", str(out_png), "--frame", "0"]), 0)
            self.assertTrue(out_png.is_file())
            frames_dir = Path(tmp) / "frames"
            self.assertEqual(cli_main(["film", str(sample), "-o", str(frames_dir), "--frames", "0..2"]), 0)
            self.assertTrue((frames_dir / "f0000.png").is_file())
            self.assertTrue((frames_dir / "f0002.png").is_file())


class TestConformanceAndGoldenShower(unittest.TestCase):
    def test_textmate_grammar_and_js_validator(self) -> None:
        import re
        import subprocess

        tm_path = REPO_ROOT / "editors" / "vscode" / "syntaxes" / "northcel.tmLanguage.json"
        tm = json.loads(tm_path.read_text(encoding="utf-8"))
        self.assertEqual(tm["scopeName"], "source.northcel")
        self.assertIn("ncel", tm["fileTypes"])
        kw_re = re.compile(tm["repository"]["keywords"]["patterns"][0]["match"])
        for kw in ("northcel", "scene", "film", "paper", "def", "use", "layer", "bend_swarm", "stroke", "ribbon"):
            self.assertIsNotNone(kw_re.search(kw), f"Keyword '{kw}' not matched by TextMate grammar")

        # Verify pure-JS validator on all sample .ncel files
        js_check = (
            "const fs=require('fs'), {checkNcelSource}=require('./js/northcel/index.cjs');"
            "for(const f of ['lantern_film.ncel','shower_f0001.ncel','shower_f0001_compact.ncel']){"
            "const r=checkNcelSource(fs.readFileSync('./python/northcel/examples/'+f,'utf8'));"
            "if(!r.ok) { console.error(f, r.errors); process.exit(1); }}"
        )
        proc = subprocess.run(["node", "-e", js_check], cwd=str(REPO_ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_conformance_suite(self) -> None:
        manifest = json.loads((CONFORMANCE_DIR / "conformance_manifest.json").read_text(encoding="utf-8"))
        for case in manifest["cases"]:
            doc = parse_ncel((CONFORMANCE_DIR / case["file"]).read_text(encoding="utf-8"))
            diags = [d for d in validate_document(doc) if d.level == "error"]
            self.assertEqual(diags, [])
            if "probes" in case:
                rgb = render_document_frame(doc, 0)
                for pr in case["probes"]:
                    got = rgb[pr["y"], pr["x"]].tolist()
                    self.assertEqual(got, pr["rgb"], f"{case['name']} probe {pr['note']}")
            if "probes_by_frame" in case:
                for f_s, plist in case["probes_by_frame"].items():
                    rgb = render_document_frame(doc, int(f_s))
                    for pr in plist:
                        got = rgb[pr["y"], pr["x"]].tolist()
                        self.assertEqual(got, pr["rgb"], f"{case['name']} f={f_s} {pr['note']}")

    def test_golden_shower_f0001_f0002_reproduction(self) -> None:
        for fname in ("f0001", "f0002"):
            ncel_path = EXAMPLES_DIR / f"shower_{fname}.ncel"
            doc = parse_ncel(ncel_path.read_text(encoding="utf-8"))
            rgb = render_document_frame(doc, 0)
            self.assertEqual(rgb.shape, (1024, 1024, 3))
            glsl_png = GOLDEN_DIR / f"shower_{fname}_glsl.png"
            if glsl_png.is_file():
                ref = np.asarray(Image.open(glsl_png).convert("RGB"), dtype=np.float64)
                mae = float(np.abs(ref - rgb.astype(np.float64)).mean())
                # The pure-Python 4x4 subpixel renderer reproduces the GLSL frame at
                # 0.0115 greyscale MAE (measured); 0.05 is the regression gate.
                self.assertLess(mae, 0.05, f"Golden MAE vs GLSL too large on {fname}: {mae}")


if __name__ == "__main__":
    unittest.main()


class TestParserHardening(unittest.TestCase):
    """Normative 'integers'/'3 or 6 digits' claims must not silently truncate or crash."""

    def test_exact_frame_index_must_be_an_integer(self) -> None:
        with self.assertRaises(NorthCelSyntaxError) as caught:
            parse_ncel('northcel "0.4.0-draft"\nfilm F(width: 100, height: 100, frames: 3) {\n'
                       '  frame 1.5 { layer a(color: #000000) { "0,0 10,0 0,10 -10,0" } }\n}\n')
        self.assertIn("Frame index must be an integer", str(caught.exception))

    def test_hex_colour_needs_three_or_six_digits(self) -> None:
        with self.assertRaises(NorthCelSyntaxError) as caught:
            parse_ncel('northcel "0.4.0-draft"\nscene S(width: 100, height: 100) {\n'
                       '  layer a(color: #1234) { "0,0 10,0 0,10 -10,0" }\n}\n')
        self.assertIn("Hex colours must have 3 or 6 digits", str(caught.exception))


class TestLauncherGlobalFlags(unittest.TestCase):
    def test_no_native_before_the_command_is_accepted(self) -> None:
        import contextlib
        import io
        from northcel.launcher.cli import main

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--no-native", "version"])
        self.assertEqual(code, 0)
        self.assertIn("northcel", out.getvalue())
