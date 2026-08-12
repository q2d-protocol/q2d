"""Corpus self-checks: every vector is well formed and cites something real.

Lint is the corpus's own fail-closed path. A vector that cannot be validated is
rejected, not passed through with a warning.

This module carries the checks the vector schema cannot express by itself --
agreement between a vector's id, its section, and where it sits on disk, and
whether its citations resolve to a claim, a class, or a specification file that
exists. A citation that points at nothing is worse than no citation: it reads as
traceability in a table nobody re-derives.

P-001 issue 5 owns the remaining `harness lint` behaviour in P-001 §8.
"""

from __future__ import annotations

import json
import re
from calendar import monthrange
from datetime import datetime, timedelta
from pathlib import Path

import cross_vector
import schema as schema_module

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = REPO_ROOT / "conformance" / "vector.schema.json"
CLAIMS_PATH = REPO_ROOT / "spec" / "claims.md"
CLASSES_PATH = REPO_ROOT / "spec" / "conformance-classes.md"

# Citations resolve against both, because a vector may exercise something the
# threat model names rather than the specification.
CITABLE_DIRS = ("spec", "threat-model")

CLAIM_RE = re.compile(r"\bQ2D-(?:C|NC)-[0-9]{2}\b")
CLASS_RE = re.compile(r"\bCC-[0-9]{1,2}\b")
SPEC_CITATION_RE = re.compile(r"^([a-z0-9-]+\.md)#(.+)$")
# A numbered heading at any depth: '## 4. Processing order', '#### 2.4.1 The...'
HEADING_RE = re.compile(r"^#{1,6}\s+([0-9]+(?:\.[0-9]+)*)\b", re.MULTILINE)


# Both live in corpus.py, so `lint` and `run` cannot disagree about what a
# vector file is -- in the one component whose job is deciding whether two
# things agree.
import corpus
from corpus import CorpusError, parse_strictly  # noqa: E402,F401


def load_schema() -> dict:
    try:
        loaded = parse_strictly(SCHEMA_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CorpusError(f"vector schema not found at {SCHEMA_PATH}") from exc
    except ValueError as exc:  # JSONDecodeError is a ValueError
        raise CorpusError(f"vector schema is not valid JSON: {exc}") from exc
    # Fail before judging anything, rather than silently under-enforcing.
    schema_module.assert_supported(loaded)
    return loaded


def known_identifiers() -> tuple[set[str], set[str]]:
    """Claim and class identifiers, read from spec/ rather than restated here."""
    claims = set(CLAIM_RE.findall(CLAIMS_PATH.read_text(encoding="utf-8")))
    classes = set(CLASS_RE.findall(CLASSES_PATH.read_text(encoding="utf-8")))
    if not claims or not classes:
        raise CorpusError("no identifiers found in spec/; the citation check would pass vacuously")
    return claims, classes


def citable_sections() -> dict[str, set[str]]:
    """Numbered headings per citable document, read rather than restated."""
    sections: dict[str, set[str]] = {}
    for directory in CITABLE_DIRS:
        for path in sorted((REPO_ROOT / directory).glob("*.md")):
            sections[path.name] = set(HEADING_RE.findall(path.read_text(encoding="utf-8")))
    return sections


def citation_errors(vector: dict, claims: set[str], classes: set[str],
                    sections: dict[str, set[str]]) -> list[str]:
    errors = []
    for citation in vector.get("requirement", []):
        if not isinstance(citation, str):
            continue  # the schema already reported this
        if CLAIM_RE.fullmatch(citation):
            if citation not in claims:
                errors.append(f"requirement: {citation} is not a claim in spec/claims.md")
        elif CLASS_RE.fullmatch(citation):
            if citation not in classes:
                errors.append(f"requirement: {citation} is not a class in spec/conformance-classes.md")
        else:
            match = SPEC_CITATION_RE.match(citation)
            if not match:
                continue  # the schema's pattern already reported this
            document, section = match.groups()
            if document not in sections:
                errors.append(
                    f"requirement: {citation} cites {document}, which is not a document in "
                    + " or ".join(f"{d}/" for d in CITABLE_DIRS))
            elif section not in sections[document]:
                # A citation to a section that does not exist is worse than no
                # citation: it reads as traceability to anyone who does not
                # re-derive it.
                errors.append(f"requirement: {citation} cites a section {document} does not have")
    return errors


def placement_errors(vector: dict, path: Path, corpus_root: Path) -> list[str]:
    """The id, the section, and the directory must all say the same thing."""
    errors = []
    section = vector.get("section")
    vector_id = vector.get("id")

    if isinstance(vector_id, str) and isinstance(section, str):
        if vector_id.split("/", 1)[0] != section:
            errors.append(f"id: {vector_id!r} does not start with its section {section!r}")

    if isinstance(section, str):
        relative = path.relative_to(corpus_root).parts
        if len(relative) < 2 or relative[0] != section:
            errors.append(f"section: {section!r} but the file sits at {'/'.join(relative)}")

    return errors


# core-model.md §6's reduced receipt: "exactly five fields, and no others".
REDUCED_RECEIPT_FIELDS = frozenset({"request_digest", "decision_class",
                                    "decided_at", "responder",
                                    "signature_suite"})


def receipt_errors(vector: dict) -> list[str]:
    """A deny receipt a vector asserts must be the shape §6 defines.

    Not a *narrower* comparison -- a wrong one. A vector may omit `receipt`
    entirely, which asserts nothing about it and is legitimate where response
    construction is not what the vector tests. But a vector that asserts a
    receipt with four fields, or with six, is asserting that a conforming
    implementation emits one, and core-model.md §6 says it does not: "exactly
    five fields, and no others", and "adding a field to it -- even an optional
    one -- is a specification change".

    The extra-field case is the one that matters most, and it is why this is an
    error rather than a note: a field present for some causes and absent for
    others is precisely the distinction normalization removes, and a
    variable-length one breaks the length guarantee §6 grounds in the shape.
    """
    expect = vector.get("expect")
    if not isinstance(expect, dict):
        return []                       # the schema is already reporting this
    rejection = expect.get("rejection")
    if not isinstance(rejection, dict):
        return []
    wire = rejection.get("wire")
    if not isinstance(wire, dict) or "receipt" not in wire:
        return []

    receipt = wire["receipt"]
    if not isinstance(receipt, dict):
        return [f"receipt: asserted as {type(receipt).__name__}, but "
                f"core-model.md §6's reduced shape is an object of five fields"]

    missing = sorted(REDUCED_RECEIPT_FIELDS - set(receipt))
    extra = sorted(set(receipt) - REDUCED_RECEIPT_FIELDS)
    errors = receipt_value_errors(receipt)
    if missing:
        errors.append(f"receipt: missing {', '.join(missing)} — core-model.md "
                      f"§6's reduced shape is exactly five fields. Omit "
                      f"`receipt` entirely to assert nothing about it")
    if extra:
        errors.append(f"receipt: carries {', '.join(extra)} — core-model.md §6 "
                      f"is 'exactly five fields, and no others', because a "
                      f"field present for some causes and absent for others "
                      f"reintroduces the distinction normalization removes")
    return errors


# core-model.md §5.2's deny response, in full. An *opaque* escalation is here
# too, not in the escalate set below: §5.3 says it "returns the same normalized
# envelope as §5.2 — including its receipt", and being indistinguishable from a
# denial is the entire point of it.
DENY_RESPONSE_FIELDS = frozenset({"status", "external_reason", "receipt",
                                  "signature"})

# §5.3's *explicit* escalation: "returns `status: escalate` with an opaque
# `pending_token` and `expires_at`", and "carries a receipt: the reduced shape
# §5.2 defines, with `decision_class: escalate`". It has no external_reason --
# it is "not denial-normalized and must never be described as such" -- so
# holding it to §5.2's field list would reject a correct vector.
EXPLICIT_ESCALATE_FIELDS = frozenset({"status", "pending_token", "expires_at",
                                      "receipt", "signature"})


def timestamp_forms(vectors) -> dict:
    """Every RFC 3339 spelling the corpus uses, and which vectors use it.

    No spelling is rejected: §6 says only "RFC 3339, second precision", so
    deciding between them here would settle a specification question in a lint
    rule. What *is* rejected is a corpus using more than one, which is
    defective whichever way §6 goes -- no implementation emits several, so none
    could satisfy such a corpus.
    """
    profiles: dict = {}
    for vector in vectors:
        body = vector.body if hasattr(vector, "body") else vector
        if not isinstance(body, dict):
            continue
        expect = body.get("expect")
        if not isinstance(expect, dict):
            continue
        rejection = expect.get("rejection")
        if not isinstance(rejection, dict):
            continue
        wire = rejection.get("wire")
        if not isinstance(wire, dict):
            continue
        receipt = wire.get("receipt")
        if not isinstance(receipt, dict):
            continue
        decided = receipt.get("decided_at")
        if isinstance(decided, str) and valid_timestamp(decided):
            profile = timestamp_profile(decided)
            if profile:
                profiles.setdefault(profile, []).append(str(body.get("id", "?")))
    return profiles


def receipt_coherence_errors(vector: dict) -> list[str]:
    """The receipt's class against the response's, wherever one is asserted.

    Not only in `denial/`: a `registry/` rejection carrying a receipt that
    says `escalate` behind a `deny` leaks the true outcome just as
    completely, and is no more conforming for being in another section.
    This lived inside the denial/-only value checks and reached nothing
    else.
    """
    expect = vector.get("expect")
    if not isinstance(expect, dict):
        return []
    rejection = expect.get("rejection")
    if not isinstance(rejection, dict):
        return []
    wire = rejection.get("wire")
    if not isinstance(wire, dict):
        return []
    receipt = wire.get("receipt")
    if not isinstance(receipt, dict):
        return []

    errors: list[str] = []
    status = wire.get("status")
    # The receipt's own field values are checked by `receipt_errors`, which
    # runs wherever a receipt is asserted rather than only here -- a
    # registry/ vector may carry one too, and an empty digest in it is no
    # more conforming for being in a different section.
    #
    # §5.3's boundary, quoted because nothing else in the specification is
    # put this strongly: "an opaque escalation must not be distinguishable
    # from any other outcome in that class by its receipt any more than by
    # its response... a receipt that recorded `escalate` for an outcome the
    # wire made uniform would defeat Q2D-C-08 through the evidence attached
    # to it, in the one place nobody looks for a normalization leak."
    #
    # So the receipt's class is not free of the response's. An explicit
    # escalation carries `decision_class: escalate` (§5.3); a denial --
    # including an opaque escalation, which is a denial on the wire --
    # carries the normalized class, which is what `external_reason` also
    # carries (§5.2 "the normalized class, not the true cause"; P-011 §4.1
    # "the normalized external class"). Two fields defined as the same
    # value that disagree would themselves be a distinction.
    decision = receipt.get("decision_class")
    if isinstance(decision, str) and decision:
        if status == "escalate":
            if decision != "escalate":
                errors.append(
                    f"wire.receipt.decision_class: {decision!r} on an "
                    f"explicit escalation — core-model.md §5.3 gives it "
                    f"'escalate'")
        elif decision == "escalate":
            errors.append(
                "wire.receipt.decision_class: 'escalate' on a response the "
                "wire made uniform — core-model.md §5.3 calls this out by "
                "name: it 'would defeat Q2D-C-08 through the evidence "
                "attached to it, in the one place nobody looks for a "
                "normalization leak'")
        else:
            external = wire.get("external_reason")
            if isinstance(external, str) and external and decision != external:
                errors.append(
                    f"wire.receipt.decision_class: {decision!r} but "
                    f"external_reason is {external!r} — both are defined "
                    f"as the normalized class (core-model.md §5.2, P-011 "
                    f"§4.1), so two values is itself a distinction")
    return errors


def response_shape_errors(vector: dict) -> list[str]:
    """Every rule about the *shape of an asserted response*, in one call.

    `run` applies these as well as the schema, because its own comparison logic
    depends on them: it decides whether a vector is a projection from the
    fields it asserts, and judges a receipt it has not checked. Relying on
    "lint would have caught it" in a mode that never calls lint is how a
    safeguard goes missing exactly when someone runs a corpus without linting
    it first.

    A list rather than two calls, so a third rule added to `lint` does not
    silently fail to reach `run` -- which has now happened twice.
    """
    errors: list[str] = []
    for rule in (denial_section_errors, extra_wire_field_errors,
                 receipt_errors, receipt_coherence_errors,
                 wire_value_errors):
        errors += rule(vector)
    return errors


def required_wire_fields(wire: dict) -> frozenset:
    """The whole response for the outcome this wire asserts.

    One function so `lint` and `run` cannot drift about it: lint uses it to
    require a whole response in `denial/`, and run uses it to decide whether a
    vector is a projection at all.

    A wire with **no `status`** has not said which response it is, so it gets
    the union: a projection asserting `pending_token` and `expires_at` is a
    partial explicit escalation, and measuring it against a denial's list would
    report §5.3's own fields as forbidden extras.
    """
    if not isinstance(wire, dict):
        return DENY_RESPONSE_FIELDS
    status = wire.get("status")
    if status == "escalate":
        return EXPLICIT_ESCALATE_FIELDS
    if status is None:
        return DENY_RESPONSE_FIELDS | EXPLICIT_ESCALATE_FIELDS
    return DENY_RESPONSE_FIELDS


def denial_section_errors(vector: dict) -> list[str]:
    """A `denial/` vector asserts the whole response, never a projection.

    Elsewhere a subset is legitimate: a `registry/` vector exercises whether a
    predicate evaluates and rejects correctly, and the envelope around the
    rejection is not its subject. Here it is the *only* subject, and a subset
    is not a narrower test but a vacuous one -- `status` and `external_reason`
    are both fixed by the normalized class, so a vector asserting only those
    compares two constants across every cause and cannot fail.

    core-model.md §5.3 puts the leak where a projection is silent: "a receipt
    that recorded escalate for an outcome the wire made uniform would defeat
    Q2D-C-08 through the evidence attached to it, in the one place nobody looks
    for a normalization leak."
    """
    if vector.get("section") != "denial":
        return []
    expect = vector.get("expect")
    if not isinstance(expect, dict) or expect.get("outcome") != "rejected":
        return []
    rejection = expect.get("rejection")
    if not isinstance(rejection, dict):
        return []
    wire = rejection.get("wire")
    if not isinstance(wire, dict):
        return []

    # Which whole response depends on which outcome the vector asserts, and
    # the two are different shapes rather than one with optional parts.
    escalating = wire.get("status") == "escalate"
    required = required_wire_fields(wire)
    where = "§5.3's explicit escalation" if escalating else "§5.2's whole response"

    missing = sorted(required - set(wire))
    if missing:
        detail = (" A subset compares only fields the normalized class already "
                  "fixes, so it cannot fail." if not escalating else "")
        return [f"wire: missing {', '.join(missing)} — a denial/ vector asserts "
                f"core-model.md {where}.{detail}"]

    # Extra fields are `extra_wire_field_errors`, which runs for every vector:
    # §5's closure is a property of the response, not of this section. Values
    # likewise, in `wire_value_errors`.
    return []


def extra_wire_field_errors(vector: dict) -> list[str]:
    """A response may carry no field §5 does not list, in any section.

    §5.2 is "exactly four fields, and no others" and §5.3's explicit escalation
    exactly five, on the reasoning §6 already gave for the receipt: a field
    present for some causes and absent for others reintroduces the distinction
    normalization removes, and a field set that is not enumerated cannot be
    size-bounded.

    **Not scoped to `denial/`,** unlike the rule that a whole response must be
    asserted. Which fields a vector must assert depends on what it is testing;
    which fields *exist* does not. A `registry/` vector asserting a projection
    plus a `retry_after` is asserting a field the response does not have, and
    an implementation would be scored against it.
    """
    expect = vector.get("expect")
    if not isinstance(expect, dict):
        return []
    rejection = expect.get("rejection")
    if not isinstance(rejection, dict):
        return []
    wire = rejection.get("wire")
    if not isinstance(wire, dict):
        return []

    allowed = required_wire_fields(wire)
    extra = sorted(set(wire) - allowed)
    if not extra:
        return []
    where = ("§5.3's explicit escalation" if wire.get("status") == "escalate"
             else "§5.2's response")
    return [f"wire: carries {', '.join(extra)} — core-model.md {where} is "
            f"exactly {len(allowed)} fields and no others, so a response that "
            f"can grow one has a field a producer can vary by cause"]


# §5.2 gives `status` one value on a denial; §5.3 gives an explicit escalation
# the other. Nothing else is an outcome a rejection vector can assert.
DENY_STATUS = ("deny", "escalate")

# §6: "RFC 3339, second precision". Checked as a format, not merely as a
# string, because §6 grounds the whole length guarantee in none of the reduced
# fields being variable-length -- and a timestamp carrying sub-second precision
# or a numeric offset is variable-length, which quietly removes it.
# RFC 3339 permits lowercase `t` and `z`, and §6 does not define an
# uppercase-only profile. Both are matched; which one a corpus may use is
# P-001 §10's question, and the answer here is the same as for the offset
# form -- allow either, report it, and fail a corpus that mixes.
RFC3339_SECOND = re.compile(
    r"\A(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})"
    r"(Z|z|[+-]\d{2}:\d{2})\Z")


def valid_timestamp(value: str) -> bool:
    """RFC 3339, second precision, `Z` -- as a shape *and* as a real instant.

    The shape carries §6's length argument: fixed width, which
    `2026-1-1T0:0:0Z` is not. Parsing carries the rest, because a regex over
    digit placement accepts `2026-99-99T99:99:99Z`, which no implementation
    emits and a vector must not assert.

    Second 60 at 23:59 is **accepted**, and no attempt is made to decide
    whether that particular leap second was really inserted. It cannot be
    decided statically -- which leap seconds exist is IERS data that changes
    after this file is written -- and it is the wrong question anyway: a vector
    *supplies* `decided_at`, no implementation's clock produces it, so what
    conformance turns on is whether an implementation parses RFC 3339, not
    whether the instant occurred.

A numeric offset is **accepted** and separately reported. §6 says "RFC 3339,
    second precision" and does not say `Z`; it also grounds the length
    guarantee in none of the reduced fields being variable-length, and
    `+00:00` is six characters where `Z` is one. So §6 arguably requires `Z` by
    implication while not saying it -- which is an open question (P-001 §10),
    and rejecting the offset form here would settle it in a lint rule and push
    both implementations toward an uncited profile. Reporting keeps it visible
    without deciding it, and makes a corpus split across the two forms
    impossible to author unnoticed.
    """
    matched = RFC3339_SECOND.match(value)
    if not matched:
        return False
    # strptime has no leap second, so the date is checked with the second
    # clamped. Everything else about the value is still validated -- and `:60`
    # is accepted only at 23:59, which is where RFC 3339 §5.7 puts it. Clamping
    # unconditionally would have blessed `00:00:60Z`, which is not an instant
    # and which one implementation could accept while another rejects: the
    # divergence this check exists to prevent, introduced by the check.
    year, month, day, hour, minute, second, offset = matched.groups()

    if offset not in ("Z", "z"):
        # The regex matches the offset's *shape*; these are its ranges.
        # Discarding it and parsing only the local time accepted `+99:99`.
        offset_hour, offset_minute = int(offset[1:3]), int(offset[4:6])
        if offset_hour > 23 or offset_minute > 59:
            return False

    if second == "60":
        # RFC 3339 §5.7 puts a leap second at 23:59 **UTC**, which is a
        # different wall time under an offset: `2016-12-31T15:59:60-08:00` is
        # the same instant as `2016-12-31T23:59:60Z` and is equally valid.
        # Checking the local fields rejected it. Whether *this* leap second was
        # inserted is still not knowable here -- see the docstring.
        shift = 0
        if offset not in ("Z", "z"):
            shift = (int(offset[1:3]) * 60 + int(offset[4:6])) * (
                -1 if offset[0] == "-" else 1)
        try:
            local_dt = datetime(int(year), int(month), int(day),
                                int(hour), int(minute))
        except ValueError:
            return False
        utc = local_dt - timedelta(minutes=shift)
        if (utc.hour, utc.minute) != (23, 59):
            return False
        # §5.7: ":60" occurs "at the end of months in which a leap second
        # occurs". The month end is fixed by the RFC and checked; *which*
        # months is IERS data that changes after this file is written, is not
        # statically decidable, and is deliberately not checked. That is the
        # line: what the grammar fixes, not what an announcement decides.
        if utc.day != monthrange(utc.year, utc.month)[1]:
            return False
        second = "59"
    try:
        datetime.strptime(f"{year}-{month}-{day}T{hour}:{minute}:{second}",
                          "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True


def timestamp_profile(value: str) -> str | None:
    """Which of RFC 3339's spellings this timestamp uses, as a label.

    RFC 3339 permits several forms of the same instant -- `T` or `t`, `Z` or
    `z` or a numeric offset -- and §6 says only "RFC 3339, second precision".
    Which one Q2D requires is P-001 §10. Until that is settled, no form is
    rejected and the *set in use* is what matters: a corpus carrying more than
    one is defective whichever way §6 goes, because no implementation emits
    more than one.
    """
    matched = RFC3339_SECOND.match(value)
    if not matched:
        return None
    separator = "T" if "T" in value[:11] else "t"
    terminator = matched.group(7)
    if terminator in ("Z", "z"):
        return f"…{separator}…{terminator}"
    return f"…{separator}…±hh:mm"


def nonempty_string(where: str, value) -> list[str]:
    if not isinstance(value, str):
        return [f"{where}: {type(value).__name__}, but core-model.md gives it a "
                f"string value"]
    if not value:
        return [f"{where}: empty — a vector asserting an empty value asserts "
                f"that a conforming implementation emits one"]
    return []


def wire_value_errors(vector: dict) -> list[str]:
    """The values §5.2 and §6 determine, for whatever the vector asserts.

    Presence alone would accept a vector asserting `status: "answer"` on a
    rejection, or an empty signature -- either of which would then be scored
    against both implementations as though it were a conforming response.

    **Only fields that are present.** Which fields a vector must assert depends
    on its section (`denial_section_errors`); what a field must *contain* does
    not, so a `registry/` projection asserting `status` and `external_reason`
    is held to those two exactly as a whole response is. This ran only for
    `denial/` and so reached neither.
    """
    expect = vector.get("expect")
    if not isinstance(expect, dict):
        return []
    rejection = expect.get("rejection")
    if not isinstance(rejection, dict):
        return []
    wire = rejection.get("wire")
    if not isinstance(wire, dict):
        return []

    errors: list[str] = []

    status = wire.get("status")
    if "status" in wire and status not in DENY_STATUS:
        errors.append(f"wire.status: {status!r} — core-model.md §5.2 gives a "
                      f"denial {DENY_STATUS[0]!r}, §5.3 an explicit escalation "
                      f"{DENY_STATUS[1]!r}, and a rejection asserts one of them")

    for field in ("external_reason", "signature", "pending_token", "expires_at"):
        if field in wire:
            errors += nonempty_string(f"wire.{field}", wire[field])

    if status == "escalate":
        if "external_reason" in wire:
            # Determinate, unlike extra fields in general (§10): §5.3 says an
            # explicit escalation "is **not** denial-normalized and must never
            # be described as such", and external_reason is the field that
            # describes an outcome as belonging to a normalized class.
            errors.append(
                "wire.external_reason: present on an explicit escalation — "
                "core-model.md §5.3 says one is 'not denial-normalized and "
                "must never be described as such', and this is the field that "
                "would describe it as such")

    receipt = wire.get("receipt")
    return errors


def receipt_value_errors(receipt: dict) -> list[str]:
    """The values §6 determines for a reduced receipt, wherever one appears."""
    errors: list[str] = []
    for field in sorted(REDUCED_RECEIPT_FIELDS & set(receipt)):
        errors += nonempty_string(f"wire.receipt.{field}", receipt[field])

    decided = receipt.get("decided_at")
    if isinstance(decided, str) and decided and not valid_timestamp(decided):
        errors.append(
            f"wire.receipt.decided_at: {decided!r} is not RFC 3339 at second "
            f"precision — core-model.md §6 grounds the length guarantee in "
            f"none of the reduced fields being variable-length, and this is "
            f"the one that can vary")
    return errors


def section_errors(vector: dict) -> list[str]:
    """Rules a section carries that the schema cannot express.

    `ordering/` exists to assert *which* step rejected (P-001 §5, §4.6). A
    vector there that states no step asserts nothing about ordering, which is
    the one thing its section is for -- and it would pass silently, because
    §4.8 holds a vector only to the step it states.
    """
    errors = []
    if vector.get("section") != "ordering":
        return errors

    expect = vector.get("expect")
    if not isinstance(expect, dict):
        return errors  # the schema is already reporting this one

    if expect.get("outcome") != "rejected":
        errors.append("section: an ordering/ vector asserts where a rejection "
                      "happened, so its outcome must be 'rejected'")
        return errors

    # These checks run alongside the schema's, not after them, so the vector
    # they are handed may be any shape at all. Reaching into a `rejection` that
    # is null or an integer would raise, and one malformed vector would abort
    # the run that was going to report it -- hiding every failure after it.
    rejection = expect.get("rejection")
    if not isinstance(rejection, dict):
        return errors  # the schema is already reporting this one
    if "step" not in rejection:
        errors.append("section: an ordering/ vector must state the step it "
                      "rejects at, or it asserts nothing about ordering")
    return errors


def vector_errors(vector, path: Path, corpus_root: Path, vector_schema: dict,
                  claims: set[str], classes: set[str],
                  sections: dict[str, set[str]]) -> list[str]:
    """Every way one vector is invalid, schema and otherwise.

    Shared with `coverage`, which must not count a vector the corpus rejects:
    a claim reported as covered by evidence lint refuses is exactly the
    overstatement claims.md's traceability rule exists to prevent. Cross-file
    checks -- duplicate identifiers -- stay in `lint`, because they are
    properties of a corpus rather than of a vector.
    """
    errors = schema_module.validate(vector, vector_schema)
    if isinstance(vector, dict):
        errors += placement_errors(vector, path, corpus_root)
        errors += citation_errors(vector, claims, classes, sections)
        errors += section_errors(vector)
        # The same list `run` applies, from the same place. Calling the rules
        # individually here is how the coherence rule reached `run` and not
        # `lint` -- two call sites, one of them updated.
        errors += response_shape_errors(vector)
    return errors


def lint(corpus_root: Path) -> int:
    """Validate every vector under `corpus_root`. Returns a process exit code."""
    if not corpus_root.is_dir():
        raise CorpusError(f"corpus directory not found: {corpus_root}")

    vector_schema = load_schema()
    claims, classes = known_identifiers()
    sections = citable_sections()

    print(f"linting {corpus_root} against {SCHEMA_PATH.name}\n")

    failures = 0
    seen: dict[str, Path] = {}
    vectors = []
    files = sorted(p for p in corpus_root.rglob("*.json") if p.is_file())

    for path in files:
        label = path.relative_to(corpus_root)
        try:
            vector = parse_strictly(path.read_text(encoding="utf-8"))
        except ValueError as exc:  # JSONDecodeError is a ValueError
            print(f"  FAIL  {label}\n          not valid JSON: {exc}")
            failures += 1
            continue

        vectors.append(corpus.Vector(path, path.relative_to(corpus_root), vector))
        errors = vector_errors(vector, path, corpus_root, vector_schema,
                               claims, classes, sections)
        if isinstance(vector, dict):
            vector_id = vector.get("id")
            if isinstance(vector_id, str):
                if vector_id in seen:
                    errors.append(f"id: {vector_id!r} already used by {seen[vector_id]}")
                else:
                    seen[vector_id] = label

        if errors:
            failures += 1
            print(f"  FAIL  {label}")
            for error in errors:
                print(f"          {error}")
        else:
            print(f"  ok    {label}")

    # Cross-vector assertions run over whatever parsed, after the per-vector
    # pass: they are properties of the corpus as a whole, and a corpus whose
    # own rejection vectors disagree cannot detect an implementation whose
    # rejections disagree.
    cross_errors, summaries = cross_vector.assertions(vectors)
    print("\ncross-vector")
    for summary in summaries:
        print(f"  {summary}")

    # Whether §6 requires `Z` is P-001 §10, and neither accepting nor rejecting
    # the offset form settles it. What can be said without settling it: a corpus
    # carrying *both* forms is defective whichever way §6 goes, because no
    # implementation can emit both -- so that fails, and either form alone is
    # reported and allowed.
    profiles = timestamp_forms(vectors)
    if profiles:
        print(f"  receipt timestamps: {', '.join(sorted(profiles))} — which "
              f"RFC 3339 spelling §6 requires is open (P-001 §10), so any one "
              f"is allowed")
    if len(profiles) > 1:
        listing = "; ".join(f"{form} in {', '.join(sorted(ids))}"
                            for form, ids in sorted(profiles.items()))
        cross_errors = list(cross_errors) + [
            f"receipt timestamps: the corpus uses {len(profiles)} spellings of "
            f"RFC 3339 — {listing}. Which one §6 requires is open (P-001 §10); "
            f"that no implementation emits several is not"]
    for error in cross_errors:
        print(f"  FAIL  {error}")

    # Counted separately from vector failures, because a cross-vector failure
    # belongs to no single vector: every vector in the group can be individually
    # correct and the group still wrong. Folding it into the per-vector count
    # would report a valid vector as invalid.
    print(f"\n{len(files) - failures}/{len(files)} vectors valid")
    if cross_errors:
        print(f"{len(cross_errors)} cross-vector assertion(s) failed")
    if failures or cross_errors:
        if failures:
            print(f"FAILED: {failures} vector(s) rejected")
        else:
            print("FAILED: the corpus is invalid as a whole")
        return 1
    if not files:
        # Vacuously clean, and worth saying: an empty corpus lints green and
        # proves nothing. `harness coverage` is what reports the emptiness.
        print("corpus is empty")
    return 0
