//! `core-model.md` §2.2's timestamp, and the RFC 3339 spellings it forbids.
//!
//! Written from the specification text rather than shared with
//! `tools/author_vectors.py`, which reads the same section. Three *separate*
//! readings — not independent ones; they share an author, and `CLAUDE.md`
//! reserves that word for a reason. What separateness buys is narrower and
//! still worth having: a disagreement between two readings of §2.2 is a
//! specification ambiguity surfaced, where shared code would have hidden it by
//! construction.
//!
//! No regex, and no date library: the grammar is fixed-width, and a dependency
//! that interprets a timestamp differently from the other two implementations
//! would be exactly the divergence this module exists to prevent.

/// The fields `core-model.md` gives a timestamp: §2.2's `issued_at` and
/// `expires_at`, §5.3's `expires_at`, §6's `decided_at`.
pub const TIMESTAMP_FIELDS: [&str; 3] = ["issued_at", "expires_at", "decided_at"];

/// The subobjects that re-enter protocol level, per §2.2's *"the core object,
/// `routing`, and a receipt"*.
///
/// Only from protocol level. A `public_context` carrying a field called
/// `receipt` is the predicate's own structure, and promoting it would enforce
/// §6's field meanings inside data §2.6 says may mean anything at all.
pub const PROTOCOL_SUBOBJECTS: [&str; 2] = ["receipt", "routing"];

/// §2.2's timestamp: the one spelling, and a real instant.
///
/// Shape *and* meaning. `2026-99-99T99:99:99Z` has §2.2's spelling exactly and
/// is no date, so a check on the spelling alone would sign it into a payload
/// that nothing downstream can read as text.
pub fn is_q2d_timestamp(value: &str) -> bool {
    // `YYYY-MM-DDTHH:MM:SSZ` — twenty ASCII characters, no alternatives.
    let b = value.as_bytes();
    if b.len() != 20 {
        return false;
    }
    let punctuation = [
        (4, b'-'),
        (7, b'-'),
        (10, b'T'),
        (13, b':'),
        (16, b':'),
        (19, b'Z'),
    ];
    for (at, expected) in punctuation {
        if b[at] != expected {
            return false;
        }
    }
    for at in [0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18] {
        if !b[at].is_ascii_digit() {
            return false;
        }
    }

    let number = |from: usize, to: usize| value[from..to].parse::<u32>().unwrap();
    let (year, month, day) = (number(0, 4), number(5, 7), number(8, 10));
    let (hour, minute, mut second) = (number(11, 13), number(14, 16), number(17, 19));

    if second == 60 {
        // RFC 3339 §5.7: 23:59 at a month end. Which leap seconds were
        // actually inserted is IERS data and not statically decidable — the
        // harness reaches the same conclusion from the same section.
        if (hour, minute) != (23, 59) || day != days_in_month(year, month) {
            return false;
        }
        second = 59;
    }

    // No year floor. RFC 3339's `date-fullyear` is four digits and admits
    // `0000`; §2.2 adds a spelling and says nothing about a range. This briefly
    // had one, because Python's `datetime` starts at year 1 and the authoring
    // tool refused what these accepted — but a library's range is not a
    // specification's, and the fix belonged in the tool. `year` is still read,
    // because February needs it.
    month >= 1
        && month <= 12
        && day >= 1
        && day <= days_in_month(year, month)
        && hour <= 23
        && minute <= 59
        && second <= 59
}

/// Whether a string has *some* RFC 3339 §5.6 spelling.
///
/// **Nothing in the serializer calls this.** §2.2 binds the fields it names, and
/// [`is_q2d_timestamp`] is what enforces that; a string elsewhere is written as
/// it is, whatever it looks like.
///
/// It is kept because [E-36] asks whether §2.2 should reach further, and this is
/// the predicate that answer needs — under option A the string arm of
/// [`crate::serialize`] refuses anything this accepts and `is_q2d_timestamp`
/// does not. Exercised by the tests below, so it is not untested code waiting
/// for a decision.
///
/// [E-36]: https://github.com/q2d-protocol/q2d/blob/main/docs/open-escalations.md
pub fn looks_like_rfc3339(value: &str) -> bool {
    let b = value.as_bytes();
    if b.len() < 20 {
        return false;
    }
    let punctuation = [(4, b'-'), (7, b'-'), (13, b':'), (16, b':')];
    for (at, expected) in punctuation {
        if b[at] != expected {
            return false;
        }
    }
    if b[10] != b'T' && b[10] != b't' {
        return false;
    }
    for at in [0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18] {
        if !b[at].is_ascii_digit() {
            return false;
        }
    }

    let mut at = 19;
    if b[at] == b'.' {
        at += 1;
        let start = at;
        while at < b.len() && b[at].is_ascii_digit() {
            at += 1;
        }
        if at == start {
            return false;
        }
    }
    match b.len() - at {
        // `Z` or `z`.
        1 => b[at] == b'Z' || b[at] == b'z',
        // `+HH:MM` or `-HH:MM`.
        6 => {
            (b[at] == b'+' || b[at] == b'-')
                && b[at + 1].is_ascii_digit()
                && b[at + 2].is_ascii_digit()
                && b[at + 3] == b':'
                && b[at + 4].is_ascii_digit()
                && b[at + 5].is_ascii_digit()
        }
        _ => false,
    }
}

fn days_in_month(year: u32, month: u32) -> u32 {
    match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if year % 4 == 0 && (year % 100 != 0 || year % 400 == 0) => 29,
        2 => 28,
        _ => 0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn the_one_spelling_is_accepted() {
        assert!(is_q2d_timestamp("2026-07-31T09:00:00Z"));
        assert!(
            is_q2d_timestamp("2024-02-29T00:00:00Z"),
            "2024 is a leap year"
        );
    }

    #[test]
    fn every_other_rfc3339_spelling_is_refused() {
        for spelling in [
            "2026-07-31t09:00:00Z", // lowercase T
            "2026-07-31T09:00:00z", // lowercase Z
            "2026-07-31T09:00:00.5Z",
            "2026-07-31T09:00:00+00:00",
            "2026-07-31T09:00:00-05:00",
        ] {
            assert!(!is_q2d_timestamp(spelling), "{spelling}");
            assert!(
                looks_like_rfc3339(spelling),
                "{spelling} is still a timestamp"
            );
        }
    }

    #[test]
    fn the_right_shape_is_not_enough() {
        // The case a spelling-only check passes, and the reason this function
        // parses rather than matches.
        for impossible in [
            "2026-99-99T99:99:99Z",
            "2026-02-30T00:00:00Z",
            "2025-02-29T00:00:00Z", // 2025 is not a leap year
            "2026-00-01T00:00:00Z",
            "2026-13-01T00:00:00Z",
            "2026-01-32T00:00:00Z",
            "2026-01-01T24:00:00Z",
        ] {
            assert!(!is_q2d_timestamp(impossible), "{impossible}");
        }
        // Year zero is *accepted*: RFC 3339's grammar admits it and §2.2 adds a
        // spelling, not a range. It is absurd and it is not this function's job
        // to say so — §4 step 6 compares `expires_at` against a clock, and no
        // year-zero query survives that. A floor here would be a rule the
        // specification does not have.
        assert!(is_q2d_timestamp("0000-01-01T00:00:00Z"));
        assert!(is_q2d_timestamp("0001-01-01T00:00:00Z"));
    }

    #[test]
    fn a_leap_second_is_the_last_second_of_a_month_or_nothing() {
        assert!(is_q2d_timestamp("2026-06-30T23:59:60Z"));
        assert!(is_q2d_timestamp("2026-12-31T23:59:60Z"));
        // Right second, wrong minute, wrong day: each is a real spelling of an
        // instant that never existed.
        assert!(!is_q2d_timestamp("2026-06-30T22:59:60Z"));
        assert!(!is_q2d_timestamp("2026-06-30T23:58:60Z"));
        assert!(!is_q2d_timestamp("2026-06-29T23:59:60Z"));
    }

    #[test]
    fn only_an_ascii_digit_is_a_digit() {
        // RFC 3339's grammar is `DIGIT`, which is ASCII. Python's `\d` matches
        // every Unicode decimal digit and `int()` accepts them all, so the
        // authoring tool accepted a timestamp in Arabic-Indic digits until
        // `[0-9]` replaced it. Asserted here because a property only one of
        // three implementations has is not one the corpus can rely on.
        //
        // Two guards, and the first is the one that fires: a non-ASCII digit is
        // at least two bytes in UTF-8, so no such string is twenty bytes long
        // and the length check refuses it before any digit is examined.
        let arabic_indic = "\u{662}\u{660}\u{662}\u{666}-\u{660}\u{667}-\u{663}\u{661}T\u{660}\u{669}:\u{660}\u{660}:\u{660}\u{660}Z";
        assert_eq!(arabic_indic.chars().count(), 20, "twenty characters");
        assert_eq!(arabic_indic.len(), 34, "and not twenty bytes, which is why");
        assert!(!is_q2d_timestamp(arabic_indic));
        assert!(!looks_like_rfc3339(arabic_indic));

        // So the digit check itself needs a case that reaches it: twenty bytes,
        // ASCII throughout, and not a digit where a digit belongs.
        assert!(!is_q2d_timestamp("2026-07-31T09:00:0xZ"));
        assert!(!is_q2d_timestamp("202x-07-31T09:00:00Z"));
        assert!(!looks_like_rfc3339("202x-07-31T09:00:00Z"));
    }

    #[test]
    fn a_string_that_is_not_a_timestamp_is_left_alone() {
        for ordinary in [
            "",
            "risotto",
            "2026-07-31",
            "sha256:bd08ff23",
            "urn:uuid:0e183389-0f37-4c5f-8c56-1ea7e5818e18",
        ] {
            assert!(!looks_like_rfc3339(ordinary), "{ordinary}");
        }
    }
}
