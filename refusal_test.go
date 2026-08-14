package q2d

import "testing"

// What the production profile refuses, and where it stops caring.
//
// These cases are the same in all three implementations — src/value.rs's
// `the_profile_refuses` tests and
// conformance/tests/test_serialization_fixtures.py's RefusalTest. They are not
// driven from a shared fixture because Rust and Go cannot yet parse one; that
// is P-002 issue 4, and this comment is the reason to revisit these three lists
// when it lands.

func refused(t *testing.T, v Value) string {
	t.Helper()
	if _, err := Serialize(v); err != nil {
		return err.Error()
	}
	t.Fatal("the profile produced bytes for a value it must refuse")
	return ""
}

func TestAMalformedTimestampFieldIsRefused(t *testing.T) {
	// By name: §2.2 gives issued_at a timestamp, so anything else in it is
	// wrong however wrong it is.
	refused(t, Object{"issued_at": String("2026-07-31t09:00:00Z")})
	refused(t, Object{"expires_at": String("2026-99-99T99:99:99Z")})
	refused(t, Object{"decided_at": String("not a date at all")})
	refused(t, Object{"issued_at": Int(42)})
	refused(t, Object{"issued_at": Null{}})
}

func TestAMalformedTimestampAnywhereIsRefused(t *testing.T) {
	// By shape: a string carrying some RFC 3339 spelling that is not §2.2's is
	// a malformed timestamp wherever it appears — including inside
	// public_context, which is exactly where an unexpected one arrives.
	refused(t, Object{"predicate": Object{"public_context": Object{
		"booked_for": String("2026-07-31T19:30:00+01:00"),
	}}})
	refused(t, Array{String("2026-07-31T09:00:00.000Z")})
}

func TestTheFieldNameRuleAppliesOnlyAtProtocolLevel(t *testing.T) {
	// §2.6: a predicate's public_context may mean anything at all, so a field
	// there called issued_at is the predicate's, not §2.2's. The shape rule
	// still reaches it — this asserts the *name* rule does not.
	value := Object{"predicate": Object{"public_context": Object{
		"issued_at": String("whenever the kitchen opens"),
	}}}
	if _, err := Serialize(value); err != nil {
		t.Errorf("public_context.issued_at was held to §2.2: %v", err)
	}
}

func TestRoutingAndReceiptReEnterProtocolLevel(t *testing.T) {
	// §2.2 covers "the core object, routing, and a receipt", so a timestamp
	// field in either is held to the same rule as one at the top.
	refused(t, Object{"routing": Object{"expires_at": String("2026-07-31T09:00:00z")}})
	refused(t, Object{"receipt": Object{"decided_at": String("2026-02-30T00:00:00Z")}})

	// And only from protocol level: a receipt nested inside public_context is
	// the predicate's own structure.
	value := Object{"predicate": Object{"public_context": Object{
		"receipt": Object{"decided_at": String("on the night")},
	}}}
	if _, err := Serialize(value); err != nil {
		t.Errorf("a receipt inside public_context was promoted to protocol level: %v", err)
	}
}

func TestARefusalNamesTheFieldAndNothingElse(t *testing.T) {
	// The message may carry the field name and the spelling the caller gave —
	// both are the caller's own — and must not carry anything the caller did
	// not already have.
	message := refused(t, Object{
		"issued_at": String("2026-07-31t09:00:00Z"),
		"nonce":     String("Ux7kFQ2mS0aVvJ1cPzN4bw"),
	})
	if !contains(message, "issued_at") {
		t.Errorf("the message does not say which field: %s", message)
	}
	if contains(message, "Ux7kFQ2mS0aVvJ1cPzN4bw") {
		t.Errorf("the message carries an unrelated field's value: %s", message)
	}
}

func TestInvalidUTF8IsRefusedRatherThanSubstituted(t *testing.T) {
	// A Go string is an arbitrary byte sequence and a Rust String is not, so
	// this value exists on one side of the pair and not the other. Ranging over
	// it substitutes U+FFFD, which would sign bytes the caller never supplied —
	// and Rust could not have produced them, so the divergence would show up as
	// a byte disagreement with no visible cause.
	//
	// 0x80 is a continuation byte with nothing to continue.
	bad := string([]byte{0x61, 0x80, 0x62})
	refused(t, Object{"a": String(bad)})
	refused(t, Object{bad: String("a")})

	// The substitution this prevents, stated as the thing that must not happen.
	if _, err := Serialize(Object{"a": String(bad)}); err == nil ||
		contains(err.Error(), "�") {
		t.Errorf("the refusal carries the substituted value: %v", err)
	}
}
