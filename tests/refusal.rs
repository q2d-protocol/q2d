//! What the production profile refuses, and where it stops caring.
//!
//! These cases are the same in all three implementations — `refusal_test.go`
//! and `conformance/tests/test_serialization_fixtures.py`'s `RefusalTest`. They
//! are not driven from a shared fixture because Rust and Go cannot yet parse
//! one; that is P-002 issue 4, and this comment is the reason to revisit the
//! three lists when it lands.

use q2d::Value as V;

fn refused(value: V) -> String {
    match q2d::serialize(&value) {
        Err(error) => error.to_string(),
        Ok(_) => panic!("the profile produced bytes for a value it must refuse"),
    }
}

fn accepted(value: V) {
    if let Err(error) = q2d::serialize(&value) {
        panic!("the profile refused a value it should not: {error}");
    }
}

fn public_context(pairs: [(&str, V); 1]) -> V {
    V::object([(
        "predicate",
        V::object([("public_context", V::object(pairs))]),
    )])
}

#[test]
fn a_malformed_timestamp_field_is_refused() {
    // By name: §2.2 gives `issued_at` a timestamp, so anything else in it is
    // wrong however wrong it is.
    refused(V::object([(
        "issued_at",
        V::string("2026-07-31t09:00:00Z"),
    )]));
    refused(V::object([(
        "expires_at",
        V::string("2026-99-99T99:99:99Z"),
    )]));
    refused(V::object([("decided_at", V::string("not a date at all"))]));
    refused(V::object([("issued_at", V::Integer(42))]));
    refused(V::object([("issued_at", V::Null)]));
}

#[test]
fn a_malformed_timestamp_anywhere_is_refused() {
    // By shape: a string carrying some RFC 3339 spelling that is not §2.2's is
    // a malformed timestamp wherever it appears — including inside
    // `public_context`, which is exactly where an unexpected one arrives.
    refused(public_context([(
        "booked_for",
        V::string("2026-07-31T19:30:00+01:00"),
    )]));
    refused(V::Array(vec![V::string("2026-07-31T09:00:00.000Z")]));
}

#[test]
fn the_field_name_rule_applies_only_at_protocol_level() {
    // §2.6: a predicate's `public_context` may mean anything at all, so a field
    // there called `issued_at` is the predicate's, not §2.2's. The shape rule
    // still reaches it — this asserts the *name* rule does not.
    accepted(public_context([(
        "issued_at",
        V::string("whenever the kitchen opens"),
    )]));
}

#[test]
fn routing_and_receipt_re_enter_protocol_level() {
    // §2.2 covers "the core object, `routing`, and a receipt", so a timestamp
    // field in either is held to the same rule as one at the top.
    refused(V::object([(
        "routing",
        V::object([("expires_at", V::string("2026-07-31T09:00:00z"))]),
    )]));
    refused(V::object([(
        "receipt",
        V::object([("decided_at", V::string("2026-02-30T00:00:00Z"))]),
    )]));

    // And only from protocol level: a receipt nested inside `public_context` is
    // the predicate's own structure.
    accepted(public_context([(
        "receipt",
        V::object([("decided_at", V::string("on the night"))]),
    )]));
}

#[test]
fn a_refusal_names_the_field_and_nothing_else() {
    // The message may carry the field name and the spelling the caller gave —
    // both are the caller's own — and must not carry anything the caller did
    // not already have.
    let message = refused(V::object([
        ("issued_at", V::string("2026-07-31t09:00:00Z")),
        ("nonce", V::string("Ux7kFQ2mS0aVvJ1cPzN4bw")),
    ]));
    assert!(
        message.contains("issued_at"),
        "the message does not say which field: {message}"
    );
    assert!(
        !message.contains("Ux7kFQ2mS0aVvJ1cPzN4bw"),
        "the message carries an unrelated field's value: {message}"
    );
}

#[test]
fn rust_cannot_construct_the_value_the_other_two_have_to_refuse() {
    // The counterpart of `refusal_test.go`'s
    // `TestInvalidUTF8IsRefusedRatherThanSubstituted` and the Python file's
    // `test_a_string_the_profile_cannot_encode_is_refused`. Each language has a
    // string type that admits something UTF-8 cannot represent, and they are
    // not the same thing: Go's `string` is arbitrary bytes, Python's `str`
    // admits an unpaired surrogate, and Rust's `String` admits neither.
    //
    // So there is no Rust value to refuse, and this test asserts the reason
    // rather than the refusal: the bytes that make the other two fail are not a
    // `String` here, and the compiler is what says so.
    assert!(String::from_utf8(vec![0x61, 0x80, 0x62]).is_err());
    assert!(String::from_utf16(&[0xD800]).is_err());

    // What matters is the consequence: all three accept the same set of values,
    // so a document one of them can sign is a document all of them can sign.
    let same = "a\u{FFFD}b";
    accepted(V::object([("a", V::string(same))]));
}
