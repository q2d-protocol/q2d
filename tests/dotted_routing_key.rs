//! A literal key containing a dot is not a nested path.
//!
//! `check_routing` walks §4.5's allowlist **segment by segment**, and this is
//! the case that forced it: nothing forbids `{"predicate.id": …}` as a single
//! member name, and comparing a joined `"predicate.id"` against the allowlist
//! would read that one key as the nested path and admit a field no projection
//! can produce.
//!
//! In its own file because it is the only test here that cares about the
//! difference between a path and a string that looks like one.

use q2d::{check_routing, Value};

#[test]
fn a_literal_dotted_key_is_an_introduced_field() {
    // Both objects carry the *literal* key, so a dotted comparison would find
    // it in the signed object, call it projectable, and pass.
    let core = Value::object([
        ("predicate.id", Value::string("https://q2d.dev/predicates/p")),
        ("type", Value::string("query")),
    ]);
    let routing = Value::object([("predicate.id", Value::string("https://q2d.dev/predicates/p"))]);

    let mismatch = check_routing(&core, Some(&routing)).expect_err("a literal key");
    assert_eq!(mismatch.path, "predicate.id");
    assert_eq!(mismatch.because, q2d::routing::Because::RoutingIntroducedField);
}

#[test]
fn the_nested_path_of_the_same_name_still_passes() {
    // And the shape §4.5 actually projects is unaffected, which is what makes
    // the segment walk a fix rather than a tightening.
    let core = Value::object([(
        "predicate",
        Value::object([("id", Value::string("https://q2d.dev/predicates/p"))]),
    )]);
    let routing = Value::object([(
        "predicate",
        Value::object([("id", Value::string("https://q2d.dev/predicates/p"))]),
    )]);
    assert_eq!(check_routing(&core, Some(&routing)), Ok(()));
}
