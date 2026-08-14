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
		// RFC 3339's grammar admits year zero and no calendar has one.
		"0000-01-01T00:00:00Z",
	} {
		if isQ2DTimestamp(impossible) {
			t.Errorf("%s: accepted an instant that never existed", impossible)
		}
	}
	// The first year that does exist, so the bound is a bound and not an
	// off-by-one.
	if !isQ2DTimestamp("0001-01-01T00:00:00Z") {
		t.Error("0001-01-01T00:00:00Z: refused the first year there is")
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
