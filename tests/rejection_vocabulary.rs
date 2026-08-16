//! The internal reasons this implementation produces agree with the corpus.
//!
//! `testdata/rejection-vocabulary.txt` is the corpus's own mapping, extracted by
//! a Python test that fails if the file and the vectors drift apart. Every
//! rejection vector names an internal reason and the wire value a requester
//! receives, and **both implementations have to agree on that mapping** — or a
//! vector passes in one and fails in the other for a reason no runner reports
//! usefully.
//!
//! This test covers the reasons P-003's verify sequence produces. The corpus
//! carries more, from sections whose modules are not built yet; those are
//! checked when they are.

use q2d::Rejected;

#[test]
fn every_reason_this_module_produces_matches_the_corpus() {
    let path = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("testdata")
        .join("rejection-vocabulary.txt");
    let text = std::fs::read_to_string(&path).expect("testdata/rejection-vocabulary.txt");

    let corpus: std::collections::BTreeMap<&str, (&str, &str)> = text
        .lines()
        .map(|line| {
            let fields: Vec<&str> = line.split("  ").collect();
            assert_eq!(fields.len(), 3, "malformed row: {line}");
            (fields[0], (fields[1], fields[2]))
        })
        .collect();
    assert!(corpus.len() > 20, "the fixture failed to load");

    // The corpus's name for each variant this module can return. Written out
    // rather than derived from the variant name: the mapping is what the two
    // implementations must agree on, and deriving it here would make this test
    // agree with itself.
    let ours: &[(&str, Rejected)] = &[
        ("compact_segment_count", Rejected::CompactSegmentCount),
        ("header_segment_not_base64url", Rejected::HeaderSegmentNotBase64url),
        ("signature_segment_not_base64url", Rejected::SignatureSegmentNotBase64url),
        ("header_member_not_permitted", Rejected::HeaderMemberNotPermitted),
        ("suite_unregistered", Rejected::SuiteUnregistered),
        ("key_unresolvable", Rejected::KeyUnresolvable),
        ("signature_invalid", Rejected::SignatureInvalid),
        ("core_object_unsupported_version", Rejected::UnsupportedVersion),
        ("core_object_carries_signature_value", Rejected::CoreObjectCarriesSignatureValue),
        ("header_not_an_object", Rejected::HeaderNotAnObject),
        ("header_member_not_a_string", Rejected::HeaderMemberNotAString),
        ("payload_segment_not_base64url", Rejected::PayloadSegmentNotBase64url),
        ("header_payload_suite_mismatch", Rejected::HeaderPayloadSuiteMismatch),
        ("header_payload_key_mismatch", Rejected::HeaderPayloadKeyMismatch),
    ];

    let mut checked = 0;
    for (name, rejected) in ours {
        // **Not a skip.** Every name listed above is claimed to be the
        // corpus's, so one that is not found is a typo in this list — and a
        // typo here makes the test pass while checking nothing, which is how
        // `core_object_unsupported_version` went unchecked under the name
        // `unsupported_version` until review found it.
        let (external, step) = corpus
            .get(name)
            .unwrap_or_else(|| panic!("`{name}` is not an internal reason the corpus uses"));
        assert_eq!(
            rejected.external_reason(),
            *external,
            "{name}: the corpus and this implementation disagree about the wire value"
        );
        if *step != "-" {
            assert_eq!(
                rejected.step(),
                *step,
                "{name}: the corpus and this implementation disagree about the step"
            );
        }
        checked += 1;
    }
    // Without this the loop passes vacuously if every name is missing.
    assert!(checked >= 5, "only {checked} reasons were checked against the corpus");
}
