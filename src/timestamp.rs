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
/// §6's field meanings inside data §2.4 leaves to a predicate's entry.
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

/// §2.2's timestamp as a count of seconds, for the arithmetic
/// [P-004](../docs/prds/P-004-replay-idempotency.md) §4.4 needs.
///
/// `None` for anything [`is_q2d_timestamp`] refuses, so there is one definition
/// of what a Q2D timestamp is and this is not a second one. A caller comparing
/// two instants therefore cannot accidentally accept a spelling the serializer
/// would not have written.
///
/// ## Why a count rather than a comparison
///
/// Ordering alone would be enough for *is this expired*, and §4.4 also needs
/// *is `expires_at - issued_at` above five minutes* and *is `now` within sixty
/// seconds of it*. Those are subtraction, so the conversion has to exist; making
/// it the only primitive means the ordering and the arithmetic cannot disagree.
///
/// ## Leap seconds
///
/// `23:59:60` at a month end is a valid §2.2 timestamp — RFC 3339 §5.7, and
/// [`is_q2d_timestamp`] accepts it — and this **collapses it onto `:59`**,
/// which is the same thing that function already does before it range-checks.
/// The alternative is a leap-second table: which seconds were actually inserted
/// is IERS data, it is not statically decidable, and two implementations
/// carrying different vintages of it would disagree about an instant. Collapsing
/// costs the ability to distinguish a leap second from the second before it, at
/// instants that have occurred twenty-seven times in fifty years, and buys an
/// arithmetic both implementations can be held to.
///
/// The epoch is 1970-01-01T00:00:00Z. Nothing in the protocol serializes this
/// value — it exists inside a comparison and no further — so the choice of
/// epoch is arbitrary and only has to be the same in both implementations.
pub fn to_epoch_seconds(value: &str) -> Option<i64> {
    if !is_q2d_timestamp(value) {
        return None;
    }
    let number = |from: usize, to: usize| value[from..to].parse::<i64>().unwrap();
    let (year, month, day) = (number(0, 4), number(5, 7), number(8, 10));
    let (hour, minute, second) = (number(11, 13), number(14, 16), number(17, 19));
    // The same collapse `is_q2d_timestamp` applies, restated because this reads
    // the text again rather than receiving that function's parsed fields.
    let second = if second == 60 { 59 } else { second };
    Some(days_from_civil(year, month, day) * 86_400 + hour * 3_600 + minute * 60 + second)
}

/// Days from 1970-01-01 to `year-month-day`, proleptic Gregorian.
///
/// Howard Hinnant's `days_from_civil`, which is exact integer arithmetic over
/// the 400-year cycle rather than a loop over years — a loop would be correct
/// too and would take a different amount of time for different inputs, which is
/// a property this repository would then have to reason about.
///
/// Integer throughout. No floating point anywhere near a protocol decision.
fn days_from_civil(year: i64, month: i64, day: i64) -> i64 {
    // March-based years, so a leap day is the last day rather than one in the
    // middle, and February needs no special case below.
    let year = year - i64::from(month <= 2);
    let era = if year >= 0 { year } else { year - 399 } / 400;
    let year_of_era = year - era * 400;
    let day_of_year = (153 * (month + if month > 2 { -3 } else { 9 }) + 2) / 5 + day - 1;
    let day_of_era = year_of_era * 365 + year_of_era / 4 - year_of_era / 100 + day_of_year;
    // 719468 is the number of days from 0000-03-01 to 1970-01-01.
    era * 146_097 + day_of_era - 719_468
}

/// Whether a string has *some* RFC 3339 §5.6 spelling.
///
/// **Nothing in the serializer calls this.** §2.2 binds the fields it names, and
/// [`is_q2d_timestamp`] is what enforces that; a string elsewhere is written as
/// it is, whatever it looks like.
///
/// It is kept because [`is_q2d_timestamp`]'s tests need it: they assert that
/// every *other* RFC 3339 spelling is refused as §2.2's timestamp while still
/// being recognisable as a timestamp at all, and that second half is this
/// function. Without it those tests could not distinguish "refused because it
/// is the wrong spelling" from "refused because it is not a date".
///
/// E-36 closed as C: §2.2 binds the fields it names, and a predicate wanting
/// one spelling for a field of its own declares `format: date-time` in its
/// registry entry. So no serializer will grow a caller for this.
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

#[cfg(test)]
mod epoch_tests {
    use super::*;

    #[test]
    fn known_instants() {
        // Values anyone can check against a published table, rather than
        // against this function's own output.
        for (text, seconds) in [
            ("1970-01-01T00:00:00Z", 0),
            ("1970-01-02T00:00:00Z", 86_400),
            ("2000-01-01T00:00:00Z", 946_684_800),
            ("2001-09-09T01:46:40Z", 1_000_000_000),
            ("2026-07-31T09:00:00Z", 1_785_488_400),
            ("1969-12-31T23:59:59Z", -1),
            ("1900-01-01T00:00:00Z", -2_208_988_800),
        ] {
            assert_eq!(to_epoch_seconds(text), Some(seconds), "{text}");
        }
    }

    #[test]
    fn a_leap_day_is_a_day() {
        let before = to_epoch_seconds("2024-02-28T00:00:00Z").unwrap();
        let leap = to_epoch_seconds("2024-02-29T00:00:00Z").unwrap();
        let after = to_epoch_seconds("2024-03-01T00:00:00Z").unwrap();
        assert_eq!(leap - before, 86_400);
        assert_eq!(after - leap, 86_400);
        // And 2100 is not a leap year, which a rule of "divisible by four" gets
        // wrong and the 400-year cycle gets right.
        assert_eq!(
            to_epoch_seconds("2100-03-01T00:00:00Z").unwrap()
                - to_epoch_seconds("2100-02-28T00:00:00Z").unwrap(),
            86_400
        );
    }

    #[test]
    fn a_leap_second_collapses_onto_the_second_before_it() {
        // Documented rather than incidental: `23:59:60` is a valid §2.2
        // timestamp and this deliberately does not distinguish it from
        // `23:59:59`, because the alternative is an IERS table two
        // implementations would carry different vintages of.
        assert_eq!(
            to_epoch_seconds("2026-06-30T23:59:60Z"),
            to_epoch_seconds("2026-06-30T23:59:59Z")
        );
        // Still ordered against its neighbours, which is what a freshness
        // comparison actually needs.
        assert!(
            to_epoch_seconds("2026-06-30T23:59:60Z").unwrap()
                < to_epoch_seconds("2026-07-01T00:00:00Z").unwrap()
        );
    }

    #[test]
    fn it_refuses_everything_the_format_check_refuses() {
        // One definition of a Q2D timestamp, not two. Every spelling here is a
        // real instant that §2.2 does not permit, so a second parser written
        // here would have accepted them.
        for text in [
            "2026-07-31t09:00:00Z",
            "2026-07-31T09:00:00z",
            "2026-07-31T09:00:00+00:00",
            "2026-07-31T09:00:00.5Z",
            "2026-02-30T00:00:00Z",
            "2026-07-31T09:00:60Z",
            "",
        ] {
            assert_eq!(to_epoch_seconds(text), None, "{text}");
        }
    }

    #[test]
    fn every_day_of_a_four_hundred_year_cycle_is_one_day_after_the_last() {
        // The whole cycle, because the arithmetic's failure mode is an
        // off-by-one at a century boundary that a handful of spot checks miss.
        let mut previous = to_epoch_seconds("1600-01-01T00:00:00Z").unwrap();
        let mut checked = 0;
        for year in 1600..2000 {
            for month in 1..=12 {
                for day in 1..=days_in_month(year, month) {
                    let text = format!("{year:04}-{month:02}-{day:02}T00:00:00Z");
                    let seconds = to_epoch_seconds(&text).unwrap_or_else(|| panic!("{text}"));
                    if checked > 0 {
                        assert_eq!(seconds - previous, 86_400, "{text}");
                    }
                    previous = seconds;
                    checked += 1;
                }
            }
        }
        assert_eq!(checked, 146_097, "a 400-year cycle is 146097 days");
    }
}
