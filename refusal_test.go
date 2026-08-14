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

func TestATimestampOutsideATimestampFieldIsLeftAlone(t *testing.T) {
	// §2.2 states its spelling for the fields it names. A string somewhere else
	// is not a Q2D timestamp however much it looks like one, and §2.6 says a
	// predicate's public_context may mean anything at all — an offset carries
	// the local time the requester is thinking in, which Z would lose.
	//
	// Whether §2.2 should reach further is E-36, open. All three implementations
	// do what §2.2 states and no more until it is decided; the register has the
	// options. If E-36 closes as A, these two become refusals and nothing else
	// moves.
	for _, value := range []Value{
		Object{"predicate": Object{"public_context": Object{
			"booked_for": String("2026-07-31T19:30:00+01:00"),
		}}},
		Array{String("2026-07-31T09:00:00.000Z")},
	} {
		if _, err := Serialize(value); err != nil {
			t.Errorf("a string outside a timestamp field was held to §2.2: %v", err)
		}
	}
}

func TestTheFieldNameRuleAppliesOnlyAtProtocolLevel(t *testing.T) {
	// §2.6: a predicate's public_context may mean anything at all, so a field
	// there called issued_at is the predicate's, not §2.2's — so neither rule
	// reaches it, and this asserts the name rule in particular, since it is the
	// one §2.2 states and the one a reader would expect to apply everywhere.
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
	// And not the refused value either. Serialize runs over responses and
	// receipts, whose strings derive from data the requester never sees, so an
	// error message is a disclosure path — CLAUDE.md's rule is that no private
	// value reaches one.
	if contains(message, "2026-07-31t09:00:00Z") {
		t.Errorf("the message carries the refused value: %s", message)
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

func TestANilValueIsRefusedRatherThanPanicking(t *testing.T) {
	// The Value interface admits a nil, and none of the concrete types is one.
	// Calling write on it panics, and a panic is not a refusal — this
	// serializer runs over responses and receipts, where the caller is a
	// pipeline rather than a literal, so malformed internal state has to come
	// back as an error.
	//
	// Nothing to mirror in the other two: Rust's Value is an enum with no
	// null-pointer state, and Python's None is the Null case.
	refused(t, nil)
	refused(t, Array{nil})
	refused(t, Object{"a": nil})
	refused(t, Object{"issued_at": nil})

	// Null{} is the JSON null and is a value. The absence of one is not.
	if got := text(t, Object{"a": Null{}}); got != `{"a":null}` {
		t.Errorf("Null{} was caught by the nil check: %s", got)
	}
}

func TestOperationDataIsSerializableOnItsOwn(t *testing.T) {
	// P-002 §4.7 digests public_context as a sub-object, so it becomes the root
	// of a serialization. If protocol level were read off the nesting, the same
	// bytes would be held to §2.2 when digested and not when reached through a
	// query — one object, two rules, decided by the call site.
	context := Object{"issued_at": String("whenever the kitchen opens")}

	got, err := SerializeOperationData(context)
	if err != nil {
		t.Fatalf("§2.6 data was held to §2.2: %v", err)
	}
	if want := `{"issued_at":"whenever the kitchen opens"}`; string(got) != want {
		t.Errorf("got %s, want %s", got, want)
	}

	// And the protocol entry point still holds a real issued_at to §2.2 — the
	// two differ in what they refuse, not in what they emit.
	if _, err := Serialize(context); err == nil {
		t.Error("the protocol entry point accepted a malformed timestamp field")
	}
	real := Object{"issued_at": String("2026-07-31T09:00:00Z")}
	viaProtocol, _ := Serialize(real)
	viaData, _ := SerializeOperationData(real)
	if string(viaProtocol) != string(viaData) {
		t.Errorf("the two entry points emit different bytes: %s vs %s", viaProtocol, viaData)
	}
}

func TestATypedNilIsRefusedToo(t *testing.T) {
	// Every write method has a value receiver, so *String is in Value's method
	// set: a nil *String is an interface holding a type and no value, which is
	// not equal to nil and panics on dispatch. The plain nil check above misses
	// it entirely.
	var pointer *String
	refused(t, pointer)
	refused(t, Array{pointer})
	refused(t, Object{"a": pointer})

	// A nil Array or Object is not this: it is an empty one, which is a value.
	if got := text(t, Object{"a": Array(nil), "b": Object(nil)}); got != `{"a":[],"b":{}}` {
		t.Errorf("a nil slice or map was treated as an absent value: %s", got)
	}
}
