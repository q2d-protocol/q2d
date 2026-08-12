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


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


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


def schema_keywords(schema, path):
    """Every keyword a schema uses, with where it sits.

    Only the schema's own keywords -- the *names* under `properties` are the
    author's field names, not JSON Schema vocabulary, so they are walked into
    rather than checked.
    """
    if not isinstance(schema, dict):
        return
    for key, value in schema.items():
        if key == "properties" and isinstance(value, dict):
            yield key, path
            for name, sub in value.items():
                yield from schema_keywords(sub, f"{path}.properties.{name}")
        elif key == "items":
            yield key, path
            yield from schema_keywords(value, f"{path}.items")
        else:
            yield key, path


def timestamps(value, path="manifest"):
    """Every string in the manifest that is shaped like a date-time."""
    if isinstance(value, str):
        if re.match(r"\A\d{4}-\d{2}-\d{2}[Tt]", value):
            yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from timestamps(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from timestamps(item, f"{path}[{index}]")


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
                # Every label count a coarsening could ask for: 2 up to the
                # registered cardinality. Below 2 is not a domain.
                # Through the registered cardinality inclusive: the table is
                # the entry's only capacity source, so it answers the
                # uncoarsened request as well as every coarsening.
                check(set(tbl) == {str(k) for k in range(2, dom["cardinality"] + 1)},
                      "capacity table covers the registered cardinality and every coarsening",
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
            rej = reject_reason(p["id"], v["public_context"])

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
            got = fn(v["public_context"], v["private_input"])
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

    for p in preds:
        schema = p.get("public_context_schema")
        where = f"{p['id'].rsplit('/', 1)[-1]}.public_context_schema"
        if not isinstance(schema, dict):
            check(False, f"{where} is a schema")
            continue
        outside = sorted({k for k, _ in schema_keywords(schema, where)
                          if k not in SCHEMA_PROFILE})
        check(not outside,
              f"{where} uses only scope.md §4.1's profile", ",".join(outside))
        check(schema.get("$schema") == DIALECT,
              f"{where} declares §4.1's dialect", str(schema.get("$schema")))
        check(schema.get("additionalProperties") is False,
              f"{where} sets additionalProperties: false",
              str(schema.get("additionalProperties")))

    wrong = [f"{path}={value}" for path, value in timestamps(manifest)
             if not Q2D_TIMESTAMP.match(value)]
    check(not wrong,
          "every date-time is core-model.md §2.2's spelling (scope.md §4.1)",
          "; ".join(wrong))

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
