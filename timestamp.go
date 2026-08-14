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
// meanings inside data §2.6 says may mean anything at all.
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

	// year >= 1 because RFC 3339's grammar admits 0000 and no calendar does.
	// Python's strptime refuses it (datetime.MINYEAR is 1), and a year the
	// authoring tool cannot express is a year no vector can assert — so
	// accepting it here would be an acceptance divergence with the tool that
	// produces the corpus's bytes, which is the one that matters most.
	return year >= 1 && month >= 1 && month <= 12 &&
		day >= 1 && day <= daysInMonth(year, month) &&
		hour <= 23 && minute <= 59 && second <= 59
}

// looksLikeRFC3339 reports whether a string has some RFC 3339 §5.6 spelling.
//
// Nothing in the serializer calls this. §2.2 binds the fields it names and
// isQ2DTimestamp is what enforces that; a string elsewhere is written as it is,
// whatever it looks like.
//
// It is kept because E-36 asks whether §2.2 should reach further, and this is
// the predicate that answer needs — under option A String.write refuses
// anything this accepts and isQ2DTimestamp does not. Exercised by the tests, so
// it is not untested code waiting for a decision.
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
