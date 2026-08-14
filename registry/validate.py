#!/usr/bin/env python3
"""Validate the reference predicate registry manifest.

Checks the manifest's internal consistency and executes every test vector
against a reference evaluation of its predicate. The vectors are the contract
the Rust and Go implementations are both built against, so a vector that is
wrong here is wrong in two places later.

    python3 registry/validate.py [path/to/manifest.json]
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import sys
from calendar import monthrange
from datetime import datetime, timedelta
from pathlib import Path

FAILURES: list[str] = []
CHECKS = 0

ALLERGENS = {
    "alcohol", "celery", "crustacean", "egg", "fish", "gluten", "lupin", "meat",
    "milk", "mollusc", "mustard", "nut", "peanut", "pork", "sesame", "shellfish",
    "soy", "sulphite",
}
CONTACT_CLASSES = ["none", "async", "synchronous"]
MIN_SLOT = timedelta(minutes=30)
MAX_CANDIDATES = 8


def check(ok: bool, label: str, detail: str = "") -> bool:
    global CHECKS
    CHECKS += 1
    print(("  ok    " if ok else "  FAIL  ") + label + (f"  [{detail}]" if detail else ""))
    if not ok:
        FAILURES.append(label)
    return ok


def canon(obj) -> bytes:
    """The deterministic production profile the entry digest is computed over."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def entry_digest(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_digest"}
    return "sha256:" + hashlib.sha256(canon(body)).hexdigest()


def has_float(obj) -> bool:
    if isinstance(obj, float):
        return True
    if isinstance(obj, dict):
        return any(has_float(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_float(v) for v in obj)
    return False


class NotATimestamp(Exception):
    """A value where a timestamp was expected. Reported, never a traceback."""


def ts(s: str) -> datetime:
    """Parse a timestamp, or raise something the caller can report.

    The eager scan above catches anything *shaped* like a date-time. A value
    that is not -- `"tomorrow"` in a field the schema declares `format:
    date-time` -- reaches here, and an unguarded `fromisoformat` would abort
    the sweep with a traceback instead of naming the file.
    """
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError) as exc:
        raise NotATimestamp(f"{s!r} is not a timestamp ({exc})") from None


# ---- reference evaluations -------------------------------------------------
# Deliberately naive. Their job is to pin the vectors' meaning, not to be an
# implementation; a real executor validates output against the effective domain
# and never reaches these on a rejected request.

def eval_menu_compatible(public, private):
    for item in public["menu"]:
        if not set(item["contains"]) & set(private["excludes"]):
            return True
    return False


def eval_availability_window(public, private):
    busy = [(ts(b["start"]), ts(b["end"])) for b in private["busy"]]
    for i, cand in enumerate(public["candidates"]):
        cs, ce = ts(cand["start"]), ts(cand["end"])
        if not any(bs < ce and cs < be for bs, be in busy):
            return i
    return None


def eval_contactable_for(public, private):
    for rule in private["rules"]:
        if rule["purpose_code"] == public["purpose_code"]:
            return rule["permits"]
    return "none"


def reject_reason(pid, public):
    """Validation a responder performs before private access."""
    if pid.endswith("menu-compatible"):
        menu = public.get("menu")
        if not menu:
            return "public_context_schema_violation"
        for item in menu:
            if set(item["contains"]) - ALLERGENS:
                return "public_context_schema_violation"
    elif pid.endswith("availability-window"):
        cands = public.get("candidates", [])
        if not cands or len(cands) > MAX_CANDIDATES:
            return "public_context_schema_violation"
        for c in cands:
            if ts(c["end"]) - ts(c["start"]) < MIN_SLOT:
                return "constraint_violation_minimum_slot_duration"
    elif pid.endswith("contactable-for"):
        allowed = {"social.event-planning", "social.introduction",
                   "commercial.enquiry", "logistics.delivery", "urgent.safety"}
        if public.get("purpose_code") not in allowed:
            return "public_context_schema_violation"
    return None


EVAL = {
    "menu-compatible": eval_menu_compatible,
    "availability-window": eval_availability_window,
    "contactable-for": eval_contactable_for,
}


def expected_capacity_mb(p, public):
    """Capacity in millibits, from the registry -- never from requester assertion.

    Recomputed here only to confirm the authored table is right. A responder
    reads the value; it never computes log2.
    """
    dom = p["answer_domain"]
    n = dom["cardinality"] if dom["kind"] == "enumerated" else len(public["candidates"]) + 1
    return math.ceil(1000 * math.log2(n))


# scope.md §4.1: `format: date-time` asserts, and the value it asserts is
# core-model.md §2.2's timestamp. Checked here so the reference manifest cannot
# drift from a rule spec/ now states -- the manifest is the one artifact every
# implementation will read as an example.
Q2D_TIMESTAMP = re.compile(r"\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")


# scope.md §4.1's profile, entire. Enforced here because the reference manifest
# is the artifact every implementation reads as an example, and an example that
# drifts from the specification teaches the drift.
SCHEMA_PROFILE = frozenset({
    "$schema", "type", "required", "properties", "additionalProperties",
    "enum", "items", "minItems", "maxItems", "minLength", "maxLength",
    "minimum", "maximum", "format",
})
DIALECT = "https://json-schema.org/draft/2020-12/schema"
JSON_TYPES = frozenset({"null", "boolean", "object", "array", "number",
                        "string", "integer"})


def schema_keywords(schema, path):
    """Every keyword a schema uses, with where it sits.

    A boolean subschema yields a name no profile contains, so it is rejected
    rather than passed over: `true` and `false` are schemas that accept or deny
    everything, with no authored vocabulary to check.

    Only the schema's own keywords -- the *names* under `properties` are the
    author's field names, not JSON Schema vocabulary, so they are walked into
    rather than checked.
    """
    if not isinstance(schema, dict):
        # `true` and `false` are valid JSON Schema subschemas, accepting or
        # denying everything with no keyword to check. §4.1's profile is a list
        # of keywords, so a schema with none is outside it -- reported under a
        # name no profile contains rather than skipped.
        yield "<boolean subschema>", path
        return
    for key, value in schema.items():
        if key == "properties":
            yield key, path
            # A non-dict here is what the shape check reports; walking into it
            # would crash the sweep that was about to name it.
            if isinstance(value, dict):
                for name, sub in value.items():
                    yield from schema_keywords(sub, f"{path}.properties.{name}")
        elif key == "items":
            yield key, path
            yield from schema_keywords(value, f"{path}.items")
        else:
            yield key, path


def schema_values(schema):
    """Every (keyword, value) pair a schema uses, at any depth."""
    if not isinstance(schema, dict):
        return
    for key, value in schema.items():
        yield key, value
        if key == "properties" and isinstance(value, dict):
            for sub in value.values():
                yield from schema_values(sub)
        elif key == "items":
            yield from schema_values(value)


def q2d_timestamp(value):
    """§2.2's spelling *and* a real instant.

    Digit placement is not a date: `2026-99-99T99:99:99Z` has the spelling
    exactly and is no time, and blessing it here would put a value in the
    reference manifest that implementations may reject or parse differently.
    """
    matched = Q2D_TIMESTAMP.match(value)
    if not matched:
        return False
    stamp = value[:-1]
    if value[17:19] == "60":
        # RFC 3339 §5.7's leap second, at 23:59 on a month end. Which ones were
        # inserted is IERS data and not decidable here.
        if value[11:16] != "23:59":
            return False
        # Whether a leap second was *inserted* at this particular month end is
        # IERS data that changes after this file is written. It is deliberately
        # not checked: no static checker can decide it correctly, and a table
        # baked in here would be wrong within a few years. What is checked is
        # RFC 3339 §5.7's placement -- 23:59 at a month end -- which is fixed by
        # the grammar. The same choice, for the same reason, as
        # `conformance/harness/lint.py`.
        try:
            day = datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return False
        if day.day != monthrange(day.year, day.month)[1]:
            return False
        stamp = value[:17] + "59"
    try:
        datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return False
    return True


def object_schemas(schema, path):
    """Every subschema that declares `type: object`, with where it sits."""
    if not isinstance(schema, dict):
        return
    # `type` may be a list -- the manifest already uses `["boolean", "null"]`
    # for a nullable output -- so an object schema can be `["object", "null"]`
    # and would not have matched an equality test.
    declared = schema.get("type")
    # By keyword as well as by declaration: a schema carrying `properties` or
    # `required` applies object validation whether or not it says
    # `type: object`, so it needs `additionalProperties: false` for the same
    # reason -- and omitting the declaration is how a schema would otherwise
    # slip past a check that looked only for it.
    if (declared == "object"
            or (isinstance(declared, list) and "object" in declared)
            or "properties" in schema or "required" in schema):
        yield path, schema
    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, sub in properties.items():
            yield from object_schemas(sub, f"{path}.properties.{name}")
    if "items" in schema:
        yield from object_schemas(schema["items"], f"{path}.items")


def admits(schema, json_type):
    """Whether a subschema admits values of a JSON type.

    **A subschema with no `type` admits every type.** That is JSON Schema's
    rule, not a lenient reading of it: `type` is a constraint, and omitting a
    constraint does not narrow anything. Treating a missing `type` as matching
    nothing would let `{"maxLength": 8}` beside a typeless sibling -- or a bare
    `{"description": ...}` -- carry an unbounded string past the one check
    written to catch it.
    """
    declared = schema.get("type")
    if declared is None:
        return True
    if isinstance(declared, list):
        return json_type in declared
    return declared == json_type


# Every JSON type an output schema can admit, and what bounds its serialized
# length. Enumerated rather than checked case by case: four rounds of review
# each found a type the previous version had not thought of -- a schema with no
# `type`, an enum's descendants, an array without `items`, an unbounded number
# -- and the fix each time was another branch. A table of all seven is the
# thing that cannot silently omit one.
BOUNDED_BY = {
    "string": ("maxLength",),        # or `format: date-time`, handled below
    "integer": ("minimum", "maximum"),
    # `number` is absent on purpose, and handled below: a range does not bound
    # a decimal expansion, and §4.1 refuses one outright. E-30, closed.
    "array": ("maxItems", "items"),  # count *and* element schema
    "boolean": (),                   # two values
    "null": (),                      # one value
    "object": (),                    # its fields, each reached by this walk
}


def unbounded_release(schema, path):
    """Every subschema that can release a value of unbounded serialized length.

    scope.md §4.1: an entry's output schema bounds every variable-length value
    it can release. Serialized length is the measure, so a number counts -- an
    integer with no range admits arbitrarily many digits, and its domain has no
    cardinality for §3.1 to price either.

    **`enum` bounds the whole value and prunes the walk below it.** A finite
    set of literals is a complete bound whatever the type, so an enum of
    objects bounds the strings inside them too; descending would reject a
    schema §4.1 permits, which is the opposite of this check's job.

    An **object** is bounded by its fields rather than by a keyword of its own:
    each is a subschema this walk reaches, and §4.1 already requires
    `additionalProperties: false`, so there are no unreached ones.
    """
    if not isinstance(schema, dict):
        return
    if "enum" in schema:
        return

    if "type" not in schema:
        # No `type` admits every type at once, so it is unbounded in every
        # direction. One finding rather than seven: the fix is to say what the
        # value is.
        yield f"{path}: no `type`, so it admits a value of any type and any length"
    else:
        declared = schema["type"]
        for json_type in (declared if isinstance(declared, list) else [declared]):
            if json_type == "number":
                # scope.md §4.1 refuses `number` in an output schema.
                # `minimum`/`maximum` bound an integer's digits and not a
                # decimal expansion -- 0.0 to 1.0 still admits arbitrarily many
                # -- and the keyword that would, `multipleOf`, is the one two
                # JSON Schema libraries most reliably disagree about, since
                # 0.1 has no exact binary representation. A predicate whose
                # answer is a decimal registers a scaled integer. E-30.
                yield (f"{path}: number, which §4.1 refuses in an output schema "
                       f"— register a scaled integer, or bound it with an `enum`")
                continue
            required = BOUNDED_BY.get(json_type)
            if required is None:
                # A type outside JSON's seven is not something §4.1's profile
                # can describe, and is reported rather than passed over.
                yield f"{path}: unknown type {json_type!r}"
                continue
            if json_type == "string" and schema.get("format") == "date-time":
                continue    # core-model.md §2.2 fixes one 20-character spelling
            missing = [k for k in required if k not in schema]
            if missing:
                yield (f"{path}: {json_type} with no "
                       + " or ".join(f"`{k}`" for k in missing))

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, sub in properties.items():
            yield from unbounded_release(sub, f"{path}.properties.{name}")
    if "items" in schema:
        yield from unbounded_release(schema["items"], f"{path}.items")


# scope.md §4.1: the widest range every conforming producer carries exactly.
# Not a protocol constant -- core-model.md states no integer range, and every
# integer Q2D itself defines is a count, a cardinality, or a capacity in integer
# millibits. This bounds *registry* data. E-37, closed.
INT64_MIN = -2**63
INT64_MAX = 2**63 - 1


def unrepresentable_integer(schema, path):
    """Every integer subschema an implementation could fail to represent.

    scope.md §4.1: an `integer` in **any** of an entry's schemas states
    `minimum` and `maximum`, and both lie within the signed 64-bit range.

    Wider than `unbounded_release`, which asks only about the output schema
    because what it bounds is disclosure. This is a divergence question: JSON's
    grammar admits an integer of any length and gives implementations no common
    range, so an entry admitting one a producer cannot represent would surface
    as two implementations emitting different bytes for the same message.

    **`enum` does not prune here**, where it does there. A finite set of
    literals bounds a value's *length*, which is what §4.1's release rule asks;
    it says nothing about whether each literal is representable, and
    `enum: [12345678901234567890123]` is finite and still unrepresentable.
    """
    if not isinstance(schema, dict):
        return

    for index, literal in enumerate(schema.get("enum", []) or []):
        # `bool` before `int`: in Python `True` is an `int`, and a boolean
        # literal is not an integer this rule has anything to say about.
        if isinstance(literal, bool) or not isinstance(literal, int):
            continue
        if not INT64_MIN <= literal <= INT64_MAX:
            yield (f"{path}.enum[{index}]: outside −2^63 … 2^63 − 1, which "
                   f"§4.1 requires an integer to lie within")

    declared = schema.get("type")
    types = declared if isinstance(declared, list) else [declared]
    if "integer" in types:
        for keyword in ("minimum", "maximum"):
            bound = schema.get(keyword)
            if bound is None:
                # An `enum` of integers is exempt from stating a range: it has
                # named every value it admits, and each was checked above.
                if "enum" not in schema:
                    yield f"{path}: integer with no `{keyword}`"
            elif isinstance(bound, int) and not INT64_MIN <= bound <= INT64_MAX:
                yield (f"{path}: `{keyword}` is outside −2^63 … 2^63 − 1, which "
                       f"§4.1 requires an integer to lie within")

    properties = schema.get("properties")
    if isinstance(properties, dict):
        for name, sub in properties.items():
            yield from unrepresentable_integer(sub, f"{path}.properties.{name}")
    if "items" in schema:
        yield from unrepresentable_integer(schema["items"], f"{path}.items")


def declared_timestamps(value, schema, path):
    """Every value an entry's schema declares to be a `core-model.md` §2.2 one.

    Driven by the schema rather than by the value's shape, which is E-36's
    resolution: §2.2 binds the fields §2.2 names, and a predicate constrains a
    field of its own by declaring `format: date-time` — which `scope.md` §4.1
    makes an assertion. A predicate that instead declares a bounded `string`
    may carry `2026-07-31T19:30:00+01:00`, and the offset is its data.

    This scanned every date-shaped string in the manifest until E-36 closed.
    That was the same rule the three serializers carried and lost, in a sixth
    place, and it was the one that mattered most: this file validates *any*
    manifest -- `python3 registry/validate.py path/to/manifest.json` -- so
    being stricter than §4.1 here rejects a conforming entry rather than
    tidying our own corpus, which is why `conformance/harness/lint.py` keeps
    its copy and this one does not.
    """
    if isinstance(schema, dict) and schema.get("format") == "date-time":
        if isinstance(value, str):
            yield path, value
        return
    if isinstance(value, dict) and isinstance(schema, dict):
        properties = schema.get("properties")
        if isinstance(properties, dict):
            for key, item in value.items():
                if key in properties:
                    yield from declared_timestamps(item, properties[key],
                                                   f"{path}.{key}")
    elif isinstance(value, list) and isinstance(schema, dict):
        items = schema.get("items")
        if items is not None:
            for index, item in enumerate(value):
                yield from declared_timestamps(item, items, f"{path}[{index}]")


def entry_timestamps(manifest):
    """`declared_timestamps` over every vector of every entry."""
    for index, entry in enumerate(manifest.get("predicates", [])):
        for vector_index, vector in enumerate(entry.get("test_vectors", [])):
            for field, schema_field in (("public_context", "public_context_schema"),
                                        ("private_input", "private_input_schema"),
                                        ("input", "input_schema"),
                                        ("output", "output_schema")):
                if field not in vector or schema_field not in entry:
                    continue
                where = (f"manifest.predicates[{index}]"
                         f".test_vectors[{vector_index}].{field}")
                yield from declared_timestamps(vector[field], entry[schema_field],
                                               where)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).with_name("manifest.json")
    print(f"validating {path}\n")

    try:
        manifest = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(f"  FAIL  manifest is not valid JSON  [{exc}]")
        return 1

    wire_seen: list[tuple[str, str]] = []

    print("manifest")
    cu = manifest.get("capacity_unit", {})
    check(cu.get("name") == "millibits", "capacity unit is millibits", str(cu.get("name")))
    check(any("MUST NOT compute log2 at runtime" in r for r in cu.get("rules", [])),
          "manifest forbids computing log2 at runtime")
    check(bool(manifest.get("denial_normalization", {}).get("external_reason")),
          "manifest declares a normalized external reason",
          str(manifest.get("denial_normalization", {}).get("external_reason")))
    check(manifest.get("q2d_version") == "0.1-draft", "targets Q2D 0.1-draft",
          str(manifest.get("q2d_version")))
    preds = manifest.get("predicates", [])
    check(len(preds) == 3, "three predicates", str(len(preds)))
    # Before any loop that *parses* a timestamp. `ts()` uses `fromisoformat`,
    # which raises on a malformed value -- so running this check after the
    # vector evaluation meant it never ran on exactly the input it exists to
    # reject, and the run died mid-sweep instead of reporting.
    wrong = [f"{path}={value}" for path, value in entry_timestamps(manifest)
             if not q2d_timestamp(value)]
    check(not wrong,
          "every declared date-time is core-model.md §2.2's spelling "
          "(scope.md §4.1)",
          "; ".join(wrong))
    # A leap second is valid RFC 3339 and valid under §2.2, and this validator
    # cannot check a manifest containing one: `ts()` uses `fromisoformat`,
    # which raises on second 60. Reported as a **limit of this tool**, not as
    # non-conformance -- the distinction matters, because narrowing §2.2 to
    # what this file can parse would be a specification change made by a
    # convenience.
    #
    # Over the **declared** timestamps, for the same reason `wrong` is: those
    # are the values `ts()` is handed, because a predicate reads the fields its
    # schema declares. A prose field containing `2016-12-31T23:59:60Z` reaches
    # no parser here, and halting on one would refuse to judge a manifest over
    # a string that is not a timestamp at all.
    # Only a `:60` that is otherwise conforming. One at the wrong hour or on a
    # wrong date is non-conforming outright, `wrong` above already holds it,
    # and calling that indeterminate would classify a registry error as
    # something this tool cannot judge.
    leap = [f"{path}={value}" for path, value in entry_timestamps(manifest)
            if value[17:19] == "60" and q2d_timestamp(value)]
    if leap:
        # Exit 2, not 1: 1 means the manifest is wrong, and this manifest may
        # be right. A caller has to be able to tell "non-conforming" from
        # "this tool cannot say".
        print("\nSTOPPED: this validator cannot check a manifest containing a "
              "leap second —")
        print("  " + "; ".join(leap))
        print("  `datetime.fromisoformat` raises on second 60. The value may "
              "well be conforming;\n  core-model.md §2.2 permits it and this "
              "tool cannot say so either way.")
        return 2

    if wrong:
        # Reported *and* stopped. Everything below parses these values --
        # `ts()` calls `fromisoformat`, which raises on them -- so continuing
        # would abort the sweep partway with a traceback instead of the report
        # just printed, and the finding would be buried by the crash it
        # predicted.
        print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed")
        print("FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        print("\nstopped here: the checks below parse these values")
        return 1

    ids = [p["id"] for p in preds]
    check(len(set(ids)) == len(ids), "predicate identifiers unique")
    check(all(p.get("status") == "active" for p in preds), "all entries active")
    check(manifest.get("status") == "draft" and any("UNSIGNED" in n for n in manifest.get("notes", [])),
          "unsigned status stated explicitly")

    for p in preds:
        short = p["id"].rsplit("/", 1)[-1]
        print(f"\n{short}  v{p['version']}  ({p['release_shape']})")

        for field in ("public_context_schema", "private_input_schema", "output_schema",
                      "answer_domain", "capacity", "sensitivity", "freshness",
                      "assurance_profiles", "provenance", "test_vectors"):
            check(field in p, f"has {field}")

        check(p["assurance_profiles"] == ["authenticated-answer"],
              "assurance profile is authenticated-answer only",
              ",".join(p["assurance_profiles"]))
        check(p["sensitivity"]["class"] in ("low", "moderate", "high", "special-category"),
              "sensitivity class from the closed vocabulary", p["sensitivity"]["class"])
        check(bool(p["sensitivity"].get("rationale")), "sensitivity has a stated rationale")
        check(p["provenance"]["revoked_from"] is None, "not revoked")

        want = entry_digest(p)
        check(p.get("entry_digest") == want, "entry_digest matches the entry's canonical bytes",
              f"{p.get('entry_digest','absent')[:24]}… vs {want[:24]}…")
        check(not has_float(p), "entry contains no floating-point value",
              "a float would make the signed bytes non-deterministic across implementations")
        check(all(k.isascii() for k in p), "entry keys are ASCII",
              "non-ASCII keys make code-point ordering differ from UTF-16 ordering")

        dom = p["answer_domain"]
        if dom["kind"] == "enumerated":
            check(dom["cardinality"] == len(dom["values"]),
                  "declared cardinality matches enumerated values",
                  f"{dom['cardinality']} vs {len(dom['values'])}")
            # An enumerated entry may carry a single value or a table.
            # core-model.md §3.2 admits a *coarsened* enum request, whose label
            # count is smaller than the registered cardinality -- and the debit
            # for that count has to be authored, because a responder may not
            # compute one. A single value is still valid and simply admits no
            # coarsening; a table is what makes coarsening available.
            capacity = p["capacity"]
            # Exactly one, never both. Two sources for one entry's debit is two
            # answers an implementation can pick between, and a stale
            # `millibits` beside a table would pass every other check here
            # while making two responders disagree on the same request.
            check(("millibits" in capacity) != ("table" in capacity),
                  "enumerated entry carries a capacity value or a table, not both",
                  ",".join(sorted(set(capacity) & {"millibits", "table"})))
            if "table" in capacity:
                tbl = capacity["table"]
                bad = [k for k, v in tbl.items()
                       if v != math.ceil(1000 * math.log2(int(k)))]
                check(not bad, "every capacity-table entry is correct", ",".join(bad))
                check(all(isinstance(v, int) for v in tbl.values()),
                      "capacity table holds integers")
                # Every label count a coarsening could ask for. core-model.md
                # §3.2 bounds it at both ends: condition 5 requires at least two
                # labels, and condition 3 requires strictly fewer than the
                # registered cardinality. Through that cardinality inclusive,
                # because the table is the entry's only capacity source and so
                # answers the uncoarsened request as well as every coarsening.
                # The floor was this range before E-27 decided condition 5; the
                # decision made the spec agree with the check rather than the
                # other way round.
                check(set(tbl) == {str(k) for k in range(2, dom["cardinality"] + 1)},
                      "capacity table covers the registered cardinality and every coarsening (core-model.md §3.2 conditions 3 and 5)",
                      f"{sorted(tbl)} vs 2..{dom['cardinality']}")
            else:
                declared = capacity["millibits"]
                actual = math.ceil(1000 * math.log2(dom["cardinality"]))
                check(declared == actual,
                      "declared capacity equals ceil(1000*log2(cardinality))",
                      f"{declared} vs {actual}")
                check(isinstance(declared, int), "capacity is an integer")
        else:
            tbl = p["capacity"]["table"]
            bad = [k for k, v in tbl.items() if v != math.ceil(1000 * math.log2(int(k)))]
            check(not bad, "every capacity-table entry is correct", ",".join(bad))
            check(all(isinstance(v, int) for v in tbl.values()), "capacity table holds integers")
            check(set(tbl) == {str(k) for k in range(2, dom["maximum_cardinality"] + 1)},
                  "capacity table covers every reachable cardinality")

        fn = EVAL[short]
        for v in p["test_vectors"]:
            name = v["name"]
            exp = v["expect"]
            try:
                rej = reject_reason(p["id"], v["public_context"])
            except NotATimestamp as exc:
                # Named and skipped, not raised: one malformed vector must not
                # hide every finding after it.
                check(False, f"{name}: public context parses", str(exc))
                continue

            if exp["outcome"] == "reject":
                check(rej == exp["internal_reason"],
                      f"vector {name}: internal reason {exp['internal_reason']}",
                      rej or "was accepted")
                check(exp.get("before_private_access") is True,
                      f"vector {name}: rejection precedes private access")
                wire_seen.append((f"{short}/{name}", json.dumps(exp["wire"], sort_keys=True)))
                continue

            if not check(rej is None, f"vector {name}: passes pre-access validation", rej or ""):
                continue
            try:
                got = fn(v["public_context"], v["private_input"])
            except NotATimestamp as exc:
                # `private_input` is parsed here rather than above, so a
                # malformed timestamp in it reaches this line. Named and
                # skipped, for the reason the public-context guard exists:
                # one bad vector must not hide the findings after it.
                check(False, f"{name}: private input parses", str(exc))
                continue
            check(got == exp["result"], f"vector {name}: result", f"got {got!r}, want {exp['result']!r}")

            want_cap = expected_capacity_mb(p, v["public_context"])
            check(exp["capacity_debit_millibits"] == want_cap,
                  f"vector {name}: capacity debit (millibits)",
                  f"{exp['capacity_debit_millibits']} vs {want_cap}")

            if dom["kind"] == "enumerated":
                check(got in dom["values"], f"vector {name}: result inside answer domain")
            else:
                n = len(v["public_context"]["candidates"])
                check(got is None or (isinstance(got, int) and 0 <= got < n),
                      f"vector {name}: result inside computed domain")

    # The cross-vector invariant: no rejection may be distinguishable from any
    # other on the wire. Per-vector checks cannot catch this; only comparing
    # every rejection against every other one can.
    print("\ndenial normalization")
    if wire_seen:
        distinct = {w for _, w in wire_seen}
        check(len(distinct) == 1,
              f"all {len(wire_seen)} rejections return an identical wire response",
              f"{len(distinct)} distinct responses: {sorted(distinct)}" if len(distinct) > 1 else "")
        expected = json.dumps(manifest["denial_normalization"] and
                              {"status": "deny",
                               "external_reason": manifest["denial_normalization"]["external_reason"]},
                              sort_keys=True)
        check(distinct == {expected}, "wire response matches the declared normalized class",
              sorted(distinct)[0])
        internal = {v["expect"]["internal_reason"] for p in preds for v in p["test_vectors"]
                    if v["expect"]["outcome"] == "reject"}
        check(len(internal) > 1,
              "distinct internal reasons exist behind that single wire response",
              f"{len(internal)}: {sorted(internal)}")

    # §4.1 says "an entry's schemas", and an entry carries three. Checking only
    # the public-context one would leave the other two able to drift from a
    # rule spec/ states about all of them.
    for p in preds:
        name = p["id"].rsplit("/", 1)[-1]
        for field in ("public_context_schema", "private_input_schema",
                      "output_schema"):
            schema = p.get(field)
            where = f"{name}.{field}"
            if not isinstance(schema, dict):
                check(False, f"{where} is a schema")
                continue
            outside = sorted({k for k, _ in schema_keywords(schema, where)
                              if k not in SCHEMA_PROFILE})
            check(not outside,
                  f"{where} uses only scope.md §4.1's profile", ",".join(outside))

            # A permitted keyword carrying the wrong kind of value is not JSON
            # Schema at all -- `properties: []`, `required: "id"` -- and two
            # libraries would reject or reinterpret it differently, which is
            # what the profile exists to prevent. The keyword filter above sees
            # names only.
            # `bool` is a subclass of `int` in Python, so a plain isinstance
            # check would accept `minItems: true`. Numbers are named
            # explicitly, and booleans excluded from them.
            def shaped(keyword, value):
                if keyword in ("minItems", "maxItems", "minLength", "maxLength"):
                    # Non-negative: JSON Schema defines these over
                    # `nonNegativeInteger`, and a negative bound is a schema two
                    # libraries may reject differently.
                    return (isinstance(value, int) and not isinstance(value, bool)
                            and value >= 0)
                if keyword in ("minimum", "maximum"):
                    return (isinstance(value, (int, float))
                            and not isinstance(value, bool))
                if keyword == "additionalProperties":
                    # §4.1 lists it as `additionalProperties: false` -- the
                    # value is part of the keyword, so `true` is outside the
                    # profile wherever it sits, including on a schema the
                    # object walk below never visits.
                    return value is False
                if keyword == "required":
                    # Unique, as JSON Schema 2020-12 requires: a duplicate is a
                    # schema conforming validators reject, so accepting it here
                    # would put a manifest in the world that only this file
                    # thinks is valid.
                    return (isinstance(value, list)
                            and all(isinstance(x, str) for x in value)
                            and len(set(value)) == len(value))
                if keyword == "type":
                    names = [value] if isinstance(value, str) else value
                    return (isinstance(names, list) and names
                            and all(n in JSON_TYPES for n in names)
                            and len(set(names)) == len(names))
                if keyword == "enum":
                    return isinstance(value, list) and len(value) > 0
                return isinstance(value, {"properties": dict, "items": dict,
                                          "$schema": str,
                                          "format": str}[keyword])

            KNOWN = {"properties", "required", "enum", "items", "type",
                     "additionalProperties", "$schema", "format", "minItems",
                     "maxItems", "minLength", "maxLength", "minimum", "maximum"}
            misshapen = sorted(
                f"{k}={type(v).__name__}" for k, v in schema_values(schema)
                if k in KNOWN and not shaped(k, v))
            check(not misshapen,
                  f"{where} gives every keyword a value of its own kind",
                  ",".join(misshapen))
            check(schema.get("$schema") == DIALECT,
                  f"{where} declares §4.1's dialect", str(schema.get("$schema")))

            # scope.md §4.1: an entry's OUTPUT schema bounds every
            # variable-length value it can release. Only the output schema --
            # the input and public-context schemas bound what a requester may
            # send, which §4.1 says is a resource question rather than a
            # disclosure one and does not decide.
            #
            # This is what core-model.md §4 step 17 validates a result against,
            # and what claims.md Q2D-C-03 rests on: the effective domain bounds
            # the answer's alphabet, and nothing but this schema bounds its
            # extent. The `attribute` shape is released *in full* and §3.2
            # permits it no narrowing, so a free-text field is bounded here or
            # nowhere.
            if field == "output_schema":
                unbounded = sorted(unbounded_release(schema, where))
                check(not unbounded,
                      f"{where} bounds every variable-length value it releases",
                      "; ".join(unbounded))

            # Every schema, not only the output one: this asks whether a value
            # can be *represented* rather than whether it can be released, and
            # an integer a producer cannot hold arrives through the input and
            # public-context schemas. E-37.
            unrepresentable = sorted(unrepresentable_integer(schema, where))
            check(not unrepresentable,
                  f"{where} keeps every integer inside the 64-bit range",
                  "; ".join(unrepresentable))
            # And nowhere else: JSON Schema lets a nested `$schema` switch
            # dialects for that subschema, which is the divergence §4.1 pins
            # the dialect to prevent, reintroduced one level down.
            nested = [at for k, at in schema_keywords(schema, where)
                      if k == "$schema" and at != where]
            check(not nested, f"{where} declares a dialect only at its root",
                  ",".join(nested))
            # Every object, not only the root: a nested one omitting it, or
            # setting it true, accepts fields the entry never declared.
            # §4.1 admits `format` with one value. The keyword check above
            # sees names only, so `format: email` would read as inside the
            # profile while being exactly the library-dependent behaviour the
            # profile excludes.
            formats = sorted({v for k, v in schema_values(schema)
                              if k == "format" and v != "date-time"})
            check(not formats,
                  f"{where} uses only `format: date-time`", ",".join(map(str, formats)))

            loose = [at for at in object_schemas(schema, where)
                     if at[1].get("additionalProperties") is not False]
            check(not loose,
                  f"{where} sets additionalProperties: false on every object",
                  ",".join(at[0] for at in loose))

    total_vectors = sum(len(p["test_vectors"]) for p in preds)
    print(f"\n{CHECKS - len(FAILURES)}/{CHECKS} checks passed  ({total_vectors} vectors across {len(preds)} predicates)")
    if FAILURES:
        print("FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("manifest is internally consistent and every vector holds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
