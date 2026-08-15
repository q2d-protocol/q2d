//! Signing the canonical query reproduces the committed compact string.
//!
//! P-003 issue 5's acceptance, in the strongest form available today.
//!
//! `testdata/canonical-query.signed` is what
//! [`tools/author_vectors.py`](../tools/author_vectors.py) produces from
//! `testdata/canonical-query.json`, and it is **byte-identical to
//! `message/sign/query-minimal`'s expected output** — a Python test asserts
//! that, so the fixture and the corpus cannot drift apart. This test and
//! `canonical_query_signed_test.go` are the other two readings.
//!
//! Three implementations, three languages, tests that share no code. The third
//! reading is the one that matters: two implementations agreeing with each other
//! but not with the authoring tool would pass every vector and still be wrong.
//!
//! **Why not read the vector file directly.** A corpus vector is not a Q2D
//! structure — it carries a `signed` string of 1604 bytes, and `q2d::parse`
//! applies `core-model.md` §2.8's 2 KiB protocol-string limit, which is a rule
//! about messages. Reading a vector needs the runner's own parser, which is
//! `src/bin/q2d-conform.rs`'s and deliberately separate. `serialization.md` §2
//! says the same thing from the other side.

use q2d::ed25519::PrivateKey;
use q2d::value::Value;

fn testdata(name: &str) -> std::path::PathBuf {
    std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("testdata")
        .join(name)
}

fn member<'a>(value: &'a Value, name: &str) -> &'a Value {
    match value {
        Value::Object(members) => members.get(name).unwrap_or_else(|| panic!("no `{name}`")),
        _ => panic!("`{name}` is not in an object"),
    }
}

#[test]
fn signing_the_canonical_query_reproduces_the_committed_string() {
    let query = q2d::parse(&std::fs::read(testdata("canonical-query.json")).expect("the query"))
        .expect("the canonical query parses");

    let keys = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("conformance")
        .join("keys")
        .join("ed25519-test-only.json");
    let material = q2d::parse(&std::fs::read(keys).expect("key material")).expect("JSON");
    let seed = match member(member(member(&material, "keys"), "test-requester-1"), "seed") {
        Value::String(s) => s.clone(),
        _ => panic!("seed"),
    };
    let seed: Vec<u8> = (0..seed.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&seed[i..i + 2], 16).expect("hex"))
        .collect();

    let payload = q2d::serialize(&query).expect("the query serializes");
    let produced = q2d::sign(
        &payload,
        &PrivateKey::from_seed(&seed).expect("a 32-byte seed"),
        "eddsa-jws-2026",
        "test-requester-1",
    )
    .expect("signing succeeds");

    let expected = std::fs::read_to_string(testdata("canonical-query.signed"))
        .expect("testdata/canonical-query.signed");
    assert_eq!(produced, expected.trim_end());
}
