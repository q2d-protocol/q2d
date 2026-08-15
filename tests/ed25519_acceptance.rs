//! Both implementations are held to one acceptance table.
//!
//! `testdata/ed25519-acceptance.txt` is the file, and `ed25519_acceptance_test.go`
//! is its other reader. Every row is a case where "Ed25519" alone does not
//! decide the answer — RFC 8032 leaves the choice open, libraries take it
//! differently, and two implementations that disagreed here would disagree
//! about whether a message is authentic while both passing RFC 8032's own
//! vectors.
//!
//! A **two-way** agreement, unlike `testdata/digests.txt`: the Python side
//! signs but does not verify, so it cannot hold an opinion about which
//! signatures are acceptable. It authored the cases instead, which is a
//! different and weaker kind of independence and is worth saying rather than
//! implying.

use q2d::ed25519::{verify, PublicKey};

fn hex(s: &str) -> Vec<u8> {
    (0..s.len())
        .step_by(2)
        .map(|i| u8::from_str_radix(&s[i..i + 2], 16).expect("hex"))
        .collect()
}

#[test]
fn every_row_of_the_acceptance_table_holds() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("testdata")
        .join("ed25519-acceptance.txt");
    let text = std::fs::read_to_string(&path).expect("testdata/ed25519-acceptance.txt");

    let mut rows = 0;
    for line in text.lines() {
        let fields: Vec<&str> = line.split("  ").collect();
        assert_eq!(fields.len(), 5, "malformed row: {line}");
        let (name, a, signature, message, expected) =
            (fields[0], fields[1], fields[2], fields[3], fields[4]);
        let message = if message == "-" { Vec::new() } else { hex(message) };

        // A key that will not decode is a rejection of the same weight: the
        // table says whether the *signature is acceptable*, and an
        // unacceptable key makes it unacceptable.
        let accepted = match PublicKey::from_bytes(&hex(a)) {
            Err(_) => false,
            Ok(key) => verify(&key, &message, &hex(signature)).is_ok(),
        };
        assert_eq!(
            accepted,
            expected == "accept",
            "{name}: expected {expected}"
        );
        rows += 1;
    }
    // A table that failed to load would pass every assertion above.
    assert_eq!(rows, 8, "the fixture lost a row");
}
