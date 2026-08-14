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
    "expired", "unauthenticated", "unavailable",
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

    def test_authentication_failures_are_indistinguishable_on_the_wire(self):
        # §5.2.1 collapses an unresolvable key and an invalid signature into
        # one class so a requester cannot probe which identities a custodian
        # holds. Asserted across causes rather than per cause: a per-vector
        # check cannot catch a divergence between two of them.
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


class ExpectedStateTest(unittest.TestCase):
    """What P-003 §5 names that this section does not have.

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

    def test_the_structurally_invalid_cases_are_absent(self):
        # All three reject and none has a class in core-model.md §5.2.1. In each
        # the declared suite is registered and acceptable, so
        # `unsupported_suite` does not fit; the key resolved and the signature
        # verified, so `unauthenticated` does not; and they parse cleanly, so
        # `malformed` fits only by stretching. What they share is being
        # structurally invalid while authentic, which the vocabulary has no
        # value for. E-34 decides it, and picking one here would settle in the
        # corpus what belongs in `spec/`.
        present = set(by_id())
        for name in ("suite/downgrade/header-carries-alg",
                     "suite/downgrade/header-payload-suite-mismatch",
                     "suite/downgrade/header-payload-key-mismatch"):
            with self.subTest(vector=name):
                self.assertNotIn(name, present,
                                 "E-34 has presumably closed — delete this and "
                                 "assert the class it decided")

    def test_status_has_no_group_yet(self):
        # It needs a deprecated or withdrawn suite to assert against, and
        # crypto-suites.md §3 registers exactly one, active.
        self.assertFalse((SECTION / "status").exists(),
                         "suite/status/ landed — a second suite has presumably "
                         "been registered, so delete this assertion")


if __name__ == "__main__":
    unittest.main()
