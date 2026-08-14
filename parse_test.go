package q2d

import (
	"strings"
	"testing"
)

// These mirror src/parse.rs's tests case for case. Both parsers were written
// from RFC 8259 and P-002 §4.1–§4.3 rather than shared, so a case one accepts
// and the other refuses is a disagreement worth seeing.

func parsed(t *testing.T, text string) Value {
	t.Helper()
	value, err := Parse([]byte(text))
	if err != nil {
		t.Fatalf("%s: %v", text, err)
	}
	return value
}

func rejected(t *testing.T, text string) string {
	t.Helper()
	if _, err := Parse([]byte(text)); err != nil {
		return err.Error()
	}
	t.Fatalf("%s: parsed, and must not", text)
	return ""
}

func TestAPayloadRoundTrips(t *testing.T) {
	// P-002 issue 4's acceptance: parse_core(serialize_core(x)) == x.
	value := Object{
		"q2d_version": String("0.1"),
		"n":           Int(-42),
		"empty":       Object{},
		"list":        Array{Null{}, Bool(true), String("é😀")},
	}
	bytes, err := Serialize(value)
	if err != nil {
		t.Fatalf("serializing a conforming value: %v", err)
	}
	// Compared by re-serializing, because Value has no equality of its own and
	// the bytes are what the protocol cares about.
	again, err := Serialize(parsed(t, string(bytes)))
	if err != nil {
		t.Fatalf("re-serializing: %v", err)
	}
	if string(again) != string(bytes) {
		t.Errorf("round trip changed the bytes:\n got: %s\nwant: %s", again, bytes)
	}
}

func TestANonConformantPayloadStillParses(t *testing.T) {
	// §4.1's whole point, and P-002 issue 11's vector in miniature: a verifier
	// must not require the production profile. Whitespace, key order, an
	// escaped character that need not be escaped, and an escaped '/'.
	value := parsed(t, "{ \"b\" : 2,\n  \"a\"\t: \"\\u00e9\\/\" }")
	got, err := Serialize(value)
	if err != nil {
		t.Fatalf("re-serializing: %v", err)
	}
	if want := `{"a":"é/","b":2}`; string(got) != want {
		t.Errorf("got %s, want %s", got, want)
	}
}

func TestADuplicateKeyIsRefused(t *testing.T) {
	message := rejected(t, `{"secret_contact":1,"secret_contact":2}`)
	if !strings.Contains(message, "duplicate key") {
		t.Errorf("message does not name the defect: %s", message)
	}
	// Neither the key nor the value. A key reads as the sender's own label, and
	// on a response it can be derived from private data — a map keyed by a
	// contact's name discloses the name.
	if strings.Contains(message, "secret_contact") {
		t.Errorf("message carries the key: %s", message)
	}
	if !strings.Contains(message, "byte") {
		t.Errorf("message names no position: %s", message)
	}
}

func TestAFloatIsRefusedHoweverItIsWritten(t *testing.T) {
	for _, text := range []string{"1.5", "[0.0]", "1e2", "1E2", "-2.0e-3", `{"a":1.0}`} {
		if message := rejected(t, text); !strings.Contains(message, "§4.3") {
			t.Errorf("%s: %s", text, message)
		}
	}
}

func TestAnIntegerOutsideTheRangeIsRefused(t *testing.T) {
	for _, text := range []string{"9223372036854775808", "-9223372036854775809"} {
		if message := rejected(t, text); !strings.Contains(message, "§4.1") {
			t.Errorf("%s: %s", text, message)
		}
	}
	// The boundaries themselves parse.
	for _, text := range []string{"9223372036854775807", "-9223372036854775808"} {
		if got := parsed(t, text); string(mustSerialize(t, got)) != text {
			t.Errorf("%s did not survive the round trip", text)
		}
	}
}

func TestJSONTheGrammarRefusesIsRefused(t *testing.T) {
	for _, text := range []string{
		"", "  ", "{", "[1", `{"a"}`, `{"a":}`, "[1,]", "{,}", "nul", "tru",
		// Numbers RFC 8259 §6 does not admit.
		"01", "+1", ".5", "1.", "-", "1e", "0x10",
		// Two values, one document.
		"1 2", "{} {}", `"a" "b"`,
		// Strings.
		`"unterminated`, `"\q"`, `"\u00"`, `"\uZZZZ"`,
	} {
		rejected(t, text)
	}
}

func TestARawControlCharacterInAStringIsRefused(t *testing.T) {
	for _, text := range []string{"\"a\x01b\"", "\"a\nb\""} {
		if message := rejected(t, text); !strings.Contains(message, "control character") {
			t.Errorf("%q: %s", text, message)
		}
	}
	// Escaped, the same character is fine and round-trips.
	// Backticks cannot carry an escape, so this one is an interpreted
	// literal: the input is the six characters \u0001, not the byte.
	escaped := "\"a\\u0001b\""
	if got := parsed(t, escaped); string(mustSerialize(t, got)) != escaped {
		t.Errorf("an escaped control character did not survive: %s", mustSerialize(t, got))
	}
}

func TestASurrogatePairIsOneCharacterAndALoneOneIsNone(t *testing.T) {
	if got := parsed(t, `"😀"`); string(mustSerialize(t, got)) != `"😀"` {
		t.Errorf("surrogate pair: %s", mustSerialize(t, got))
	}
	for _, lone := range []string{`"\ud800"`, `"\udc00"`, `"\ud800\ud800"`, `"\ud800x"`} {
		if message := rejected(t, lone); !strings.Contains(message, "surrogate") {
			t.Errorf("%s: %s", lone, message)
		}
	}
}

func TestInvalidUTF8IsRefusedBeforeAnythingElse(t *testing.T) {
	// encoding/json would substitute U+FFFD here, which is one of the three
	// reasons this parser is hand-written.
	if _, err := Parse([]byte{'"', 0x80, '"'}); err == nil {
		t.Fatal("parsed invalid UTF-8")
	} else if !strings.Contains(err.Error(), "UTF-8") {
		t.Errorf("message does not name the defect: %v", err)
	}
}

func TestNestingPastTheLimitIsRefusedRatherThanOverflowing(t *testing.T) {
	// Verified is not trusted: a signature says who sent the bytes, not that
	// they meant well. Recursive descent without a bound is a stack overflow,
	// which is a crash rather than a rejection.
	parsed(t, strings.Repeat("[", maxDepth)+strings.Repeat("]", maxDepth))

	deeper := strings.Repeat("[", maxDepth+1) + strings.Repeat("]", maxDepth+1)
	if message := rejected(t, deeper); !strings.Contains(message, "§4.8") {
		t.Errorf("one past the limit: %s", message)
	}
	// And the crash this prevents, at a depth no bound-free parser survives.
	if message := rejected(t, strings.Repeat("[", 100_000)); !strings.Contains(message, "§4.8") {
		t.Errorf("absurd depth: %s", message)
	}
}

func TestAnErrorNamesAPositionAndNeverAValue(t *testing.T) {
	message := rejected(t, `{"answer":"the value that must not leak",}`)
	if !strings.Contains(message, "byte") {
		t.Errorf("message names no position: %s", message)
	}
	if strings.Contains(message, "must not leak") {
		t.Errorf("message carries the value: %s", message)
	}
}

func mustSerialize(t *testing.T, v Value) []byte {
	t.Helper()
	bytes, err := Serialize(v)
	if err != nil {
		t.Fatalf("serializing: %v", err)
	}
	return bytes
}
