"""The folded `registry/` section still matches the manifest (P-001 issue 11).

    python3 -m unittest discover -s conformance/tests

[CLAUDE.md](../../CLAUDE.md)'s hierarchy puts `registry/manifest.json` above the
corpus, so the corpus's `registry/` section is *generated* from it by
[`tools/fold_registry.py`](../../tools/fold_registry.py) rather than
transcribed. What makes that worth doing is this check: without it, generated
files are just copies that happen to have been correct once.

The failure it exists to catch is quiet. Somebody changes a predicate's capacity
in the manifest, `registry/validate.py` passes because the manifest agrees with
itself, and the corpus goes on asserting the old value at every implementation
that runs it — a conformance suite failing a correct implementation, for a
reason that is in neither of them.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FOLD = REPO / "tools" / "fold_registry.py"
SECTION = REPO / "conformance" / "corpus" / "registry"


class FoldTest(unittest.TestCase):
    def test_the_committed_section_matches_the_manifest(self):
        result = subprocess.run([sys.executable, str(FOLD), "--check"],
                                capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0,
                         f"{result.stdout}\n{result.stderr}")

    def test_the_section_is_not_empty(self):
        # A generator that produced nothing would satisfy the check above
        # vacuously, and an empty section reads as "no registry vectors" rather
        # than as "the fold broke".
        self.assertGreater(len(list(SECTION.rglob("*.json"))), 0)

    def test_every_folded_vector_says_where_it_came_from(self):
        # A reader who finds one of these and edits it has edited a file that
        # will be overwritten. The description says so, in the file itself,
        # because that is where they are looking.
        for path in sorted(SECTION.rglob("*.json")):
            with self.subTest(vector=path.name):
                self.assertIn("edit the manifest, not this file",
                              path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
