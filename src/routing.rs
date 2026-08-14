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
    fn the_projection_of_a_projection_is_itself() {
        // Idempotence, which is what makes "derived, never authored" checkable
        // by the far end: a relay that re-derived from what it received would
        // get the same bytes, so the §4.6 comparison has one fixed point.
        let once = project_routing(&query());
        let twice = project_routing(once.as_value());
        assert_eq!(text(&once), text(&twice));
    }
}
