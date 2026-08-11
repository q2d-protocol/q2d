"""No projection carries the expectation (P-001 issue 2).

    python3 -m unittest discover -s conformance/tests

A property test, not an example test. An example proves one vector was
projected correctly; the failure mode here is a vector shape nobody thought of,
so what has to be shown is that *no* generated vector leaks its expectation --
whatever else it carries, however deeply, whatever the field is called.

The generator is seeded, so a failure is reproducible from the seed printed in
the assertion rather than being a shape that appeared once in CI and never
again.
"""

from __future__ import annotations

import json
import random
import sys
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1] / "harness"
sys.path.insert(0, str(HARNESS))

import projection  # noqa: E402

SEED = 20260811
CASES = 400

# Field names a delete-the-key projection would miss. Every one of these is a
# plausible thing for a future vector to carry.
NEAR_MISSES = [
    "expect", "expected", "Expect", "EXPECT", "expect_bytes", "expects",
    "expectation", "result", "output", "answer", "wire", "rejection",
    "comparison", "notes_for_the_runner", "solution", " expect", "expect ",
]


def random_json(rng: random.Random, depth: int = 0):
    """A JSON value, sometimes carrying an expectation-shaped key."""
    kind = rng.randrange(7 if depth < 3 else 5)
    if kind == 0:
        return rng.choice([None, True, False])
    if kind == 1:
        return rng.randint(-1000, 1000)
    if kind == 2:
        return rng.choice(["", "value", "sha256:abc", "expect", "🔑"])
    if kind == 3:
        return rng.random() * 100
    if kind == 4:
        return []
    if kind == 5:
        return [random_json(rng, depth + 1) for _ in range(rng.randrange(3))]
    return {
        rng.choice(NEAR_MISSES + ["key", "nested"]): random_json(rng, depth + 1)
        for _ in range(rng.randrange(4))
    }


def random_vector(rng: random.Random) -> dict:
    vector = {
        "id": "message/sign/generated",
        "section": "message",
        "requirement": ["Q2D-C-05"],
        "description": "generated",
        "operation": "sign_query",
        "input": random_json(rng, depth=1) if rng.random() < 0.3 else {
            "key_id": "test-requester-1",
            # An `expect` inside input is protocol data, not an expectation.
            **({"expect": random_json(rng, 2)} if rng.random() < 0.4 else {}),
            "payload": random_json(rng, 1),
        },
        "expect": {
            "outcome": "ok",
            "output": random_json(rng, 1),
            "comparison": "bytes",
        },
    }
    # Fields a future vector might gain, or a careless author might add.
    for _ in range(rng.randrange(4)):
        vector[rng.choice(NEAR_MISSES)] = random_json(rng, 1)
    return vector


def leaked_keys(projected: dict) -> set[str]:
    return set(projected) - set(projection.PROJECTED_FIELDS)


class ProjectionPropertyTest(unittest.TestCase):
    def setUp(self):
        self.rng = random.Random(SEED)

    def test_no_projection_carries_anything_but_the_three_fields(self):
        for case in range(CASES):
            vector = random_vector(self.rng)
            projected = projection.project(vector)
            with self.subTest(case=case):
                self.assertEqual(
                    leaked_keys(projected), set(),
                    f"seed={SEED} case={case}: projection carried "
                    f"{sorted(leaked_keys(projected))}")
                self.assertNotIn("expect", projected)

    def test_input_survives_untouched(self):
        # The rule is about the authored expectation, not about a key named
        # `expect` that the operation legitimately needs. A projection that
        # reached inside `input` would corrupt the vector it was protecting.
        for case in range(CASES):
            vector = random_vector(self.rng)
            projected = projection.project(vector)
            with self.subTest(case=case):
                self.assertEqual(projected["input"], vector["input"],
                                 f"seed={SEED} case={case}: input was altered")

    def test_projection_survives_a_file_round_trip(self):
        # It is written to a file for the runner to read, so leaking through
        # serialization would be as bad as leaking through the dict.
        for case in range(CASES):
            vector = random_vector(self.rng)
            written = json.loads(json.dumps(projection.project(vector)))
            with self.subTest(case=case):
                self.assertEqual(leaked_keys(written), set(),
                                 f"seed={SEED} case={case}: leaked through JSON")

    def test_field_order_is_fixed(self):
        # A harness decision recorded in P-001 §4.2, not a §6 requirement: §6
        # fixes the field set a runner receives, not its serialized order. The
        # reason to fix it anyway is that two harness runs must write
        # byte-identical projections, or a runner that digests its input sees a
        # difference the corpus did not intend.
        for case in range(CASES):
            projected = projection.project(random_vector(self.rng))
            with self.subTest(case=case):
                self.assertEqual(tuple(projected), projection.PROJECTED_FIELDS)


class ProjectionShapeTest(unittest.TestCase):
    def test_a_vector_missing_a_projected_field_raises(self):
        # Better than emitting a partial projection: a runner handed a vector
        # with no operation cannot report a result, and the harness would be
        # judging its own omission.
        for missing in projection.PROJECTED_FIELDS:
            vector = {f: {} for f in projection.PROJECTED_FIELDS}
            del vector[missing]
            with self.subTest(missing=missing):
                with self.assertRaises(KeyError):
                    projection.project(vector)

    def test_the_real_fixtures_project_cleanly(self):
        fixtures = Path(__file__).resolve().parent / "fixtures" / "valid"
        vectors = sorted(fixtures.rglob("*.json"))
        self.assertTrue(vectors, "no fixtures to project")
        for path in vectors:
            vector = json.loads(path.read_text(encoding="utf-8"))
            with self.subTest(vector=path.name):
                self.assertEqual(leaked_keys(projection.project(vector)), set())


if __name__ == "__main__":
    unittest.main()
