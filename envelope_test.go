package q2d

import (
	"strings"
	"testing"
)

// These mirror src/envelope.rs's tests case for case.

func envelope(t *testing.T, text string) Envelope {
	t.Helper()
	value, err := ParseEnvelope([]byte(text))
	if err != nil {
		t.Fatalf("%s: %v", text, err)
	}
	return value
}

func refusedEnvelope(t *testing.T, text string) string {
	t.Helper()
	if _, err := ParseEnvelope([]byte(text)); err != nil {
		return err.Error()
	}
	t.Fatalf("parsed, and must not: %s", text)
	return ""
}

func TestAnEnvelopeIsBothOf21sParts(t *testing.T) {
	one := envelope(t, `{"signed":"aGVhZGVy.cGF5bG9hZA.c2ln","routing":{}}`)
	if one.Signed != "aGVhZGVy.cGF5bG9hZA.c2ln" {
		t.Errorf("signed: %s", one.Signed)
	}

	two := envelope(t, `{"signed":"a.b.c","routing":{"type":"query"}}`)
	got, err := Serialize(two.Routing)
	if err != nil {
		t.Fatalf("serializing routing: %v", err)
	}
	if want := `{"type":"query"}`; string(got) != want {
		t.Errorf("routing: got %s, want %s", got, want)
	}
}

func TestAMissingOrMistypedMemberIsRefused(t *testing.T) {
	for text, want := range map[string]string{
		`{"routing":{}}`:                  "no `signed`",
		`{"signed":42,"routing":{}}`:      "`signed`",
		`{"signed":"a.b.c","routing":[]}`: "`routing`",
		`[]`:                              "JSON object",
	} {
		if message := refusedEnvelope(t, text); !strings.Contains(message, want) {
			t.Errorf("%s: got %q, want it to mention %q", text, message, want)
		}
	}
}

func TestAnUnknownMemberDeniesRatherThanBeingIgnored(t *testing.T) {
	// Unknown, missing and indeterminate all deny. Ignoring it would let one
	// party read a field another does not.
	message := refusedEnvelope(t, `{"signed":"a.b.c","routing":{},"hint":"trust me"}`)
	if !strings.Contains(message, "unknown envelope member") {
		t.Errorf("message does not name the defect: %s", message)
	}
	if !strings.Contains(message, "hint") {
		t.Errorf("message does not name the member: %s", message)
	}
}

func TestAnOversizedEnvelopeIsRefusedOnItsLength(t *testing.T) {
	// The §4 step 1 check: on the slice, before a parser exists. The input is
	// deliberately not valid JSON, so a parser reaching it at all would report
	// something else.
	huge := make([]byte, MaxEnvelope+1)
	for i := range huge {
		huge[i] = 'x'
	}
	_, err := ParseEnvelope(huge)
	if err == nil {
		t.Fatal("parsed an oversized envelope")
	}
	if !strings.Contains(err.Error(), "§4.8") || !strings.Contains(err.Error(), "envelope of") {
		t.Errorf("message does not name the limit: %v", err)
	}
}

func TestSignedMayBeLargerThanAStringFieldAndRoutingMayNot(t *testing.T) {
	// The reading §4.8 leaves open, and the arithmetic that settles it: a JWS
	// compact of the canonical query is about 1.6 KiB before any public context,
	// so a 2 KiB cap on signed would make the protocol unable to carry its own
	// worked example.
	long := strings.Repeat("s", MaxString*4)
	envelope(t, `{"signed":"`+long+`","routing":{}}`)

	message := refusedEnvelope(t, `{"signed":"a.b.c","routing":{"custodian":"`+long+`"}}`)
	if !strings.Contains(message, "§4.8") || !strings.Contains(message, "routing") {
		t.Errorf("message does not name the limit: %s", message)
	}
}

func TestARoutingKeyCountsAsAStringToo(t *testing.T) {
	long := strings.Repeat("k", MaxString+1)
	message := refusedEnvelope(t, `{"signed":"a.b.c","routing":{"`+long+`":1}}`)
	if !strings.Contains(message, "§4.8") {
		t.Errorf("message does not name the limit: %s", message)
	}
}

func TestTheParsersOwnLimitsStillApply(t *testing.T) {
	// Depth and members are enforced during the parse, so an envelope gets them
	// without ParseEnvelope repeating the checks.
	deep := `{"signed":"a.b.c","routing":` + strings.Repeat("[", 20) + strings.Repeat("]", 20) + `}`
	if message := refusedEnvelope(t, deep); !strings.Contains(message, "§4.8") {
		t.Errorf("depth: %s", message)
	}

	members := make([]string, 0, 65)
	for i := 0; i < 65; i++ {
		members = append(members, `"k`+string(rune('a'+i%26))+string(rune('a'+i/26))+`":1`)
	}
	wide := `{"signed":"a.b.c","routing":{` + strings.Join(members, ",") + `}}`
	if message := refusedEnvelope(t, wide); !strings.Contains(message, "members") {
		t.Errorf("members: %s", message)
	}
}

func TestThePayloadIsNotInspected(t *testing.T) {
	// §4.4: signed is opaque here. This one is not valid base64url and not a
	// JWS, and the envelope layer has no opinion — P-003 does, at step 3, and
	// the ordering is the point.
	if got := envelope(t, `{"signed":"not a jws at all","routing":{}}`).Signed; got != "not a jws at all" {
		t.Errorf("signed: %s", got)
	}
}

func TestTwoDefectsGiveTheSameReasonEveryRun(t *testing.T) {
	// A Go map has no order, so ranging over one reported whichever defect the
	// runtime reached first — differing between runs and from Rust, whose
	// BTreeMap walks in order. A rejection reason two implementations disagree
	// about is a divergence even when both reject.
	//
	// Two unknown members, so which is named is decided by the walk order.
	const twoDefects = `{"signed":"a.b.c","aaa":1,"zzz":2}`
	first := refusedEnvelope(t, twoDefects)
	for i := 0; i < 200; i++ {
		if again := refusedEnvelope(t, twoDefects); again != first {
			t.Fatalf("run %d disagreed:\n first: %s\n then:  %s", i, first, again)
		}
	}
	// And it is the first by §4.2's key order, which is what Rust reports.
	if !strings.Contains(first, "aaa") {
		t.Errorf("reported a later member than the first: %s", first)
	}
}

func TestAnEnvelopeWithoutRoutingIsAccepted(t *testing.T) {
	// §2.1, as E-38 closed it: "routing may be absent, and a responder must
	// accept a message carrying only signed."
	//
	// Absent and empty are still different, and both are legal. An empty routing
	// is a projection of nothing, which §4.6 compares field by field and finds
	// no field to compare; an absent one is no projection.
	if got := envelope(t, `{"signed":"a.b.c"}`).Routing; got != nil {
		t.Errorf("routing should be absent: %v", got)
	}
	empty := envelope(t, `{"signed":"a.b.c","routing":{}}`).Routing
	if empty == nil {
		t.Error("an empty routing is present, not absent")
	}
}
