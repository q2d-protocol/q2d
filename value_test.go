package q2d

import "testing"

func text(t *testing.T, v Value) string {
	t.Helper()
	b, err := Serialize(v)
	if err != nil {
		t.Fatalf("the profile refused a value it should not: %v", err)
	}
	return string(b)
}

func TestKeysAreAscendingWhateverOrderTheyWereGiven(t *testing.T) {
	// A Go map has no order at all, so this is not "sorted despite insertion
	// order" — it is the only way the output could be deterministic.
	got := text(t, Object{
		"type":        String("query"),
		"q2d_version": String("0.1"),
		"nonce":       String("x"),
	})
	want := `{"nonce":"x","q2d_version":"0.1","type":"query"}`
	if got != want {
		t.Errorf("got %s, want %s", got, want)
	}
}

func TestThereIsNoWhitespaceBetweenTokens(t *testing.T) {
	got := text(t, Object{
		"a": Array{Int(1), Int(2)},
		"b": Object{"c": Null{}},
	})
	if want := `{"a":[1,2],"b":{"c":null}}`; got != want {
		t.Errorf("got %s, want %s", got, want)
	}
}

func TestIntegersCarryNoExponentSignOrLeadingZero(t *testing.T) {
	for _, c := range []struct {
		n    Int
		want string
	}{{0, "0"}, {-1, "-1"}, {1000000, "1000000"}, {-9223372036854775808, "-9223372036854775808"}} {
		if got := text(t, c.n); got != c.want {
			t.Errorf("Int(%d): got %s, want %s", int64(c.n), got, c.want)
		}
	}
}

func TestStringsEscapeOnlyWhatMustBeEscaped(t *testing.T) {
	// serialization.md §1: no \uXXXX for characters representable directly.
	// encoding/json escapes <, > and & by default, which is why this does not use
	// it — those are representable directly and escaping them would emit
	// different bytes from the Rust side.
	for _, c := range []struct{ in, want string }{
		{"é😀", `"é😀"`},
		{"a\"b\\c", `"a\"b\\c"`},
		{"\n\t\r", `"\n\t\r"`},
		{"\x01", `"\u0001"`},
		{"<a>&b", `"<a>&b"`},
	} {
		if got := text(t, String(c.in)); got != c.want {
			t.Errorf("String(%q): got %s, want %s", c.in, got, c.want)
		}
	}
}

func TestAnAbsentOptionalIsAbsentRatherThanNull(t *testing.T) {
	// P-002 issue 1's acceptance is that the two are distinguishable. Here they
	// are different documents, which is stronger than distinguishable.
	absent := text(t, Object{"a": Int(1)})
	null := text(t, Object{"a": Int(1), "b": Null{}})
	if absent != `{"a":1}` || null != `{"a":1,"b":null}` {
		t.Fatalf("absent=%s null=%s", absent, null)
	}
	if absent == null {
		t.Error("an absent optional and a null one serialize the same")
	}
}

func TestKeysSortByUTF16CodeUnit(t *testing.T) {
	// The one case where serialization.md §1's ordering differs from Go's byte
	// order: UTF-16 encodes a supplementary character as a surrogate pair
	// beginning at 0xD800, which is below U+FFFD, so it sorts first — where
	// comparing UTF-8 bytes would put it last.
	//
	// Nothing in core-model.md §2 has a non-ASCII field name, so the protocol
	// does not reach this today. It is implemented so that the day something
	// does, the two implementations already agree.
	got := text(t, Object{"�": Int(1), "\U00010000": Int(2)})
	if want := "{\"\U00010000\":2,\"�\":1}"; got != want {
		t.Errorf("got %s, want %s", got, want)
	}
}

func TestAnEmptyObjectAndAnEmptyArrayHaveOneFormEach(t *testing.T) {
	if got := text(t, Object{}); got != "{}" {
		t.Errorf("empty object: %s", got)
	}
	if got := text(t, Array{}); got != "[]" {
		t.Errorf("empty array: %s", got)
	}
}
