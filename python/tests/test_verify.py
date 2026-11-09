"""Verification tools: diff, onion, contact, continuity and distinct-frames metrics."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from northcel.cli import main
from northcel.parser import parse_ncel
from northcel.renderer import render_document_frame, render_film_frames

MOVE = '''northcel "0.5.0-draft"
film Move(width: 64, height: 48, fps: 12, frames: 4) {
  paper { color: #FFFFFF }
  group g(pivot: (32, 24)) {
    layer a(color: #FF0000) { "16,12 16,0 0,24 -16,0" }
  }
  transform g(translate: (f * 8, 0))
}
'''

STILL = '''northcel "0.5.0-draft"
film Still(width: 64, height: 48, fps: 12, frames: 3) {
  paper { color: #FFFFFF }
  group g { layer a(color: #FF0000) { "16,12 16,0 0,24 -16,0" } }
}
'''

GROW = '''northcel "0.5.0-draft"
film Grow(width: 64, height: 48, fps: 12, frames: 4) {
  paper { color: #FFFFFF }
  group g(pivot: (32, 48)) {
    layer a(color: #FF0000) { "16,12 16,0 0,24 -16,0" }
  }
  transform g(scale: (1, 1 + f * 0.1), anchor: (32, 48))
}
'''

TRANSITIONS = '''northcel "0.5.0-draft"
film Trans(width: 64, height: 48, fps: 12, frames: 8) {
  paper { color: #FFFFFF }
  group g { layer a(color: #FF0000) { "16,12 16,0 0,24 -16,0" } }
  frame 1..3 {
    layer b(color: #0000FF) { "80,12 16,0 0,24 -16,0" }
  }
  frame 6 {
    layer c(color: #00FF00) { "120,12 16,0 0,24 -16,0" }
  }
}
'''


def write_source(directory: Path, name: str, source: str) -> Path:
    path = directory / name
    path.write_text(source, encoding="utf-8")
    return path


def run_cli(arguments: list[str]) -> tuple[int, str, str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(arguments)
    return code, stdout.getvalue(), stderr.getvalue()


class TestDiff(unittest.TestCase):
    def test_matching_render_reports_near_zero_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            reference = directory / "frame0.png"
            Image.fromarray(render_document_frame(parse_ncel(MOVE), 0), mode="RGB").save(reference)

            code, stdout, stderr = run_cli(
                [
                    "diff",
                    str(source),
                    "--against",
                    str(reference),
                    "--frame",
                    "0",
                    "--region",
                    "box:0,0,64,48",
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertTrue(result["overall"]["identical"])
            self.assertEqual(result["overall"]["mae"], 0.0)
            self.assertIsNone(result["overall"]["psnr"])
            self.assertEqual(result["regions"][0]["name"], "box")
            self.assertTrue(any(group["name"] == "g" for group in result["groups"]))
            self.assertIsNone(result["heatmap"])
            self.assertEqual(result["renderer"], "python-reference")
            self.assertFalse(result["native"])

    def test_different_image_reports_error_and_writes_heatmap(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            reference = directory / "red.png"
            Image.new("RGB", (64, 48), (255, 0, 0)).save(reference)
            heatmap = directory / "heat.png"

            code, stdout, stderr = run_cli(
                [
                    "diff",
                    str(source),
                    "--against",
                    str(reference),
                    "-o",
                    str(heatmap),
                    "--json",
                ]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertFalse(result["overall"]["identical"])
            self.assertGreater(result["overall"]["mae"], 0.0)
            self.assertIsNotNone(result["overall"]["psnr"])
            self.assertTrue(heatmap.is_file())
            heat = np.asarray(Image.open(heatmap))
            self.assertEqual(heat.shape, (48, 64, 3))
            self.assertGreater(int(heat.max()), 0)
            self.assertEqual(result["heatmap"], str(heatmap))

    def test_reference_size_mismatch_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            reference = directory / "small.png"
            Image.new("RGB", (32, 24), (255, 0, 0)).save(reference)
            code, _stdout, stderr = run_cli(
                ["diff", str(source), "--against", str(reference)]
            )
            self.assertEqual(code, 1)
            self.assertIn("resize the reference", stderr)
            self.assertNotIn("Traceback", stderr)

    def test_region_and_nested_group_errors_use_their_own_boxes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            nested = MOVE.replace("group g(pivot: (32, 24)) {", "group outer { group g {")
            nested = nested.replace("  transform g", "  }\n  transform g")
            source = write_source(directory, "nested.ncel", nested)
            rgb = render_document_frame(parse_ncel(nested), 2)
            rgb[:4, :4] = 0  # An error outside either group, inside the manual box.
            reference = directory / "reference.png"
            Image.fromarray(rgb).save(reference)
            code, stdout, stderr = run_cli([
                "diff", str(source), "--frame", "2", "--against", str(reference),
                "--region", "corner:0,0,4,4", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["overall"]["mae"], 1.328125)
            self.assertEqual(result["regions"][0]["mae"], 255.0)
            self.assertEqual({row["name"] for row in result["groups"]}, {"g", "outer"})
            self.assertTrue(all(row["mae"] == 0.0 for row in result["groups"]))


class TestOnion(unittest.TestCase):
    def test_neighbouring_frames_have_document_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            for frame in (0, 2):
                output = directory / f"onion-{frame}.png"
                code, _stdout, stderr = run_cli(
                    ["onion", str(source), "-o", str(output), "--frame", str(frame)]
                )
                self.assertEqual(code, 0, stderr)
                with Image.open(output) as image:
                    self.assertEqual(image.size, (64, 48))
                    self.assertEqual(image.mode, "RGB")
                    onion = np.asarray(image)
                self.assertTrue(np.any(onion[:, :, 0] != onion[:, :, 2]))

    def test_against_reference_has_document_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            reference = directory / "frame1.png"
            Image.fromarray(render_document_frame(parse_ncel(MOVE), 1), mode="RGB").save(reference)
            output = directory / "against.png"
            code, _stdout, stderr = run_cli(
                [
                    "onion",
                    str(source),
                    "-o",
                    str(output),
                    "--frame",
                    "1",
                    "--against",
                    str(reference),
                ]
            )
            self.assertEqual(code, 0, stderr)
            with Image.open(output) as image:
                self.assertEqual(image.size, (64, 48))
                rgb = np.asarray(image)
            # Matching ink must be neutral and must not be hidden by a legend.
            self.assertTrue(np.array_equal(rgb[:, :, 0], rgb[:, :, 1]))
            self.assertTrue(np.array_equal(rgb[:, :, 1], rgb[:, :, 2]))
            self.assertLess(int(rgb[4, 13, 0]), 255)

    def test_single_scene_uses_its_only_frame(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            scene = STILL.replace("film Still", "scene Still").replace(", frames: 3", "")
            source = write_source(directory, "scene.ncel", scene)
            output = directory / "scene.png"
            code, stdout, stderr = run_cli(["onion", str(source), "-o", str(output), "--json"])
            self.assertEqual(code, 0, stderr)
            self.assertEqual(json.loads(stdout)["mode"], "single")
            with Image.open(output) as image:
                self.assertEqual(image.size, (64, 48))
                self.assertTrue(np.array_equal(np.asarray(image), render_document_frame(parse_ncel(scene))))

    def test_top_left_motion_is_visible_and_tinted(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            scene = STILL.replace("film Still", "scene Still").replace(", frames: 3", "")
            scene = scene.replace('"16,12 16,0 0,24 -16,0"', '"40,40 80,0 0,60 -80,0"')
            source = write_source(directory, "scene.ncel", scene)
            white = directory / "white.png"
            Image.new("RGB", (64, 48), "white").save(white)
            output = directory / "onion.png"
            code, _stdout, stderr = run_cli([
                "onion", str(source), "-o", str(output), "--against", str(white),
            ])
            self.assertEqual(code, 0, stderr)
            with Image.open(output) as image:
                rgb = np.asarray(image)
            self.assertGreater(int(rgb[12, 12, 0]), int(rgb[12, 12, 2]))
            self.assertLess(int(rgb[12, 12, 1]), 255)


class TestContact(unittest.TestCase):
    def test_grid_sheet_and_frame_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            output = directory / "sheet.png"
            code, _stdout, stderr = run_cli(
                ["contact", str(source), "-o", str(output), "--frames", "0..3"]
            )
            self.assertEqual(code, 0, stderr)
            self.assertTrue(output.is_file())
            with Image.open(output) as image:
                self.assertGreater(image.width, 64)
                self.assertGreater(image.height, 48)

    def test_transitions_write_one_sheet_per_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "trans.ncel", TRANSITIONS)
            output = directory / "transitions"
            code, stdout, stderr = run_cli(
                ["contact", str(source), "-o", str(output), "--transitions", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(len(result["sheets"]), 2)
            kinds = [sheet["transition"]["kind"] for sheet in result["sheets"]]
            self.assertEqual(kinds, ["range", "exact"])
            for sheet in result["sheets"]:
                self.assertTrue(Path(sheet["path"]).is_file())
            self.assertEqual(result["sheets"][0]["frames"], [0, 1, 2, 3])
            self.assertEqual(result["sheets"][1]["frames"], [5, 6])

    def test_adjacent_exact_overrides_are_separate_transitions(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "keys.ncel", MOVE.replace(
                "  transform g(translate: (f * 8, 0))",
                "  frame 1 { transform g(translate: (8, 0)) }\n"
                "  frame 2 { transform g(translate: (16, 0)) }\n"
                "  frame 3 { transform g(translate: (24, 0)) }",
            ))
            output = directory / "keys.png"
            code, stdout, stderr = run_cli([
                "contact", str(source), "-o", str(output), "--transitions", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            sheets = json.loads(stdout)["sheets"]
            self.assertEqual([sheet["frames"] for sheet in sheets], [[0, 1], [1, 2], [2, 3]])
            self.assertFalse(output.exists())
            self.assertTrue(all(Path(sheet["path"]).parent == directory / "keys-transitions"
                                for sheet in sheets))

    def test_transition_sampling_keeps_incoming_and_key_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "trans.ncel", TRANSITIONS)
            code, stdout, stderr = run_cli([
                "contact", str(source), "-o", str(directory / "sheets"),
                "--transitions", "--every", "10", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            self.assertEqual([sheet["frames"] for sheet in json.loads(stdout)["sheets"]],
                             [[0, 1, 3], [5, 6]])

    def test_directory_output_selection_stride_and_renderer_reuse(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            with patch("northcel.verify.render_film_frames", wraps=render_film_frames) as render:
                code, stdout, stderr = run_cli([
                    "contact", str(source), "-o", str(directory / "sheets"),
                    "--frames", "0,1,3", "--every", "2", "--json",
                ])
            self.assertEqual(code, 0, stderr)
            sheet = json.loads(stdout)["sheets"][0]
            self.assertEqual(sheet["frames"], [0, 3])
            self.assertEqual(sheet["path"], str(directory / "sheets" / "contact.png"))
            render.assert_called_once()
            self.assertFalse(Path(render.call_args.args[1]).exists())

    def test_transitions_without_blocks_is_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "still.ncel", STILL)
            code, _stdout, stderr = run_cli(
                ["contact", str(source), "-o", str(directory / "out"), "--transitions"]
            )
            self.assertEqual(code, 1)
            self.assertIn("no frame overrides", stderr)
            self.assertNotIn("Traceback", stderr)


class TestContinuity(unittest.TestCase):
    def test_height_jump_over_eight_percent_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "grow.ncel", GROW)
            code, stdout, stderr = run_cli(
                ["continuity", str(source), "--group", "g", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(len(result["rows"]), 4)
            self.assertEqual(len(result["jumps"]), 3)
            self.assertEqual(len(result["height_jumps"]), 3)
            self.assertGreater(result["max_height_jump_pct"], 8.0)
            for jump in result["height_jumps"]:
                self.assertGreater(jump["height_change_pct"], 8.0)
                self.assertTrue(jump["height_jump"])

    def test_shape_can_restrict_the_measurement(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "grow.ncel", GROW)
            code, stdout, stderr = run_cli(
                ["continuity", str(source), "--group", "g", "--shape", "a", "--json"]
            )
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["selection"]["shape"], "a")
            self.assertTrue(all(row["present"] for row in result["rows"]))

    def test_missing_group_lists_available_names(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            code, _stdout, stderr = run_cli(
                ["continuity", str(source), "--group", "absent"]
            )
            self.assertEqual(code, 1)
            self.assertIn("available groups", stderr)
            self.assertIn("g", stderr)
            self.assertNotIn("Traceback", stderr)

    def test_missing_shape_lists_shapes_within_the_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            code, stdout, stderr = run_cli([
                "continuity", str(source), "--group", "g", "--shape", "absent", "--json",
            ])
            self.assertEqual(code, 1, stderr)
            message = json.loads(stdout)["errors"][0]
            self.assertIn("shape 'absent'", message)
            self.assertIn("available shapes: a", message)

    def test_translation_reports_position_without_scale_jumps(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            code, stdout, stderr = run_cli(["continuity", str(source), "--group", "g", "--json"])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["height_jumps"], [])
            for jump in result["jumps"]:
                self.assertEqual(jump["centroid_dx"], 8.0)
                self.assertEqual(jump["centroid_dy"], 0.0)
                self.assertEqual(jump["width_change_pct"], 0.0)
                self.assertEqual(jump["height_change_pct"], 0.0)

    def test_exactly_eight_percent_is_not_a_jump(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "grow.ncel", GROW.replace("f * 0.1", "f * 0.08"))
            code, stdout, stderr = run_cli(["continuity", str(source), "--group", "g", "--json"])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["jumps"][0]["height_change_pct"], 8.0)
            self.assertEqual(result["height_jumps"], [])

    def test_disappearance_is_reported_not_divided_by_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "drop.ncel", STILL.replace(
                '\n}\n', '\n  frame 1 { drop a }\n}\n',
            ))
            code, stdout, stderr = run_cli(["continuity", str(source), "--group", "g", "--json"])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual([row["present"] for row in result["rows"]], [True, False, True])
            self.assertTrue(all(jump["present_change"] for jump in result["jumps"]))
            self.assertTrue(all(jump["height_change_pct"] is None for jump in result["jumps"]))


class TestDistinct(unittest.TestCase):
    def test_identical_frames_count_as_zero_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "still.ncel", STILL)
            code, stdout, stderr = run_cli(["distinct", str(source), "--json"])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["changed_pairs"], 0)
            self.assertEqual(result["distinct_frames"], 0)
            self.assertEqual(result["distinct_per_second"], 0.0)
            self.assertTrue(all(pair["diff"] == 0.0 for pair in result["pairs"]))
            self.assertEqual(result["width"], 320)
            self.assertEqual(result["height"], 180)

    def test_moving_frames_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            code, stdout, stderr = run_cli(["distinct", str(source), "--json"])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["changed_pairs"], 3)
            self.assertEqual(result["distinct_frames"], 3)
            self.assertEqual(result["distinct_per_second"], 9.0)
            self.assertTrue(all(pair["diff"] > 0.2 for pair in result["pairs"]))

    def test_sampled_rate_uses_timeline_span_not_sample_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            code, stdout, stderr = run_cli([
                "distinct", str(source), "--frames", "0..3", "--every", "3", "--json",
            ])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertTrue(result["sampled"])
            self.assertEqual(result["sampled_frames"], 2)
            self.assertEqual(result["changed_pairs"], 1)
            self.assertEqual(result["distinct_per_second"], 3.0)
            self.assertAlmostEqual(result["seconds"], 4 / 12, places=6)

    def test_single_frame_has_no_comparison_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            code, stdout, stderr = run_cli(["distinct", str(source), "--frames", "2", "--json"])
            self.assertEqual(code, 0, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["pairs"], [])
            self.assertEqual(result["distinct_frames"], 0)
            self.assertEqual(result["distinct_fps"], 0.0)


class TestErrors(unittest.TestCase):
    def test_all_commands_handle_missing_invalid_and_non_utf8_documents(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            invalid = write_source(directory, "invalid.ncel", "not a document")
            non_utf8 = directory / "binary.ncel"
            non_utf8.write_bytes(b"\xff\xfe")
            for source in (directory / "missing.ncel", invalid, non_utf8):
                for command, options in (
                    ("diff", ["--against", "missing.png"]),
                    ("onion", ["-o", str(directory / "onion.png")]),
                    ("contact", ["-o", str(directory / "contact.png")]),
                    ("continuity", ["--group", "g"]),
                    ("distinct", []),
                ):
                    with self.subTest(source=source.name, command=command):
                        code, stdout, stderr = run_cli([command, str(source), *options, "--json"])
                        self.assertEqual(code, 1, stderr)
                        result = json.loads(stdout)
                        self.assertFalse(result["ok"])
                        self.assertEqual(result["command"], command)
                        self.assertTrue(result["errors"])
                        self.assertNotIn("Traceback", stdout + stderr)

    def test_invalid_options_and_paths_are_actionable(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            reference = directory / "frame.png"
            Image.fromarray(render_document_frame(parse_ncel(MOVE))).save(reference)
            corrupt = write_source(directory, "corrupt.png", "not an image")
            blocked = write_source(directory, "blocked", "not a directory")
            for command, options, message in (
                ("diff", ["--against", str(reference), "--frame", "4"], "out of range"),
                ("diff", ["--against", str(reference), "--region", "oops"], "name:x0"),
                ("diff", ["--against", str(reference), "--region", "box:nan,0,4,4"], "non-finite"),
                ("diff", ["--against", str(corrupt)], "cannot read image"),
                ("diff", ["--against", str(directory / "missing.png")], "image not found"),
                ("diff", ["--against", str(reference), "-o", str(directory / "heat.bad")], "cannot write"),
                ("onion", ["-o", str(blocked / "onion.png")], "cannot create directory"),
                ("contact", ["-o", str(directory / "out"), "--every", "0"], "at least 1"),
                ("contact", ["-o", str(directory / "out"), "--frames", "0,,2"], "empty entry"),
                ("contact", ["-o", str(directory / "out"), "--frames", "0..1000000000"], "out of range"),
                ("contact", ["-o", str(directory / "out"), "--frames", "2..0"], "reversed range"),
                ("distinct", ["--frames", "2,0"], "strictly increasing"),
                ("distinct", ["--frames", "1,1"], "without duplicates"),
            ):
                with self.subTest(command=command, options=options):
                    code, stdout, stderr = run_cli([command, str(source), *options, "--json"])
                    self.assertEqual(code, 1, stderr)
                    result = json.loads(stdout)
                    self.assertIn(message, result["errors"][0])
                    self.assertNotIn("Traceback", stdout + stderr)

    def test_frames_and_transitions_cannot_be_combined(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "trans.ncel", TRANSITIONS)
            code, stdout, stderr = run_cli([
                "contact", str(source), "-o", str(directory / "out"),
                "--transitions", "--frames", "0..3", "--json",
            ])
            self.assertEqual(code, 1, stderr)
            self.assertIn("cannot be combined", json.loads(stdout)["errors"][0])

    def test_source_read_failure_is_actionable(self):
        with patch("northcel.cli._load_and_validate", side_effect=PermissionError("permission denied")):
            code, stdout, stderr = run_cli(["distinct", "unreadable.ncel", "--json"])
        self.assertEqual(code, 1, stderr)
        self.assertIn("cannot read document", json.loads(stdout)["errors"][0])

    def test_bad_numeric_input_and_runtime_expressions_are_actionable(self):
        with patch("northcel.cli._load_and_validate", side_effect=ValueError("bad numeric value")):
            code, stdout, stderr = run_cli(["distinct", "invalid.ncel", "--json"])
        self.assertEqual(code, 1, stderr)
        self.assertIn("check values and expressions", json.loads(stdout)["errors"][0])
        with tempfile.TemporaryDirectory() as tmp:
            source = write_source(Path(tmp), "move.ncel", MOVE)
            with patch("northcel.verify.render_document_frame", side_effect=KeyError("unknown variable")):
                code, stdout, stderr = run_cli(["distinct", str(source), "--json"])
            self.assertEqual(code, 1, stderr)
            self.assertIn("check document expressions", json.loads(stdout)["errors"][0])

    def test_evaluation_errors_are_located_without_tracebacks(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "bad-nudge.ncel", MOVE.replace(
                "  transform g(translate: (f * 8, 0))", "  nudge a(vertex: 999, dx: 1)",
            ))
            code, stdout, stderr = run_cli(["distinct", str(source), "--json"])
            self.assertEqual(code, 1, stderr)
            result = json.loads(stdout)
            self.assertEqual(result["command"], "distinct")
            self.assertIn("Nudge vertex 999", result["errors"][0])
            self.assertNotIn("Traceback", stdout + stderr)


class TestHelp(unittest.TestCase):
    def test_verification_commands_are_in_help(self):
        from northcel.cli import build_parser

        help_text = build_parser().format_help()
        for command in ("diff", "onion", "contact", "continuity", "distinct"):
            self.assertIn(command, help_text)

    def test_launcher_routes_verification_commands(self):
        # The installed `northcel` command goes through the launcher; verification
        # tools are reference-only and must still be reachable from it.
        from northcel.launcher.cli import main as launcher_main

        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = write_source(directory, "move.ncel", MOVE)
            reference = directory / "frame0.png"
            Image.fromarray(render_document_frame(parse_ncel(MOVE), 0), mode="RGB").save(reference)
            for command, options in (
                ("diff", ["--against", str(reference)]),
                ("onion", ["-o", str(directory / "onion.png")]),
                ("contact", ["-o", str(directory / "contact.png")]),
                ("continuity", ["--group", "g"]),
                ("distinct", []),
            ):
                with self.subTest(command=command):
                    stdout, stderr = io.StringIO(), io.StringIO()
                    with redirect_stdout(stdout), redirect_stderr(stderr):
                        code = launcher_main([command, str(source), *options, "--json"])
                    self.assertEqual(code, 0, stderr.getvalue())
                    result = json.loads(stdout.getvalue())
                    self.assertEqual(result["command"], command)
                    self.assertEqual(result["renderer"], "python-reference")
                    self.assertFalse(result["native"])
                    if command == "diff":
                        self.assertTrue(result["overall"]["identical"])


if __name__ == "__main__":
    unittest.main()
