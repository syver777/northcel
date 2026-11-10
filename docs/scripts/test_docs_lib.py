"""Regression checks for valid examples vs intentional diagnostic text fences."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import docs_lib as lib
from check_docs import Checker


class ExtractBlocksTest(unittest.TestCase):
    def extract(self, text):
        with tempfile.TemporaryDirectory() as td:
            page = Path(td) / "page.md"
            page.write_text(text)
            return lib.extract_blocks(page)

    def test_program_and_diagnostic_keep_indices_and_locations(self):
        blocks = self.extract(
            '<!-- render: assets/a.png frames=0,1 -->\n'
            '```ncel\nscene A {}\n```\n\n'
            '<!-- expect-error: exact message -->\n'
            '```text\nnot a program\n```\n'
        )
        self.assertEqual([b.index for b in blocks], [0, 1])
        self.assertEqual([b.start_line for b in blocks], [3, 8])
        self.assertEqual([b.language for b in blocks], ["ncel", "text"])
        self.assertEqual([b.kind for b in blocks], ["render", "error"])
        self.assertEqual(blocks[1].marker["text"], "exact message")

    def test_unmarked_text_is_not_a_program(self):
        self.assertEqual(self.extract('```text\npartial syntax\n```\n'), [])

    def test_markers_inside_other_fences_do_not_leak(self):
        blocks = self.extract(
            '```text\n<!-- expect-error: not a marker here -->\n```\n'
            '```ncel\nscene A {}\n```\n'
        )
        self.assertEqual(len(blocks), 1)
        self.assertIsNone(blocks[0].marker)

    def test_marker_does_not_skip_an_intervening_fence_or_prose(self):
        blocks = self.extract(
            '<!-- expect-error: stale -->\n```sh\ncommand\n```\n'
            '```ncel\nscene A {}\n```\n'
            '<!-- source: stale.ncel -->\nintervening prose\n'
            '```ncel\nscene B {}\n```\n'
        )
        self.assertTrue(all(b.marker is None for b in blocks))

    def test_unclosed_fence_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "unclosed ncel fence at line 1"):
            self.extract('```ncel\nscene A {}\n')


class AllFencesCheckTest(unittest.TestCase):
    def check_page(self, text):
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            page = tmp / "outside-the-guide.md"
            page.write_text(text)
            checker = Checker()
            with patch.object(lib, "markdown_files", return_value=[page]):
                checker.check_ncel_fences(tmp)
            return checker

    def test_valid_complete_program_outside_guide_passes(self):
        checker = self.check_page('```ncel\nscene A(width: 32, height: 32) {}\n```\n')
        self.assertEqual(checker.counts["valid_ncel_fences"], 1)
        self.assertEqual(checker.failures, [])

    def test_invalid_ncel_outside_guide_fails(self):
        checker = self.check_page('```ncel\ngroup part {}\n```\n')
        self.assertEqual(checker.counts["valid_ncel_fences"], 1)
        self.assertEqual(len(checker.failures), 1)
        self.assertIn("invalid ncel fence", checker.failures[0])

    def test_diagnostic_text_is_not_claimed_as_a_valid_program(self):
        checker = self.check_page(
            '<!-- expect-error: expected diagnostic -->\n```text\nbroken input\n```\n'
        )
        self.assertEqual(checker.counts["valid_ncel_fences"], 0)
        self.assertEqual(checker.failures, [])


if __name__ == "__main__":
    unittest.main()
