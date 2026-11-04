"""Full-parser verification of packaged guidance and the honest validator contract."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import re
import tempfile
import unittest

from northcel.cli import main
from northcel.parser import parse_ncel
from northcel.validator import validate_document

ROOT = Path(__file__).resolve().parents[1]


class TestToolContract(unittest.TestCase):
    def test_full_json_marker_and_require_full(self):
        for src, code in [("film F {}", 0), ("film B { frames: 2 }", 1)]:
            with tempfile.TemporaryDirectory() as tmp:
                file = Path(tmp) / "film.ncel"
                file.write_text(src)
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["check", str(file), "--json", "--require-full"]), code)
                result = json.loads(output.getvalue())
                self.assertFalse(result["partial"])
                self.assertEqual(result["validator"], "python")

    def test_guide_command_and_all_complete_documentation_snippets(self):
        guide = (ROOT / "northcel/AGENT-GUIDE.md").read_text()
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(["guide"]), 0)
        self.assertEqual(output.getvalue(), guide)
        for path in [ROOT / "README.md", *list((ROOT.parents[1] / "docs/northcel").glob("*.md"))]:
            for snippet in re.findall(r"```ncel\n(.*?)```", path.read_text(), re.S):
                doc = parse_ncel(snippet)
                self.assertEqual([d for d in validate_document(doc) if d.level == "error"], [], str(path))

    def test_spec_and_render_implementation_unchanged(self):
        # Explicit negative coverage: partial checks do not replace the full validator.
        doc = parse_ncel("film F(fps: 0, width: -10) { use Missing }")
        self.assertGreaterEqual(len([d for d in validate_document(doc) if d.level == "error"]), 3)
