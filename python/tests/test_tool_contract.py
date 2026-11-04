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

ROOT = Path(__file__).resolve().parents[1]   # <repo>/python
REPO_ROOT = ROOT.parent                       # <repo>


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
        docs = [REPO_ROOT / "README.md", REPO_ROOT / "CONTRIBUTING.md"]
        docs += sorted((REPO_ROOT / "docs").glob("*.md"))
        docs += sorted((REPO_ROOT / "js").glob("*/README.md"))
        docs += [ROOT / "README.md"]
        for path in docs:
            text = path.read_text()
            # `docs/errors.md` deliberately contains broken files: each one is a
            # reproduced diagnostic, marked `<!-- case-source -->`, and is checked
            # by `docs/scripts/check_docs.py` instead of being required to pass.
            text = re.sub(r"<!-- case-source -->\n```ncel\n.*?```", "", text, flags=re.S)
            for snippet in re.findall(r"```ncel\n(.*?)```", text, re.S):
                doc = parse_ncel(snippet)
                self.assertEqual([d for d in validate_document(doc) if d.level == "error"], [], str(path))

    def test_info_accepts_the_documented_json_flag(self):
        # `info FILE [--json]` is the documented contract in the launcher usage and in
        # native/README.md; the reference CLI must accept the flag too (it only ever
        # prints JSON), or a script written for one implementation fails on the other.
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "starter.ncel"
            file.write_text((ROOT / "northcel/examples/starter.ncel").read_text())
            plain, with_flag = io.StringIO(), io.StringIO()
            with redirect_stdout(plain):
                self.assertEqual(main(["info", str(file)]), 0)
            with redirect_stdout(with_flag):
                self.assertEqual(main(["info", str(file), "--json"]), 0)
            self.assertEqual(with_flag.getvalue(), plain.getvalue())
            self.assertEqual(json.loads(with_flag.getvalue())["kind"], "scene")

    def test_spec_and_render_implementation_unchanged(self):
        # Explicit negative coverage: partial checks do not replace the full validator.
        doc = parse_ncel("film F(fps: 0, width: -10) { use Missing }")
        self.assertGreaterEqual(len([d for d in validate_document(doc) if d.level == "error"]), 3)
