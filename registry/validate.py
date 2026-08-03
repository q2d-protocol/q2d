#!/usr/bin/env python3
"""Validate the reference predicate registry manifest.

Checks the manifest's internal consistency and executes every test vector
against a reference evaluation of its predicate. The vectors are the contract
the Rust and Go implementations are both built against, so a vector that is
wrong here is wrong in two places later.

    python3 registry/validate.py [path/to/manifest.json]
"""

from __future__ import annotations

import json
import math
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


def expected_capacity(p, public):
    """Capacity from the effective domain -- never from requester assertion."""
    dom = p["answer_domain"]
    if dom["kind"] == "enumerated":
        return math.log2(dom["cardinality"])
    n = len(public["candidates"])
    return math.log2(n + 1)


def main(argv: list[str]) -> int:
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).with_name("manifest.json")
    print(f"validating {path}\n")

    try:
        manifest = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        print(f"  FAIL  manifest is not valid JSON  [{exc}]")
        return 1

    print("manifest")
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

        dom = p["answer_domain"]
        if dom["kind"] == "enumerated":
            check(dom["cardinality"] == len(dom["values"]),
                  "declared cardinality matches enumerated values",
                  f"{dom['cardinality']} vs {len(dom['values'])}")
            declared = p["capacity"]["bits"]
            actual = math.log2(dom["cardinality"])
            check(declared is not None and math.isclose(declared, actual, rel_tol=1e-12),
                  "declared capacity equals log2(cardinality)",
                  f"{declared} vs {actual}")

        fn = EVAL[short]
        for v in p["test_vectors"]:
            name = v["name"]
            exp = v["expect"]
            rej = reject_reason(p["id"], v["public_context"])

            if exp["outcome"] == "reject":
                check(rej == exp["reason"], f"vector {name}: rejected as {exp['reason']}",
                      rej or "was accepted")
                check(exp.get("before_private_access") is True,
                      f"vector {name}: rejection precedes private access")
                continue

            if not check(rej is None, f"vector {name}: passes pre-access validation", rej or ""):
                continue
            got = fn(v["public_context"], v["private_input"])
            check(got == exp["result"], f"vector {name}: result", f"got {got!r}, want {exp['result']!r}")

            want_cap = expected_capacity(p, v["public_context"])
            check(math.isclose(exp["capacity_debit_bits"], want_cap, rel_tol=1e-12),
                  f"vector {name}: capacity debit",
                  f"{exp['capacity_debit_bits']} vs {want_cap}")

            if dom["kind"] == "enumerated":
                check(got in dom["values"], f"vector {name}: result inside answer domain")
            else:
                n = len(v["public_context"]["candidates"])
                check(got is None or (isinstance(got, int) and 0 <= got < n),
                      f"vector {name}: result inside computed domain")

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
