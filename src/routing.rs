//! The routing projection: derived from a core object, never authored.
//!
//! P-002 §4.5. A producer that sends `routing` derives it by projection; it
//! never constructs one independently. Hand-authoring makes producer-side
//! disagreement possible — two fields built from two code paths that can drift
//! — where deriving makes `core-model.md` §2.1's strict-subset property
//! structurally true and leaves the §4.6 check exactly one job: detecting
//! tampering in transit.
//!
//! ## What is projected, and what never is
//!
//! `q2d_version`, `type`, `target.custodian`, `predicate.id`,
//! `predicate.version`, `expires_at` — each because a relay needs it to
//! dispatch or capability-match without unwrapping.
//!
//! **Never** `purpose`, `delivery`, `answer_contract`, `target.subjects`, or
//! `public_context`. Anything projected travels in the clear, and those are
//! what the protocol exists to bound. The list is closed: adding to it is a
//! disclosure decision rather than a plumbing one, and an escalation (§9.4).
//!
//! ## Why this type has no other constructor
//!
//! [`Routing`] wraps a value whose only origin is [`project_routing`]. The
//! field is private, so nothing outside this module can build one from
//! whatever it likes, and §4.5's rule is enforced by the type rather than
//! remembered by a caller.
//!
//! The limit is honest and P-002 §8's last row states it: a *module in this
//! crate* could still construct one, and an implementation determined to route
//! around the interface can. What the type removes is the accident — the code
//! path that assembles a projection by hand because it was convenient, drifts
//! from this one, and produces an envelope that fails §4.6 at the far end for
//! no attacker's benefit.
//!
//! A `routing` that arrived from the wire is **not** this type. That one is a
//! [`Value`] and stays one: it is a claim, not a derivation, and issue 7's
//! `check_routing` is what compares the two.

use crate::value::Value;

/// The fields §4.5 projects, as paths into the core object.
///
/// A path rather than a name because three of them are nested, and flattening
/// them into `custodian` and `id` would lose which object they came from —
/// which is exactly what §4.6 has to compare them against.
const PROJECTED: [&[&str]; 6] = [
    &["q2d_version"],
    &["type"],
    &["target", "custodian"],
    &["predicate", "id"],
    &["predicate", "version"],
    &["expires_at"],
];

/// A projection of a core object, derived by [`project_routing`].
///
/// The wrapped value is private: §4.5's *never authored* is a property of this
/// type rather than a rule a caller has to keep.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Routing(Value);

impl Routing {
    /// The projection as a [`Value`], for serializing into an envelope.
    ///
    /// Borrowed rather than owned, and there is no `From<Value>` going the
    /// other way: a caller can read a projection and cannot mint one.
    pub fn as_value(&self) -> &Value {
        &self.0
    }
}

/// Derive `routing` from a core object.
///
/// **Total.** A core object missing a projected field simply does not project
/// it, which is the behaviour §2.1 and §4.6 already describe: `routing` is a
/// *strict subset*, and the consistency check compares each field **present**
/// in it. There is nothing here to fail on, so there is no error path for a
/// caller to handle wrongly, and no temptation to substitute a default for a
/// field that was not there.
///
/// It follows that this cannot introduce a field, which is §2.1's other rule:
/// every key it writes was read from the core object one line earlier.
pub fn project_routing(core: &Value) -> Routing {
    let mut projection = Value::object(Vec::<(&str, Value)>::new());
    for path in PROJECTED {
        if let Some(found) = at(core, path) {
            insert(&mut projection, path, found.clone());
        }
    }
    Routing(projection)
}

/// The value at a path, if the path exists and every step of it is an object.
fn at<'a>(value: &'a Value, path: &[&str]) -> Option<&'a Value> {
    let mut here = value;
    for step in path {
        match here {
            Value::Object(pairs) => here = pairs.get(*step)?,
            _ => return None,
        }
    }
    Some(here)
}

/// Write a value at a path, creating the objects along the way.
fn insert(into: &mut Value, path: &[&str], value: Value) {
    let (last, parents) = path.split_last().expect("no projected path is empty");
    let mut here = into;
    for step in parents {
        let pairs = match here {
            Value::Object(pairs) => pairs,
            // Unreachable: every parent this walk creates is an object, and
            // `into` starts as one. Written as a return rather than a panic
            // because a projection that gave up on one field is still a strict
            // subset, where a panic in a producer is an outage.
            _ => return,
        };
        here = pairs
            .entry((*step).to_string())
            .or_insert_with(|| Value::object(Vec::<(&str, Value)>::new()));
    }
    if let Value::Object(pairs) = here {
        pairs.insert((*last).to_string(), value);
    }
}

/// A `routing` projection that disagrees with the verified core object.
///
/// The **internal** reason. `core-model.md` §5.2.1 gives `routing_mismatch` as
/// an external value too, and the two coinciding is not a licence to use one
/// variable for both: P-009 builds the wire response, and this type is what a
/// responder logs. Carrying the path is the whole reason it exists — an
/// operator needs to know which field was tampered with, and a requester must
/// not be told.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct RoutingMismatch {
    /// The path in `routing` that disagreed, as `target.custodian`.
    pub path: String,
    /// Why, in one of two ways, and never with either value: the projection is
    /// attacker-supplied and the core object is the requester's.
    pub because: Because,
}

/// The two internal reasons a projection is rejected.
///
/// **The names are the corpus's**, not this module's:
/// `conformance/corpus/message/routing/` already distinguishes them, and a
/// third vocabulary for the same two facts is how a runner comes to report
/// something no vector asserts. Both normalize to §5.2.1's external
/// `routing_mismatch`, which is P-009's to emit.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Because {
    /// `routing_signed_mismatch` — the field holds something else in the
    /// verified object, or is not there at all. §4 step 8's tampering.
    RoutingSignedMismatch,
    /// `routing_introduced_field` — the field is not one §4.5 projects, and
    /// §2.1 says `routing` *carries at most* those six.
    ///
    /// Refused **however faithful the copy**, which is the rule the corpus
    /// vector exists to pin: its `purpose` is byte-identical to the signed
    /// one, so agreement is not what fails. §2.1 says `routing` carries at
    /// most those six, and a field outside the list is rejected whether or not
    /// it agrees.
    ///
    /// *Why* §2.1 says so is [E-41], open: its stated reason is that
    /// projecting those fields would expose them, and the 0.1 suite signs the
    /// payload without encrypting it. The rule is not in question.
    ///
    /// [E-41]: https://github.com/q2d-protocol/q2d/blob/main/docs/open-escalations.md
    RoutingIntroducedField,
}

impl std::fmt::Display for RoutingMismatch {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        let because = match self.because {
            Because::RoutingSignedMismatch => "disagrees with the signed object",
            Because::RoutingIntroducedField => "is not a field §4.5 projects",
        };
        write!(
            f,
            "`routing.{}` {because} — core-model.md §4 step 8",
            self.path
        )
    }
}

impl std::error::Error for RoutingMismatch {}

/// Compare a received `routing` against the verified core object.
///
/// `core-model.md` §4 step 8, after verification and parse. For each field
/// **present in** `routing`, the same path must exist in the core object and
/// hold the same value — *exactly, with no coercion: same type, same value, and
/// for a string the same characters.* Any difference is tampering: reject, do
/// not reconcile.
///
/// # This reads nothing *from* `routing`
///
/// It compares and returns a verdict. The projection is unauthenticated until
/// this passes and is not authoritative afterwards either — §2.1 forbids using
/// it for any decision the signature covers, and the way to keep that true is
/// for no value to leave here.
///
/// # Objects recurse, everything else is exact
///
/// A projection carrying `target: {custodian: …}` is a *subset* of a core
/// object whose `target` also has `subjects`, so an object is compared field by
/// field. A leaf, an array, or a type mismatch is compared whole: §4.4 makes
/// array order significant, and a subset rule for arrays would let a relay drop
/// an element and call it a projection.
///
/// # Absent `routing` is not a disagreement
///
/// [`None`] passes. §2.1 permits a message with no projection at all
/// ([E-38](https://github.com/q2d-protocol/q2d/blob/main/docs/open-escalations.md)),
/// and nothing that is not there can disagree with anything.
pub fn check_routing(core: &Value, routing: Option<&Value>) -> Result<(), RoutingMismatch> {
    match routing {
        None => Ok(()),
        Some(routing) => {
            // Against the **projection** of the core object, not against the
            // core object itself.
            //
            // Both were tried. Comparing against the core object means
            // enumerating what `routing` may not contain — a field outside the
            // allowlist, a key that looks like a nested path, a value that
            // differs — and review found three of those one at a time, which is
            // the shape of a wrong model rather than three bugs. §4.5 already
            // says exactly what a projection may hold, and it says it by
            // construction: `project_routing` is total, so every core object has
            // one, and *is this a subset of that* answers all three questions at
            // once.
            let derived = project_routing(core);
            compare(derived.as_value(), routing, &mut Vec::new())
        }
    }
}

/// A path as `target.custodian`, for a message. Only ever for a message: the
/// comparison walks segments, because a key may contain a dot.
fn shown(path: &[String]) -> String {
    if path.is_empty() {
        "<root>".into()
    } else {
        path.join(".")
    }
}

/// `routing` against `derived`.
fn compare(
    derived: &Value,
    routing: &Value,
    path: &mut Vec<String>,
) -> Result<(), RoutingMismatch> {
    // Both objects: `routing` may carry a subset of the fields, so descend.
    if let (Value::Object(signed), Value::Object(projected)) = (derived, routing) {
        // By UTF-16 code unit, not `BTreeMap` order, so a projection with two
        // bad fields names the same one here as in Go. Third place in this
        // codebase to need that, which is why the comparator now lives in
        // `value.rs` rather than being written out a third time.
        let mut keys: Vec<&String> = projected.keys().collect();
        keys.sort_by_key(|key| crate::value::utf16_units(key));

        for key in keys {
            let value = &projected[key];
            path.push(key.clone());
            match signed.get(key) {
                Some(found) => compare(found, value, path)?,
                None => {
                    // Not in the projection, and that is the whole test: §4.5
                    // says what a projection holds, so a field the derivation
                    // did not produce was introduced — whether the core object
                    // has it elsewhere (a faithful `purpose`, the corpus's own
                    // case) or nowhere at all.
                    return Err(RoutingMismatch {
                        path: shown(path),
                        because: Because::RoutingIntroducedField,
                    });
                }
            }
            path.pop();
        }
        return Ok(());
    }

    // Anything else: equal or it is tampering. `Value`'s equality is
    // structural and does not coerce — an `Integer` never equals a `String`
    // that spells it, which is what "same type, same value" asks for.
    if derived == routing {
        Ok(())
    } else {
        Err(RoutingMismatch {
            path: shown(path),
            because: Because::RoutingSignedMismatch,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn query() -> Value {
        Value::object([
            ("q2d_version", Value::string("0.1")),
            ("type", Value::string("query")),
            ("issued_at", Value::string("2026-07-31T09:00:00Z")),
            ("expires_at", Value::string("2026-07-31T09:05:00Z")),
            ("nonce", Value::string("Ux7kFQ2mS0aVvJ1cPzN4bw")),
            (
                "target",
                Value::object([
                    (
                        "custodian",
                        Value::string("https://friend.example/.well-known/q2d"),
                    ),
                    (
                        "subjects",
                        Value::Array(vec![Value::string("did:key:z6MkSubject")]),
                    ),
                ]),
            ),
            (
                "predicate",
                Value::object([
                    (
                        "id",
                        Value::string("https://q2d.dev/predicates/dietary/menu-compatible"),
                    ),
                    ("version", Value::string("0.1")),
                    (
                        "public_context",
                        Value::object([("menu", Value::string("risotto-contains-milk"))]),
                    ),
                ]),
            ),
            (
                "purpose",
                Value::object([("code", Value::string("social.meal-planning"))]),
            ),
            (
                "delivery",
                Value::object([("answer_recipient", Value::string("did:key:z6MkRuntime"))]),
            ),
            (
                "answer_contract",
                Value::object([("release_shape", Value::string("boolean"))]),
            ),
        ])
    }

    fn text(routing: &Routing) -> String {
        String::from_utf8(crate::serialize(routing.as_value()).expect("a projection"))
            .expect("UTF-8")
    }

    #[test]
    fn it_projects_the_six_fields_and_their_shape() {
        assert_eq!(
            text(&project_routing(&query())),
            r#"{"expires_at":"2026-07-31T09:05:00Z","predicate":{"id":"https://q2d.dev/predicates/dietary/menu-compatible","version":"0.1"},"q2d_version":"0.1","target":{"custodian":"https://friend.example/.well-known/q2d"},"type":"query"}"#
        );
    }

    #[test]
    fn nothing_the_protocol_exists_to_bound_is_projected() {
        // The rule that matters most in this file: anything projected travels
        // in the clear. Asserted on the serialized bytes rather than the
        // structure, because a relay reads bytes.
        let projected = text(&project_routing(&query()));
        for withheld in [
            "purpose",
            "delivery",
            "answer_contract",
            "subjects",
            "public_context",
            // And their values, in case a future projection carried one under
            // a different name.
            "social.meal-planning",
            "did:key:z6MkRuntime",
            "did:key:z6MkSubject",
            "boolean",
            "risotto-contains-milk",
            // Two fields §2.2 marks required and §4.5 does not project.
            "issued_at",
            "nonce",
        ] {
            // Not `"menu"` on its own: `predicate.id` is
            // `.../menu-compatible`, which is projected and legitimately
            // contains it. A substring test over serialized bytes has to pick
            // markers that cannot collide with a field it is *not* about, and
            // this one collided on the first run.

            assert!(
                !projected.contains(withheld),
                "{withheld} reached `routing`"
            );
        }
    }

    #[test]
    fn it_is_total() {
        // §4.5's acceptance. A core object missing every projected field, one
        // that is not an object at all, and one whose `target` is a string
        // rather than an object — none of them an error, all of them a strict
        // subset.
        assert_eq!(
            text(&project_routing(&Value::object([(
                "nonce",
                Value::string("x")
            )]))),
            "{}"
        );
        assert_eq!(text(&project_routing(&Value::Null)), "{}");
        assert_eq!(text(&project_routing(&Value::Array(vec![]))), "{}");
        assert_eq!(
            text(&project_routing(&Value::object([
                ("target", Value::string("not an object")),
                ("type", Value::string("query")),
            ]))),
            r#"{"type":"query"}"#
        );
    }

    #[test]
    fn a_partial_core_object_projects_a_partial_routing() {
        // Absent rather than defaulted. A projection that substituted an empty
        // string for a missing `custodian` would introduce a field §2.1 says it
        // may never introduce, and §4.6 would then compare a value nothing
        // signed.
        let partial = Value::object([
            ("type", Value::string("query")),
            ("predicate", Value::object([("id", Value::string("p"))])),
        ]);
        assert_eq!(
            text(&project_routing(&partial)),
            r#"{"predicate":{"id":"p"},"type":"query"}"#
        );
    }

    #[test]
    fn every_key_it_writes_was_read_from_the_core_object() {
        // §2.1: `routing` may never introduce a field. Stated as a property
        // over the projection rather than as a list, so it holds for whatever
        // `PROJECTED` becomes.
        let projected = project_routing(&query());
        assert!(
            subset_of(projected.as_value(), &query()),
            "the projection introduced a field"
        );
    }

    /// Every key in `projection`, at every depth, exists in `core` with the
    /// same value at a leaf.
    fn subset_of(projection: &Value, core: &Value) -> bool {
        match (projection, core) {
            (Value::Object(projected), Value::Object(signed)) => projected
                .iter()
                .all(|(key, value)| signed.get(key).is_some_and(|found| subset_of(value, found))),
            (a, b) => a == b,
        }
    }

    #[test]
    fn a_derived_projection_agrees_with_its_own_core_object() {
        // The property that makes the check meaningful: if projection and
        // comparison disagreed about the same message, every conforming
        // exchange would fail step 8.
        let core = query();
        let derived = project_routing(&core);
        assert_eq!(check_routing(&core, Some(derived.as_value())), Ok(()));
    }

    #[test]
    fn an_absent_projection_is_not_a_disagreement() {
        // §2.1 permits a message with no projection (E-38), and nothing that
        // is not there can disagree with anything.
        assert_eq!(check_routing(&query(), None), Ok(()));
        // Nor is an empty one, which is a projection of nothing.
        let empty = Value::object(Vec::<(&str, Value)>::new());
        assert_eq!(check_routing(&query(), Some(&empty)), Ok(()));
    }

    #[test]
    fn a_changed_value_is_tampering() {
        // `message/routing/disagrees` in miniature: a relay rewrites the
        // custodian so the request reaches it instead.
        let tampered = Value::object([(
            "target",
            Value::object([("custodian", Value::string("https://attacker.example"))]),
        )]);
        let mismatch = check_routing(&query(), Some(&tampered)).expect_err("tampering");
        assert_eq!(mismatch.path, "target.custodian");
        assert_eq!(mismatch.because, Because::RoutingSignedMismatch);
    }

    #[test]
    fn a_field_outside_the_allowlist_is_refused_however_faithful_the_copy() {
        // `message/routing/introduces-field`, whose `purpose` is
        // **byte-identical to the signed one** — so agreement is not what
        // fails. §2.1 says `routing` carries at most six fields, and this
        // check accepted that vector until review caught it.
        let core = query();
        let signed_purpose = match &core {
            Value::Object(pairs) => pairs["purpose"].clone(),
            _ => unreachable!(),
        };
        let faithful = Value::object([("purpose", signed_purpose)]);
        let mismatch = check_routing(&core, Some(&faithful)).expect_err("not projectable");
        assert_eq!(mismatch.path, "purpose");
        assert_eq!(mismatch.because, Because::RoutingIntroducedField);

        // A field nobody signed either, and a nested one whose parent is
        // projected and whose child is not.
        for (routing, path) in [
            (
                Value::object([("shortcut", Value::string("skip-the-checks"))]),
                "shortcut",
            ),
            (
                Value::object([(
                    "predicate",
                    Value::object([("elevated", Value::Bool(true))]),
                )]),
                "predicate.elevated",
            ),
        ] {
            let mismatch = check_routing(&core, Some(&routing)).expect_err("not projectable");
            assert_eq!(mismatch.path, path);
            assert_eq!(mismatch.because, Because::RoutingIntroducedField);
        }
    }

    #[test]
    fn a_projectable_name_the_core_object_lacks_is_introduced() {
        // `expires_at` is a name §4.5 projects, but a core object without one
        // projects nothing there — so `routing` carrying it is §2.1's *may
        // never introduce a field*, which is the corpus's
        // `routing_introduced_field` rather than a value disagreement.
        //
        // Under the older model, which compared against the core object and
        // consulted an allowlist, this was a mismatch. Comparing against the
        // projection makes the two reasons mean what their names say:
        // introduced is *not in the derivation*, mismatch is *in it and
        // different*.
        let core = Value::object([("type", Value::string("query"))]);
        let routing = Value::object([("expires_at", Value::string("2026-07-31T09:05:00Z"))]);
        let mismatch = check_routing(&core, Some(&routing)).expect_err("absent");
        assert_eq!(mismatch.path, "expires_at");
        assert_eq!(mismatch.because, Because::RoutingIntroducedField);
    }

    #[test]
    fn an_empty_prefix_object_is_accepted() {
        // `{"target":{}}` is not something `project_routing` emits, and it is
        // refused by nothing: §2.1 asks that `routing` carry at most the six
        // and introduce no field, and an empty object carries none and
        // introduces none. Rejecting it would be a rule §2.1 does not state.
        //
        // **E-42, open**: nothing derives it and nothing forbids it, so both
        // implementations accept it — the minimum §2.1 states — and the
        // register carries the question. This is the one case where *not
        // derivable* and *not permitted* come apart.
        let core = query();
        let empty_prefix = Value::object([("target", Value::object(Vec::<(&str, Value)>::new()))]);
        assert_eq!(check_routing(&core, Some(&empty_prefix)), Ok(()));
    }

    #[test]
    fn nothing_is_coerced() {
        // §4 step 8: *same type, same value*. A projection whose `q2d_version`
        // is the number 0.1 rather than the string does not agree with one that
        // spells it — and a comparison that coerced would let a relay choose
        // the spelling a responder compares.
        let core = Value::object([("expires_at", Value::string("1"))]);
        let numeric = Value::object([("expires_at", Value::Integer(1))]);
        assert_eq!(
            check_routing(&core, Some(&numeric))
                .expect_err("no coercion")
                .because,
            Because::RoutingSignedMismatch
        );
    }

    #[test]
    fn an_array_is_compared_whole() {
        // No subset rule for arrays: §4.4 makes their order significant, and
        // treating a shorter one as a projection would let a relay drop an
        // element and call it a subset.
        let core = Value::object([(
            "list",
            Value::Array(vec![Value::Integer(1), Value::Integer(2)]),
        )]);
        let shortened = Value::object([("list", Value::Array(vec![Value::Integer(1)]))]);
        assert_eq!(
            check_routing(&core, Some(&shortened))
                .expect_err("not a subset")
                .path,
            "list"
        );
    }

    #[test]
    fn the_mismatch_names_a_path_and_never_a_value() {
        // The internal reason is what a responder logs, and the projection is
        // attacker-supplied while the core object is the requester's. An
        // operator needs to know which field; neither value belongs in the
        // record, and neither belongs on the wire.
        let core = Value::object([("nonce", Value::string("the-requesters-nonce"))]);
        let tampered = Value::object([("nonce", Value::string("the-attackers-nonce"))]);
        let message = check_routing(&core, Some(&tampered))
            .expect_err("tampering")
            .to_string();
        assert!(message.contains("nonce"), "{message}");
        assert!(!message.contains("the-requesters-nonce"), "{message}");
        assert!(!message.contains("the-attackers-nonce"), "{message}");
    }

    #[test]
    fn the_projection_of_a_projection_is_itself() {
        // Idempotence, which is what makes "derived, never authored" checkable
        // by the far end: a relay that re-derived from what it received would
        // get the same bytes, so the §4.6 comparison has one fixed point.
        let once = project_routing(&query());
        let twice = project_routing(once.as_value());
        assert_eq!(text(&once), text(&twice));
    }
}
