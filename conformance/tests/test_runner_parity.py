"""The Rust and Go runners implement the contract identically (P-001 issue 19).

    cargo build && go build -o target/q2d-go ./cmd/q2d-conform
    python3 -m unittest discover -s conformance/tests

**Skipped when the binaries are absent**, which is the usual case in the
Python-only CI job and on a checkout without either toolchain. The rust-and-go
job builds them and runs this, so the assertions below are enforced somewhere
even though they cannot be enforced everywhere.

## What this is for

`harness cross` compares two runners over one corpus, and a disagreement is
supposed to mean *the two implementations read the specification differently*.
That inference only holds if everything **around** the protocol is already
identical — if one runner accepted a duplicate object key and the other refused
it, `cross` would report a divergence about JSON, not about Q2D.

So this asserts the non-protocol half of
[`RUNNER-CONTRACT.md`](../RUNNER-CONTRACT.md) is the same in both: same exit
code, same acceptance, same refusal, on inputs chosen because a permissive
implementation would differ on them. Neither implements any Q2D behaviour yet,
which is exactly when this is worth pinning down — the parity is established
before there is anything to blame it on.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNERS = {
    "rust": REPO / "target" / "debug" / "q2d-conform",
    "go": REPO / "target" / "q2d-go",
}

VALID = {"id": "message/sign/query-minimal", "operation": "sign_query", "input": {}}

# Each case is a document and the exit code the contract requires. They are
# chosen so that a runner leaning on a permissive JSON library would differ:
# `encoding/json` keeps the last duplicate key silently, and most parsers accept
# at least one of NaN or a trailing document.
CASES = {
    "a projection": (json.dumps(VALID), 0),
    "an unprojected vector": (json.dumps(dict(VALID, expect={"outcome": "ok"})), 1),
    "an unknown operation": (json.dumps(dict(VALID, operation="http_exchange")), 1),
    "a missing input": (json.dumps({k: v for k, v in VALID.items() if k != "input"}), 1),
    "a non-string id": (json.dumps(dict(VALID, id=7)), 1),
    "a duplicate key": ('{"id":"a","id":"b","operation":"digest","input":{}}', 1),
    "a nested duplicate key": (
        '{"id":"a","operation":"digest","input":{"x":1,"x":2}}', 1),
    "NaN": ('{"id":"a","operation":"digest","input":{"x":NaN}}', 1),
    "Infinity": ('{"id":"a","operation":"digest","input":{"x":Infinity}}', 1),
    "a trailing document": (json.dumps(VALID) + " {}", 1),
    "an unescaped control character": (
        '{"id":"a\nb","operation":"digest","input":{}}', 1),
    "a top-level array": ("[]", 1),
    # Both found by review rather than by this list, which is the reason the
    # list is worth extending rather than trimming. Go's `string(data)` replaces
    # malformed UTF-8 with U+FFFD where Rust's `read_to_string` refuses it, and
    # Rust rejected the first half of a surrogate pair where Go decoded the
    # pair — two divergences about *encoding* that `harness cross` would have
    # reported as a disagreement about Q2D.
    "a lone high surrogate": (
        '{"id":"a\\ud83d","operation":"digest","input":{}}', 1),
    "a lone low surrogate": (
        '{"id":"a\\ude00","operation":"digest","input":{}}', 1),
}

# RFC 8259 §6's grammar admits none of these, and `f64::from_str` accepts every
# one — which is why the Rust runner walks the grammar rather than delegating.
# `encoding/json` refuses them all, so a delegating runner would have answered
# projections the other rejects.
for _bad in ("01", "1.", ".5", "+1", "-", "1e", "1e+", "00"):
    CASES[f"the number {_bad!r}"] = (
        '{"id":"a","operation":"digest","input":{"x":' + _bad + '}}', 1)

# A valid surrogate pair is a character, and both must accept it: RFC 8259 §7
# encodes every non-BMP character this way, so a runner refusing one would
# refuse a legitimate vector.
ACCEPTED = {
    "a surrogate pair": '{"id":"\\ud83d\\ude00","operation":"digest","input":{}}',
    # A valid RFC 8259 number outside float64's range. `encoding/json` refuses
    # it unless told `UseNumber`, and the Rust scanner validates only the
    # grammar -- so a runner that converted would reject a projection the other
    # answers. Neither has any use for a numeric value.
    "a number beyond float64":
        '{"id":"a","operation":"digest","input":{"x":1e400}}',
    "a number with many digits":
        '{"id":"a","operation":"digest","input":{"x":'
        + "1" * 400 + '}}',
}

# Bytes rather than text, because the point is that they are not valid UTF-8 and
# so cannot be written as a str.
MALFORMED_UTF8 = b'{"id":"a\xff\xfe","operation":"digest","input":{}}'

available = {name: path for name, path in RUNNERS.items() if path.exists()}


def answer(runner: Path, document) -> tuple[int, str]:
    mode = "wb" if isinstance(document, bytes) else "w"
    with tempfile.NamedTemporaryFile(mode, suffix=".json", delete=False) as f:
        f.write(document)
        path = f.name
    try:
        done = subprocess.run([str(runner), path], capture_output=True, text=True)
        return done.returncode, done.stdout
    finally:
        Path(path).unlink(missing_ok=True)


@unittest.skipUnless(len(available) == 2,
                     f"needs both runners built; found {sorted(available) or 'none'}")
class ParityTest(unittest.TestCase):
    def test_both_agree_on_every_contract_case(self):
        for label, (document, expected) in CASES.items():
            with self.subTest(case=label):
                codes = {name: answer(path, document)[0]
                         for name, path in available.items()}
                self.assertEqual(set(codes.values()), {expected},
                                 f"{label}: {codes}")

    def test_both_accept_what_the_specification_permits(self):
        # A list of refusals alone would be satisfied by a runner that refused
        # everything, and a runner refusing valid vectors is worse than a
        # permissive one: it fails a conforming producer.
        for label, document in ACCEPTED.items():
            with self.subTest(case=label):
                codes = {name: answer(path, document)[0]
                         for name, path in available.items()}
                self.assertEqual(set(codes.values()), {0}, f"{label}: {codes}")

    def test_both_refuse_malformed_utf8(self):
        codes = {name: answer(path, MALFORMED_UTF8)[0]
                 for name, path in available.items()}
        self.assertEqual(set(codes.values()), {1}, codes)

    def test_both_report_the_same_result_for_a_projection(self):
        # Same `vector_id`, same `outcome`. `detail` and `implementation` differ
        # by design -- a runner names itself, and `cross` does not compare
        # either, because a divergence in how two runners describe themselves is
        # not a divergence about Q2D.
        results = {name: json.loads(answer(path, json.dumps(VALID))[1])
                   for name, path in available.items()}
        for field in ("vector_id", "outcome"):
            with self.subTest(field=field):
                self.assertEqual({r[field] for r in results.values()},
                                 {VALID["id"] if field == "vector_id" else "error"})
        self.assertEqual({r["implementation"]["name"] for r in results.values()},
                         {"q2d-rust", "q2d-go"},
                         "each runner names itself, so a result can be attributed")

    def test_neither_answers_a_vector_yet(self):
        # The state this file exists to record, and the assertion that turns red
        # the day it stops being true -- which is the day `cross` starts meaning
        # something and P-001 issue 19 can be finished.
        for name, path in available.items():
            with self.subTest(runner=name):
                result = json.loads(answer(path, json.dumps(VALID))[1])
                self.assertEqual(result["outcome"], "error",
                                 "a runner learned to answer — issue 19's "
                                 "cross-verification is now buildable, and this "
                                 "assertion should be replaced by it")


if __name__ == "__main__":
    unittest.main()
