//! The digest of every `testdata/` fixture, against a shared expectation.
//!
//! `src/digest.rs` implements SHA-256 by hand because Rust's standard library
//! has none and this crate takes no dependencies; `digest.go` uses
//! `crypto/sha256`. Both are held to `testdata/digests.txt`, which
//! `hashlib` produced — so three provenances agree on the same four answers,
//! and a defect in the hand-written one shows up as a disagreement with two
//! standard libraries rather than as its own private truth.
//!
//! Over the fixtures rather than over invented inputs, because those are the
//! bytes a `request_digest` actually covers: `canonical-query` is a real
//! payload and `profile-edges` is the one that carries every encoding edge.

use std::path::Path;

fn fixture(name: &str) -> Vec<u8> {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("testdata")
        .join(format!("{name}.serialized"));
    std::fs::read(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()))
}

#[test]
fn every_fixture_digests_to_the_shared_expectation() {
    let path = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("testdata")
        .join("digests.txt");
    let expected = std::fs::read_to_string(&path).expect("the digest fixture");

    let mut checked = 0;
    for line in expected.lines() {
        let (name, want) = line
            .split_once("  ")
            .expect("two spaces separate the columns");
        let bytes = if name == "<empty>" {
            Vec::new()
        } else {
            fixture(name)
        };
        assert_eq!(q2d::digest(&bytes), want, "{name}");
        checked += 1;
    }
    assert_eq!(checked, 4, "the fixture lost a line");
}
