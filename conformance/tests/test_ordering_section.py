"""The committed `ordering/` section still matches its author (P-001 issue 14).

    python3 -m unittest discover -s conformance/tests

`ordering/` asserts *where* a request is refused, and its value comes entirely
from those steps being right — a vector naming the wrong one still lints, still
rejects, and silently licenses the reordering
[P-010](../../docs/prds/P-010-responder-pipeline.md) §4.2 wrote the section to
catch. So the checks here are about the section's shape rather than its bytes:
one operation throughout, one vector per step, ascending, and no step that
`core-model.md` §4 does not have.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUTHOR = REPO / "tools" / "author_ordering.py"
SECTION = REPO / "conformance" / "corpus" / "ordering"
CORE_MODEL = REPO / "spec" / "core-model.md"

# A vector asserting rejection at step N must *pass* steps 1 to N-1, so this
# section stops at the first step it cannot get past rather than at the first
# defect it cannot express. Step 7 is delegation verification and P-014 has
# defined no fixture format for a profile or its evidence, so nothing at or
# after 7 is authorable -- including step 8, whose own defect is expressible,
# and steps 10 to 13, whose registry is in hand.
#
# A request that cannot pass an earlier step is wrong in two ways, and a
# fail-closed implementation rejects it at the earlier one. Such a vector fails
# *conforming* implementations, which is worse than not existing.
FIRST_UNPASSABLE_STEP = 7

# §4 makes step 2 optional and "never a security decision", so there is no
# rejection to assert -- a responder that sheds there and one that does not are
# both conforming.
NO_REJECTION = {2}


def vectors() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(SECTION.rglob("*.json"))]


def steps() -> list:
    return [v["expect"]["rejection"]["step"] for v in vectors()]


class AuthoredSectionTest(unittest.TestCase):
    def test_the_committed_section_matches_its_author(self):
        result = subprocess.run([sys.executable, str(AUTHOR), "--check"],
                                capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0,
                         f"{result.stdout}\n{result.stderr}")

    def test_the_section_is_not_empty(self):
        self.assertGreater(len(vectors()), 0)


class ShapeTest(unittest.TestCase):
    def test_one_operation_throughout(self):
        # Ordering is a property of the pipeline. A `verify_query` vector could
        # show a bad signature refused and never show that the signature was
        # checked *before* the registry was consulted, so a section mixing
        # operations would have step numbers that are partly artefacts of which
        # operation each vector used.
        self.assertEqual({v["operation"] for v in vectors()}, {"process_query"})

    def test_every_vector_is_a_rejection(self):
        # A section about where requests are refused has nothing to say about
        # one that succeeds.
        self.assertEqual({v["expect"]["outcome"] for v in vectors()},
                         {"rejected"})

    def test_one_vector_per_step(self):
        # Two vectors for one step is not extra coverage: they would pass or
        # fail together, and the second hides that some other step has none.
        self.assertEqual(len(steps()), len(set(steps())))

    def test_the_id_names_the_step_it_asserts(self):
        # The filename is what a reader scans. One that disagreed with the
        # assertion inside would send someone to the wrong vector to debug an
        # ordering failure.
        for vector in vectors():
            with self.subTest(vector=vector["id"]):
                named = vector["id"].split("/")[1]
                self.assertEqual(named,
                                 f"step-{vector['expect']['rejection']['step']}")


class StepsAreRealTest(unittest.TestCase):
    """Every asserted step exists in `core-model.md` §4's query order.

    Read from the specification rather than embedded, because that is the one
    direction this check is useful in: a vector asserting a step §4 does not
    have is asserting an ordering the protocol does not define, and the schema's
    enum only constrains the lettered ones.
    """

    def query_steps(self) -> set:
        table = CORE_MODEL.read_text(encoding="utf-8")
        table = table[table.index("## 4. Processing order"):]
        table = table[:table.index("### 4.1") if "### 4.1" in table else len(table)]
        found = set()
        for row in re.findall(r"^\| (\d+[a-z]?) \|", table, re.M):
            found.add(int(row) if row.isdigit() else row)
        return found

    def test_every_asserted_step_is_in_section_4(self):
        available = self.query_steps()
        for lettered in ("5a", "9a", "11a"):
            self.assertIn(lettered, available,
                          "the §4 table did not parse as expected")
        for step in steps():
            with self.subTest(step=step):
                self.assertIn(step, available)

    def test_no_step_is_covered_twice_or_missed_silently(self):
        # Which steps are absent, and why, is the thing worth asserting: the
        # section is incomplete on purpose and a reader has to be able to tell
        # that from a check rather than from prose.
        def number(step):
            return int(step[:-1]) if isinstance(step, str) else step

        rejecting = {s for s in self.query_steps()
                     if number(s) < FIRST_UNPASSABLE_STEP and s not in NO_REJECTION}
        self.assertEqual(set(steps()), rejecting,
                         "a step gained or lost a vector — if a delegation "
                         "fixture format landed, raise FIRST_UNPASSABLE_STEP "
                         "and author the steps it unblocks")


if __name__ == "__main__":
    unittest.main()
