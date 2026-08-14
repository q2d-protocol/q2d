//! The Rust serializer produces the fixture's exact bytes.
//!
//! P-002 §7's first acceptance criterion is that both implementations serialize
//! the same logical query to byte-identical output. `testdata/README.md`
//! describes the fixture and the two sibling tests; this is the Rust third.
//!
//! The query is built by hand rather than read from
//! `testdata/canonical-query.json`, because parsing is P-002 issue 4 and does
//! not exist yet. When it does, this becomes a round trip and the hand-built
//! copy goes. Until then the JSON file is for the reader and these bytes are
//! for the machine.

use q2d::Value as V;

fn s(text: &str) -> V {
    V::string(text)
}

/// `tools/author_message.py`'s `QUERY`: every field `core-model.md` §2 marks
/// required, and no optional one, so the bytes are the smallest a conforming
/// requester produces.
fn canonical_query() -> V {
    V::object([
        ("q2d_version", s("0.1")),
        ("type", s("query")),
        (
            "query_id",
            s("urn:uuid:0e183389-0f37-4c5f-8c56-1ea7e5818e18"),
        ),
        ("issued_at", s("2026-07-31T09:00:00Z")),
        ("expires_at", s("2026-07-31T09:05:00Z")),
        ("nonce", s("Ux7kFQ2mS0aVvJ1cPzN4bw")),
        (
            "requester",
            V::object([
                ("principal", s("did:key:z6MkRequesterPrincipal")),
                ("agent", s("did:key:z6MkRequesterAgent")),
                (
                    "delegation",
                    V::object([
                        ("profile", s("local-pairing-0.1")),
                        ("reference", s("sha256:7ef1")),
                    ]),
                ),
            ]),
        ),
        (
            "target",
            V::object([("custodian", s("https://friend.example/.well-known/q2d"))]),
        ),
        (
            "predicate",
            V::object([
                (
                    "id",
                    s("https://q2d.dev/predicates/dietary/menu-compatible"),
                ),
                ("version", s("0.1")),
                (
                    "registry_digest",
                    s("sha256:bd08ff230de0d8ce34de99967f7a9097988b49058f0a21dd35b9444c24098e35"),
                ),
                (
                    "public_context",
                    V::object([(
                        "menu",
                        V::Array(vec![
                            V::object([
                                ("item_id", s("risotto")),
                                ("contains", V::Array(vec![s("milk")])),
                            ]),
                            V::object([("item_id", s("salad")), ("contains", V::Array(vec![]))]),
                        ]),
                    )]),
                ),
            ]),
        ),
        (
            "answer_contract",
            V::object([
                ("release_shape", s("boolean")),
                ("domain", V::Array(vec![V::Bool(false), V::Bool(true)])),
                ("allowed_detail_fields", V::Array(vec![])),
            ]),
        ),
        (
            "purpose",
            V::object([
                ("code", s("social.meal-planning")),
                ("description", s("Choose a dinner venue for 2026-07-31")),
            ]),
        ),
        (
            "delivery",
            V::object([
                ("answer_recipient", s("did:key:z6MkRequesterRuntime")),
                (
                    "permitted_sinks",
                    V::Array(vec![s("urn:q2d:sink:model:local")]),
                ),
            ]),
        ),
        (
            "signature",
            V::object([
                ("profile", s("eddsa-jws-2026")),
                ("key_id", s("test-requester-1")),
            ]),
        ),
    ])
}

fn fixture() -> Vec<u8> {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("testdata")
        .join("canonical-query.serialized");
    std::fs::read(&path).unwrap_or_else(|e| panic!("cannot read {}: {e}", path.display()))
}

#[test]
fn the_canonical_query_serializes_to_the_fixture_bytes() {
    let produced = q2d::serialize(&canonical_query()).expect("a conforming query");
    let expected = fixture();
    // Compared as **bytes**, and decoded only to say what went wrong. This test
    // claims byte-identical output, and `from_utf8_lossy` maps every invalid
    // sequence to U+FFFD — so comparing the decoded text would call a fixture
    // containing a bad byte equal to a serializer emitting a literal U+FFFD.
    assert_eq!(
        produced,
        expected,
        "\n produced: {}\n expected: {}",
        String::from_utf8_lossy(&produced),
        String::from_utf8_lossy(&expected)
    );
}

#[test]
fn the_signature_block_carries_no_value() {
    // E-31: under `eddsa-jws-2026` the signature is the compact form's third
    // segment, so a payload carrying `signature.value` would be signing itself.
    // Asserted over the bytes rather than the structure, since that is what a
    // verifier sees.
    let text = String::from_utf8(fixture()).expect("the profile emits UTF-8");
    assert!(text.contains(r#""signature":{"key_id""#));
    assert!(!text.contains(r#""value""#));
}
