package q2d

import (
	"os"
	"testing"
)

// profileEdges is testdata/profile-edges.json, built by hand because parsing is
// P-002 issue 4 and does not exist yet.
//
// canonical_query_test.go holds all three serializers to a real query, which is
// P-002 §7's first acceptance criterion. It is also entirely ASCII, has no
// escape in it, and no integer near a boundary — so three serializers could
// agree on it while disagreeing about most of §4.2. They did: the Rust side was
// emitting Unicode scalar key order where §4.2 asks for UTF-16 code-unit order,
// and the canonical query could not have caught it, because no field name in
// core-model.md §2 is outside ASCII.
//
// This is deliberately not a Q2D message. Every entry is a property of §4.2
// rather than a protocol field.
func profileEdges() Value {
	return Object{
		// Key ordering above the BMP: U+10000 encodes as D800 DC00 under UTF-16
		// and so sorts below U+FFFD, where scalar order puts it above. U+E000 is
		// the other side of the same boundary — the first code point after the
		// surrogate range, where the two orders agree again.
		"�":          String("bmp"),
		"\U00010000": String("supplementary"),
		"\U0001F680": String("rocket"),
		"":          String("private-use"),
		"a":          String("a"),
		"A":          String("A"),
		"":           String("the empty key is a key"),
		// Every escape RFC 8259 requires a two-character form for, then one
		// control character that has none and takes the six-character \u0001 form.
		"escapes": String("\"\\\b\f\n\r\t\u0001"),
		// Characters encoding/json escapes by default and this profile must
		// not — the reason writeString is hand-rolled.
		"unescaped":       String("<a>&b'c/d"),
		"non_ascii_value": String("é\U0001F600日本語"),
		"integers": Array{
			Int(0), Int(-1), Int(1), Int(1000000),
			Int(9223372036854775807), Int(-9223372036854775808),
		},
		"empty_object": Object{},
		"empty_array":  Array{},
		"null_present": Null{},
		"nested":       Object{"z": Object{"y": Object{"x": Array{Object{"w": Int(1)}}}}},
	}
}

func TestProfileEdgesSerializeToTheFixtureBytes(t *testing.T) {
	expected, err := os.ReadFile("testdata/profile-edges.serialized")
	if err != nil {
		t.Fatalf("cannot read the fixture: %v", err)
	}
	if got, want := string(Serialize(profileEdges())), string(expected); got != want {
		t.Errorf("serialized edges differ from the fixture\n got: %s\nwant: %s", got, want)
	}
}
