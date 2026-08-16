"""The committed `suite/` section still matches its author (P-001 issue 13).

    python3 -m unittest discover -s conformance/tests

Same discipline as [`test_message_section.py`](test_message_section.py): the
bytes come from [`tools/author_suite.py`](../../tools/author_suite.py) by way of
[`tools/author_vectors.py`](../../tools/author_vectors.py), and `--check` keeps
the committed vectors and the tool that produced them from drifting apart.

What this section asserts beyond that is **where** a rejection happens. A header
is read at §4 step 3, before there is a signature to rely on, and nothing else
can be judged until step 4 — so an unregistered suite fails earlier than a bad
signature does. A vector that got the step wrong would still lint, still reject,
and still be wrong about the thing the section exists to pin down.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
AUTHOR = REPO / "tools" / "author_suite.py"
SECTION = REPO / "conformance" / "corpus" / "suite"

# core-model.md §5.2.1's closed vocabulary, embedded rather than read from the
# document being checked against.
EXTERNAL_REASONS = frozenset({
    "malformed", "unsupported_version", "unsupported_suite", "routing_mismatch",
    "expired", "structurally_invalid", "unauthenticated", "unavailable",
})


def vectors() -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8"))
            for p in sorted(SECTION.rglob("*.json"))]


def by_id() -> dict[str, dict]:
    return {v["id"]: v for v in vectors()}


class AuthoredSectionTest(unittest.TestCase):
    def test_the_committed_section_matches_its_author(self):
        result = subprocess.run([sys.executable, str(AUTHOR), "--check"],
                                capture_output=True, text=True, cwd=str(REPO))
        self.assertEqual(result.returncode, 0,
                         f"{result.stdout}\n{result.stderr}")

    def test_the_section_is_not_empty(self):
        self.assertGreater(len(vectors()), 0)


class RejectionTest(unittest.TestCase):
    def rejections(self):
        return [v for v in vectors() if v["expect"]["outcome"] == "rejected"]

    def test_every_external_reason_is_in_the_vocabulary(self):
        for vector in self.rejections():
            with self.subTest(vector=vector["id"]):
                self.assertIn(
                    vector["expect"]["rejection"]["wire"]["external_reason"],
                    EXTERNAL_REASONS)

    def test_the_internal_reason_is_never_the_external_one(self):
        for vector in self.rejections():
            rejection = vector["expect"]["rejection"]
            with self.subTest(vector=vector["id"]):
                self.assertNotEqual(rejection["internal_reason"],
                                    rejection["wire"]["external_reason"])


class OrderingTest(unittest.TestCase):
    """Where each rejection happens, which is this section's subject.

    `crypto-suites.md` §3: the header is the only attacker-controlled data a
    verifier touches while it has no signature to rely on. So what it declares
    is checked at §4 step 3, and everything else waits for step 4 — including
    the payload, which §2.1 forbids parsing until the bytes verify. A vector
    asserting the wrong step would still reject, and would still be wrong about
    the ordering the suite's whole design rests on.
    """

    def test_what_the_header_declares_is_rejected_before_verification(self):
        name = "suite/downgrade/unregistered-suite"
        self.assertEqual(by_id()[name]["expect"]["rejection"]["step"], 3)

    def test_what_only_the_signature_can_settle_is_rejected_after_verification(self):
        # Everything that needs the signature checked first lands at step 4, and
        # nothing here may claim step 3: a verifier at step 3 has read a header
        # and nothing else.
        for name in ("suite/verify/tampered-payload",
                     "suite/verify/tampered-header",
                     "suite/verify/tampered-signature",
                     "suite/keys/unresolvable"):
            with self.subTest(vector=name):
                self.assertEqual(by_id()[name]["expect"]["rejection"]["step"], 4)

    def test_authentication_causes_map_to_one_class(self):
        # §5.2.1 collapses an unresolvable key and an invalid signature into one
        # class so a requester cannot probe which identities a custodian holds.
        #
        # **This does not establish that they are indistinguishable**, and the
        # distinction matters. These vectors project `status` and
        # `external_reason` only, so comparing them across causes compares two
        # constants -- exactly the vacuous check CLAUDE.md warns about, and what
        # `harness lint`'s cross-vector report means when it says a partial
        # response "cannot detect a receipt-level divergence".
        #
        # What is asserted is the mapping: every authentication cause here
        # reaches the same class. Uniformity of the whole response, receipt
        # included, is `denial/`'s -- P-009's to author, and the one section
        # `vector.schema.json` forbids from projecting, for this reason.
        authentication = [
            v for v in vectors()
            if v["expect"]["outcome"] == "rejected"
            and v["expect"]["rejection"]["internal_reason"] in {
                "signature_invalid", "key_unresolvable"}
        ]
        self.assertGreaterEqual(len(authentication), 4)
        self.assertEqual(
            {v["expect"]["rejection"]["wire"]["external_reason"]
             for v in authentication},
            {"unauthenticated"})


class StructurallyInvalidTest(unittest.TestCase):
    """Every case §5.2.1 gives `structurally_invalid` to.

    E-34 introduced the value for three cases that *parsed*, and
    [E-46](../../docs/open-escalations.md) moved the line: the class is
    separated from `malformed` by **what is wrong**, not by whether the message
    parsed. `malformed` is an envelope or a verified core object -- a
    requester's serializer. `structurally_invalid` is the signed container or
    the protected header, which `crypto-suites.md` §3 defines -- a requester's
    suite implementation.

    That is what admits the container cases. A `signed` string that will not
    split into three decodable segments has not parsed either, and calling it
    `malformed` would send a requester to the wrong half of its own code.

    Two kinds are caught at §4 step 3, before any signature is checked -- the
    container, and a header that is not §3's object -- so neither is an
    authenticated message. The disagreements need the parsed payload and are
    caught at step **5a**, which E-35 added for symmetry with the response
    order's 4a.
    """

    # Every cause §5.2.1 gives `structurally_invalid` for. E-46 added the first
    # three: the line moved from *did the message parse* to *what is wrong with
    # it*, and a container that will not split is the suite implementation's
    # fault rather than the envelope's.
    CASES = ("suite/verify/not-three-segments",
             "suite/verify/header-not-base64url",
             "suite/verify/payload-not-base64url",
             "suite/verify/respelled-signature-segment",
             "suite/verify/header-not-an-object",
             "suite/verify/header-member-not-a-string",
             "suite/downgrade/header-carries-alg",
             "suite/downgrade/header-payload-suite-mismatch",
             "suite/downgrade/header-payload-key-mismatch")

    def test_they_all_share_one_class(self):
        # §5.2.1 gives one value for every one of them: each is visible in the
        # message the requester itself produced, so putting the detail on the
        # wire would tell the receiver what it already holds -- at the cost of a
        # mapping both implementations must get identically right.
        self.assertEqual(
            {by_id()[name]["expect"]["rejection"]["wire"]["external_reason"]
             for name in self.CASES},
            {"structurally_invalid"})

    def test_each_records_a_different_internal_reason(self):
        # The wire collapses them; the responder's own record must not, or the
        # separation core-model.md §5.2 requires between the two halves has been
        # lost in the direction that matters for an audit.
        internal = [by_id()[name]["expect"]["rejection"]["internal_reason"]
                    for name in self.CASES]
        self.assertEqual(len(set(internal)), len(self.CASES))

    def test_the_header_only_case_is_caught_before_verification(self):
        # `alg` is visible in the header alone, so it needs no signature and §4
        # step 3 has already read the header.
        rejection = by_id()["suite/downgrade/header-carries-alg"]["expect"]["rejection"]
        self.assertEqual(rejection["step"], 3)

    def test_the_disagreements_are_caught_at_step_5a(self):
        # They need the parsed object, so they cannot precede step 5, and they
        # precede every step that acts on a payload field. E-35 added 5a for
        # that, symmetric with the response order's 4a.
        for name in ("suite/downgrade/header-payload-suite-mismatch",
                     "suite/downgrade/header-payload-key-mismatch"):
            with self.subTest(vector=name):
                self.assertEqual(
                    by_id()[name]["expect"]["rejection"]["step"], "5a")


class ExpectedStateTest(unittest.TestCase):
    """What P-003 §6 names that this section does not have.

    `.github/workflows/checks.yml` prescribes an assertion over the expected
    state rather than a job that is red by design. These turn red when the thing
    blocking each is removed, which is when to author the group and delete the
    assertion.
    """

    def test_rfc8032_has_no_group_yet(self):
        # It needs an operation for signing a raw message, and P-001 §4.5's
        # vocabulary is protocol-level. Adding one is issue 17's, which settles
        # vocabulary additions as a single change.
        self.assertFalse((SECTION / "rfc8032").exists(),
                         "suite/rfc8032/ landed — issue 17 has presumably added "
                         "a raw-signing operation, so delete this assertion")

    def test_no_below_floor_downgrade_vector_yet(self):
        # A vector asserting that a suite below the verifier's floor is rejected
        # needs a second registered suite to be below it. With one registered
        # and active, such a vector could only assert a floor nobody can
        # configure -- and it would look like coverage while testing nothing.
        premature = [name for name in by_id()
                     if name.startswith("suite/downgrade/below-floor")]
        self.assertEqual(premature, [],
                         "a below-floor vector landed — a second suite has "
                         "presumably been registered, so delete this assertion")

    def test_status_has_no_group_yet(self):
        # It needs a deprecated or withdrawn suite to assert against, and
        # crypto-suites.md §3 registers exactly one, active.
        self.assertFalse((SECTION / "status").exists(),
                         "suite/status/ landed — a second suite has presumably "
                         "been registered, so delete this assertion")

class RejectionVocabularyTest(unittest.TestCase):
    """`testdata/rejection-vocabulary.txt` is the corpus's own mapping, extracted.

    Every rejection vector names an internal reason and the wire value a
    requester receives. Both implementations have to agree on that mapping or a
    vector passes in one and fails in the other for a reason no runner reports
    usefully -- so it is a fixture, read by all three.

    Derived rather than authored: this test rebuilds it from the corpus and
    fails if the committed file differs, which is what stops the fixture and the
    vectors drifting apart.
    """

    def mapping(self):
        rows = {}
        for path in sorted((REPO / "conformance" / "corpus").rglob("*.json")):
            vector = json.loads(path.read_text("utf-8"))
            rejection = vector.get("expect", {}).get("rejection")
            if not rejection:
                continue
            step = rejection.get("step")
            rows[rejection["internal_reason"]] = (
                rejection["wire"]["external_reason"],
                str(step) if step is not None else "-")
        return rows

    def test_no_internal_reason_has_two_wire_values(self):
        # The direction that would be a defect. Many internal reasons share one
        # wire value, which is correct; one reason with two values means a
        # requester can tell two causes apart through a value that is supposed
        # to collapse them.
        seen = {}
        for path in sorted((REPO / "conformance" / "corpus").rglob("*.json")):
            vector = json.loads(path.read_text("utf-8"))
            rejection = vector.get("expect", {}).get("rejection")
            if not rejection:
                continue
            reason = rejection["internal_reason"]
            wire = rejection["wire"]["external_reason"]
            if reason in seen:
                self.assertEqual(seen[reason], wire, f"{reason} in {vector['id']}")
            seen[reason] = wire

    def test_the_fixture_matches_the_corpus(self):
        expected = "\n".join(
            f"{reason}  {wire}  {step}"
            for reason, (wire, step) in sorted(self.mapping().items())) + "\n"
        self.assertEqual(
            (REPO / "testdata" / "rejection-vocabulary.txt").read_text("utf-8"),
            expected,
            "regenerate testdata/rejection-vocabulary.txt from the corpus")

if __name__ == "__main__":
    unittest.main()
