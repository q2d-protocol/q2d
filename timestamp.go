package q2d

// core-model.md §2.2's timestamp, and the RFC 3339 spellings it forbids.
//
// Written from the specification text rather than shared with
// tools/author_vectors.py, which reads the same section. Three separate
// readings — not independent ones; they share an author, and CLAUDE.md reserves
// that word for a reason. What separateness buys is narrower and still worth
// having: a disagreement between two readings of §2.2 is a specification
// ambiguity surfaced, where shared code would have hidden it by construction.
//
// No regexp, and no time.Parse: the grammar is fixed-width, and a library that
// interprets a timestamp differently from the other two implementations would be
// exactly the divergence this file exists to prevent. time.Parse with RFC3339
// would in fact accept a lowercase t, which §2.2 does not.

// timestampFields are the fields core-model.md gives a timestamp: §2.2's
// issued_at and expires_at, §5.3's expires_at, §6's decided_at.
var timestampFields = map[string]bool{
	"issued_at": true, "expires_at": true, "decided_at": true,
}

// protocolSubobjects re-enter protocol level, per §2.2's "the core object,
// routing, and a receipt".
//
// Only from protocol level. A public_context carrying a field called receipt is
// the predicate's own structure, and promoting it would enforce §6's field
// meanings inside data §2.4 leaves to a predicate's entry.
var protocolSubobjects = map[string]bool{"receipt": true, "routing": true}

// isQ2DTimestamp reports whether a string is §2.2's timestamp: the one
// spelling, and a real instant.
//
// Shape and meaning. 2026-99-99T99:99:99Z has §2.2's spelling exactly and is no
// date, so a check on the spelling alone would sign it into a payload that
// nothing downstream can read as text.
func isQ2DTimestamp(value string) bool {
	// YYYY-MM-DDTHH:MM:SSZ — twenty ASCII characters, no alternatives.
	if len(value) != 20 {
		return false
	}
	for _, fixed := range []struct {
		at   int
		want byte
	}{{4, '-'}, {7, '-'}, {10, 'T'}, {13, ':'}, {16, ':'}, {19, 'Z'}} {
		if value[fixed.at] != fixed.want {
			return false
		}
	}
	if !digitsAt(value, 0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18) {
		return false
	}

	year, month, day := number(value, 0, 4), number(value, 5, 7), number(value, 8, 10)
	hour, minute, second := number(value, 11, 13), number(value, 14, 16), number(value, 17, 19)

	if second == 60 {
		// RFC 3339 §5.7: 23:59 at a month end. Which leap seconds were actually
		// inserted is IERS data and not statically decidable — the harness
		// reaches the same conclusion from the same section.
		if hour != 23 || minute != 59 || day != daysInMonth(year, month) {
			return false
		}
		second = 59
	}

	// No year floor. RFC 3339's date-fullyear is four digits and admits 0000;
	// §2.2 adds a spelling and says nothing about a range. This briefly had one,
	// because Python's datetime starts at year 1 and the authoring tool refused
	// what these accepted — but a library's range is not a specification's, and
	// the fix belonged in the tool. year is still read, because February needs
	// it.
	return month >= 1 && month <= 12 &&
		day >= 1 && day <= daysInMonth(year, month) &&
		hour <= 23 && minute <= 59 && second <= 59
}

// TimestampToEpochSeconds is §2.2's timestamp as a count of seconds, for the
// arithmetic P-004 §4.4 needs.
//
// The second return is false for anything isQ2DTimestamp refuses, so there is
// one definition of what a Q2D timestamp is and this is not a second one. A
// caller comparing two instants therefore cannot accidentally accept a spelling
// the serializer would not have written.
//
// # Why a count rather than a comparison
//
// Ordering alone would be enough for "is this expired", and §4.4 also needs "is
// expires_at - issued_at above five minutes" and "is now within sixty seconds of
// it". Those are subtraction, so the conversion has to exist; making it the only
// primitive means the ordering and the arithmetic cannot disagree.
//
// # Leap seconds
//
// 23:59:60 at a month end is a valid §2.2 timestamp — RFC 3339 §5.7, and
// isQ2DTimestamp accepts it — and this collapses it onto :59, which is the same
// thing that function already does before it range-checks. The alternative is a
// leap-second table: which seconds were actually inserted is IERS data, it is
// not statically decidable, and two implementations carrying different vintages
// of it would disagree about an instant. Collapsing costs the ability to
// distinguish a leap second from the second before it, at instants that have
// occurred twenty-seven times in fifty years, and buys an arithmetic both
// implementations can be held to.
//
// This follows a decision isQ2DTimestamp already made; it does not make one, and
// it is not in spec/. §2.2 fixes the spelling and says nothing about how an
// accepted :60 participates in arithmetic, and P-004 §4.4 specifies the
// subtraction without saying either. A third implementation could count it,
// collapse it, or refuse it, and disagree with both of these at a leap boundary.
// That is E-49 in docs/open-escalations.md, raised with the other freshness
// constants that have no normative home, and this paragraph is what stops the
// code being read as the answer.
//
// The epoch is 1970-01-01T00:00:00Z. Nothing in the protocol serializes this
// value — it exists inside a comparison and no further — so the choice of epoch
// is arbitrary and only has to be the same in both implementations.
//
// time.Parse is not used. It accepts spellings §2.2 refuses, so reaching for it
// would put a second definition of a Q2D timestamp in this file — and the Rust
// side has no equivalent to reach for, which is exactly when the two drift.
func TimestampToEpochSeconds(value string) (int64, bool) {
	if !isQ2DTimestamp(value) {
		return 0, false
	}
	year := int64(number(value, 0, 4))
	month := int64(number(value, 5, 7))
	day := int64(number(value, 8, 10))
	hour := int64(number(value, 11, 13))
	minute := int64(number(value, 14, 16))
	second := int64(number(value, 17, 19))
	// The same collapse isQ2DTimestamp applies, restated because this reads the
	// text again rather than receiving that function's parsed fields.
	if second == 60 {
		second = 59
	}
	return daysFromCivil(year, month, day)*86400 + hour*3600 + minute*60 + second, true
}

// daysFromCivil returns days from 1970-01-01 to year-month-day, proleptic
// Gregorian.
//
// Howard Hinnant's days_from_civil, which is exact integer arithmetic over the
// 400-year cycle rather than a loop over years — a loop would be correct too and
// would take a different amount of time for different inputs, which is a
// property this repository would then have to reason about.
//
// Integer throughout. No floating point anywhere near a protocol decision.
func daysFromCivil(year, month, day int64) int64 {
	// March-based years, so a leap day is the last day rather than one in the
	// middle, and February needs no special case below.
	if month <= 2 {
		year--
	}
	era := year
	if era < 0 {
		era -= 399
	}
	era /= 400
	yearOfEra := year - era*400
	shift := int64(9)
	if month > 2 {
		shift = -3
	}
	dayOfYear := (153*(month+shift)+2)/5 + day - 1
	dayOfEra := yearOfEra*365 + yearOfEra/4 - yearOfEra/100 + dayOfYear
	// 719468 is the number of days from 0000-03-01 to 1970-01-01.
	return era*146097 + dayOfEra - 719468
}

// looksLikeRFC3339 reports whether a string has some RFC 3339 §5.6 spelling.
//
// Nothing in the serializer calls this. §2.2 binds the fields it names and
// isQ2DTimestamp is what enforces that; a string elsewhere is written as it is,
// whatever it looks like.
//
// It is kept because isQ2DTimestamp's tests need it: they assert that every
// other RFC 3339 spelling is refused as §2.2's timestamp while still being
// recognisable as a timestamp at all, and that second half is this function.
// Without it those tests could not distinguish "refused because it is the wrong
// spelling" from "refused because it is not a date".
//
// E-36 closed as C: §2.2 binds the fields it names, and a predicate wanting one
// spelling for a field of its own declares format: date-time in its registry
// entry. So no serializer will grow a caller for this.
func looksLikeRFC3339(value string) bool {
	if len(value) < 20 {
		return false
	}
	for _, fixed := range []struct {
		at   int
		want byte
	}{{4, '-'}, {7, '-'}, {13, ':'}, {16, ':'}} {
		if value[fixed.at] != fixed.want {
			return false
		}
	}
	if value[10] != 'T' && value[10] != 't' {
		return false
	}
	if !digitsAt(value, 0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18) {
		return false
	}

	at := 19
	if value[at] == '.' {
		at++
		start := at
		for at < len(value) && isDigit(value[at]) {
			at++
		}
		if at == start {
			return false
		}
	}
	switch len(value) - at {
	case 1: // Z or z
		return value[at] == 'Z' || value[at] == 'z'
	case 6: // +HH:MM or -HH:MM
		return (value[at] == '+' || value[at] == '-') &&
			digitsAt(value, at+1, at+2, at+4, at+5) &&
			value[at+3] == ':'
	default:
		return false
	}
}

func isDigit(c byte) bool { return c >= '0' && c <= '9' }

func digitsAt(value string, positions ...int) bool {
	for _, at := range positions {
		if !isDigit(value[at]) {
			return false
		}
	}
	return true
}

// number reads value[from:to] as a decimal. Every caller has already checked
// that the range is digits, so there is nothing to fail on.
func number(value string, from, to int) int {
	n := 0
	for at := from; at < to; at++ {
		n = n*10 + int(value[at]-'0')
	}
	return n
}

func daysInMonth(year, month int) int {
	switch month {
	case 1, 3, 5, 7, 8, 10, 12:
		return 31
	case 4, 6, 9, 11:
		return 30
	case 2:
		if year%4 == 0 && (year%100 != 0 || year%400 == 0) {
			return 29
		}
		return 28
	default:
		return 0
	}
}
