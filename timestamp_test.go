package q2d

import "testing"

// These mirror src/timestamp.rs's tests case for case. Two readings of
// core-model.md §2.2 that disagree would be a specification ambiguity found, so
// the cases are deliberately the same and the code deliberately is not shared.

func TestTheOneSpellingIsAccepted(t *testing.T) {
	for _, spelling := range []string{
		"2026-07-31T09:00:00Z",
		"2024-02-29T00:00:00Z", // 2024 is a leap year
	} {
		if !isQ2DTimestamp(spelling) {
			t.Errorf("%s: refused §2.2's own spelling", spelling)
		}
	}
}

func TestEveryOtherRFC3339SpellingIsRefused(t *testing.T) {
	for _, spelling := range []string{
		"2026-07-31t09:00:00Z", // lowercase T — which time.Parse would accept
		"2026-07-31T09:00:00z", // lowercase Z
		"2026-07-31T09:00:00.5Z",
		"2026-07-31T09:00:00+00:00",
		"2026-07-31T09:00:00-05:00",
	} {
		if isQ2DTimestamp(spelling) {
			t.Errorf("%s: accepted a spelling §2.2 does not permit", spelling)
		}
		if !looksLikeRFC3339(spelling) {
			t.Errorf("%s: not recognised as a timestamp at all, so it would pass "+
				"through as an ordinary string", spelling)
		}
	}
}

func TestTheRightShapeIsNotEnough(t *testing.T) {
	// The cases a spelling-only check passes, and the reason isQ2DTimestamp
	// parses rather than matches.
	for _, impossible := range []string{
		"2026-99-99T99:99:99Z",
		"2026-02-30T00:00:00Z",
		"2025-02-29T00:00:00Z", // 2025 is not a leap year
		"2026-00-01T00:00:00Z",
		"2026-13-01T00:00:00Z",
		"2026-01-32T00:00:00Z",
		"2026-01-01T24:00:00Z",
	} {
		if isQ2DTimestamp(impossible) {
			t.Errorf("%s: accepted an instant that never existed", impossible)
		}
	}
	// Year zero is accepted: RFC 3339's grammar admits it and §2.2 adds a
	// spelling, not a range. It is absurd and it is not this function's job to
	// say so — §4 step 6 compares expires_at against a clock, and no year-zero
	// query survives that. A floor here would be a rule the specification does
	// not have.
	for _, low := range []string{"0000-01-01T00:00:00Z", "0001-01-01T00:00:00Z"} {
		if !isQ2DTimestamp(low) {
			t.Errorf("%s: refused a year RFC 3339 admits", low)
		}
	}
}

func TestALeapSecondIsTheLastSecondOfAMonthOrNothing(t *testing.T) {
	for _, ok := range []string{"2026-06-30T23:59:60Z", "2026-12-31T23:59:60Z"} {
		if !isQ2DTimestamp(ok) {
			t.Errorf("%s: refused RFC 3339 §5.7's leap second", ok)
		}
	}
	// Right second, wrong minute, wrong day: each is a real spelling of an
	// instant that never existed.
	for _, bad := range []string{
		"2026-06-30T22:59:60Z",
		"2026-06-30T23:58:60Z",
		"2026-06-29T23:59:60Z",
	} {
		if isQ2DTimestamp(bad) {
			t.Errorf("%s: accepted a leap second away from a month end", bad)
		}
	}
}

func TestAStringThatIsNotATimestampIsLeftAlone(t *testing.T) {
	for _, ordinary := range []string{
		"",
		"risotto",
		"2026-07-31",
		"sha256:bd08ff23",
		"urn:uuid:0e183389-0f37-4c5f-8c56-1ea7e5818e18",
	} {
		if looksLikeRFC3339(ordinary) {
			t.Errorf("%q: treated an ordinary string as a timestamp", ordinary)
		}
	}
}

func TestOnlyAnASCIIDigitIsADigit(t *testing.T) {
	// RFC 3339's grammar is DIGIT, which is ASCII. Python's \d matches every
	// Unicode decimal digit and int() accepts them all, so the authoring tool
	// accepted a timestamp in Arabic-Indic digits until [0-9] replaced it.
	// Asserted here because a property only one of three implementations has is
	// not one the corpus can rely on.
	//
	// Two guards, and the first is the one that fires: a non-ASCII digit is at
	// least two bytes in UTF-8, so no such string is twenty bytes long and the
	// length check refuses it before any digit is examined.
	arabicIndic := "٢٠٢٦-٠٧-٣١T٠٩:٠٠:٠٠Z"
	if len(arabicIndic) != 34 {
		t.Fatalf("expected 34 bytes for 20 characters, got %d", len(arabicIndic))
	}
	if isQ2DTimestamp(arabicIndic) || looksLikeRFC3339(arabicIndic) {
		t.Error("accepted a timestamp written in non-ASCII digits")
	}

	// So the digit check itself needs a case that reaches it: twenty bytes,
	// ASCII throughout, and not a digit where a digit belongs.
	for _, notADigit := range []string{"2026-07-31T09:00:0xZ", "202x-07-31T09:00:00Z"} {
		if isQ2DTimestamp(notADigit) {
			t.Errorf("%s: accepted a non-digit where a digit belongs", notADigit)
		}
	}
	if looksLikeRFC3339("202x-07-31T09:00:00Z") {
		t.Error("treated a non-digit year as an RFC 3339 spelling")
	}
}
