//! The Rust serializer agrees with the other two on §4.2's *edges*.
//!
//! [`tests/canonical_query.rs`] holds all three to a real query, which is the
//! acceptance criterion P-002 §7 opens with. It is also entirely ASCII, has no
//! escape in it, and no integer near a boundary — so three serializers could
//! agree on it while disagreeing about most of the profile.
//!
//! They did. Codex found the Rust side emitting `BTreeMap` order — Unicode
//! scalar order — where §4.2 asks for UTF-16 code-unit order, and the canonical
//! query could not have caught it, because no field name in `core-model.md` §2
//! is outside ASCII. This document exists to be the thing that would have.
//!
//! It is deliberately not a Q2D message. Nothing here should be read as a
//! protocol structure; every entry is a property of §4.2 rather than a field.
//!
//! [`tests/canonical_query.rs`]: ./canonical_query.rs

use q2d::Value as V;

fn s(text: &str) -> V {
    V::string(text)
}

/// `testdata/profile-edges.json`, built by hand because parsing is P-002 issue
/// 4 and does not exist yet. When it does, this becomes a round trip.
fn profile_edges() -> V {
    V::object([
        // Key ordering above the BMP: U+10000 encodes as D800 DC00 under
        // UTF-16 and so sorts *below* U+FFFD, where scalar order puts it above.
        // U+E000 is the other side of the same boundary — the first code point
        // after the surrogate range, so scalar and UTF-16 order agree on it.
        ("\u{FFFD}", s("bmp")),
        ("\u{10000}", s("supplementary")),
        ("\u{1F680}", s("rocket")),
        ("\u{E000}", s("private-use")),
        // Ordinary ASCII keys, so the common case is asserted by the same
        // document. `A` before `a`: both orders are by code unit, not by
        // anything locale-aware.
        ("a", s("a")),
        ("A", s("A")),
        ("", s("the empty key is a key")),
        // Every escape RFC 8259 requires a two-character form for, then one
        // control character that has none and takes the six-character `\u0001`.
        ("escapes", s("\"\\\u{8}\u{c}\n\r\t\u{1}")),
        // Characters `encoding/json` escapes by default and this profile must
        // not. The Go side's string writer is hand-rolled for this row.
        ("unescaped", s("<a>&b'c/d")),
        ("non_ascii_value", s("é\u{1F600}日本語")),
        (
            "integers",
            V::Array(vec![
                V::Integer(0),
                V::Integer(-1),
                V::Integer(1),
                V::Integer(1000000),
                V::Integer(i64::MAX),
                V::Integer(i64::MIN),
            ]),
        ),
        ("empty_object", V::object(Vec::<(&str, V)>::new())),
        ("empty_array", V::Array(vec![])),
        ("null_present", V::Null),
        (
            "nested",
            V::object([(
                "z",
                V::object([(
                    "y",
                    V::object([("x", V::Array(vec![V::object([("w", V::Integer(1))])]))]),
                )]),
            )]),
        ),
    ])
}

#[test]
fn the_profile_edges_serialize_to_the_fixture_bytes() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("testdata")
        .join("profile-edges.serialized");
    let expected = std::fs::read(&path).unwrap_or_else(|e| panic!("{}: {e}", path.display()));
    let produced = q2d::serialize(&profile_edges());
    assert_eq!(
        String::from_utf8_lossy(&produced),
        String::from_utf8_lossy(&expected)
    );
}
