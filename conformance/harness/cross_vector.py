"""Assertions a per-vector check structurally cannot make.

P-001 §4.8 lists three. Two are implemented here; the third is not, and §4.8
now says why.

**Denial uniformity** (P-001 issue 7) is the one `registry/validate.py` already
performs over registry rejections, generalized to any section. A per-case test
sees one rejection and has nothing to compare it against -- the divergence
exists only *between* causes, so testing per cause is precisely the failure
CLAUDE.md names under denial normalization.

**Budget accumulation** (P-001 issue 8) is order-independence: a debit sequence
and its permutations reach the same total. A single sequence proves nothing,
because the failure it looks for -- accumulated floating-point error, or a
total that depends on iteration order -- is invisible until two orders are
compared.

Both run over the authored corpus rather than over runner output. They are
properties the vectors must have before any implementation is asked about them:
a corpus whose own rejection vectors disagree cannot detect an implementation
whose rejections disagree.
"""

from __future__ import annotations

import json
from collections import defaultdict

def mapping(value):
    """`value` if it is an object, else an empty one.

    Cross-vector assertions run over whatever parsed, alongside the per-vector
    checks rather than after them, so every vector they see may be any shape at
    all. Reaching into a non-object would abort the sweep that was about to
    report it, and one malformed file would hide every other failure.
    """
    return value if isinstance(value, dict) else {}


def as_authored(value) -> str:
    """The value as its file wrote it, for a comparison that means bytes.

    **No `sort_keys`.** Python's parser preserves the order keys appeared in,
    so authored order survives into this comparison -- and two wire responses
    with the same fields in a different order are different bytes on the wire,
    which is exactly the divergence a normalized class must not contain.
    Sorting here would normalise away the thing being checked.
    """
    return json.dumps(value, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def multiset_key(value) -> str:
    """A form that ignores authored order, for grouping rather than comparing."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


# core-model.md §5.2's deny response, in full. A vector asserting fewer of these
# asserts nothing about the ones it omits, and for a normalized class that
# matters more than it looks: `status` and `external_reason` are fixed by the
# class, so comparing only those two compares two constants.
DENY_RESPONSE_FIELDS = ("status", "external_reason", "receipt", "signature")



def rejection_vectors(vectors):
    for vector in vectors:
        if not isinstance(vector.body, dict):
            continue
        expect = mapping(vector.body.get("expect"))
        if expect.get("outcome") != "rejected":
            continue
        rejection = expect.get("rejection")
        if isinstance(rejection, dict) and isinstance(rejection.get("wire"), dict):
            yield vector, rejection


def denial_uniformity(vectors) -> tuple[list[str], str]:
    """Every rejection claiming one external class must be indistinguishable.

    Grouped by the external class the vector's own wire response declares,
    rather than by section: two rejections that tell a requester the same thing
    must tell it in the same bytes, wherever in the corpus they live. Grouping
    by section would be wrong in both directions -- Tier A causes share a
    section and are deliberately distinct, and a normalized class spans
    sections.
    """
    errors: list[str] = []
    groups: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    partial: dict[str, set] = {}

    for vector, rejection in rejection_vectors(vectors):
        wire = rejection["wire"]
        external = wire.get("external_reason")
        if external is None:
            # Nothing declares which class it belongs to, so it is its own
            # group and there is nothing to compare it against.
            continue
        groups[str(external)].append(
            (vector.id, as_authored(wire), str(rejection.get("internal_reason", ""))))
        # Only whole §5.2 fields. A `receipt` that is present but the wrong
        # shape is not a narrower comparison -- it is a vector asserting a
        # receipt the specification says no implementation emits -- and
        # `lint.receipt_errors` fails it.
        absent = {f for f in DENY_RESPONSE_FIELDS if f not in wire}
        if absent:
            partial.setdefault(str(external), set()).update(absent)

    thin = []

    for external, members in sorted(groups.items()):
        wires = {wire for _, wire, _ in members}
        if len(wires) > 1:
            listing = ", ".join(sorted(v for v, _, _ in members))
            errors.append(
                f"denial uniformity: {len(wires)} distinct wire responses claim "
                f"external_reason {external!r} — {listing}")

        # §4.8's second clause -- distinct internal reasons behind one class --
        # is *reported*, and the reason is P-009 §4.1's Tier A. Those rejections
        # are deliberately distinct from one another: a malformed envelope and
        # an unknown version tell a requester different things on purpose,
        # because they describe the request rather than the custodian. Each is
        # therefore one cause under one external value, and a rule that failed
        # every single-cause class would reject a correct corpus for containing
        # the tier that exists to be informative.
        #
        # What the harness cannot know is which external values name a
        # *normalized* class and which name a Tier A error, because nothing in
        # the format says. So the contradiction fails -- two causes under one
        # class disagreeing on the bytes -- and the incompleteness reports.
        if len({reason for _, _, reason in members}) < 2:
            thin.append(external)

    summary = (f"{len(groups)} external class(es) across "
               f"{sum(len(m) for m in groups.values())} rejection vector(s)")

    if partial:
        # Said every run, because the alternative is a confident line over a
        # comparison that could not have failed. Where every wire in a class is
        # a proper subset of §5.2's response, the fields actually compared are
        # `status` and `external_reason` -- both fixed by the class -- so the
        # check is a tautology unless the receipt is present. §5.3 puts the
        # leak precisely there.
        for external in sorted(partial):
            missing = ", ".join(sorted(partial[external]))
            summary += (f"; {external!r} compared a partial response (no "
                        f"{missing}), which cannot detect a receipt-level "
                        f"divergence — see vector.schema.json on `wire`")

    if thin:
        summary += (f"; {len(thin)} with a single cause, which show nothing about "
                    f"indistinguishability and may simply be Tier A: "
                    f"{', '.join(sorted(thin))}")
    return errors, summary


def budget_accumulation(vectors) -> tuple[list[str], str]:
    """A debit sequence and its permutations must reach the same total.

    Vectors are grouped by the multiset of their debits, so two vectors listing
    the same debits in different orders land together and must agree on the
    total. What this catches is a total that depends on order -- accumulated
    floating-point error, or iteration over something unordered -- neither of
    which a single sequence can reveal.

    The input shape it reads is `{"debits": [...]}` on a `capacity_debit`
    vector. P-008 owns the `budget/` section and may author a different shape;
    if it does, this follows it rather than the other way round.
    """
    errors: list[str] = []
    groups: dict[tuple, list[tuple[str, str]]] = defaultdict(list)

    for vector in vectors:
        if not isinstance(vector.body, dict):
            continue
        if vector.body.get("operation") != "capacity_debit":
            continue
        debits = mapping(vector.body.get("input")).get("debits")
        if not isinstance(debits, list) or not debits:
            continue
        expect = mapping(vector.body.get("expect"))
        if expect.get("outcome") != "ok":
            continue
        key = tuple(sorted(multiset_key(d) for d in debits))
        groups[key].append((vector.id, multiset_key(expect.get("output")),
                            as_authored(debits)))

    permuted = 0
    lonely = []
    for key, members in groups.items():
        # Two vectors listing the *same* order are not a permutation of each
        # other, and a group of them exercises nothing. Grouping by multiset
        # brings them together; only distinct orders make the group a test.
        orders = {order for _, _, order in members}
        if len(members) < 2 or len(orders) < 2:
            # Nothing to compare against, so order-independence has nowhere to
            # surface. Reported for the same reason as a single-cause class: an
            # incomplete corpus rather than a contradictory one.
            lonely.append(members[0][0])
            continue
        permuted += 1
        totals = {total for _, total, _ in members}
        if len(totals) > 1:
            listing = ", ".join(sorted(v for v, _, _ in members))
            errors.append(
                f"budget accumulation: the same debits in different orders reach "
                f"{len(totals)} different totals — {listing}")

    summary = (f"{permuted} permutation group(s) across "
               f"{sum(len(m) for m in groups.values())} debit vector(s)")
    if lonely:
        summary += (f"; {len(lonely)} debit sequence(s) have no permutation to "
                    f"compare against and demonstrate nothing: "
                    f"{', '.join(sorted(lonely))}")
    return errors, summary


def assertions(vectors) -> tuple[list[str], list[str]]:
    """Run every cross-vector assertion. Returns errors and summary lines."""
    errors: list[str] = []
    summaries: list[str] = []

    for name, check in (("denial uniformity", denial_uniformity),
                        ("budget accumulation", budget_accumulation)):
        found, summary = check(vectors)
        errors += found
        summaries.append(f"{name}: {summary}")

    return errors, summaries
