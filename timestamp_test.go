package q2d

import (
	"fmt"
	"testing"
)

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

func TestEpochKnownInstants(t *testing.T) {
	// Values anyone can check against a published table, rather than against
	// this function's own output.
	for _, c := range []struct {
		text    string
		seconds int64
	}{
		{"1970-01-01T00:00:00Z", 0},
		{"1970-01-02T00:00:00Z", 86400},
		{"2000-01-01T00:00:00Z", 946684800},
		{"2001-09-09T01:46:40Z", 1000000000},
		{"2026-07-31T09:00:00Z", 1785488400},
		{"1969-12-31T23:59:59Z", -1},
		{"1900-01-01T00:00:00Z", -2208988800},
	} {
		got, ok := TimestampToEpochSeconds(c.text)
		if !ok || got != c.seconds {
			t.Errorf("%s: %d %v, want %d true", c.text, got, ok, c.seconds)
		}
	}
}

func TestEpochLeapDayIsADay(t *testing.T) {
	at := func(s string) int64 {
		v, ok := TimestampToEpochSeconds(s)
		if !ok {
			t.Fatalf("%s did not parse", s)
		}
		return v
	}
	if at("2024-02-29T00:00:00Z")-at("2024-02-28T00:00:00Z") != 86400 {
		t.Error("2024-02-29 is not one day after 2024-02-28")
	}
	if at("2024-03-01T00:00:00Z")-at("2024-02-29T00:00:00Z") != 86400 {
		t.Error("2024-03-01 is not one day after 2024-02-29")
	}
	// And 2100 is not a leap year, which a rule of "divisible by four" gets
	// wrong and the 400-year cycle gets right.
	if at("2100-03-01T00:00:00Z")-at("2100-02-28T00:00:00Z") != 86400 {
		t.Error("2100 was treated as a leap year")
	}
}

func TestEpochLeapSecondCollapses(t *testing.T) {
	// Documented rather than incidental: 23:59:60 is a valid §2.2 timestamp and
	// this deliberately does not distinguish it from 23:59:59, because the
	// alternative is an IERS table two implementations would carry different
	// vintages of.
	leap, _ := TimestampToEpochSeconds("2026-06-30T23:59:60Z")
	before, _ := TimestampToEpochSeconds("2026-06-30T23:59:59Z")
	if leap != before {
		t.Errorf("leap second %d, second before it %d", leap, before)
	}
	// Still ordered against its neighbours, which is what a freshness
	// comparison actually needs.
	next, _ := TimestampToEpochSeconds("2026-07-01T00:00:00Z")
	if leap >= next {
		t.Errorf("leap second %d is not before the next day %d", leap, next)
	}
}

func TestEpochRefusesWhatTheFormatCheckRefuses(t *testing.T) {
	// One definition of a Q2D timestamp, not two. Every spelling here is a real
	// instant that §2.2 does not permit, so a second parser written here would
	// have accepted them.
	for _, text := range []string{
		"2026-07-31t09:00:00Z",
		"2026-07-31T09:00:00z",
		"2026-07-31T09:00:00+00:00",
		"2026-07-31T09:00:00.5Z",
		"2026-02-30T00:00:00Z",
		"2026-07-31T09:00:60Z",
		"",
	} {
		if _, ok := TimestampToEpochSeconds(text); ok {
			t.Errorf("%q was accepted", text)
		}
	}
}

func TestEpochEveryDayOfAFourHundredYearCycle(t *testing.T) {
	// The whole cycle, because the arithmetic's failure mode is an off-by-one at
	// a century boundary that a handful of spot checks miss.
	//
	// The Rust side runs the same loop over the same range, which is two
	// readings of the same algorithm rather than cross-implementation evidence:
	// a shared vector is what would demonstrate agreement, and there is none for
	// this yet because no operation in P-001 §4.5 converts a timestamp. Both
	// sides being wrong identically is the case this does not catch.
	previous, _ := TimestampToEpochSeconds("1600-01-01T00:00:00Z")
	checked := 0
	for year := 1600; year < 2000; year++ {
		for month := 1; month <= 12; month++ {
			for day := 1; day <= daysInMonth(year, month); day++ {
				text := fmt.Sprintf("%04d-%02d-%02dT00:00:00Z", year, month, day)
				seconds, ok := TimestampToEpochSeconds(text)
				if !ok {
					t.Fatalf("%s did not parse", text)
				}
				if checked > 0 && seconds-previous != 86400 {
					t.Fatalf("%s is %d seconds after the day before", text, seconds-previous)
				}
				previous = seconds
				checked++
			}
		}
	}
	if checked != 146097 {
		t.Errorf("a 400-year cycle is 146097 days, walked %d", checked)
	}
}
